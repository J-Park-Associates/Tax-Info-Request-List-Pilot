# SPEC — Cleanup: dead code, folds, bloat and repository residue

Written 2026-10-08 from a read-only analysis of `main` at 213d876. Nothing in
this SPEC has been built. It is the handoff for the cleanup jobs in section 7;
each job is its own session that reads this file, not this session's
transcript. Appendices A–F hold every finding with `file:line` references.

## 1. The answer

The application is not slow, and its code is not bloated with copy-paste. The
Python side loads in about a seventh of a second, there is no load-time import
cycle, the linter is clean, and only 51 lines in the whole package are exact
duplicates of other lines. What makes the repository hard for a newcomer is
three other things, in this order:

1. **Session residue checked into `pilot/`.** 83 handoff notes, 56 review and
   ruling files (7.3 MB of which is screenshots of screens that were later
   replaced), 13 superseded working papers and 6 SPECs nothing cites. Every
   decision they record that was sampled is already a row in
   `pilot/DECISIONS.md` or `docs/repo-map.curated.json`. About 163 files and
   8.7 MB can go with no code change.
2. **Prose inside the code.** 43% of the `tracker/` package (23,100 of 53,500
   lines) is docstrings and comments. Most of it is the reasoning the project's
   conventions ask for and stays. About 400 lines of it is changelog and
   decision history pasted into function bodies and small helpers, describing
   behaviour that no longer exists.
3. **Near-duplicate functions.** About 700 lines of Python, 215 lines of
   JavaScript and 185 lines of CSS are functions or rules that do the same
   thing as a neighbour with one constant changed. They fold into one each.
   The single largest is a 135-line copy of the SQLite transaction helpers
   that `store.py` and `checkpoint.py` both carry.

Truly dead code (nothing references it, tests included) is about 130 lines.
With the seven decisions in section 5 taken, everything in this SPEC is
buildable; nothing waits on a further word.

Totals, all areas:

| What | Removable with no decision | Needed a decision (all seven taken, section 5) |
|---|---|---|
| Files in the repository | 163 files, 8.7 MB | +120 files, 2.8 MB (brand exports, `.claude/skills`) — decided, P231/P232 |
| Python lines (`tracker/`, `tools/`) | about 1,600 of 57,000 | +about 500 (unused CLIs, migration shims, one tidy-up that runs every pass) — decided, P233–P236 |
| JavaScript and CSS lines (`app/`) | about 420 of 12,750 | 0 |

## 2. Runtimes, measured

**The app.** `import tracker.api`, which is what the Electron shell launches,
takes 141 ms on this machine. The heaviest modules are `filer` (13 ms),
`content_check` (10 ms) and `records` (10 ms). Nothing to fix.

**The test suite**, run once, single process, on Linux with Python 3.13:

| | |
|---|---|
| Tests | 4,409 collected (3,137 functions, some parametrised) |
| Wall time | 18 min 15 s |
| Four slowest tests | 365 s, one third of the whole run |
| Everything else | 4,405 tests averaging 0.17 s |
| Failed | 14, every one a missing optional package on this box (`cv2`/RapidOCR, `olefile`, `tqdm`, HEIC support). None is a code defect. |

The four tests that cost a third of the suite each walk the whole blank-IRS
corpus or the learned-keyword lint over it:

| Seconds | Test |
|---|---|
| 134 | `test_content_check.py::test_on_every_corpus_form_the_scans_miss_verdict_equals_the_routers_kept_verdict` |
| 88 | `test_content_check.py::test_every_verdict_is_the_same_judged_in_the_child_as_in_the_pass` |
| 72 | `test_irs_forms.py::test_a_notice_files_z01_and_no_return_or_form_does` |
| 71 | `test_learned_keywords.py::test_lint_marks_a_keyword_that_would_misfile_a_corpus_form_and_leaves_the_rest_alone` |

The next eleven slowest are each a deliberate 5- or 10-second "a reader that
never finishes is stopped" timeout test. Those are testing real clocks and
should stay as they are.

The standing rule already says agents run only the affected test files, so
the 18 minutes is paid only by a person running the whole suite. Two things
would still help that person:

- Run the files in parallel. Measured: the same suite with `pytest-xdist` on
  the four cores of this box took 5 min 21 s, with the same 14 package-missing
  failures and no new one, so the tests are safe to run side by side.
  `pytest-xdist` is not in the lockfile; adding it needs decision 191's
  hash-checked lockfile updated through `tools/lockfiles.py`.
- Mark the four corpus walks with a `corpus` marker so a quick run can skip
  them (`-m "not corpus"`) and the gate before a merge still runs them.

## 3. Where the size is

| Area | Files | Lines | Of which prose |
|---|---|---|---|
| `tracker/` (the Python package) | 37 | 53,500 | 43% (15,200 docstring + 7,900 comment) |
| `tests/` | 60 test files + 106 IRS PDFs (40 MB) | 82,100 | 17% |
| `app/` (Electron, plain JavaScript) | 25 | 13,500 | – |
| `docs/` | 11 | 35,600 (3.3 MB) | the decision log is 580 KB; the generated map 1.7 MB |
| `pilot/` | 303 | 32,000 (14.8 MB) | SPECs, handoffs, reviews, brand art |
| `.claude/skills/` | 63 | 21,100 (2.2 MB) | vendored design skill packs |
| `tools/` | 6 | 3,600 | 26% |

The biggest modules by prose share: `ledger.py` 57%, `page.py` 54%,
`errors.py` 53%, `layout.py` 52%, `router.py` 51%. By prose volume:
`filer.py` 3,675 lines of prose over 3,496 of code; `api.py` 2,547 over
3,479.

## 4. Findings

### 4.1 Repository residue (Appendix A)

Delete now, git history keeps every byte:

- `pilot/handoffs/` (83 files), `pilot/reviews/` and `pilot/review/`
  (56 files, 7.6 MB).
- 13 top-level working papers in `pilot/`: `AUDIT-shell.md`,
  `BRIEF-shell.md`, `PLAN-ui.md`, `PROMPTS.md`, `RECOMMENDATIONS.md`,
  `mockup-shell.html`, `shell-test-pins.md`, `wording-inventory.tsv`, the
  four `handoff-*-lane-*.md` files, and the withdrawn `SPEC-glass.md`.
- 6 SPECs nothing cites, and 5 old Windows-check results under
  `pilot/wintest/` (named in Appendix A).
- Three comment lines in `tests/test_shell.py` that point at deleted files.

Keep, with the evidence in Appendix A: `pilot/README.md`, `RELEASE.md`,
`Tester Guide.md`, `wording-shell.tsv`, `DECISIONS.md` (code cites its
P-numbers about 907 times), the 17 SPECs that code cites by section, the
installer script and `setup.iss`, the check scripts, the harness, and the
brand sources the build consumes. `HANDOFF.md` is stale (it stops at P204,
the log runs to P230) and should be rewritten to point at this SPEC.

Also keep, because a test or the build needs them: both `docs/repo-map.md`
and `docs/repo-map.json` (the `check` command compares both), all 106 PDFs
under `tests/irs/` (each is opened by a test), all four requirements sets,
and `gate.yml` (the single copy of the CI steps that `ci.yml` calls twice).
`docs/runbook.md` and `README.md` share no sentences.

Needs Jason's word first:

- `.claude/skills/` (63 files, 2.2 MB of UI-design skill packs) and
  `.mcp.json`. Nothing in the repo uses them, but P56/P57 approved
  committing them; removing them is a new decision row.
- 57 brand exports nothing consumes (Windows tile PNGs, the rejected
  concept image). `pilot/brand/.../source/export.py` writes them, so it must
  stop first or the next export brings them back.

### 4.2 Dead code, verified (Appendices B–E)

Nothing references these, tests included. About 130 lines in all:

- `filer.missing_in_pbc`, the `_find_parked` alias, `filer.ROOM_SHORT` (the
  only test asserts its text is *absent*, so it passes regardless), and the
  `MULTI_FORM_FAMILIES` re-export in `router.py`.
- `ocr.current_session`.
- `ledger.FILES_KEY`.
- `names.NAME_OUTCOMES`, `review.IDENTITY_AGREES_WRONG_YEAR`,
  `rollover.RolledItem.prior_file_count`, `tools/repo_map.py:parse_python`.
- Parameters no caller passes: `registry.engagement_dirs(max_depth)` and
  `registry.MAX_DEPTH` (its only purpose), `layout._parts_below_of(inner_kind)`,
  `runner._why_no_draft(today)`, `filer._the_home(runs)`,
  `store.read_with_head(known)`, `store.unlearn_keyword(lock_held)`,
  `store.recover(now)`, `store._expect(held)`,
  `fsio.write_json_atomically(indent)`.
- Branches that cannot run: `filer.judgment_of` has one; `reminder.client_ask`
  has two (its docstring says they wait for a future action, so that one is
  Jason's call).

Test-only public names, about 150 lines: functions and re-exports that only a
test calls (`ledger.fold/statuses/rules/_write_line`, `store.sync`,
`content_check.extract_bounded` and `own_forms`, the decision-100 "kept for
one release" re-exports, `reminder.is_approved_this_week`,
`layout.names_one_folder`, `names.spelling_in`, `view.render_page`,
`settings.default_data_home`, `api.NO_OPEN_CODES`, `progress.line`). Each
can be deleted together with the test that uses it, or the test rewritten
against the production path. Appendix lists say which.

Every other vulture hit was a false positive; the appendices say where each
is used (several are read by Windows through `ctypes`, by the app through
`asdict`, or by `errors.error_class` through `getattr`).

### 4.3 Folds: functions that are one function with a constant changed

Only folds where the functions are intuitively linked in the code are listed.
Each appendix names the tests that pin the old names.

**Storage (Appendix C, about 195 lines)**

- `store.py` carries its own copy of `checkpoint.py`'s SQLite helpers:
  `_let_go_of`, `_Cursor`, `_Connection`, `_close_after_failure`,
  `_transaction`, `BUSY_TIMEOUT_MS`. They differ only in which error class
  they raise. One parameterised version lives in `checkpoint` (layer 0;
  `store` already imports it), and `store` keeps the names as aliases because
  tests monkeypatch them. About 105 lines net.
- `households._the_record` is `manifest._the_record` without its `follow`
  flag. Households imports manifest's at call time. About 18.
- `records.people_from_json` and `feeds_from_json` are the same 15 lines.
  About 12. The hash-pinning test re-pins under the current
  `ADMISSION_VERSION`.
- `api._info_payload` is `records.info_to_json` with blank dates mapped to
  `""`. One `blank_date` parameter. About 12.
- The engagement-row insert duplicated in `_catching_up` and
  `rebuild_engagement`, the learned-keywords query, the one-use wrappers
  `manifest._named`/`_asked`, and the hand-written transaction in
  `store.open()`. About 32.
- Rejected after reading: `_apply_release`/`_apply_intent_event` (different
  fold rules), and a generic `*_to_json` converter (cleverer, not clearer).

**App face (Appendix D, about 260 lines)**

- The four row-action handlers `_cmd_dismiss`, `_cmd_unfile`,
  `_cmd_mark_missing`, `_cmd_restore` are 82–92% identical. Two helpers,
  `_original_of(spec, refusal)` and `_row_reply(engagement, key, entry,
  **extra)`. About 25.
- `settings.set_firm`/`set_firm_phone` → one `_set_text(key, value)`.
- `scheduling.install_task`/`remove_task` share the "run schtasks, raise on
  non-zero" tail.
- `firm_cache.load`/`page_rows.load` share only the read, save and digest
  helpers (the file formats differ on purpose).
- About 15 more in `api.py`: one `_rescan` helper for its four copies,
  `handle_of` inlined into `ledger_key`, one shell for `_cmd_firm`/
  `_cmd_firm_last`, one failure helper for `main`/`_cmd_run_now`, and one
  helper each for the root-walk logging, the fact-to-`Engagement` rebuild,
  the return-row dicts, the reminder date dicts, the schedule replies and the
  `.label` constructions.
- The three duplicated link-tag sets in `firm_cache.py`, `after_install.py`
  and `fsio.py` fold into `fsio`.

**Sorting engine (Appendix B, about 170 lines)**

- `find_parked`, `find_filed`, `find_moved` are one loop differing by the
  decisions accepted and the refusal sentence. About 35.
- `_ocr_pdf`/`_ocr_image` share their exception handling; it moves to their
  only caller `extract_by_ocr`. About 16.
- `required_matched`/`any_keyword_matched`; `interrupted_at`/
  `interrupted_note` (the only caller always calls both); two copies of
  "record the intent, then do the steps, undoing on failure".
- Forward-only wrappers: `_across_households`, `clients_root_of`,
  `_through_the_door`, `_taken_names`. About 35.
- Of `filer.py`'s 126 private functions, 48 are called once; most are
  deliberate named steps and stay. Six read better inlined: `_fitted`,
  `_carry_out`, `_taken_names`, `_through_the_door`, `_judged`, `_is_named`.

**Runner, reminder and the rest (Appendix E, about 165 lines)**

- The "typed folder through the door" block is copied into about ten module
  CLIs. One helper in `door.py`, no new import. About 60 repo-wide.
- `runner._retire_unedited_drafts`/`_refresh_stale_draft` differ only in
  the action per file.
- `scaffold._readme_returns`/`readme_returns`: both callers discard the year.
- Small tidies: inline `skipped_because` and `_missing_detail`; have
  `records_needing_a_person` call `checkpoint_said`; spell the checkpoint
  file-name list once; stop `left_behind_warnings` walking the disk twice.
- Rejected: a shared CLI skeleton for the six tools (saves 25 lines, adds a
  module, a test, a map node and an import into `repo_map`, which imports
  nothing of the repo today).

**Electron (Appendix F, about 215 lines of JavaScript, 185 of CSS)**

- Ten `app.js` functions repeat "write one row, redraw, report"
  (`restoreMoved`, `fileRow`, `withdrawAnswer`, `unfileDocument`,
  `markShared` among them). Two helpers.
- `keepMoved` does exactly what `assignParked` does; delete it.
- Three editor lookups should call the existing `editorRowItem`; `pilot.js`
  and `tour.js` each define identical `fill` and `make`.
- The element builders `el` (app.js) and `h` (shell.js) are identical apart
  from their attribute lists; four copies of the same localStorage
  try/catch; `openAddReturn`/`openNewHousehold` are the same opener; the feed
  and related-household pickers share one shape. About 12 smaller folds.
- CSS: `pilot-ui.css` re-skins `style.css` by repeating 88 of its selectors;
  200 of `style.css`'s 570 declarations are overridden by an identical later
  selector and 24 rules overridden whole. Deleting the overridden lines
  changes nothing on screen (about 140). About 45 lines of rules nothing
  sets (`.card`, `.card-head`, `.chosen-badge`, `.tmpl-id`, `.wiz-sub`,
  `.form-blurb`, `.btn-danger`, `.icon-fill`, `.tabular`, two editor column
  rules, 10 custom properties).
- 22 `typeof fn === "function"` guards protect functions `index.html` always
  loads; the fallbacks behind them cannot run.
- Clean: no dead top-level function, IPC names match both ways, every
  element id exists, no `console.*` or commented-out code, both vendored
  Floating UI files are used. The pilot files (`pilot.js`, `tour.js`,
  `pilot-content.js`, `pilot-ui.css`) are live, not superseded.

### 4.4 Prose that describes behaviour that no longer exists (about 400 lines)

- `store.py:257-340`: an 80-line changelog of schema versions 2–16; the code
  treats every version below 16 the same way. Shrinks to a few lines.
- `filer.py`: a 20-line `CACHE_VERSION` changelog, a 47-line comment retelling
  decisions 150, 169 and 154, and decision history in the docstrings of 1-
  to 4-line helpers (`read_once` has 26 docstring lines over 1 line of code).
- `api.py`: the refrain "the page types none of them" appears 21 times and
  "the shell opens only the paths this map holds" 7 times, inside `_state`
  (110 comment lines over 85 of code) and `_vocab`; the decision-112 `seq`
  paragraph is copied into four handler docstrings.
- About 10 lines of "until decision 190…" history in `reasons.py` and 3 in
  `tracker/__init__.py`.
- `docs/storage.md`: about 10 KB of migration history that retells decisions
  101–104.
- Not bloat, checked: the 326 comment lines in `reasons.py` and 253 in
  `templates.py` are code-local reasoning (why each catalog keyword was
  chosen), not copies of ROADMAP rows.

### 4.5 Defects found on the way

These are not cleanup; they are small bugs the reviewers hit while reading,
and each gets its own fix with a test:

1. `api.py`: `REMINDER_LINE_UNREADABLE.format(label=..., kind=...)` has no
   placeholders, so the warning never names the return. The test at
   `tests/test_api.py:7215` makes the same no-op call and checks nothing.
2. `api.py`: `str(spec.get("original", "")).strip()` turns a JSON `null` into
   the text `"None"`, which gets past the "Pick the file" refusal.
3. `filer.py:2453-2468`: the comment above `MISSING_IN_PBC` is cut
   mid-sentence by the `RETIRED_CACHE_REMOVED` constant pasted into it.
4. `manifest.py:787` points to `router._required_matched`, which no longer
   exists; it should name `content_check.required_matched`.
5. The curated map still says the pass reads through
   `content_check.extract_bounded`; it does not.
6. Two `filer.py` docstrings promise aliases that do not exist.

### 4.6 Looks like bloat, is not

`docs/ROADMAP.md` (97.5% decision rows that code cites; moving its 14 KB of
architecture sections above the 560 KB log would help a newcomer),
`docs/runbook.md`, both repo-map files, `gate.yml`, the four requirements
sets, every PDF in `tests/irs/`, the module CLIs the conventions ask for, and
the reasoning prose the conventions ask for.

## 5. Decisions taken (Jason, 2026-10-08, rows P231–P237 in `pilot/DECISIONS.md`)

Each was put to Jason with its options in the session that wrote this SPEC;
he took the recommended option on all seven.

1. **P231.** Remove `.claude/skills/` and `.mcp.json` (reverses P56/P57).
   Keep `.claude/settings.json`. → job 1.
2. **P232.** Change `export.py` to stop writing the unused brand tiles and
   delete the 57 exported images. → job 1.
3. **P233.** Drop the `__main__` blocks nothing runs and narrow the
   CLAUDE.md convention to "a module keeps a command line when something
   runs it". → job 6, with the CLAUDE.md line. *Built as:* only `names`
   lost its block; a test runs `validators` and `containers` in a
   subprocess, which the analysis had missed, so under the rule they stay.
4. **P234.** Move the decision-107 cache tidy-up from the pass into
   `after_install.run()`. → job 5 (the pass side) and job 4 (the
   after-install job), landed together.
5. **P235.** Retire the three upgrade carry-overs (files beside the program,
   the old-name settings file, the n8n output), about 250 lines; one runbook
   line says older installs are set up fresh. → job 4.
6. **P236.** Delete the two unreachable `reminder.client_ask` branches. →
   job 6.
7. **P237.** Add `pytest-xdist` to the lockfile and a `corpus` marker on the
   four corpus walks. → job 7.

## 6. Rules for every job below

- Behaviour does not change. A fold is one function with the old names kept
  as one-line aliases wherever a test pins them; the appendices name those.
- The standing rules, the layering table in `tests/test_layers.py` and the
  single-source tests hold. No new load-time import crosses a layer.
- Every job edits `docs/repo-map.curated.json` where a module's purpose or a
  curated note changes, runs `python tools/repo_map.py update`, and commits
  the map in the same commit.
- Gate before push, per decision 207: dead code first, then the changed
  files' own tests, the own tests of their importers, and `test_layers`,
  `test_single_source`, `test_repo_map`; then `ruff`, `repo_map.py check`
  and, for jobs 3 or 5, `vocab_report.py check`. Never the whole suite.
- Build on Sonnet, review on Opus at high effort in a session that did not
  build. Numbered findings against this SPEC. Rebuild fixes findings and
  nothing more.
- Everything lands in one draft pull request, in the order below, each job
  its own commits (decision 211).

## 7. The jobs

Jobs 1, 2 and 3–6 are independent and can run as separate lanes at once;
each touches different files, except that P234 spans jobs 4 and 5 and they
land together. Job 7 runs last because it re-pins the map after the others.

| # | Job | Files | Tests to run | Appendix |
|---|---|---|---|---|
| 1 | Delete the repository residue (4.1, "delete now"), remove `.claude/skills/` and `.mcp.json` (P231), trim `export.py` and delete the 57 brand exports (P232), fix the three `test_shell.py` comments, rewrite `pilot/HANDOFF.md` to point here, update `.gitignore`'s skills lines | `pilot/`, `.claude/`, `.mcp.json`, `.gitignore`, `tests/test_shell.py` | `test_shell`, `test_pilot`, `test_pilot_installer`, `test_single_source`, `test_repo_map` | A |
| 2 | Electron folds, dead CSS, overridden CSS, unreachable guards | `app/renderer/*.js`, `app/renderer/*.css` | `test_shell`, `test_shell_menu`, `test_pilot_ui`, `test_tour`, `test_row_columns`, `test_single_source` | F |
| 3 | Storage: the SQLite-helper fold, `_the_record`, the `_from_json` pair, dead names, the schema changelog | `store`, `checkpoint`, `ledger`, `records`, `manifest`, `households`, `fsio` | their own tests, `test_api`, `test_runner`, `test_layers`, `test_single_source`, `test_repo_map` | C |
| 4 | App face: the row-action handlers, `_info_payload`, `settings`/`scheduling` pairs, the `api.py` refrains, defects 1 and 2; retire the three carry-overs (P235) with the runbook line; the after-install job for P234 | `api`, `settings`, `scheduling`, `firm_cache`, `page_rows`, `after_install`, `view` | their own tests, `test_single_source`, `test_layers`, `test_repo_map`, `test_errors` | D |
| 5 | Sorting engine: `find_*` fold, OCR exception tail, wrappers, dead names, the changelogs, defects 3, 5 and 6; take the decision-107 tidy-up out of the pass (P234) | `filer`, `scanner`, `router`, `content_check`, `ocr` | their own tests, `test_runner`, `test_catalog`, `test_irs_forms`, `test_single_source`, `test_layers`, `test_repo_map`, `vocab_report.py check` | B |
| 6 | Runner and the rest: the door helper, the two draft loops, unused parameters, `reasons`/`__init__` history, defect 4; drop the three unused CLIs and narrow the CLAUDE.md line (P233); delete the two `client_ask` branches (P236) | `runner`, `reminder`, `scaffold`, `registry`, `layout`, `review`, `names`, `rollover`, `door`, `reasons`, `tracker/__init__.py`, `tools/repo_map.py` | their own tests, `test_api`, `test_single_source`, `test_layers`, `test_repo_map` | E |
| 7 | Test runtime: `corpus` marker and `pytest-xdist` in the lockfile (P237), `docs/storage.md` trim | `pyproject.toml`, `requirements*.txt/.lock`, `tests/conftest.py`, `docs/storage.md` | `test_tripwire`, `test_single_source`, `test_repo_map`, `tools/lockfiles.py` check | – |

Each job ends with a handoff note in its pull request description, not a
file in `pilot/handoffs/` (that folder is gone after job 1).

---



# Appendix A — Non-code contents review: what a newcomer can do without


**Summary.** About **163 files and 8.7 MB** can be deleted outright, with no test, build or code change beyond three comment lines in `tests/test_shell.py`. Nearly all of it sits in `pilot/`: 83 session handoffs (0.64 MB), the 56 review and ruling files (7.6 MB, of which 7.3 MB is 26 before/after screenshots), 13 top-level working papers, 6 SPECs that nothing cites, and 5 old Windows-check results. Every decision these files record that I sampled is already a row in `pilot/DECISIONS.md`, and the newer ones are also in `docs/repo-map.curated.json`. Two more groups could go, but each needs something first. The first is 57 unused brand exports (0.55 MB), which needs `source/export.py` to stop producing them. The second is the 63-file `.claude/skills` design packs (2.2 MB), which needs Jason to reverse decisions P56/P57. With both, the total is about **283 files and 11.5 MB**. Everything else should stay:
- `docs/ROADMAP.md` is 97.5% decision rows, and code cites those rows.
- Both repo-map files are checked by a test.
- The runbook and README share no text.
- All four requirement sets are used.
- `gate.yml` exists to *avoid* duplication.
- All 106 PDFs in `tests/irs` (40 MB, not 14) are opened by a test.

Deleting files shrinks the checkout but not the clone. Git history keeps every byte unless the history is rewritten.

Method: `git ls-files` sizes, a grep of `tests/ tracker/ tools/ app/ *.bat .github/ pilot/wintest pilot/harness pilot/installer` for every name, and a check of which tests actually call `read_text`/`open` on a file (a mention in a comment does not count). `python tools/repo_map.py check` was current (445 nodes) at the time of review. Nothing was edited.

---

### 1. `pilot/` (303 files, 14.8 MB)

**Background.** `pilot/README.md` rule 2 says pilot decisions are logged as P-rows in `pilot/DECISIONS.md` and *never* in `docs/ROADMAP.md`. `ROADMAP.md` has 0 P-numbers, and the curated map mentions P-numbers on 38 lines. So the record that the session residue should be checked against is `pilot/DECISIONS.md` (P1-P230, 218 rows), not `ROADMAP.md`.

### 1.1 Still read by code or tests: KEEP

| File | Who reads it |
|---|---|
| `pilot/README.md`, `RELEASE.md`, `Tester Guide.md` | `tests/test_single_source.py:345, 4297` (person-facing wording checks), `tests/test_pilot_installer.py:209` |
| `pilot/wording-shell.tsv` | `tests/test_api.py:10161, 10419` |
| `pilot/Build Pilot Installer.bat`, `pilot/installer/setup.iss` | `tests/test_pilot_installer.py:19-20`; `setup.iss` is the installer |
| `pilot/wintest/run_checks.ps1`, `uninstall_checks.ps1` | `tests/test_pilot.py:285-434`, `tests/test_pilot_installer.py:160-163` |
| `pilot/wintest/PROMPT-shell.md` | `tests/test_shell.py:4290` |
| `pilot/wintest/make_samples.py` | `run_checks.ps1:330` |
| `pilot/harness/*` (9 files) | `tests/test_shell.py` reads `stub.js`, `app-stub.js` and runs `make_vocab.py` (lines 1358, 2545-2584, 2877); curated map node |
| `pilot/brand/.../app/icon.ico` | `tests/test_build.py:758-775` (must be byte-identical to `app/assets/icon.ico`) |
| `pilot/brand/.../installer/setup.ico` + 14 `wizard-*.bmp` | `pilot/installer/setup.iss:43-45` |
| `pilot/brand/.../source/*.py`, `README.md` | the generator; `export.py` and the README are curated map nodes |
| `pilot/DECISIONS.md` (137 KB) | Code and tests cite P-numbers about 907 times (110 distinct). This is the only place those numbers resolve. |

### 1.2 Live operator material: KEEP
- `pilot/wintest/PROMPT.md`, `PROMPT-0.3.md`, `PROMPT-shell-local.md`, `RESULTS-TEMPLATE.md`, `SAMPLE-DOCUMENTS.md`, `Pilot-Sample-Documents.zip` (81 KB): the Windows check kit (P28).
- **SPECs that code cites by name and section (17 files, 577 KB): KEEP where they are.** Examples: `SPEC-shell` 76 hits, `SPEC-lists` 57, `SPEC-rename` 28, `SPEC-firm-cache(-fill)` 23, `SPEC-scale-1000`, `SPEC-sort-speed`, `SPEC-speed-round` (22 times in the curated map). Comments such as `tests/test_shell.py:71` "SPEC-shell 10.1, word for word" point into them. No test *reads* a SPEC file, so moving them would only break about 30 path mentions in comments. That is churn, not clarity.
- Optional: add a one-line status per SPEC (built / withdrawn / which P-rows) to the "Where things are" list in `pilot/README.md`. It currently lists only SPEC.md and SPEC-glass.

### 1.3 Session residue: DELETE (git history keeps it)

| Group | Files | Size | Evidence |
|---|---|---|---|
| `pilot/handoffs/` | 83 | 0.64 MB | Builder and reviewer notes for jobs S1-S8b and the F6/F7/cache/lists builds. The only references from code are comments: `tests/test_shell.py:10` (`shell-S3.md`) and `:2130` (`shell-S5-rebuild-1.md`). `handoffs/shell-rulings.md` rulings 1-29 are rows P85-P114 (checked: P85 = ruling 1, P86 = ruling 2, word for word). |
| `pilot/reviews/` + `pilot/review/` | 56 | 7.62 MB | 26 PNG before/after screenshots (7.3 MB) of the 0.1/0.2 screens, which were later replaced by the shell. The rest is review and ruling rounds. Only reference from code: a comment at `tests/test_shell.py:3776` (`lists-rulings.md`). `review/wording-table.md` is a 0.2 snapshot of `wording-shell.tsv`. |
| Top-level working papers | 13 | 0.38 MB | `AUDIT-shell.md`, `BRIEF-shell.md`, `PLAN-ui.md` (says "Partly replaced (P62)"), `PROMPTS.md` (copy-paste prompts for 0.1), `RECOMMENDATIONS.md` (0.1 review synthesis), `mockup-shell.html` (80 KB), `shell-test-pins.md` (a survey that fed SPEC-shell §14, whose own header says "the SPEC wins"), `wording-inventory.tsv` (superseded by `wording-shell.tsv`), the four `handoff-*-lane-[PR].md` (speed rounds, landed as P216-P230 in PR #32), `SPEC-glass.md` (header: "WITHDRAWN (P50) ... Nothing in this file is built"). Nothing in code cites any of them (0 hits each). |
| SPECs nothing cites | 6 | 0.04 MB | `SPEC-F6-schedule-after-reinstall`, `SPEC-F7-redirected-data-folder`, `SPEC-check-scripts-0.3`, `SPEC-icon-ledger`, `SPEC-min-page-width`, `SPEC-stuck-tip`: 0 hits in code, tests or scripts. They are referenced only from other residue (`wintest/RESULTS-*.md`, `brand/README.md` links `SPEC-icon-ledger`; fix that link or keep that one file). They are built and logged as P193/P195-P203. |
| Old check results | 5 | 0.05 MB | `wintest/RESULTS-0.3.md`, `RESULTS-0.3-followup.md`, `RESULTS-shell.md`, `results/RESULT-2026-09-28.md`, `PROMPT-RERUN-3.md`. |
| **Total** | **163** | **8.74 MB** | |

**Are the decisions captured? Three samples, all yes:**
1. `reviews/lists-rulings.md` M1 ("re-saving either side must repair a one-sided link") is P170: "a save that stopped half way still shows the link and saving again completes it". It is also in the curated map (`P170` on 3 notes about `household_related`).
2. `reviews/firm-cache-rulings.md` SHOULD-2 (fingerprint records by content) is P120's review fold, and it was later reversed by P212, which names it ("Reverses P120's review fold (SHOULD-2...)").
3. `handoffs/F7-root-cause.md` is P193 (the `%LOCALAPPDATA%` redirect under the Claude package). The curated map carries the mechanism (`redirect_probe`, `redirected_copies`).

**Also residue, but rewrite rather than delete:** `pilot/HANDOFF.md` (50 KB, 812 lines). It was last touched 2026-10-01, and its newest decision is P204, while `DECISIONS.md` runs to P230. Most of its sections label themselves "history, superseded" or "answered since". Replace it with a short current-state note (what `main` is, open questions for Jason), or drop it and let `DECISIONS.md` plus the Drive CODE UPDATE serve. `tests/test_pilot_ui.py:11` mentions it only in a docstring.

### 1.4 Brand exports nothing consumes: DELETE, but only together with a generator change
- `pilot/brand/tax-document-console/windows/` (56 PNG, 257 KB): Square44/150 packaged-app tiles. There is no MSIX/appx packaging anywhere, and nothing outside `brand/` names them.
- `concept-approved.png` (290 KB): the brand README says it is the *rejected* earlier mark's concept, "kept for the record".
- These two groups come to 57 files and 0.55 MB. `source/export.py` writes `windows/`, so either remove that output from `export.py` or the next export brings them back.
- Lower value: `app/icon-*.png`, `app/*.svg` and `brand/lockup-*` (13 files, 0.21 MB) are also unused by the build, tests or app (`app/renderer/logo.svg` is not byte-equal to any of them). The README describes them as general brand assets ("for documents and email"), so keep them unless Jason says otherwise.

### 2. `docs/`

**2.1 `ROADMAP.md` (580 KB): KEEP, optionally reorder.** The 197 numbered decision rows are 565,931 bytes, which is **97.5%** of the file (all table lines together are 98.0%). The median row is 1.9 KB, but 32 rows exceed 5 KB and hold 271 KB between them. The largest are 190 (25 KB), 159 (19 KB) and 104 (16 KB). The non-log content (Hard Constraints, Architecture, Manifest Schema, Validation Tiers, Build Order, Edge Cases, Stack) is about 14 KB, and all of it except Hard Constraints sits *after* the 560 KB log (lines 259-442 of 442). A newcomer must scroll past the whole log to find the architecture. Better structure: move Architecture through Stack up beside Hard Constraints, or split the log into `docs/decisions.md`. But `tests/test_single_source.py` pins `docs/ROADMAP.md` by path in about 15 places, and `pilot/README.md` rule 2 treats it as the original's file. A split therefore means test edits and wider divergence from upstream. (Git log shows no upstream merge since the P17 copy, so that divergence cost is currently theoretical.) Do not trim rows: code cites "decision N" throughout.

**2.2 `repo-map.md` (598 KB) + `repo-map.json` (1.1 MB): KEEP both as long as `check` is the contract.** `tools/repo_map.py` writes both in `write_outputs`. The `.md` is `render_markdown(graph)` of the JSON. `check` (and `tests/test_repo_map.py::test_the_committed_map_is_current`) verifies hashes, then rebuilds the derived layer, then requires `markdown_is_current(graph, docs/repo-map.md)`. So the `.md` carries no information the JSON lacks. The JSON is itself rebuildable: `check` does a full rebuild in about 2.4 s here, so the committed JSON is a cache that `update` and `show` read. The tradeoff:
- Untracking `repo-map.md` (rendering it on demand) would cut 0.6 MB of generated churn from every commit.
- But CLAUDE.md, `ci.yml`'s header and the test name `repo-map.md` as the committed page agents read, so this is a policy change, not a cleanup.

Separately: deleting the §1.3 residue and the skills removes about 194 of the map's 445 nodes (pilot and `.claude` are 245 of 445 now). That makes `show` output and the node list much less noisy, but saves only about 40 KB of JSON, because those nodes carry no edges. None of the deleted files is a curated node: the only curated `pilot/` keys are `harness/make_vocab.py`, `brand/.../README.md` and `brand/.../source/export.py`, all kept. So `update` after the deletion will not refuse.

**2.3 `runbook.md` (194 KB) vs `README.md`: no duplication. KEEP.** The heading lists do not match. README has How it works / Chasing / Running unattended / Returning clients / How files get matched / Templates / Setup / Running the app. Runbook has What runs where / Every morning / Every Saturday / Reason column / Validation Notes / Machine dies / Season one / K-1s / Who to ask / Names. Sentences of 60 or more characters shared between the two files: **0 of 152**. Paragraphs of 200 or more characters with a ratio above 0.6: **0 of 46**. The two overlap in *topic* only (the Saturday draft, engagement details: "Share Link"/"Filing Deadline" appear 3 times in README and 4 times in the runbook), told for a setup reader and for an operator respectively, as CLAUDE.md intends.

**2.4 `storage.md` (43 KB) vs `store.py`/`ledger.py` docstrings: small overlap. KEEP, trim history.** Shared sentences: 0 with either docstring (`store.py`'s is 11.9 KB, `ledger.py`'s 8.7 KB). Two sections restate the *ideas* of `store.py`'s docstring in other words: "The words, used exactly" (0.9 KB) and "Why the journal syncs and the store does not" (4.9 KB). The rest (schema, intent, cache, keeping in step, the check gate) is cross-module design that no single docstring holds. Trim candidates: "History" (0.8 KB) and "What each stage did, and what is left" (9.3 KB), which retell ROADMAP rows 101-104 stage by stage. If trimmed, keep any file name quoted in backticks real, because `storage.md` is in `test_single_source.DOCUMENTS` (line 1394), which checks those names exist.

### 3. `.claude/skills` (63 files, 2.2 MB, 21,111 lines) and `.mcp.json`

**Recommendation: DELETE from the repo, but only on Jason's word.** Install them per user (`~/.claude/skills`) or as a plugin instead.
- **What references them:** nothing in tests, `.bat` files, workflows, `CLAUDE.md`, `tracker/`, `tools/` or `app/`. The only references are the `.gitignore` re-include (`!.claude/skills/`, comment "P56"), pilot history (`DECISIONS.md` P56/P57, `HANDOFF.md`, `SPEC-shell.md`, `SPEC-ui.md`, `BRIEF-shell.md`, `handoffs/shell-S3.md`), `PRODUCT.md` (Impeccable's context file, marked `<!-- impeccable:product-schema 1 -->`), and the generated map.
- **Why they are tracked:** they are not stray. P56 records "Jason: 'i approve installing both skills, commit them'", and P57 records the same for `winui-design`. Removing them reverses a recorded decision, so it needs a P-row.
- **What it holds:** the bulk is Impeccable's `scripts/data/font-index.json` (1.1 MB) and `scripts/live-browser.js` (547 KB).
- **`.mcp.json`:** registers the `fluent-ui` MCP server (`npx mcp-fluent-ui@1.0.2`, commit 18876ea "Add approved fluent-ui MCP server"). Nothing in code references it. Same recommendation, same ruling needed.
- **KEEP `.claude/settings.json`:** its `deny` list fences agents off client data, and `tests/test_single_source.py:425-596` pins it (decision 186).
- **KEEP `PRODUCT.md` (74 lines) even if Impeccable goes:** it shares no sentence with README, is a fair product statement, and is in `test_single_source._PERSON_FACING_DOCUMENTS` (line 4296).

### 4. `tests/irs/`: KEEP all

**Correction to the inventory:** this folder holds 106 PDFs and **40.1 MB**, more than all of `pilot/`. The 5 PDFs over 1 MB are `fw2.pdf` 2.15 MB, `fw2c.pdf` 1.50 MB, `fw2_2025.pdf` 1.34 MB, `fw2_2024.pdf` 1.34 MB and `ca568.pdf` 1.14 MB (7.5 MB together).
- **Unreferenced PDFs: none.** Every one of the 106 file names appears quoted in a test (mostly the `EXPECT` table in `tests/test_irs_forms.py`).
- Three consumers also glob the whole folder, so every PDF is opened regardless: `tests/test_irs_forms.py:291` (`IRS.glob("*.pdf")`), `tests/test_content_check.py:2621`, and `tools/vocab_report.py:144`. The last one hashes them into the committed vocabulary report, so removing a PDF also forces a vocab report rebuild and would drop catalog coverage.
- They are public-domain blank forms. Any shrink would be by re-fetching smaller revisions, not deletion.

### 5. Root

**5.1 Requirements: all four sets used. KEEP.** `requirements.lock` and `-nodeps.lock` are used by `Setup.bat`, `Build App.bat`, `gate.yml`, `build.yml` and `pilot/wintest/run_checks.ps1`. `-gpu.lock` is used by `Build GPU Pack.bat`. `-build.lock` is used by `Build App.bat`. All four `.txt` files are the inputs `tools/lockfiles.py` compiles into the locks, and `requirements-build.txt` is also named in `api_entry.spec`.

**5.2 README vs PRODUCT.md and CLAUDE.md: no real duplication. KEEP.**
- README and PRODUCT.md share 0 sentences.
- README and CLAUDE.md share 3 sentences: the standing rules, which are *required* to match word for word (`tests/test_single_source.py` keeps CLAUDE.md, README, roadmap and map quoting `STANDING_RULES` exactly).
- README's Setup block (`pip install ... requirements.lock`, `pytest`, lines 535-537) repeats 3 lines of CLAUDE.md's "Working on this repo". That is fine for two audiences.

### 6. `.github/workflows`

**6.1 `gate.yml` does not duplicate `ci.yml` or `build.yml`. KEEP.** `ci.yml` (112 lines) has no steps of its own. Its two jobs (`linux` matrix 3.11/3.14, label-gated `windows`) both `uses: ./.github/workflows/gate.yml`. `gate.yml`'s header explains why: a job-level `if:` cannot see `matrix`, so the steps are written once and called twice. `build.yml` shares only checkout, setup-python and the two-lock install. Its other steps (freeze, smoke-run the frozen API, scratch dry pass, package-content checks, zip and SHA-256) are not in the gate, and it runs no suite, lint or map check. `audit.yml` is a weekly OSV audit via `tools/lockfiles.py audit`.

**6.2 In this repository all four workflows are dormant.** `pilot/README.md` rule 4 says Actions is turned off for the pilot repository, and pilot releases are tagged `pilot-<version>`, while `build.yml` triggers only on `v*` tags. They are still worth keeping: `tests/test_build.py`, `tests/test_single_source.py` and `tests/test_repo_map.py` read them, and they are shared with the original repository. A newcomer should be told they do not run here. One line in `pilot/README.md` would do.


# Appendix B — Sorting engine cleanup findings (filer, scanner, router, content_check, ocr)


**Summary.** The five engine files total 13,939 lines. Their executable code is already fairly lean. Most of the size is reasoning prose, which is there by design, so the cleanup that is both safe and worth doing is modest: about **450-500 lines (~3.5%)**, plus about 50 more if Jason retires the decision-107 tidy-up (B2). By group:
- **Dead code: about 35 lines** that nothing references, tests included:
  - `filer.missing_in_pbc`
  - `ocr.current_session`
  - the `_find_parked` alias
  - router's `MULTI_FORM_FAMILIES` re-export
  - `filer.ROOM_SHORT` (only a test asserts that this text is *not* said)
- **Test-only code: about 60 lines.** These need small test rewiring:
  - `content_check.extract_bounded`
  - the public `own_forms` wrapper
  - the "kept for one release" re-exports pinned by `tests/test_records.py`
  - `ContentResult/Extraction.extractable`
  - `FileError.left_in_place`
- **Folds: about 170 lines.**
  - The best ones:
    - `find_parked`/`find_filed`/`find_moved` become one lookup (~35)
    - the twin OCR exception ladders (~16)
    - `required_matched`/`any_keyword_matched` (~15)
    - `interrupted_at`/`interrupted_note` (~10)
    - two copies of the "intend, then do all-or-take-back" loop (~18)
    - forwarding wrappers: `_across_households`, `clients_root_of`, `_through_the_door`, `_taken_names` (~35)
  - Do not fold the vulture-flagged structural duplicates (`moved_to`/`interrupted_at`, `take_notes`/`readers_that_could_not_start`) on their own: the shared part is docstring shape plus 3-4 lines of code. F4 is the useful fold there.
- **Prose bloat: about 220 lines** of history-style prose: the CACHE_VERSION changelog, a 47-line decision-150/169 narrative comment, and decision-log recaps in 1-4-line helpers.
- **Bugs and stale text:**
  - One unused parameter: `_the_home(runs)`.
  - One garbled comment: the `MISSING_IN_PBC` comment is split in half by `RETIRED_CACHE_REMOVED`.
  - Stale docstrings that promise aliases which no longer exist.

Of the 126 private functions in `filer.py`, 48 have exactly one call site. Thirty-six of those are longer than 5 lines, but most are deliberate named phases of 25-160 lines and should stay as functions. Only a handful read better inlined (see section 4).

Method: each vulture entry was grepped across `tracker/`, `tools/`, `tests/`, `app/`, `api_entry.py`, `pilot/` and `docs/`. Call counts come from a token scan of every production `.py` file, done separately for `tests/` (`scratchpad/calls.tsv`). Every function body named below was read.

---

### DEAD

Vulture entries are numbered 1-10. Entries 11-14 are dead code found beyond vulture.

1. **DEAD - `filer.missing_in_pbc`** (`tracker/filer.py:2518-2528`, 11 lines).
   - No caller in code, tests, tools or app. Only `docs/ROADMAP.md` (decision 72 history) and the generated `repo-map.json` mention it.
   - The pass uses `_missing_positions()` directly.
   - Delete it.
2. **DEAD - `ocr.current_session`** (`tracker/ocr.py:1192-1194`, 3 lines + blank lines).
   - Never called. Everything reads `_SESSION` directly (`run_in_child`).
   - Delete it.
3. **TEST-ONLY - `content_check.extract_bounded`** (`tracker/content_check.py:2124-2147`, 24 lines).
   - No production caller. Its own docstring says that since decision 189 the pass reads through `judge_bounded`.
   - Used by these tests:
     - `tests/test_ocr.py:438,453`
     - `tests/test_content_check.py:1511,1571,1594,1837,1852`
     - `tests/child_readers.py`
     - `tests/conftest.py:207` (docstring)
   - Delete it and point those tests at `judge_bounded(path, Questions()).extraction`.
   - Fix the stale curated-map sentence at the same time. `docs/repo-map.curated.json` still says "extract_bounded() is what the pass reads through (router.read_once ...)".
   - Also drop "and :func:`extract_bounded`" from the `READ_IN_A_CHILD` comment (`content_check.py:2095`).
4. **TEST-ONLY - `content_check.own_forms`** (`tracker/content_check.py:921-938`).
   - Production calls `_own_of(self_named_forms(...))` directly (`content_check.py:1576`).
   - `own_forms` is called only by tests (`tests/test_content_check.py:541-548, 2358, 2575-2603`).
   - Many docstrings cite `:func:own_forms` as *the* concept (`router.py:532,782`; `content_check.py:1344-1346,1494-1496,1519,1570,2359`).
   - See F13: merge the two into one function and keep the decision-107 rationale once.
5. **FALSE POSITIVE - `extractable`** (`content_check.py:293`, `content_check.py:321`).
   - These are dataclass fields, set in about 13 constructors (`content_check.py:1950,1976,1980,2009,2014,2021,2024,2044,2214,2268,2379`; `router.py:716`).
   - In practice they are **TEST-ONLY reads**: nothing in `tracker/` ever reads `.extractable`. Readers are `tests/test_content_check.py:132,145,1414,1447` and `tests/test_filer.py:678`.
   - Removing the field is safe for old cache rows, because `ContentCache.get_by_digest` (`content_check.py:2513`) keeps only the keys in `fields(ContentResult)`.
   - Optional: about 3 lines net, plus shorter constructor calls.
6. **FALSE POSITIVE - `left_in_place`** (`filer.py:500`).
   - This is a `FileError` field, set positionally at about 35 sites.
   - In practice it is **TEST-ONLY**: `runner.py:1532,1537` reads only `.name` and `.error`. About 12 asserts in `tests/test_filer.py` read it.
   - Low value to remove, because every constructor changes. Leave it, or drop it together with F14-style constructor cleanup.
7. **TEST-ONLY - `filer.ROOM_SHORT`** (`filer.py:711-718`, 8 lines with its comment).
   - The app now says `api.ROOM_SHORT_WORDS` ("Names Shortened to Fit"), and nothing in `tracker/` formats `filer.ROOM_SHORT`.
   - Its only users are `tests/test_runner.py:2034-2068`, which assert that this text is **not** among the run's warnings. That test passes vacuously.
   - Delete the constant and change the test to assert `run.warnings == []` (which it already does).
   - Note, outside this area: `api.ROOM_SHORT_WORDS.format(short=...)` at `api.py:3074,3175` formats a string that has no placeholder.
8. **FALSE POSITIVE - `ocr.LimitFlags`** (`ocr.py:917,919`).
   - This is a ctypes `Structure` field (`ocr.py:859`) that Win32 reads through `SetInformationJobObject`.
9. **DEAD - `router.MULTI_FORM_FAMILIES` re-export** (`router.py:171-176`, 5 lines).
   - Nothing imports it from `router`. The one test imports it from `content_check` (`tests/test_content_check.py:541`).
   - `tests/test_records.py` `RE_EXPORTED` does not pin it.
   - Delete the comment and the import line.
10. **DEAD - `filer._find_parked` alias** (`filer.py:6777-6779`, 3 lines).
    - Its comment says "kept for one release". No reference exists anywhere.
    - Delete it, and the "underscored name is kept for one release" sentences in the `find_parked` (`filer.py:6758-6759`) and `find_filed` (`filer.py:7210-7211`) docstrings.
    - There was never a `_find_filed` alias, so that sentence is simply false.
11. **TEST-ONLY - "kept for one release" re-exports from decision 100**:
    - `content_check.py:103-125`: `EVIDENCE_PLACES`, `EVIDENCE_RULES`, `RULE_FILENAME`, `RULE_REFUSED`, `format_evidence`, `parse_evidence`, all marked `noqa: F401`.
    - `filer.py:278-305` (`parse_evidence`).
    - `router.py:192-196` (`Routing`, `EVIDENCE_CONTENT`: these are used in `router` itself, so only the comment goes).
    - Production does not use them, with one exception: `api.py` calls `content_check.parse_evidence`. That one is a **FALSE POSITIVE** until api imports it from `records`.
    - `tests/test_records.py:172-189` (`RE_EXPORTED`) pins them, and `test_review.py`, `test_api.py`, `test_router.py` and `test_content_check.py` import them from the old modules.
    - About 20 lines (comments plus `noqa` lines, and the module-docstring sentences at `filer.py:175-177`, `content_check.py:82-85`, `router.py:149-151`).
    - This is Jason's call, since it retires a compatibility promise.
12. **Unused parameter - `_the_home(accepting, routed, runs)`** (`filer.py:5370`).
    - The body never reads `runs`.
    - Drop it here and at its one call site (`filer.py:5213`).
13. **Dead branch - `judgment_of`** (`content_check.py:1579-1582`).
    - `words = "" if reading.needs_ocr else (reading.text or "")` is followed by `if reading.text is None or reading.needs_ocr: return base`.
    - Past that return, `needs_ocr` is False and `text` is not None. Compute `words = reading.text` after the guard.
14. **Duplicate constant - `_MAX_OCR_PAGES = MAX_PAGES`** (`content_check.py:195`).
    - An alias used once (`content_check.py:1825`). Use `MAX_PAGES`.

### FOLD

Ordered by value. Line savings are net estimates.

1. **F1 - `find_parked` / `find_filed` / `find_moved` into one `_find_row(entries, original, decisions, refusal)`.**
   - Locations: `filer.py:6741` (34 lines), `filer.py:7197` (26 lines), `filer.py:7279` (18 lines).
   - The three bodies are the same loop: newest-first scan, `_names_row`, accept if `decision in wanted`, skip a same-name `DUPLICATE`, otherwise raise. They differ only in:
     - the accepted decision set (`_PARKED` or `FILED` or `FILE_MOVED`, plus `accepting`)
     - the refusal sentence
   - Keep the three public names as one-line wrappers, because `api.py:4714,4802` and the review commands call `find_parked`.
   - `_find_to_put_back` (`filer.py:7310`) repeats the same loop a fourth time, and can reuse the helper's iterator.
   - Saves about 35 lines.
2. **F2 - `_ocr_pdf` / `_ocr_image` exception ladders into `extract_by_ocr`.**
   - Locations: `content_check.py:1803`, `content_check.py:1852`, `content_check.py:1994`.
   - Both readers end in the same 13-line `except` chain: `ReaderUnavailable` (log, then None), `ReadingStopped` (re-raise), `MemoryError` (re-raise), `Exception` (log, `errors.keep`, raise `OcrError`).
   - `extract_by_ocr` is their only caller and already catches `ReadingStopped`/`TooLargeToRead`/`OcrError`.
   - Move the ladder there once. `_ocr_image` keeps its `DecompressionBombError` mapping.
   - Tests that monkeypatch the readers to return None or text still work. `tests/test_content_check.py:1081`, which expects `OcrError` from a direct `_ocr_pdf` call, would expect its own `Stop` instead.
   - Saves about 16 lines.
3. **F3 - `required_matched` / `any_keyword_matched` into one function.**
   - Locations: `content_check.py:1273`, `content_check.py:1257`.
   - Same shape: return False on an empty keyword tuple, default `dominant`, then `all`/`any` of `says(...)`.
   - Their only production caller is `judgment_of` (`content_check.py:1590-1591`), which always passes `dominant`.
   - Fold into `_keywords_said(text, keywords, combine, dominant)`, or keep the two names as one-liners for the tests (`any_keyword_matched` is used by 6 tests, `required_matched` by 2).
   - The 12-line and 9-line docstrings collapse to one.
   - Saves about 15 lines.
4. **F4 - `interrupted_at` + `interrupted_note` into one `interrupted(entry) -> tuple[str, str] | None`.**
   - Locations: `filer.py:3331`, `filer.py:3352`.
   - Both check `decision == NEEDS_REVIEW` and match `_INTERRUPTED_TAIL` on the same row. One returns group `to`, the other the sentence after `base`.
   - The only caller, `scanner._interrupted` (`scanner.py:285-293`), calls both on every row, which matches the regex twice.
   - This is also the right answer to vulture's "duplicate" pair `moved_to`/`interrupted_at`. Their shared code is 4 lines, so do not fold those two.
   - Saves about 10 lines.
5. **F5 - The all-or-nothing intent loop in `_make_again` and `_put_back_home` into one `_do_all_or_take_back(engagement_dir, key, ops, cache)`.**
   - Locations: `filer.py:3014-3022` and `filer.py:4521-4528`.
   - Both run the identical block: `done=[]`, `_do_op` and append, `except (OSError, FilingError)`, `_take_back`, `_abandon`.
   - Saves about 8 lines.
6. **F6 - `_carry_out` and the tail of `_file_into` into one `_intend_and_do(engagement_dir, entry, ops, *, by, then, cache, dry_run, also=())`.**
   - Locations: `filer.py:5502` and `filer.py:5564-5569`.
   - Both do: if dry run or no ops, return; then `_intend(..., row=entry_to_json(entry), then=...)`, then `_do_op` for each op.
   - `assign_review_file` (`filer.py:6328-6331`) repeats the intend-then-do pair as well.
   - `_carry_out` is called once.
   - Saves about 10 lines.
7. **F7 - Inline `_across_households(run)`** (`filer.py:5310`).
   - The body is `return not run.home`, under an 8-line docstring, with 5 call sites (`filer.py:5180,5187,5196,5329,5871`).
   - The `_ReturnRun.home` field already carries the explanation (`filer.py:3707-3711`).
   - Saves about 11 lines.
8. **F8 - Replace the forwarding wrapper `clients_root_of` with `store.root_for`** (`filer.py:1281`).
   - Three call sites, all in filer (`filer.py:1320,1771,3999`). No test or other module uses it.
   - Its docstring's claim that "commands that drive them call it" is stale.
   - Saves about 11 lines.
9. **F9 - Inline `_through_the_door`** (`filer.py:1951`).
   - One 1-line call to `_door_for` with a 5-line docstring. Its single caller is `_do_op` (`filer.py:2025`).
   - Saves about 7 lines.
10. **F10 - Inline `_taken_names`** (`filer.py:1232`).
    - A one-line dict merge with one caller, `_taken_in_the_year` (`filer.py:1246`).
    - Saves about 6 lines.
11. **F11 - `scanner._a_stranger_at` / `_the_rows_copy_is_here` into one `_rows_bytes_here(path, row, cache) -> bool | None`.**
    - Locations: `scanner.py:389`, `scanner.py:403`.
    - Same guard (`is_file`, not a placeholder) and the same `cache.digest_of(path)` compared with `row.digest`, one using `!=` and the other `==`.
    - The None case (not readable or not there) is what keeps them distinct. Callers are at `scanner.py:385,496,575`.
    - Saves about 6 lines.
12. **F12 - `_stem_of` / `_fitted`: one cut loop, not two nested.**
    - Locations: `filer.py:567`, `filer.py:588`.
    - `_fitted` cuts `document` from its end and calls `_stem_of` on each candidate, and `_stem_of` cuts `document` from its end again until it reaches `_MAX_STEM`. That is two identical loops, nested.
    - Fold into one `_fitted(..., room)` that cuts once against `min(room, cap)`.
    - `_fitted` is called once, from `prepared_name_for`.
    - `_unique_path` (`filer.py:1199-1201`) has a third copy of the same "cut stem from its end" generator, with different strip characters, so leave that one.
    - Saves about 6 lines.
13. **F13 - `own_forms` / `_own_of` into one function** (`content_check.py:921`, `content_check.py:941`).
    - Make `own_forms(named: tuple)` take the self-named forms, put the decision-107 rationale on it, and update the tests to pass `self_named_forms(text)`.
    - Related duplicates in the same file:
      - `_title_forms` re-implements `form_family` inline (`content_check.py:899`, `{_FAMILY.match(key).group(0) ...}`). Call `form_family`.
      - `form_key` calls `is_form_number` and then recomputes the same `bare` string (`content_check.py:533-561`). Make `is_form_number(k)` return `form_key(k) is not None`, or compute once.
      - `_one_says_where` calls `is_form_number(keyword)` and later `form_key(keyword)` (`content_check.py:1218,1232`). Compute `key = form_key(keyword)` once.
    - Saves about 12 lines.
14. **F14 - Failed-reading constructors into one helper.**
    - About 10 sites build `Extraction(None, reason=reasons.X.format(...), extractable=False, code=reasons.X.code, ...)` (`content_check.py:1950,1974-1981,2009,2013,2021,2024,2043,2214,2268`).
    - Use `_unread(reason: Reason, *, transient=False, error="", seconds=0.0, **fmt)` (Reason in the sense of `tracker.reasons`), which derives both the sentence and its code from one Reason, so the two cannot drift.
    - `abandoned`, `reading_failed` and `could_not_start` become one-liners.
    - Saves about 10 lines.
15. **F15 - The sort loop's own copy of `_keep`** (`filer.py:4428-4430`).
    - `run.entries.append(entry); if entry.decision != DUPLICATE and digest: run.known[digest] = entry` is `_keep(run, entry, digest)` (`filer.py:4603`). The `_keep` docstring even says "exactly what the sort's own loop does".
    - Saves 2 lines.
16. **F16 - `ocr._self_test_page` into `_self_test`** (`ocr.py:273`, `ocr.py:283`).
    - Each has one caller and no tests. The page is built only to be read once.
    - Saves about 4 lines.
17. **F17 - `ocr.Session.close` should call `_replace()`** (`ocr.py:1144`, `ocr.py:1126`).
    - The same `child, self.child = self.child, None; child.finish()` appears in both.
    - Saves about 3 lines.
    - Also: `_build_engine` wraps the same exception as `ReaderUnavailable(f"{error_class}: {exc}")` twice (`ocr.py:236`, `ocr.py:261`). One outer `try` saves about 3 lines.
18. **F18 - `router._explained_by` / `_sections` share the "keyword evidence that is a form number" filter** (`router.py:423`, `router.py:441`).
    - `_shows_its_form_number` (`router.py:312`) re-derives it as well.
    - One `_form_hits(evidence) -> [(term, key)]` makes each a one-liner.
    - Saves about 4 lines.
19. **Optional - one walk instead of four** (`filer.py:2306-2373`).
    - `unreachable_drops`, `unfinished_drops`, `ignored_in_inbox` and `unlistable_folders` each walk the inbox. The `ignored_in_inbox` walk calls `unfinished_drops`, so the pass at `filer.py:3863-3870` walks `unfinished_drops` twice.
    - One `inbox_census(inbox)` would do it, but `reminder.py:1432-1436` uses three of the four separately, so the saving is small (~8 lines). Low priority.
20. **Not worth folding:**
    - `ocr.take_notes` and `content_check.readers_that_could_not_start` (vulture's structural duplicate pair). Each is three lines of "copy a module list, clear it, return it", in different modules, with different meanings.
    - `holds_the_row` and `_the_bytes(path) == digest` (`filer.py:7374`, `filer.py:3379`). They differ on purpose: `holds_the_row` lets `OSError` escape and `_the_bytes` returns None. `store.verify` depends on the former.
    - Test seams such as `router.read_once` (a 1-line forward to `judge_bounded` under a 26-line docstring) and `content_check._read_in_a_child`. They look like pure forwards, but tests monkeypatch them (`tests/test_filer.py:5229-5235`; `tests/test_content_check.py:1417,1449,1531,1784,2010`), so a fold has to move those seams. Trim `read_once`'s docstring (B6) instead.

### BLOAT

1. **Garbled comment** (`filer.py:2453-2468`).
   - The `MISSING_IN_PBC` comment ("The sentence a recorded original that has left the year's folder gets ... while the row went on") is cut mid-sentence.
   - The `RETIRED_CACHE_REMOVED` comment and constant were pasted into the middle of it, and the sentence resumes after them ("naming a path that holds no file ...").
   - Move `RETIRED_CACHE_REMOVED` out, so each comment sits above its own constant.
2. **One-time migration that runs on every pass** (`filer.py:4183-4214` `_remove_the_retired_cache`, `filer.py:2457-2465` `RETIRED_CACHE_REMOVED`, `content_check.py:144-147` `RETIRED_CACHE_FILENAME`, call at `filer.py:3914-3916`).
   - This is the decision-107 cleanup of `_content_cache.json`.
   - Under decision 209 (CLAUDE.md "One-time steps run themselves"), it belongs in `tracker/after_install.py`, or it can be retired now that every install has passed decision 107.
   - About 50 lines. Needs Jason's ruling.
3. **CACHE_VERSION changelog** (`content_check.py:148-170`).
   - Twenty lines of per-version history (3 to 13), decision-log style.
   - Keep the first three lines (what the version is for) and point to ROADMAP for the history.
   - Saves about 17 lines.
4. **Decision-150/169/154 narrative comment** (`content_check.py:2047-2093`, 47 lines).
   - Restates the `ocr` module docstring and the `in_a_child`/`judge_bounded` docstrings: one child per pass, the stop, the open test, could-not-start, containers.
   - Cut to the 5-8 lines that are not said elsewhere.
   - Saves about 35 lines.
5. **Judgment banner comment** (`content_check.py:1397-1417`, 21 lines).
   - The second paragraph ("The rules did not change ... So CACHE_VERSION did not move") is change history, not reasoning a reader needs.
   - Saves about 10 lines.
6. **Decision-log recaps in docstrings of 1-4-line helpers.** Trimming these to the rule plus the decision number saves about 100 lines. The worst ratios (docstring lines / code lines):
   - `router.read_once` 26/1 (`router.py:591`)
   - `content_check.carries_a_1099b_section` 28/4 (`content_check.py:955`)
   - `content_check.contains_keyword` 22/3 (`content_check.py:484`)
   - `filer.refuse_a_path_past_the_limit` 27/6 (`filer.py:840`)
   - `filer.ensure` 26/5 (`filer.py:1743`)
   - `filer._move_whole` 20/3 (`filer.py:1100`)
   - `filer._record` 20/3 (`filer.py:1846`)
   - `content_check.extract_bounded` 19/4
   - `content_check.own_forms` 16/1
   - `filer._not_read` 14/1 (`filer.py:5292`)
   - `filer.interrupted_at` 14/4
   - `filer.holds_the_row` 13/1
   - `filer._the_home` 13/4
   - `filer.marked_missing` 12/1
   - `filer.moved_to` 12/4
   - `ocr.awake_clock` 13/1
   - `content_check.required_matched` 12/5 (it narrates "Moved here from the router with decision 189")

   Per CLAUDE.md, the *reasoning* stays. Only the provenance ("until decision N it was X; the review found Y") goes, since `docs/ROADMAP.md` already holds it.
7. **Router reason aliases** (`router.py:210-251`).
   - Thirteen module constants that only rename `reasons.X` (`UNMATCHED`, `AMBIGUOUS`, `OCR_ONLY`, `PENDING`, `UNREADABLE`, `NO_REQUEST_ACCEPTS`, `ISSUER_NOT_NAMED`, `SEVERAL_FORMS`, `SEVERAL_FORMS_UNSORTED`, `SHOWS_ITS_FORM_NUMBER`, `NAME_POINTS_AT`, `FILED_WHOLE`, `ALSO_ANSWERS`), plus `CONTESTED_PREFIX` (`router.py:397-399`).
   - Each has a comment saying "Worded once, in tracker.reasons", and most are used once in `router.py`.
   - Tests import some of them from `router` (`tests/test_filer.py:56`, `test_review.py:54`, `test_rollover.py:37`, `test_router.py:15`).
   - Using `reasons.X` directly saves about 35 lines, with test imports switched over.
8. **Stale docstring claims:**
   - `find_filed` (`filer.py:7210-7211`) promises an underscored alias that does not exist.
   - `clients_root_of` (`filer.py:1284-1289`) cites callers that no longer exist.
   - The `own_forms` references in `evaluate_rules`/`RowJudgment`/`Judgment` docstrings name a function production no longer calls (fixed by F13).
9. **Commented-out code:** none found in the five files. Every `#` line that looks like code is prose.

### 4. One-call private helpers in filer.py

- `filer.py` defines **126 private (`_`-prefixed) functions**. **48** have exactly one production call site; **36** of those are longer than 5 lines of code.
- **Keep as functions:** most of the 36 are deliberate named phases with their own contracts and lock or rollback boundaries:
  - `_sort_all` 163 lines, `_put_back_a_moved_copy` 153, `_prove_working_copies` 133, `_sort_one` 133
  - `_open_container` 85, `_finish_interrupted_moves` 82, `_prepare_return` 80
  - `_put_back_home` 47, `_finish_the_ops` 46, `_decide_attachment` 44, `_a_copy_to_act_on` 42
  - `_follow_and_say` 35, `_make_again_or_hold` 34, `_plan_working_copy` 33, `_unaccounted_in_opened` 31
  - `_named_by_another_records_intent` 30, `_follow_moved_originals` 29, `_make_a_gone_copy_again` 27, `_record_missing_digests` 25
  - `_issuer_to_add` 24, `_rows_changed` 22, `_prove` 26, `_the_trouble` 15, `_find_to_put_back` 15, `_remove_the_retired_cache` 15
  - `_prune_empty_dirs` 14, `_row_these_bytes_left` 13, `_take_out` 13, `_request_of_copy` 12 (9 test refs)
  - `_originals_away`, `_spend_a_stray`, `_refuse_unless_it_waits_for` 10 each
  - `_holds_the_firms_readme_text` 8
  - Inlining these would make the long functions longer and lose a name that matches a decision.
- **Read better inlined or folded:**
  - `_fitted` (via F12)
  - `_carry_out` (via F6)
  - `_with_the_name` (7 lines, one use inside `_by_the_name`'s loop; borderline)
- Among the 12 one-call helpers of 5 code lines or fewer, these are worth inlining, because each docstring is longer than its body:
  - `_taken_names` (F10)
  - `_through_the_door` (F9)
  - `_judged` (`filer.py:5008`, 3 lines)
  - `_is_named` (`filer.py:4935`, 2 lines)

  Keep `_inbox_order` (a sort key), `_subfolder_of`, `_opened_sentence`, `_renamed`, `_may_be_made_again` and `_day_of`, because they name a rule.


# Appendix C — Storage layer cleanup findings (store, ledger, locking, checkpoint, records, manifest, fsio)


**Summary.** About **340 lines can come out** of the storage layer's 12,236 lines without changing behaviour or the layering rules. Roughly 70 are dead or test-only code, about 195 come from folds and about 75 are an obsolete changelog comment. One change dominates. `store.py` carries its own copy of `checkpoint.py`'s SQLite error plumbing (`_let_go_of`, `_Cursor`, `_Connection`, `_close_after_failure`, `_transaction`, `BUSY_TIMEOUT_MS`). These are about 135 lines that differ only by the error class they raise. `store` already imports `checkpoint` at load time, so the shared version can live in `checkpoint` (layer 0) with no new edge, saving about 105 lines net. Of the vulture entries, only 4 are real: `ledger.FILES_KEY` is dead, and `ledger._write_line`, `ledger.fold` and `store.sync` are test-only. The other 6 are false positives. The listed duplicates are confirmed except `_apply_release`/`_apply_intent_event`, which share only a 3-line guard. A generic dataclass-driven `*_to_json/*_from_json` converter would be cleverer, not clearer, so I recommend against it. Nothing in `docs/ROADMAP.md` retires the in-place store upgrades (v16-19), the retired-event readers or the old-store-beside-the-program refusal, so none of those shims can be removed. Two test guards constrain any edit. First, `tests/test_store.py::test_admission_version_changes_with_the_admission` pins source digests of everything the store's admission reaches, including `records.people_from_json`, `feeds_from_json`, `person_from_json`, `feed_from_json`, `ledger.op_ends` and `store._refuse_a_malformed_line`. A pure refactor of those means re-pinning under the current `ADMISSION_VERSION`, not raising it. Second, tests monkeypatch `store._transaction`, `store.BUSY_TIMEOUT_MS`, `store._Connection.execute` and `store._Cursor.execute`, so those names must survive as aliases or subclasses.

### DEAD

Status of each vulture entry, after grepping tracker/, tools/, tests/, pilot/ and app/ (app/ holds no Python):

1. **tracker/ledger.py:192 `FILES_KEY` - DEAD.** It has no reader or writer anywhere. It names the payload of `MIGRATED`, which nothing has written since decision 104 (ledger.py:474-479 says so); `MIGRATED` stays readable, but no code reads its `files` key. Delete lines 189-192 and drop ":data:`FILES_KEY`" from the `MIGRATED` comment at 475. Saves about 4 lines.
2. **tracker/ledger.py:721 `_write_line` - TEST-ONLY.** Its only caller is `tests/conftest.py:691` (`written_elsewhere`). `append` uses `_write_raw` directly. Move the one line into conftest as `ledger._write_raw(path, json.dumps(event, ensure_ascii=False, sort_keys=True).encode("utf-8"))`. Saves about 5 lines.
3. **tracker/ledger.py:1053 `fold` - TEST-ONLY**, and so are its siblings **`statuses` (1078) and `rules` (1087)**, which vulture missed because the names are common. Each is `return replay(events).<field>`. No production module calls any of them: the store calls `ledger.replay`/`apply`. Callers are 10 in test_ledger, 1 in test_filer, 1 in test_store and 1 in test_row_columns. Delete all three (about 44 lines) and have the tests use `ledger.replay(events).rows/.statuses/.rules`. Move `fold`'s "in the index's order" paragraph onto `Folded.rows` (+about 8). Fix the references in `apply`'s docstring (ledger.py:1147), `replay`'s docstring (1319) and `tracker/filer.py:1299`. Net about -35.
4. **tracker/store.py:2512 `sync` - TEST-ONLY** (27 calls, all in tests/test_store.py). It is `_look_then_catch_up(..., build=False)`. Production uses `catch_up` (build=True) and `follow_the_journal`. Every test call is on an engagement the store already holds, where the two behave the same. The parametrize at test_store.py:1385 already treats them as interchangeable. Delete `sync` (22 lines), point the tests at `catch_up`, move the "by count, not by head" paragraph into `catch_up`, and reword the refusal at store.py:2447 ("sync() it before recording to it"). Net about -20.
5. **`says_its_code` at checkpoint.py:206, ledger.py:568 and store.py:501 - FALSE POSITIVE.** `tracker/errors.py:128` reads it reflectively, as `getattr(type(exc), SAYS_ITS_CODE, False)` with `SAYS_ITS_CODE = "says_its_code"` (errors.py:111).
6. **`row_factory` at checkpoint.py:305, store.py:903 and store.py:945 - FALSE POSITIVE.** It is a `sqlite3.Connection` attribute that the driver consumes. Every `row["col"]` access depends on it.

Dead parameters: no caller passes them, in production or in tests (AST scan of every call site).

7. **tracker/ledger.py:981 `read_with_head(..., known=)`** is never passed. Its only production caller is `tracker/view.py:563`, without `known`. Delete the parameter, the 2-line branch and the docstring paragraph. Saves about 8 lines. `read_with_chain`'s `known` is used, so it stays.
8. **tracker/manifest.py:1652 `unlearn_keyword(..., lock_held=)`** is never passed. Delete it, the call-time `from contextlib import nullcontext` (1704) and the conditional at 1710. Saves about 3 lines.
9. **tracker/store.py:3927 `recover(..., now=)`** is never passed, not even by tests. Use `dt.datetime.now()` at 3958. Saves 1 line.
10. **tracker/store.py:3051 `_expect(..., held=)`** is never passed. Saves 1 line.
11. **tracker/fsio.py:391 `write_json_atomically(..., indent=2)`** is never passed. Hard-code 2. Trivial.
12. Not dead, but test-only: `locking.race(name=)` (1078) is passed only by tests, and `fsio.mark_from_internet(_opener=)` (293) is an explicit test seam. Keep both.

### FOLD

1. **SQLite error plumbing duplicated between store.py and checkpoint.py - confirmed, and the biggest fold.** The two modules each define the same choke point (decision 189):
   - `_let_go_of`: store.py:512-528 / checkpoint.py:221-226.
   - `_Cursor`: store.py:531-578 / checkpoint.py:229-264. Store's adds `executemany` and `fetchmany`.
   - `_Connection`: store.py:581-617 / checkpoint.py:267-294.
   - `_close_after_failure`: store.py:912-929 / checkpoint.py:310-326. The docstrings are near-identical.
   - `_transaction`: store.py:1063-1076 / checkpoint.py:489-496. The bodies are identical.
   - `BUSY_TIMEOUT_MS = 5000`: store.py:461 / checkpoint.py:113.

   The pairs differ only in the error each raises (`StoreUnavailable(code)` vs `CheckpointUnavailable(where, code)`). The fold:
   - Give checkpoint one connection class with a single overridable `_refused(self, exc) -> Exception` method. Its cursor calls `self.connection._refused(exc)`, and the cursor carries the superset of methods.
   - Make public helpers in checkpoint: `transaction(conn)`, `close_after_failure(conn)` and a `connected(target, factory, *, timeout_ms, **options)`.
   - In store, reduce the copy to `class _Connection(checkpoint.GuardedConnection): def _refused(self, exc): return _unavailable(exc)`, plus `_transaction = checkpoint.transaction`.

   Layering holds: `store -> checkpoint` is already a load-time edge (store.py:206), and checkpoint gains no import. Keep both `BUSY_TIMEOUT_MS` constants and pass the value in at call time. test_store.py:2447 and test_checkpoint.py:217/256 monkeypatch them separately. Keep `store._Connection`/`store._Cursor`/`store._transaction` as module names, because tests patch them (test_store.py:1934/1945/2453/3639/3648/4278/4976/4982). Fold the `except sqlite3.Error` handling of `close` into the base class too. Saves about 135 lines in store, adds about 30 in checkpoint: **net about -105**.
2. **store.py `open()` in-place upgrade step (store.py:849-866)** writes `BEGIN IMMEDIATE`/`COMMIT`/`ROLLBACK` by hand and also calls `conn.close()`, which the outer `except` already does through `_close_after_failure`. Use `with _transaction(conn):` and drop the inner close. Saves about 6 lines.
3. **`households._the_record` (tracker/households.py:79) vs `manifest._the_record` (manifest.py:1211) - confirmed.** The households version is exactly manifest's with `follow=True` and the same `NOT_AN_ENGAGEMENT`/`ManifestError` refusal, which it already imports from manifest at call time. Make manifest's public (`the_record`) and call it from households with a call-time import, which may point anywhere. No load-time edge is added: households still imports only layout and records at load time. Saves about 18 lines.
4. **`records.people_from_json` (825) vs `feeds_from_json` (1108) - confirmed.** They are identical except for the element reader and the noun in the error. Fold them into `_objects_from_json(raw, one, what)` and keep the two public names as one-liners, because store.py:2058/2215 and the admission pin name them. Saves about 12 lines. Both are in `ADMISSION_PIN` (test_store.py:3002/3015 and 3258/3271), so re-pin `admission_digests()` under the current version; the admission refuses nothing new. `related_from_json` (1227) handles `None` and strings differently and checks string elements, so leave it out.
5. **`records.info_to_json` (1003) vs `api._info_payload` (tracker/api.py:2098) - confirmed.** The only difference is that a blank date is `None` in the record and `""` for the renderer. Give `info_to_json(info, *, blank_date=None)` the parameter and call it from api with `blank_date=""`, or post-process its result. `api -> records` is already a downward edge. Saves about 12 lines.
6. **Engagement-row creation, duplicated in store.py `_catching_up` (2637-2647) and `rebuild_engagement` (3416-3427).** Each is the same `_new_engagement_defaults()` plus `INSERT INTO engagements (_NEW_ENGAGEMENT_COLUMNS) VALUES (...)` plus `_apply(...)` plus `_vouch_for(...)`, differing only in the `built_at` stamp. Fold into `_build_engagement(conn, rel, events, head, chain, built_at, foreign, held)`. Saves about 10 lines.
7. **store.py `_check_statuses` (3643) vs `_check_intents` (3570) - confirmed as a shape, not as identical bodies.** Both, and the per-row half of `_check_rules` (3666), are a keyed two-way compare: in the record and not the store, differing fields, in the store and not the record. A `_compare_keyed(name, stored, recorded, missing_here, missing_there, differences)` helper would serve all three. The per-kind sentences become format strings; no test asserts their exact wording. `_check_rules` also checks the count and the engagement fields, which stay in it. While doing this, note that `_check_rules` compares with `!=` where `_check_statuses`/`_check_documents` use `_agree(...)`. That is harmless today, since no requests column is in `_ADDED_IN_PLACE`, but it is inconsistent. Net about -15. Optional.
8. **store.py `learned_keywords` (1612-1623) and `_check_learned` (3722-3727)** run the same `SELECT identifier, keyword FROM learned_keywords ... ORDER BY seq, keyword` and build the same tuples. Extract `_stored_learned(conn, engagement_id)`. Saves about 6 lines. Similarly, `_check_documents` (3544) repeats `_stored_rows`'s query, and could iterate `_stored_rows(...)` instead (about -2).
9. **manifest.py `_named` (1024) and `_asked` (1029)** are two-line wrappers around `_yes_no`, each used once, at 1088-1089. Inline them as `_yes_no(fields.get("named"), COL_NAMED, where)`. Saves about 10 lines.
10. **fsio.py `write_text_atomically` (213) and `write_bytes_atomically` (229)** have the same body apart from the open mode. Have one private `_write_atomically(path, mode, data, **open_kw)` that both call. Saves about 5 lines. Optional. Text mode must keep its newline translation, so do not reduce the text version to `.encode()`.
11. **Optional, read decision 136 first:** store.py `_recorded_learned` (3617-3640) re-implements `ledger._apply_keyword_event` keyed by `records.identifier_key`, deliberately, because ledger may not import records. `replay(events, key=str)` could take a key function from its caller: store passes `identifier_key`, and ledger still imports nothing. That would cut about 20 lines and keep one fold rule. It reverses a documented choice, so it is Jason's call.

Rejected folds:
- **`ledger._apply_release` (1208) vs `_apply_intent_event` (1228).** They share only the `KEY_KEY` guard (3 lines). One deletes a row and its intents for two identities; the other sets or clears an intent. Merging them would mix two fold rules.
- **A generic dataclass-driven `*_to_json/*_from_json`.** The pairs (`entry`, `person`, `info`, `feed`, `household`, `rule`, `status`) share only the "keep known fields" idiom (`{k: v for k, v in raw.items() if k in known}`, 3 times). Every pair carries its own rule:
  - an entry's `None` reads as the field's default;
  - an info's `tax_year` of `""` reads as `None`, and its yes/no fields are coerced to `bool`;
  - a household's `members` may be a single string;
  - a status requires `status`, and `file_count` is coerced to `int`;
  - a rule is duck-typed on `RULE_FIELDS`, since records cannot import manifest;
  - persons and feeds are validated.

  A generic converter would need a per-field codec table to say all of that. It would be cleverer, not clearer, and it would move code the admission pin hashes. Leave them as they are.

### BLOAT

1. **store.py:257-340, the schema-version changelog.** It is about 80 comment lines narrating versions 2-16, one paragraph per bump. The code treats every version below 16 the same way: set aside and rebuild (store.py:871-878). Several paragraphs are also stale: they say an older file is "refused, deleted and rebuilt", which decision 159 replaced with set-aside (the `open()` docstring at 820-833 says so). Cut to the rule plus "each bump is a decision-log row", and keep the v17-v20 in-place notes that `_IN_PLACE` depends on. Saves about 75 lines. Nothing in tests or docs quotes these lines.
2. **Duplicated docstring prose in the SQLite plumbing** (Windows/WinError 32, Python 3.11 cursor retention) appears in store `_let_go_of`, `_close_after_failure`, the comment at store.py:842-846, checkpoint `_Cursor._say` and checkpoint `_close_after_failure`. FOLD 1 removes it; say it once.
3. **Stale docstring reference, tracker/manifest.py:787.** It cites `tracker.router._required_matched`, which no longer exists. The function is `tracker.content_check.required_matched` (content_check.py:1273).
4. **Stale cross-references once DEAD 3 lands:** `ledger.apply` (1147) and `replay` (1319) both say ":func:`fold` and :func:`statuses` are this function over a whole file", and `tracker/filer.py:1299` names `tracker.ledger.fold`.
5. **Inconsistent default in tracker/locking.py:1219-1220.** The CLI's `--rounds` defaults to 30 while `race(rounds=20)` (1078) defaults to 20. Pick one.
6. **Compatibility shims checked and kept:**
   - `_IN_PLACE` v16-19 (store.py:396-402);
   - `ledger.RETIRED_EVENTS` (`rules_imported`, `handed_over_by_person`), with `IMPORTED`/`MIGRATED` still readable;
   - `records.Override.RETIRED` ("Waived");
   - `store.OLD_STORE_NAMED`/`store_named` (decision 186);
   - `checkpoint.CheckpointLeftBehind`.

   ROADMAP has no row retiring any of them (I grepped "retired" against store, version, in-place, migration and the event names). A journal is permanent, so the readers of retired names must stay.
7. **Single-use private helpers that are fine as they are.** These are not proposed: store `_write_memo`/`_write_verdict` (3228/3236), `_rule_from_sql`, `_positional_root`, and `checkpoint._opened`/`_write_ahead`. Each names a step and inlining saves nothing meaningful.

Rough tally: DEAD about 70, FOLD about 195 (about 215 with FOLD 11), BLOAT about 75, for **about 340 lines total**.


# Appendix D — App-facing layer: cleanup findings


**Summary.** I found no production dead code in the app-facing layer (api, after_install, settings, scheduling, view, page, page_rows, door, errors, progress, firm_cache, api_entry). Every vulture entry is either a false positive (a dataclass field that `asdict` serialises, a tuple-unpacked WinBase enum, a constant pinned by a test or `Setup.bat`) or a deliberate test seam (`view.render_page`, `settings.default_data_home`, `api.NO_OPEN_CODES`, and also `progress.line`, which vulture missed). `ruff` is clean, and there is no commented-out code. The real gain is folding. Five of the seven given pairs are worth folding: the four row-action handlers, `_info_payload` → `records.info_to_json`, `set_firm`/`set_firm_phone`, and `install_task`/`remove_task` (shared helper only). The `firm_cache.load`/`page_rows.load` pair should be folded only partly, because the two file formats differ on purpose. api.py has about 15 more same-shape folds: a shared re-scan helper, `_firm_key`'s two loops, the firm-reply shell built twice, the failure path written twice, the `handle_of` alias, and the event-date dicts written four times. On top of that come repeated decision-log refrains inside `_state`/`_vocab`, error rewraps that `_failure_of` already handles, and two no-op `.format()` calls. **Estimate: about 200 lines from folds plus about 50–60 from bloat, roughly 250–270 lines in total (about 2% of the 12,900 lines).** About 190 of those are in api.py. Nothing here changes behaviour except two small, intended fixes: FOLD 1 adds a few reply keys to `marked_missing`, and BLOAT 4 routes a JSON `null` to the existing refusal instead of the literal string `"None"`. Tests that pin names (`api._slug`, `progress.line`, `test_layers.ALLOWED_SPELLINGS` naming `settings._within`) move with their fold.

### DEAD

Every entry vulture reported in these files, checked by grep across tracker/, tools/, tests/, app/, pilot/, `*.bat`, api_entry.py and docs/:

1. `after_install.py:304 SETUP_RETRY`: **FALSE POSITIVE.** It is echoed word for word by `Setup.bat:83` and pinned by `tests/test_build.py:728-736`.
2. `after_install.py:402 check_sentence` and `:407 cache_sentence`: **FALSE POSITIVE.** They are fields of the `AfterInstall` dataclass, written at `:1124` and `:1216-1217`. `AfterInstall.reply()` (`:434`) sends them to the app via `asdict`. They are asserted in `tests/test_after_install.py` (293, 619, 625, 649-703). app.js does not read them, but they are part of the reply.
3. `api.py:848 NO_OPEN_CODES`: **TEST-ONLY by design.** It is the fail-closed partner of `READ_AND_PARKED_CODES`, and `tests/test_api.py:1005,1035` and `tests/test_single_source.py:2520` prove that every reason code is in exactly one of the two. Keep it. Optionally move it into the test file (about 27 lines), at the cost of the "placed by a person" home its comment claims.
4. `settings.py:136 DRIVE_UNKNOWN, DRIVE_NO_ROOT_DIR, DRIVE_RAMDISK`: **FALSE POSITIVE.** They come from a `range(7)` unpack that mirrors WinBase.h, and `tests/test_settings.py:771-777` and `tests/test_api.py:7690` use them.
5. `settings.py:1029 default_data_home()`: **TEST-ONLY.** It is used by the guards in `tests/conftest.py:764` and `tests/test_tripwire.py:109`, by `tests/test_settings.py:494`, and listed by name in `tests/test_api.py:10017`. Keep it as a test seam.
6. `view.py:349 / :785 ViewResult.unchanged`: **FALSE POSITIVE.** It is set at `view.py:785` and asserted in `tests/test_view.py:521-583` (P210 behaviour).
7. `view.py:716 render_page()`: **TEST-ONLY by design.** It is the agreement fixture's renderer (`tests/conftest.py:29,592,607`, `tests/test_view.py:616`). Keep it. Its 4-line prologue duplicates `write_view` (see FOLD 20).
8. Names vulture reports only when it scans `tracker/` alone, so not in the given report: `settings.py:201 EXPECTATIONS_FILENAME`, `:206 EXPECTATIONS_COLUMNS`, `:213 EXPECTED_SEP`, `:428 real_corpus_dir`, `:1043 process_scratch`. These are **TOOLS-ONLY**, used by `tools/backtest.py:103-106,321`, `tools/vocab_report.py:92-94` and their tests. They are not dead. They are routing-tool constants living in the app's settings module; moving them is optional and saves nothing.
9. `progress.py:137 line()`: **TEST-ONLY**, and vulture missed it because the name is common. Only `tests/test_progress.py:35,45` calls it. `Watch.say` (`progress.py:307`) rebuilds the same `json.dumps({PROGRESS_KEY: said}, ensure_ascii=True) + "\n"` inline. See FOLD 19.

### FOLD

All line counts are net lines removed.

1. **The four row-action handlers: CONFIRMED.** These are `api.py:4982 _cmd_dismiss`, `:5019 _cmd_unfile`, `:5058 _cmd_mark_missing` and `:5095 _cmd_restore`. Each one does the same steps: `_engagement_dir` → `_read_spec` → `original = str(spec.get("original","")).strip()` → refuse when blank → call one filer function with `seq=_seq_of(spec)` → `_refresh_readmes` → `{key: {original_name, decision, reason, prepared_location, …extra}, "state": _state(engagement)}`. Fold into two helpers next to `_seq_of` (`:4681`):
   - `_original_of(spec, refusal) -> str`
   - `_row_reply(engagement, key, entry, **extra) -> dict`, which also calls `_refresh_readmes` and `_state`.

   Each handler keeps its own docstring, which is the JSON contract, and becomes about 8 lines of body. `_cmd_mark_missing` currently omits `decision` and `prepared_location`; including them is additive. `_cmd_assign` (`:4857`) and `_cmd_add_issuer_and_file` (`:4934`) also use `_original_of`. **About 25 lines.**

2. **Shared re-scan: NEW.** The block `scan_note = ""; try: scan_engagement(x) except ScanLockedError as exc: scan_note = f"not re-scanned: {exc}"` is written out at `api.py:3535` (unlearn), `:4762` (`_hand_over`) and `:4880` (assign). It appears with a different note at `:4955` (add-issuer, `ISSUER_NOT_RESCANNED` plus `errors.keep`). Fold into `_rescan(folder, *, note=None) -> str`. **About 12 lines.**

3. **`records.py:1003 info_to_json` vs `api.py:2098 _info_payload`: CONFIRMED.** The bodies are identical except that a blank date becomes `""` in api and `None` in records. Replace the body of `_info_payload` with `payload = info_to_json(info); payload.update({n: payload[n] or "" for n in DATE_FIELDS}); return payload`. records.py does not need to change. **About 9 lines.**

4. **`handle_of` alias: NEW.** `handle_of` (`api.py:2264`) is `return ledger_key(entry)` behind a 7-line docstring. No test names it. The six call sites (`:2421, :2517, :3089, :5823, :5831`, plus the docstring reference at `:2385`) also compute `seqs.get(ledger_key(entry))` right beside it. Inline `ledger_key` and keep one sentence on `_triage_payload` saying the handle is the record key. **About 9 lines.**

5. **`_cmd_firm` / `_cmd_firm_last` shell: NEW.** The same 4-line `try: root = _saved_root() except (DoorError, SettingsError): raise ManifestError` appears at `api.py:5898` and `:6278`. The same 3-line reply literal `{"returns": [], "files": [], "totals": {...}, "paths": {}, "next_sort": _next_sort()}` appears at `:5902` and `:6290`, and the `_cmd_firm_last` docstring promises the two replies have "the same keys". Fold into `_firm_root()` and `_firm_reply_shell()`. Drop the `del argv` at `:6277`, since no other handler does that. **About 8 lines**, and the two key sets can no longer drift apart.

6. **`_firm_key`'s two loops: NEW.** In `api.py:5844`, the plain walk is the memo walk with an empty memo. Fold to `given = {} if spelled_for is None or " #" in key else spelled_for.setdefault(key, {})`, followed by the memo branch only. **About 7 lines.**

7. **The failure path written twice: NEW.** The block `except Exception as exc: if _failure_of(exc)["kind"] == "failed": errors.keep(...); log.error(...); return _reply_failure(exc)` appears at `api.py:3270-3277` (`_cmd_run_now`) and `:6498-6504` (`main`). `_reply_failure` (`:580`) calls `_failure_of` again (a second `_lock_payload` disk read for a locked failure), then re-splats the failure dict into `progress.failure_reply` a second time. Fold into `_say_failure(command, exc) -> int`, which computes the failure once, logs it, and prints `{"error": f["sentence"], "failure": f, "warnings": list(_WARNINGS)}`. **About 9 lines.**

8. **"Root could not be walked": NEW.** The pattern `errors.keep(...); log.warning("... could not be walked (%s)", error_class(exc)); _warn(PRACTICE_NOT_WALKED)` appears at `api.py:3674-3676` (`_cmd_list`), `:3871-3874` (`_listing`), `:5961-5963` (`_firm_fresh`, which raises instead of warning) and `:2656-2658` (`_feed_payload`, "feeds could not be resolved"). Fold into `_not_walked(where, exc) -> str`, which returns the sentence. **About 6 lines.**

9. **Fact → `Engagement` rebuilt twice: NEW.** The identical 3-line `Engagement(path=Path(one["path"]), household_path=..., problem=..., info=EngagementInfo(active, tax_year, rolled_from))` appears at `api.py:6097` and `:6169`. Fold into `_fact_engagement(one)`. Also, `_firm_fresh` (`:5978-5979`) sets `row["paused"]` and `row["links"]` by hand; `_firm_marked` (`:6188`) already does exactly that. **About 5 lines.**

10. **`_list_payload` return rows: NEW.** `api.py:3708-3714` (each household's returns) and `:3718-3726` (`engagements`) build the same row: `label`/`name`, `path`, `year`, `return_name` and `form`. Use one `_return_row(one)` with the household-only extras added on top. The year expression `one.tax_year if one.tax_year is not None else year_of(one.path)` is written out at `:2894, :3711, :3721` and `:5782`. `scaffold._ReturnLine.tax_year` already has it as a property; give `registry.Engagement` the same property, or add a local `_year(one)`. Also, `_cmd_list`'s final return (`:3680-3684`) copies `empty`'s keys back one by one; `{**empty, **_list_payload(...), ...}` does the same. **About 10 lines.**

11. **Reminder event dicts: NEW.** `{"date": ledger.day_of(str(ev.get(AT_KEY, ""))).isoformat(), "stage": ev.get(STAGE_KEY) or 0}` is written out four times: `api.py:2608, :2610` (`_return_reminder`) and `:5278, :5282` (`_reminder_now`, which adds `file` and `asked`). Fold into `_event_day(ev, *keys)`. **About 6 lines.**

12. **Schedule replies: NEW.** `_cmd_install_schedule` (`api.py:5545-5562`), `_cmd_set_schedule` (`:5580-5590`) and `_cmd_move_schedule_here` (`:5606-5608`) each copy `installed`, `outcome`, `sentence` and `after_install` out of `done`. `done.reply()` already carries all of them. Fold into `_schedule_reply(done)`. While doing so, settle the key name: move-schedule-here says `schedule_sentence` and the other two say `sentence`; `app.js:2046` reads the former. **About 4 lines.**

13. **Small api.py one-liners: NEW.** About 12 lines in total:
    - `_head_of(spec)`: the same `head` check and `NO_LIST_HEAD` refusal appears at `:3378-3380` and `:4938-4940`.
    - `_cmd_watch` (`:3295-3297`) re-parses `ENGAGEMENT_FLAG` exactly as `_engagement_dir` (`:1108-1111`) does. Use a shared `_flag_value(argv)`.
    - `_slug = slug` (`:1170-1173`) is a 4-line alias. Use `page.slug`; three test lines change.
    - `Engagement(path=…, household_path=…, info=load_engagement_info(…)).label` appears at `:4071, :4446, :4544, :4557, :4560`. Fold into `_label(path, household_dir)`.
    - `_root` (`:590`) is `_saved_root` (`:603`) plus a refusal when it returns None.

14. **`settings.py:542 set_firm` / `:550 set_firm_phone`: CONFIRMED.** Same shape: read, set one key to `str(v).strip()`, write, return. Fold into a private `_set_text(key, value)` and keep both public names as one-line wrappers, because they are used in more than 15 test sites. `api._cmd_set_root` (`:5439-5442`) then still does two read/write cycles; a combined setter could do one, but that is optional. **About 6 lines.** Related: `settings._within` (`:1127`) has one caller, `_inside`, and could be inlined (about 5 lines). However, `tests/test_layers.py:748` names `_within` in `ALLOWED_SPELLINGS`, so that entry goes in the same commit.

15. **`scheduling.py:429 install_task` / `:529 remove_task`: PARTLY CONFIRMED.** Merge only the "run schtasks, raise RuntimeError with its stderr or stdout" tail (`:443-449` and `:540-545`) into `_schtasks_or_raise(command, what)`. Do not merge the functions themselves: one creates, the other checks existence and deletes. **About 6 lines.**

16. **`firm_cache.py:291 load` / `page_rows.py:126 load`: PARTLY CONFIRMED.** The formats differ on purpose. page_rows uses two lines with a digest of the raw text, so a 2 MB file is never re-encoded; firm_cache uses one JSON object. The validators also differ, so do not merge `load`. Share these parts only:
    - the read step: `read_text` with `FileNotFoundError` → `{}` and other errors → log by class (`firm_cache:298-303`, `page_rows:137-143`);
    - `save`'s `mkdir` + `write_text_atomically` + log on `OSError` (`firm_cache:363-367`, `page_rows:177-181`);
    - the blake2b-16 digest (`page_rows._digest:90` and `firm_cache._households_digest:284`).

    page_rows already imports firm_cache, so these can be small public helpers in firm_cache. **About 10 lines.**

17. **Duplicated link test: NEW.** `firm_cache.py:106` and `after_install.py:654` each redefine `_LINK_TAGS` (the same frozenset), and `fsio.py:329` already holds it beside `fsio.is_link`, "the one test of a link the package has". Export the tags from fsio and use them in firm_cache (about 3 lines). Replace `after_install._is_link` (`:658`, 12 lines) with `fsio.is_link`. One difference to review first: fsio returns False on any `OSError`, while `after_install` re-raises everything except `FileNotFoundError`. **About 13 lines.**

18. **`progress.Watch.say`'s two except arms: NEW.** `progress.py:308-327`: the `OSError` and `ValueError` arms each import errors at call time and log the same debug line. Use one `except (OSError, ValueError)` and set `_gone` only for `OSError`. **About 4 lines.**

19. **`progress.line` vs `Watch.say` encoding: NEW.** Both encode the same way (see DEAD 9). Have `say` call `line`, or a shared `_encoded(said)`, so the progress line is encoded in one place. **About 2 lines.**

20. **`view.py:716 render_page` / `:740 write_view` prologue: NEW, small.** Both run `_readers` → `review.triage` → `parked` (`:731-734` and `:780-783`). Fold into `_drawn(...)`. Also, `view_state`'s two `UNKNOWN` returns (`:877-880`) collapse to one. **About 5 lines.**

21. Not worth folding: `api._firm_draft` (`:5740`) vs `_return_reminder` (`:2572`). They read the same facts but return different shapes for different cards, and folding them would merge two concerns.

### BLOAT

1. **Error rewraps that `_failure_of` already handles.** `api._failure_of` (`:529`) already says `ReminderError`, `SettingsError`, `DoorError` and `LayoutError` as `"refused"` with `str(exc)`. The following rewraps to `ManifestError(str(exc))` therefore change nothing: `api.py:5215-5219` and `:5247-5250` (`_reminder_now`), `:5435-5438` (`_cmd_set_root`), `:5898-5901` and `:6278-6281` (the firm pair, removed anyway by FOLD 5). No caller catches `ManifestError` around them; tests go through `main`. **About 10 lines.** Keep `:5578` (`ScheduleChoiceError` is a `ValueError` and would otherwise be said as `"failed"`) and `:6424` (`CheckpointError`).

2. **No-op `.format()` calls.**
   - `REMINDER_LINE_UNREADABLE` (`api.py:417`) has no placeholders, yet `:2605` calls `.format(label=..., kind=...)`, so the warning no longer names the return. `tests/test_api.py:7215` repeats the same no-op, so it passes without checking anything. It is also word for word `REMINDER_UNREADABLE` (`:415`). Either restore a `{label}` placeholder or drop the `.format`, and merge the two constants.
   - `ROOM_SHORT_WORDS` (`api.py:1581`, "Names Shortened to Fit") is formatted with `short=` at `:3074` and `:3175` for nothing. `_room_sentences` (`:3171`) and `_state`'s `warnings`/`room_note` (`:3069-3074`) build the same two sentences.

3. **Repeated refrains inside `_state` and `_vocab`.**
   - `_state` (`api.py:2974`) has 110 comment lines, 85 code lines and no docstring.
   - `_vocab` (`:1593`) has 164 comment lines.
   - "The page/renderer types none of them" appears about 21 times and "the shell opens only the paths this map holds" 7 times (five of those inside `_state`'s `paths` block, `:3127-3165`). `_vocab`'s own docstring already states the first rule.

   Say each once (in the docstrings of `_vocab` and `_state`) and keep only the per-key decision numbers. **About 35 lines.**

4. **Same paragraph in several docstrings.** The `seq` paragraph ("``seq`` is the row as the person saw it and is required (decision 112)") appears in `_cmd_dismiss` (`:4992`), `_cmd_unfile` (`:5032`), `_cmd_restore` (`:5111`) and `_cmd_assign`, and `_seq_of`'s docstring (`:4681`) owns the rule. Point to it instead. **About 9 lines.**

   Related: `str(spec.get(k, "")).strip()` without `or ""` (`:3530-3531, :3964, :4369, :4384, :4857-4858, :4934, :5002, :5038, :5077-5078, :5117`) turns a JSON `null` into the non-empty string `"None"`, which gets past the "Pick the file…" refusal. A shared `_text(spec, key)` (34 sites) fixes this; it shortens lines rather than removing them.

5. **Tiny helpers with docstrings longer than their code.**
   - `api._placed` (`:2208`): a 7-line docstring for one `replace`, with 2 callers. It also shares its name with the unrelated `door._placed`.
   - `api._refresh_readmes` (`:3208`): 8 docstring lines, 3 of code.
   - `api._reminder_card`, `_cmd_reminder` (12 docstring lines, 3 of code).

   These are judgement calls given CLAUDE.md's rule that docstrings carry reasoning. Trim only what repeats a decision row.

6. **`scheduling.py` comment placement.** The comment at `:148` ("The two n8n nodes…") sits above `TASK_XML_NAMESPACE`, not above `N8N_*`. The comment at `:152` ("How a person is told to install the schedule…") sits above `SCHEDULE_XML_ENCODING`, whose own comment follows it. `task_scheduler_here` (`:166`) has no blank line above it. Fixing this is cosmetic and saves 0–2 lines.

7. **`api.py:6468-6471`.** Four blank lines before `def main`; two are enough.

8. **`rollover` `skipped` is always empty.** `_cmd_roll_household` (`api.py:4555`) returns `skipped`, which its own docstring says "is always empty". `app.js:1472-1478` and `rollover.py:1060-1062` still read it. Removing it spans three modules, so it needs an owner decision.

9. **Time-bound migration code (decision for Jason, not dead).**
   - The "left behind beside the program" mover: `after_install.py:658-998`, about 250 lines (decision 186).
   - The rename carry-over: `_carry_over_settings` / `_replace_earlier_task`, `:1001-1083` (P155).
   - The n8n output of the scheduling CLI: `scheduling.py:143-164, :370-424, :870-880`, about 70 lines, with no runbook mention.

   Once every pilot machine is past these steps, they can go. I have not counted them in the estimate.


# Appendix E — Cleanup findings: runner, reminder, rollover, registry, layout, households, templates, reasons, validators, review, names, containers, scaffold, `__init__`, tools/


### Summary

There is little dead code in this area. Of the 19 vulture entries in these files, 3 are false positives (the app reads `Emphasis.subject_*` in JS, `validators.__getattr__` is a PEP 562 hook, and `SETUP_MODE_FLAG` is used by `api_entry.py`). 5 are dead: `parse_python`, `NAME_OUTCOMES`, `IDENTITY_AGREES_WRONG_YEAR`, `prior_file_count`, and the two `max_depth` parameters. The other 11 are referenced only by tests. Of the requested duplicates, the `_the_record` pair is a real fold. The `repo_map`/`vocab_report` `main`/`write_outputs` similarity is real, but a shared tools module would be cleverer, not clearer, so I do not recommend it. Better folds are elsewhere:
- the 8-line "typed folder through the door" block copied into about 10 module CLIs;
- the two draft-file loops in runner;
- `scaffold._readme_returns` / `readme_returns`;
- reminder's `is_approved_this_week` wrapper.

The comments in reasons.py and templates.py are not copies of ROADMAP decision rows. They are local reasoning, such as why each catalog keyword was chosen, and should stay. Only a few "until decision N…" history sentences could go.

**Estimated removable lines in this area:**
- about 165 with no behaviour or convention change (DEAD + FOLD below);
- about 60 more repo-wide from the door-block fold outside this area;
- about 105 more if Jason agrees to drop the three module CLIs that nothing runs (BLOAT 1).

That makes roughly 270 to 330 of about 18,000 lines. The size of runner.py and reminder.py is prose, not dead code.

### DEAD

Each entry is marked DEAD (no reader anywhere), TEST-ONLY (only tests read it) or FALSE POSITIVE. "Grep" covers tracker/, tools/, tests/, app/, pilot/wintest/, `*.bat`, `api_entry.py` and docs/runbook.md.

1. **DEAD:** `tools/repo_map.py:435-438` `parse_python`. Nothing calls it, including tests. Delete it (about 6 lines) and reword `parse_python_full`'s docstring opener "As parse_python, plus…" (line 444).
2. **DEAD:** `tracker/names.py:77` `NAME_OUTCOMES`. It has no reader in code, tests or JS. Delete it (1 line).
3. **DEAD:** `tracker/review.py:149` `IDENTITY_AGREES_WRONG_YEAR = 1`. It is "reserved on purpose" (lines 145-147) but nothing ranks on it. Ranking only compares `IDENTITY_AGREES = 0` with `IDENTITY_UNKNOWN = 2`. Delete it and keep a one-line note that the year never ranks (saves about 3 lines).
4. **DEAD:** `tracker/rollover.py:186` `RolledItem.prior_file_count`. It is written at :496 and read nowhere (code, tests or JS). Delete the field and the kwarg (2 lines).
5. **DEAD parameter:** `tracker/registry.py:536` `engagement_dirs(max_depth=)` and `:796` `discover_engagements(max_depth=)`. No caller anywhere passes `max_depth`. `registry.MAX_DEPTH` (`:98-104`, a 5-line comment and the value) exists only as their default. The docstring at `:539-542` keeps the parameter "for a script nobody reran", which is obsolete compatibility. Delete both parameters, `MAX_DEPTH` and its comment, and that docstring paragraph (about 12 lines; the repo-map constants refresh with `update`).
6. **DEAD parameter:** `tracker/layout.py:789` `_parts_below_of(inner_kind)`. The body never reads it; only `outer_kind` matters. Drop it from the signature and from the call at `:786`. This loses no lines but makes the cache key honest: the result depends on `inner_text` only.
7. **DEAD parameter:** `tracker/runner.py:1858` `_why_no_draft(today)`. It is unused, and its one caller is `:1614`. Drop it.
8. **DEAD in production (TEST-ONLY branches):** `tracker/reminder.py:836-866` `client_ask`. Its only production caller is `triage` (`:1102`), which calls it only for PARTIAL rows that `_firm_side_reason` and `_ambiguous_reason` (`:908-924`) have already cleared. So:
   - the FAILED branch (`:861-865`) is unreachable from the pass;
   - the PARTIAL "; reason" append (`:856-859`) is unreachable, because any reason already sent the row to `attention` or `held`.

   The docstring says so itself ("since decision 115 no pass asks it… this branch waits for the action…"). Only `tests/test_reminder.py:229,242,2062,2102` reach them. Removing them saves about 12 lines, including the docstring. Jason's call, because the docstring keeps the branch for a future action.
9. **TEST-ONLY:** `tracker/reminder.py:1892-1918` `is_approved_this_week`. It is a 27-line wrapper (`approval_state(...) == APPROVED_NOTE`), almost all docstring. Production uses `approval_state` directly (`runner.py:1757`). `approval_state`'s own docstring points to it ("`since` is read as is_approved_this_week reads it"). Move the `since` paragraph into `approval_state`, delete the wrapper, and have tests compare to `APPROVED_NOTE` (about 22 lines; tests at `test_reminder.py:1452-1559`).
10. **TEST-ONLY:** `tracker/reminder.py:751-752` `ReminderDraft.total_requests` / `received_requests`. They are set at `:1573-1574` and read only by `test_reminder.py:391,499,2000`. The same numbers already reach the letter through `progress_line`. Delete the fields and the assignments (4 lines) and change the tests to assert on `draft.letter.progress`.
11. **TEST-ONLY:** `tracker/rollover.py:185` `RolledItem.prior_status`. It is read only by `tests/test_ledger.py:603-606`. Keep it or drop it together with item 4; it is a small call.
12. **TEST-ONLY:** `tracker/households.py:383-386` and `:65`, the `CLIENT_FOLDER_MISSING` re-export of `layout.CLIENT_FOLDER_MISSING`. Only `tests/test_runner.py:3401,3560` import it from households. Point those tests at `tracker.layout` and delete the re-export and its import (5 lines).
13. **TEST-ONLY:** `tracker/runner.py:723-727` `READING_STOP_PAGE_SECONDS` / `READING_STOP_DOCUMENT_SECONDS`, re-exports of `content_check`'s values. No production code reads `runner.READING_STOP_*`. Tests should import from `content_check` (5 lines).
14. **TEST-ONLY:** `tracker/layout.py:860-865` `names_one_folder`. Production compares by `folder_name_key` (`registry.py:830-832`). Its only reader is `tests/test_layout.py:674-689`, which asserts that it equals the key comparison. Delete it (7 lines) and that test clause, then reword `registry.py:829` and the `folder_name_key` docstring (`:869`).
15. **TEST-ONLY:** `tracker/registry.py:536` `engagement_dirs`. Production uses `record_dirs` and `_walk_root`; 11 test call sites use it (test_registry, test_view, test_after_install). Recommendation: keep it as the public walk the tests use, but shrink it to 3 lines with item 5.
16. **TEST-ONLY:** `tracker/names.py:105-115` `spelling_in`. It is a one-liner over `_said_at`, and only `tests/test_names.py` (9 asserts) uses it. It is named in the module docstring as API. Optional: delete it and test `_said_at`/`check_name` (about 11 lines).
17. **TEST-ONLY, keep:**
    - `tracker/layout.py:935` `STEP_PROBLEMS`: the closed set `test_layout.py:351,423` checks `place_problem` against.
    - `tools/backtest.py:160` `UNMEASURED_NOTE`: pins the committed `docs/backtest-baseline.json` note (`test_backtest.py:319`).

    Both are contracts, not cruft.
18. **FALSE POSITIVE:** `tracker/reminder.py:554-555` `Emphasis.subject_colour` / `subject_bold`. `api.py:1183` ships them with `asdict(STAGE_EMPHASIS[...])`, and `app/renderer/app.js:562` reads them.
19. **FALSE POSITIVE:** `tracker/validators.py:76` `__getattr__`. It is the module-level PEP 562 hook for lazy `validators.PdfReader`; tests read and replace it.
20. **FALSE POSITIVE** (found while checking): `tracker/runner.py:573` `SETUP_MODE_FLAG`. `api_entry.py:39,69` uses it, as does `tests/test_pilot_installer.py`.

### FOLD

1. **Confirmed:** `tracker/households.py:79-97` `_the_record` vs `tracker/manifest.py:1211-1229` `_the_record`. The bodies are identical apart from manifest's `follow` flag (households is `follow=True`). Both modules are in layer 1, and households already imports manifest at call time. Delete the households copy and import manifest's at call time; ideally rename it to public `the_record`, since it now has a second caller. This saves about 17 lines.
2. **Confirmed but rejected:** `tools/vocab_report.py:599` `main` / `:500` `write_outputs` vs `tools/repo_map.py:1219` / `:1092`. The shared part is about 8 lines of "subparser dict, dispatch, catch ToolError, exit 2" plus a 3-line JSON+markdown write. The JSON formats even differ (indent 2 vs indent 1 with sort_keys). Across the six tools:
   - `backtest` has the same dispatch shape;
   - `lockfiles` uses if/elif;
   - `learned_keywords` and `gpu_pack` have no subcommands;
   - `repo_map` deliberately imports nothing of the repo (agents run it first);
   - `tools/` is not a package, and the others use `sys.path` inserts.

   A shared `tools/_cli.py` would save about 25 lines, but it would add a module, its test, a map node and a cross-tool import. That is cleverer, not clearer, so leave it. The one cheap in-file tidy is to give `vocab_report.write_outputs` the LF-reasoning docstring that repo_map's has, or drop that docstring. Similarly, `load_report` in vocab_report and backtest and `load_map` in repo_map are about 68% alike, but each has its own error wording and hints, so leave them.
3. **New, cross-module:** the "typed folder is parsed, never trusted" block is copied verbatim into the CLI of about 10 modules (about 8 lines each: comment, two imports, try/except `parser.error`):
   - `tracker/reminder.py:2219-2227`
   - `tracker/review.py:521-529`
   - `tracker/scaffold.py:794-801`
   - `tracker/validators.py:634-641`
   - and in content_check, filer, ledger, router, scanner and view; rollover `:984-994` and store are household/return variants.

   Fold it into one `door.typed_return(parser, typed) -> Path` (and `typed_household`) in `tracker/door.py`. It needs no new import: door already loads `layout`, and the parser is passed in. One line per CLI saves about 28 lines here and about 60 repo-wide.
4. **New:** `tracker/runner.py:1816-1831` `_retire_unedited_drafts` and `:1833-1855` `_refresh_stale_draft` are the same loop. Each goes over `(DRAFT_FILENAME, NEW_DRAFT_FILENAME)`, skips a missing or `is_protected` file, does one action, and turns an `OSError` into `errors.keep` plus a log warning. Only the action differs (`unlink` vs `write_draft`). Make it one `_each_own_draft(engagement_dir, approved_since, act, verb)`, or a generator of the unprotected paths. This saves about 8 lines.
5. **New:** `tracker/runner.py:1678-1681` `skipped_because` has one caller (`_working`, `:2000`). Inline it as `why_skipped(run.engagement)[0]`, since the code is empty exactly when the sentence is. This saves 5 lines.
6. **New:** `tracker/runner.py:2216-2221` `checkpoint_said` vs `:2213`. `records_needing_a_person` repeats its body (`errors.said(exc, (checkpoint.CheckpointError,))`). Call `checkpoint_said` there, so the two callers share one spelling.
7. **New:** `tracker/scaffold.py:433-455`. `_readme_returns` returns `(year, returns)`, but both callers (`readme_returns` at `:454` and `write_readme` at `:577`) throw the year away. Fold the two into one `readme_returns` that returns the list or `None`. This saves about 9 lines.
8. **New:** `tracker/runner.py:314-412` (`left_behind` family):
   - The checkpoint file-name tuple is spelled twice, in `left_behind` (`:342-344`) and `_to_move` (`:379-381`). Make it one `_CHECKPOINT_FILES` constant.
   - `left_behind_warnings` (`:400-404`) walks the disk twice, once directly and once through `left_behind_to_move`. Filter `found` with `_to_move` instead.

   This saves about 4 lines and one walk.
9. **Minor:** `tracker/reminder.py`.
   - `render_html` (`:1657-1663`) and `render_text_html` (`:1745-1748`) build the same outer `<div>` from the same `LETTER_INK` lookups; one `_letter_div()` would serve both.
   - `_compose_letter`'s two `Letter(...)` returns (`:1346-1368`) repeat 6 keyword arguments (greeting, progress, sections, drop, link, signoff); build the shared part once.
   - `_missing_detail` (`:894-895`) is `return item.expected_text` with one caller (`:1102`); inline it.

   About 10 lines in all.
10. **Cross-area, 1 line:** `api.py:717` `MISFITS_HEADING` has the same text as `runner.py:2493` `STATUS_MISFITS_HEADING`, and api already imports from runner, so one should name the other.
11. **Cross-area, consider:** `tracker/rollover.py:553` `_same_folder` and `tracker/store.py:2802` `_spelled` both resolve and then `normcase`. rollover's also tolerates `OSError`. `runner.py:303` `_spelled` is the `abspath` variant. They could be one helper if the layer table allows it, which `layout` does not, since it is lexical only.

### BLOAT

1. **Module CLIs that nothing runs:**
   - `tracker/validators.py:614-681` (68 lines; it is also the only reason validators reaches `scaffold` and `door` at call time)
   - `tracker/names.py:308-323` (16 lines)
   - `tracker/containers.py:664-685` (22 lines)

   No `.bat` file, runbook line, README line, test or app code invokes any of them. By contrast, the reminder, rollover, registry, review, scaffold and runner CLIs are documented in README or runbook and/or driven by tests. CLAUDE.md's convention ("each with its own CLI") argues for keeping them, so this needs Jason's decision. Removing all three saves about 106 lines.
2. **Pass-order version-1 read:** `tracker/runner.py:802-803` `_PASS_ORDER_READ = (1, PASS_ORDER_VERSION)` and the `versions` parameter of `_hint_households` (`:2045`). The file is only a hint: a version-1 file would read as unreadable once (one warning) and then be rewritten as version 2. This is optional legacy compatibility, about 3 lines.
3. **Repeated tails:** `tracker/runner.py:2020-2040` `_read_order_hint` has three identical `_warn(report, CODE_ORDER_HINT_UNREADABLE, ORDER_HINT_UNREADABLE); return path, {}, False` tails. Restructure them into one exit (about 4 lines).
4. **History prose in tracker/reasons.py.** I checked decisions 90, 140, 144, 157 and 190 against `docs/ROADMAP.md` rows 163, 212, 220, 230 and 243. The comment blocks are not copies; they carry the code-local reasoning (the `Said` design, `holds` vs `firm_side`). Only the "used to / until decision 190" history describes behaviour that no longer exists: `:3-8`, `:18-24` and `:125-128`. Trimming it to the current rule saves about 10 lines.
5. **tracker/templates.py comments: keep.** Its 253 comment lines are per-keyword misfile evidence ("the thirteenth reading", the W-3/1099 collisions). That is exactly what `docs/tools.md` says to read before changing a keyword, and it is not in ROADMAP.
6. **tracker/__init__.py:50-52** "The re-exports that used to live here were thirteen names no file consumed…" is history. The rule "imports nothing at load time" is enough (3 lines). The module list at `:5-40` matches the files exactly (verified).
7. **No other unused parameters** in these files (AST check). The only ones are items 5, 6 and 7 in DEAD. No duplicated constants that mean the same thing, beyond FOLD 10: the `"no-room"` / `"inactive"` literal coincidences across runner, reasons and learned_keywords are different code namespaces, and `"gpu-runtime"` is duplicated deliberately between `tools/gpu_pack.py` and `ocr.py`, with `test_gpu_pack.py:50` pinning the two to the same value.


# Appendix F — Electron side: dead code, folds, bloat (read-only review)


**Summary.** The Electron side is cleaner than its size suggests. No top-level function or const has zero references once spread (`...name`) uses are counted. The IPC surface matches exactly: preload's 7 exposed calls, main.js's 4 `ipcMain.handle` plus 1 `ipcMain.on` channel and 2 `send` channels are all used, and every menu id in `BAR`/`POPUPS` has an answer in `MENU_ANSWERS` or `PAGES_ROW_ANSWERS`. Every id the JS looks up exists in index.html. There are no `console.*` calls, no `debugger`, no commented-out code and no TODOs. Both vendored Floating UI files are loaded and used.

The removable weight is in three places:
1. **CSS dead weight.** About 140 lines of style.css are declarations that pilot-ui.css overrides with the identical selector: 200 of style.css's 570 declarations are overridden, and 24 of its rules are overridden whole. About 45 more lines across the sheets are classes and tokens that nothing ever sets (the old `.card`/`.card-head` family, `.chosen-badge`, `.tmpl-id`, `.wiz-sub`, `.form-blurb`, `.btn-danger`, `.icon-fill`, `.tabular`, 10 never-read custom properties).
2. **Near-duplicate JS.** About 215 lines: the "write one row" pattern repeated in 10 app.js functions; `keepMoved`, which is byte-for-byte `assignParked`; three editor lookups that should call the existing `editorRowItem`; two element builders (`el`/`h`); four localStorage read/write pairs; plus about 12 smaller folds.
3. **Defensive code that can never fire.** About 20 lines: 22 `typeof X === "function"` guards (plus the `unanswered(...)` fallback branches behind some of them) for functions that index.html always loads, and the hidden `#legacy` inputs used as variables.

**Estimated total removable: about 400 to 430 lines of the 12,750 in scope** (JS 9,479, CSS 2,691, HTML 583).

**The pilot files are live, not superseded.** pilot.js draws the badge and the terms gate. tour.js is the tour. pilot-content.js is read by the About dialog, the tests, `tracker/api.py` and the installer build. pilot-ui.css is the token layer every other sheet reads, and main.js reads its window colour from it.

Most folds touch names or literal strings that the tests pin; each item below lists them.

Line numbers are from the tree as of 2026-10-08.

---

### DEAD

1. **The `.card` / `.card-head` family (the old screen's cards). No JS or HTML sets either class.**
   - style.css:98-104 (`.card`), style.css:106-111 (`.card-head`), style.css:112 (`.card-head h3`).
   - pilot-ui.css:208-214 (`.card-head h3`), pilot-ui.css:417-425 (`.card`, `.card-head`).
   - About 25 lines.
   - Keep the nearby `#page > * { flex-shrink: 0 }` (pilot-ui.css:415), which tests/test_pilot_ui.py:248 pins.
   - Checked by collecting every class the code can set: `className` values including template literals, `classList.*` arguments, `querySelector`/`closest`/`matches` selectors, pilot's `make()` arguments and `class="..."` in the HTML. Dynamic prefixes (`notice-`, `edge-`, `section-`, `ed-`, `rem-stage-`, `is-*`, `rem-em-*` via `marked()`) were resolved by hand.

2. **`.chosen-badge`: never set (the form-step header lost its badge).**
   - Its own rules: style.css:468-476, pilot-ui.css:433-438, pilot-ui.css:580.
   - Its entries in the shared selector lists at pilot-ui.css:247, 258 and 432.
   - About 17 lines.

3. **`.tmpl-id`, `.wiz-sub`, `.form-blurb`: never set.**
   - style.css:311, style.css:424, style.css:456.
   - Their entries in pilot-ui.css's size and weight selector lists (pilot-ui.css:232, 247, 257).
   - tests/test_shell.py:1890 already asserts that `className: "tmpl-id"` is gone from app.js.
   - About 4 lines plus selector edits.

4. **`.btn-danger` (pilot-ui.css:344), `.icon-fill` (shell.css:330), `.tabular` (shell.css:21): never set.**
   - The other selectors in the `.btn-danger` and `.tabular` lists are live, so only those names go.
   - tests/test_shell.py:3904-3906 and 4358 find the tabular-nums rule by `selector.startswith(".tabular,")`; update both to match the new first selector.

5. **`.editor-table .ed-identifier input` (style.css:351) and the `.ed-min_size_kb` half of style.css:352-353: never set.**
   - The editor always draws in fold mode (`renderEditorRows` passes `fold`), which writes `td.ed-${key}` only for `vocab.editor.plain_columns` (tracker/api.py:983).
   - `identifier` and `min_size_kb` are routing columns, drawn in `.field` labels and never in such a `td`.
   - `.ed-expected_count` and `.ed-document` (the custom rows) are live.

6. **Ten custom properties defined and never read by any `var()` or JS.**
   - pilot-ui.css:111: `--amber-deep`, `--amber-soft` (and again at pilot-ui.css:182 in the dark block).
   - pilot-ui.css:119-128: `--navy-deep`, `--surface-hover`, `--surface-pressed`, `--surface-selected`, `--surface-sunken`, `--surface-disabled`, `--danger-hover-bg`, `--danger-border`.
   - style.css:7 also defines `--navy-deep`.
   - tests/test_shell.py:235-236 lists the alias pairs; drop them there too.
   - About 8 lines.

7. **The `#legacy` block (index.html:190-197; the block itself is 193-197): three hidden inputs used only as variables.**
   - `#root-input`, `#firm-input`, `#phone-input` are written and read at app.js:1882-1884 and 1976-1978, and at shell.js:1071-1094 and 1134-1135.
   - Replace them with one object (`let setupDraft = {root, firm, phone}`) in app.js.
   - Removes 8 HTML lines and the DOM round-trip.
   - Tests: tests/test_shell.py:539-561 and tests/test_single_source.py:4104-4106 pin the block; rewrite them to pin the object.

8. **`pageBackground()`'s fallback to style.css `--bg` (main.js:826) never runs.**
   - pilot-ui.css always defines `--window-light`/`--window-dark`, and tests pin them.
   - Drop the second `tokenColour(...)` call when style.css's `:root` goes (see BLOAT 1).

Not dead, though a quick look suggests otherwise:
- Every IPC name, menu id, `#i-*` icon symbol (some are reached through tables such as `PAGES_REASON_ICONS` and `PAGES_SECTIONS`) and HTML id is used.
- The static-structure ids (`#shell`, `#main`, `#side-scroll`, `#sheet-head`, `#side-brand*`) are styled by shell.css.
- `vendor/floating-ui/*` is used by tooltip.js:62 and pages.js:410; the LICENSE files must stay.

### FOLD

1. **One "write one row" helper in app.js (about 55 lines).**
   - Ten functions repeat the same body: save `viewGeneration`, disable the button (sometimes a `writeStart` key), call `call(withEng(cmd), payload)`, then `renderFor(view, result.state)`, then build `notes = [head]` with `if (x.foo) notes.push(x.foo)`, then `outcome(notes.join(". ") + ".", anyExtra ? "warn" : "ok")`, then `catch → refused(err, btn)`.
   - The ten:
     - `restoreMoved` 770
     - `fileRow` 979
     - `addIssuerAndFile` 1023
     - `handOver` 1106
     - `withdrawAnswer` 1194
     - `dismissParked` 1222
     - `unfileDocument` 1272
     - `acceptFolderName` 1493
     - `markShared` 1511
     - `clearLock` 1810
   - Fold into two helpers:
     - `writeRow(command, payload, {btn, busy})`: returns the result or null, and owns the view, the button, the busy key and the refusal.
     - `sayNotes(lead, extras)`: warns when any extra is present.
   - Tests: tests/test_single_source.py:1961-1979 regex-matches the literal `call(withEng("dismiss"|"unfile"|"mark-missing"|"assign"), {...})` shapes. Keep the payload object literal at each call site, or update those regexes.

2. **`keepMoved` (app.js:790-803) is `assignParked` (app.js:1129-1142).**
   - The bodies differ only by `spellingFrom(li)`.
   - On a moved row that returns null, because `movedRow` draws no `.r-spelling`.
   - The API treats a null spelling as none: `spec.get("spelling") or {}` at tracker/api.py:4864.
   - Delete `keepMoved` and route `.r-keep` (app.js:3850) to `assignParked`. About 14 lines.
   - Tests: tests/test_single_source.py:1977 loops over both names; drop `keepMoved` from it.

3. **The editor's item lookups (app.js:3103-3127) should use `editorRowItem` (app.js:3193).**
   - `editorRowYear`, `editorRowShortName` and `editorRowHasDocument` each repeat the same `editorState.items.find(i => i.identifier === row.identifier)` that `editorRowItem` already wraps.
   - Move `editorRowItem` up and make each a one-liner. About 9 lines.

4. **`el` (app.js:39-61) and `h` (shell.js:113-136) are the same builder with two allowlists.**
   - The bodies are identical line for line.
   - Keep one builder, with the union allowlist, in app.js (it loads first). Make the other name an alias, or rename the 175 `el(` lines.
   - Decision 137's rule (no `on*`, `href`, `src` or `style`) holds for the union. About 22 lines.
   - Tests: tests/test_api.py:5412-5417, tests/test_shell.py:665, 1136, 4493-4494, 4622 and tests/test_single_source.py:3496 lift `EL_ATTRIBUTES` or `H_ATTRIBUTES` by name.

5. **`openAddReturn` (app.js:2488-2503) and `openNewHousehold` (app.js:2505-2522) are the same opener.**
   - Same steps: `loadForms` try/catch, set `addingTo`, null `selectedForm`, `hideCreateNote`, set the title, `renderFormGrid`, `showStep`, `openDialog("modal")`.
   - They differ only by `hh` being given or not.
   - Fold into `openReturnDialog(hh)`. About 10 lines.
   - Tests: test_shell and test_single_source name both.

6. **One localStorage helper pair (about 20 lines).**
   - The same try/catch read-or-default and write-or-ignore appears four times:
     - pages.js:885-913: order read and save.
     - pages.js:916-958: widths read and save.
     - pages.js:970-978: widths reset.
     - shell.js:636-646 and 671-679: Under Construction read and toggle.
   - pilot.js:33-47 (`readStored`/`writeStored`) is the same again, but pilot.js promises (P7) to call no app.js function, so leave it or accept that exception.
   - Fold into `storeRead(key)` / `storeWrite(key, value|null)`.
   - Tests: test_shell lifts `pagesStoredOrder`, `pagesStoredWidths`, `pagesSaveOrder`, `pagesSaveWidths` and `shellReadSoon` by name; keep those names as thin callers or update the tests.

7. **`sheetAfter` (sheet.js:183-186) and `sheetDraftsAfter` (sheet.js:310-313) differ only in the match.**
   - `sheetAfter` matches `ret` and `handle`; `sheetDraftsAfter` matches `ret` only.
   - One function can decide by `now.kind`. About 4 lines. test_shell names both.

8. **The feed and related-household pickers in the household editor share one shape.**
   - `renderEditorRelated` 1576 and `addEditorRelated` 1590; `renderEditorFeeds` 1601 and `addEditorFeed` 1630; plus the two copy-paste remove delegates at app.js:3708-3720.
   - The shape: a list of items with Remove, a `<select>` of what is not taken (or "—"), and Add enabled only when there is a choice.
   - One `pickList({listId, pickId, addId, items, labelOf, choices})` helper. About 15 lines.
   - Feeds keep their warning line.

9. **Redraw-and-refocus in pages.js.**
   - `pagesPick` 1041, `pagesOrderBy` 781 and `pagesTurn` 1027 each do: change state, `delete pagesPageAt[list]`, `pagesDraw(shellRoute, $("page"))`, `querySelector(sel)?.focus()`.
   - One `pagesRedraw(list, selector)`. About 6 lines.

10. **The pressed toggle button in pages.js.**
    - `pagesTabs`' `tab` (1053), `pagesSwitch`' `option` (1337) and `pagesReasonCards`' `card` (1202) each build a button with `aria-pressed` and `data-pick` that calls `pagesPick`.
    - One `pagesPickButton(list, className, pressed, pick, set, ...children)`. About 6 lines.

11. **Floating UI placement.**
    - tooltip.js:59-80 `placeTip` and pages.js:410-416 in `pagesShowPanel` both call `computePosition` with fixed strategy and the same offset/flip/shift.
    - One `floatAt(anchor, node, placement, onHidden)`. About 5 lines.

12. **Labelled input boxes in app.js.**
    - `keywordBox` 728, `noteBox` 738, the spelling box in `teachSpelling` 822-824 and the issuer box in `issuerBox` 1015-1017 all build `label.field > span + input.<class>`.
    - One `labelledInput(boxClass, words, inputClass)`. About 8 lines.
    - Tests: tests/test_single_source.py names `keywordBox` and `noteBox`.

13. **pilot.js and tour.js each define the same `fill` and `make`.**
    - pilot.js:111-122 and tour.js:35-46 are character for character the same.
    - Expose them once from pilot.js; tour.js already uses `PilotRecord` from it. About 12 lines.

14. **main.js `learn()` (main.js:235-276): ten repeated lines of the form `if (said && typeof said.X === "string") X = said.X;`.**
    - Keep the shell's sentences in one object (`shellSays = {killed, killed_write, ...}`) and copy known string keys in a loop. About 10 lines.
    - Tests: tests/test_single_source.py:3073-3078 and 4283 read `let killedWrite = ...` and the like by variable name; update them to read the object's defaults.

15. **`shellAdoptEarly` (shell.js:319-326) repeats `call()`'s reply handling (app.js:167-179).**
    - The repeated part: warnings become notices, `error` throws `TrackerError`.
    - Factor `takeReply(result, args, payload, opts)` out of `call()` and use it in both. About 4 lines.

16. **Small single-use wrappers and duplicates (about 15 lines together).**
    - `renderLock(state)` (app.js:1671) is just `showLock(state.lock)`. Tests name it.
    - `showEveryFold()` (app.js:3215) is just `setAdvanced(true)`. Tests name it.
    - `pagesStepWords` (pages.js:537) rebuilds a four-key object to index into; `screenWords().steps[step.kind]` does the same.
    - `SIDE_KEYS` (shell.js:47) is a copy of `FIRM_LEVELS` (shell.js:46).
    - `SCREEN_KEYS` (shell.js:48) repeats the `needs-review` → `needs_review` map that is also in `pagesListOf` (pages.js:733).
    - The `wp-add` and `ep-add` handlers (app.js:3814-3821) differ only by array and id: one loop.
    - `openSafeguards`, `openAbout` and `openMisfits` (app.js:3665-3700) share title, close and `openDialog`.
    - The four "hidden Loading word + `shellSkeleton(3)`" calls (app.js:480, 2099; sheet.js:63, 201) can be one `shellWaiting(n)`.

### BLOAT

1. **style.css is mostly overridden by pilot-ui.css (about 140 lines).**
   - pilot-ui.css re-skins by repeating style.css's selectors (its own header says so). Across the four sheets, 91 selectors are defined in more than one file: 88 are style.css vs pilot-ui.css, and 3 are pilot-ui.css vs shell.css (`input/select/textarea`, `#notices`, `.modal`).
   - Measured per (media context, selector, property), with later file and `!important` respected:
     - 200 of style.css's 570 declarations are overridden.
     - 24 rules are overridden whole, including:
       - style.css:5 `:root` (every token)
       - :53-55 `.btn:hover/:focus-visible/:disabled`
       - :73-74, 90-94, 571: all banner and notice colours
       - :112 `.card-head h3`
       - :160 `.rem-stage:hover`
       - :265 `.modal h3`
       - :308 `.tmpl-item:hover`
       - :369 `.side`
       - :447-452 `.form-card` hover/focus
       - :490-491 `.wiz-back` hover/focus
       - :533 `.prior-item:hover`
       - :570 `.btn-small`
   - 138 declaration lines (plus 4 brace lines) can go with no visual change.
   - The cleaner end state merges style.css into pilot-ui.css's token system. That would also retire pilot-ui.css:113-128's "kept names" alias block, which exists only so style.css's old names resolve. Pilot README rule 1 ("small, named differences") was written when style.css was the upstream file; that reason no longer holds now that shell.css carries the app.
   - Tests: test_pilot_ui, test_shell, test_shell_menu, test_single_source and test_tour read these sheets.

2. **22 `typeof fn === "function"` guards and the dead fallback branches behind them (about 20 lines).**
   - index.html loads every renderer script, synchronously and in a fixed order (index.html:572-581), and the guarded calls all run after load. So none of these can be false:
     - app.js:1306
     - pages.js:576, 579, 553 (`!==`), 1751 (it guards a function in the same file)
     - shell.js:514, 574, 591, 953, 1027, 1047, 1055, 1268-1271, 1286, 1324, 1329, 1341, 1342, 1397, 1400
   - Also always true or always present: app.js:591 `typeof sheetNow`; shell.js:620 `typeof pagesClientType`; app.js:2159 `if (window.tracker.onAfterInstallDone)`; shell.js:1402 `if (window.tracker.menu)`. preload.js always exposes both.
   - Their `else unanswered(...)` branches (pages.js:577, 580; shell.js:1268-1271; app.js:1306) are unreachable.
   - shell.js's header comment (lines 25-33, "What this file calls, if it exists") documents the guards and should go with them.
   - Caveats:
     - tests/test_shell.py:3410 pins one guard string verbatim.
     - Several tests lift single functions into Node with stubs and may lean on a guard; run test_shell and test_shell_menu after removing them.
     - `unanswered` itself stays: `openRoll`, `pagesRunLink` and `pagesCheckThen` use it for real.

3. **Stale comments.**
   - app.js:3495 "the four dialogs": the `DIALOGS` registry holds 11.
   - app.js:3657 and index.html:522 "the four dialogs the menu and the notices open": they name three (Safeguards, About, Misfits).

4. **Duplicated tables and formats.**
   - Date and time display options are written three times:
     - `{month:"short", day:"numeric"}` at pages.js:126 and shell.js:724.
     - `{hour:"numeric", minute:"2-digit"}` at pages.js:134 and shell.js:723.
     - The year-long form in pilot.js:223 `signedDay`.
     - Have shell.js call `pagesDay`/`pagesTime`-style helpers that take a `Date`.
   - pages.js:1528's group → tone map repeats what `PAGES_SECTIONS` (pages.js:115) already says.
   - `DEFAULT_MENU_WORDS` (main.js:606-654) intentionally copies tracker.api's MENU for the first frame and is pinned by tests; leave it.

5. **Checked and clean.**
   - No `console.*`, `debugger`, commented-out code or TODO/FIXME anywhere in main.js, preload.js or app/renderer.
   - No inline `style=` or `on*=` in index.html.
   - Comment volume is high: app.js 896 of 3,890 lines, main.js 274 of 934, pages.js 412 of 1,984, shell.js 260 of 1,402. The repo's conventions ask for reasoning in comments, so this is not counted as removable. Many comments are decision and review citations ("the review's S4", "P213") that a trim pass could shorten.

### The pilot files: live

- **pilot.js is the running pilot UI.**
  - It draws the badge into `#side-foot` (pilot.js:316-332) and runs `PilotTerms.gate()` at load.
  - The shell's menu calls it: `MENU_ANSWERS.terms → PilotTerms.show()` (shell.js:1267).
  - Its own header records what shell.js superseded: "The Tour button is gone: Help > Take the tour starts the tour". The surviving code is the badge and the terms card.
- **tour.js is live.**
  - `MENU_ANSWERS.tour → PilotTour.start()` (shell.js:1266), and terms acceptance starts it on first run (pilot.js:295).
- **pilot-content.js is live.**
  - app.js:3681 About reads `PILOT.edition.version`.
  - `tracker/api.py` validates terms versions against it (around line 5653).
  - `pilot/Build Pilot Installer.bat`:40 reads the version from it with node.
  - tests/test_pilot.py and tests/test_tour.py parse its JSON.
- **pilot-ui.css is the app's token and design layer.**
  - shell.css (228 `var(--sp/fs/bg-*)` uses) and pilot-style.css read its tokens.
  - main.js:809-827 reads `--window-light`/`--window-dark` from it for the first paint.
  - tests/test_pilot_ui.py polices it.
- **pilot-style.css is live.** It styles the badge, terms and tour, and has no dead class or id selector.
- **The docs confirm it.**
  - pilot/README.md: this repository *is* the pilot edition, and the pilot code lives in these files by rule.
  - pilot/SPEC-shell.md ("Pilot 0.2 - the app shell") builds the shell on top of the pilot rather than replacing it.
  - Nothing here is superseded except the removed Tour button and the old card-based screen, whose CSS is listed under DEAD 1-3.
