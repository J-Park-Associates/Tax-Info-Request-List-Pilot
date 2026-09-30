# SPEC-rename build notes (builder, 2026-09-30)

Branch `claude/rename-0.3`, worktree `C:\Users\User\pl\rename`. Built from
`pilot/SPEC-rename.md` in its two commits. Nothing pushed.

## Commits

- **Commit A** `e0ffc4c` - the name, version 0.3, the installer, the
  after-install carry-over, their tests and documents.
- **Commit B** (the commit holding this file) - "the tracker" becomes "the app"
  in the engine's sentences and the person-facing documents, and the two gate
  tests.

Owner question Q1 is built on its recommendation (a): the terms bullet names
Tax Document Console and `terms.version` stays 1.

## Files changed

Commit A:
- `app/package.json` - productName "Tax Document Console"; `config.userDataName`
  "Tax Document Tracker Pilot" (R4).
- `app/main.js` - `app.setPath("userData", ...)` from `config.userDataName`
  before anything asks for a path and before the single-instance lock; the
  three default screen words say "App"; the fallback-log comment.
- `app/renderer/pilot-content.js` - version 0.3; the terms bullet (Q1 (a)).
- `tracker/settings.py` - `EARLIER_PRODUCT_NAME`, `earlier_settings_path()`.
- `tracker/after_install.py` - the carry-over constants,
  `_carry_over_settings()`, `_replace_earlier_task()`, wired into `_run()`;
  `AfterInstall.carried`; the record's `"carried"`; `read_record()` reads a
  record without it as `[]`; module docstring and CLI description.
- `tracker/api.py` - side panel product is `product_name()`; SHELL_NO_REPLY,
  SHELL_COULD_NOT_START, SHELL_NO_LOG, MISFITS_HEADING, the override label, and
  the "Folders the App Leaves Alone" sentence.
- `tracker/runner.py` - STATUS_MISFITS_HEADING. `tracker/ocr.py` - C:\JPA App.
- `pilot/installer/setup.iss` - as SPEC 6.1 (name, file, folder,
  `UsePreviousGroup=no`, `[InstallDelete]`, both uninstall task lines, the R2
  comment; AppId unchanged).
- `pilot/Build Pilot Installer.bat` - installer file name.
- `pilot/wintest/run_checks.ps1`, `uninstall_checks.ps1` - new names,
  `$EarlierName`; the program folder found under the new name, then the
  earlier one; uninstall checks both task names.
- `pilot/wintest/PROMPT-shell.md` (task name, fallback folder, steps 18-22 =
  SPEC section 9), `RESULTS-TEMPLATE.md` (0.3, task name).
- `pilot/harness/interact.mjs` (About reads the version from
  pilot-content.js), `pilot/harness/stub.js` (C:\JPA App).
- Documents: `pilot/Tester Guide.md` (name, file, uninstall entry, the upgrade
  line), `pilot/RELEASE.md` (0.3, tag pilot-0.3, no 0.2 tag, names),
  `pilot/README.md`, `README.md` line 1, `docs/ROADMAP.md` line 1,
  `docs/runbook.md` (fallback log folder, "App Failed", C:\JPA App, new
  paragraph "After the rename (P155)" quoting every carry-over sentence).
- `docs/repo-map.curated.json` (main.js, the error-log artifact, settings,
  api, after_install notes), then `tools/repo_map.py update`.
- Tests: `test_after_install.py` (16 new tests; the schtasks fakes keep the
  earlier name's task apart; the step's lines are read past the two
  carry-over sentences), `test_settings.py` (3 new), `test_pilot_installer.py`
  (6 new; the "no InstallDelete" assertion now scopes to the earlier name's
  files), `test_single_source.py` (the side panel, the userData folder, the
  0.3 version, the runbook's carry-over quotes; App Failed; the new fallback
  folder), `test_pilot.py` (the terms name the product exactly once),
  `test_shell.py`, `test_shell_menu.py`, `test_api.py` (the schtasks fake
  ignores the earlier name's query), `test_ocr.py`.

Commit B:
- Engine constants, "the tracker" -> "the app": `after_install.py`
  (FINDINGS_WAIT), `api.py` (FAILED, MEMBERS_HELP, SHARING_NOTE, ROUTING_HELP,
  HOUSEHOLD_NOT_OURS), `checkpoint.py`, `door.py`, `errors.py` (WHERE_KEPT;
  the file name stays), `layout.py`, `ledger.py`, `reasons.py`,
  `registry.py`, `runner.py`, `settings.py`, `store.py`, `scheduling.py`
  (command-line help; "the tracker package" kept). No function changed.
- `app/main.js` - "That path is not one the app reported; nothing was
  opened." (found by the widened gate; not in SPEC 4.5's list).
- Documents: `docs/runbook.md` (82), `README.md` (5), `docs/workflow.md` (3),
  `PRODUCT.md` (1). pilot/README, Tester Guide and RELEASE had none left
  after Commit A.
- `pilot/harness/stub.js` - its copies of two changed engine sentences.
- Tests quoting the changed sentences: `test_after_install.py`,
  `test_api.py`, `test_door.py`, `test_ledger.py`, `test_registry.py`,
  `test_scanner.py` (edited, so run too), `test_shell_menu.py`, `test_store.py`,
  `test_single_source.py` (the runbook heading "A document the app did not
  file", and the two gate tests
  `test_no_sentence_the_app_shows_calls_it_the_tracker`,
  `test_no_person_facing_document_calls_the_program_the_tracker`).
- Map refreshed; this file.

## Left undone, and why

- **`.claude/settings.json`** (SPEC 4.1: eight deny rules for the new
  fallback-log folder `%LOCALAPPDATA%\Tax Document Console\error.log`) and the
  test **`test_the_fallback_log_rules_deny_the_current_and_the_earlier_folder`**:
  excluded by the orchestrator - permission configuration waits for Jason.
  Consequence: on Windows the new fallback log (which can name a client) is
  not in the deny list until that lands. To keep the existing deny-list test
  true meanwhile, `tests/test_single_source.py::_fallback_log_rules()` now
  names the earlier product's folders (what the list holds today), with a
  docstring saying the new folder's rules wait for Jason. When the rules are
  added, that helper covers both names and the named test is added.
- **`pilot/harness/interact.mjs`** was not run: Playwright is not installed on
  this PC. `node --check` passes, and the version it reads parses to "0.3".
- The Windows hands-on steps (SPEC section 9) are for the 0.3 Windows check.
- The gate's allowlist holds one name, `settings.EARLIER_PRODUCT_NAME` (a
  name, not a sentence). The gate also reads every spaced string literal in
  `app/main.js`, which is how the one sentence above was found.

## Test results (each file its own process, four at a time)

Python 3.14.3 (`C:\Users\User\pl\order\.venv`) and 3.11.15
(`...\Tax-Info-Request-List-Pilot-main\.venv311`), on the final tree:

| File | 3.14 | 3.11 |
|---|---|---|
| test_api.py | 428 passed | 428 passed |
| test_store.py | 179 passed | 179 passed |
| test_runner.py | 194 passed | 194 passed |
| test_after_install.py | 89 passed, 3 skipped | 89 passed, 3 skipped |
| test_single_source.py | 178 passed | 178 passed |
| test_shell.py | 152 passed | 152 passed |
| test_shell_menu.py | 30 passed, 3 skipped | 30 passed, 3 skipped |
| test_settings.py | 58 passed | 58 passed |
| test_scheduling.py | 114 passed | 114 passed |
| test_ocr.py | 32 passed | 32 passed |
| test_pilot.py | 19 passed | 19 passed |
| test_pilot_installer.py | 18 passed | 18 passed |
| test_pilot_ui.py | 11 passed | 11 passed |
| test_layers.py | 29 passed | 29 passed |
| test_repo_map.py | 80 passed | 80 passed |
| test_errors.py | 83 passed | 83 passed |
| test_tripwire.py | 19 passed | 19 passed |
| test_checkpoint.py | 14 passed | 14 passed |
| test_door.py | 5 passed | 5 passed |
| test_layout.py | 48 passed | 48 passed |
| test_ledger.py | 58 passed | 58 passed |
| test_reasons.py | 58 passed | 58 passed |
| test_registry.py | 35 passed | 35 passed |
| test_scanner.py | 41 passed | 41 passed |

The skips are the existing ones (a symbolic link this PC cannot make, and the
like); none is new.

Quick checks on the final tree: `python -m ruff check .` - All checks passed;
`python tools/repo_map.py check` - Map is current; `python tools/vocab_report.py
check` - Report is current (no catalog text changed); `node --check` on
`app/main.js`, `pilot/harness/stub.js`, `pilot/harness/interact.mjs` - clean.
Dead code: none left in the changed files (ruff, and a read of each change).

## For the reviewer

- The carry-over is `tracker/after_install.py` `_carry_over_settings` and
  `_replace_earlier_task`, and their place in `_run`.
- `tests/test_after_install.py`'s `windows` fixture and `task_scheduler`
  helper, and `tests/test_api.py`'s `_on_the_office_computer`, keep the
  earlier name's schtasks commands apart from this computer's own task, so
  the existing assertions on "our" task are unchanged.

## Commit C (SPEC-rename section 12: P188 sign-off, P189 log rules)

What was built:
- `app/renderer/pilot.js`: the terms card has a "Type Your Full Name to
  Sign" box (the app's own `.field` look) below the checkbox and above the
  buttons. "Sign and Accept" stays disabled until the box is ticked and the
  name, trimmed, is not blank. The click sends the trimmed name with the
  acceptance (`PilotRecord.acceptTerms(version, signedBy)` sends
  `signed_by`). Help, Terms reads the record and shows "Signed by {name} on
  {date}" as text, only when a name and a date are held. The date comes from
  `pagesDay` in pages.js (the app's existing short date).
- `app/renderer/pilot-content.js`: `terms.sign` and `terms.signed` are new,
  and `terms.accept` is now "Sign and Accept". The terms version stays 1.
- `tracker/api.py` pilot-record: `signed_by` is taken only with `terms`. It
  must be text, not blank once trimmed, and at most `SIGNED_BY_LONGEST`
  (200) characters, or the whole request is refused with the widened
  `PILOT_RECORD_REFUSED`. It is saved trimmed as `terms_signed_by`. An
  acceptance without a name drops any earlier name, because a name belongs
  to the acceptance it signed. The reply now also carries `terms_signed_by`
  and `terms_accepted_at` ("" when none).
- `.claude/settings.json` (P189, approved): the eight `Tax Document Console`
  error.log Read/Edit rules come after the eight earlier ones. Nothing else
  in the file changed. `tests/test_single_source.py` `_fallback_log_rules()`
  names both folders again, and
  `test_the_fallback_log_rules_deny_the_current_and_the_earlier_folder`
  pins them.
- Docs: `pilot/Tester Guide.md` section 4 step 1; `pilot/RELEASE.md`'s
  first-launch step, which named "I agree. Continue."; one
  `pilot/wording-shell.tsv` row for `terms.sign`. The table lists only
  strings over five words, and the other two new strings are five words or
  fewer, as the old accept words were. `pilot/harness/stub.js` answers the
  engine's new reply shape. The api node's note in
  `docs/repo-map.curated.json`, then `repo_map.py update`.
  `pilot-style.css` has two small rules, `.pilot-terms-name` and
  `.pilot-terms-signed`.

The automatic path at pilot.js 227 (12.1's question). It fires only when the
window's cache already holds this version's acceptance. That acceptance was
made on this PC, before the sign-off or with it, so it stands without a name
(P188 Q2 (a)). It sends no `signed_by`, so it never records a name nobody
typed, and it cannot fire for a record the tester has never accepted. There
is one known edge case: if a signed acceptance's record write failed (it is
logged) and a later launch's level-up writes the acceptance, the name is
lost and no name is invented.

Tests on both interpreters (3.14.3 `C:\Users\User\pl\order\.venv`; 3.11.15
`...\Tax-Info-Request-List-Pilot-main\.venv311`), each file its own process,
four at a time:

| File | 3.14 | 3.11 |
|---|---|---|
| test_pilot.py | 24 passed | 24 passed |
| test_api.py | 437 passed | 437 passed |
| test_single_source.py | 179 passed | 179 passed |
| test_errors.py (refusal wording changed) | 83 passed | 83 passed |
| test_repo_map.py | 80 passed | 80 passed |

test_shell.py and test_tripwire.py were not touched and pin nothing changed
here, so they were not run. Quick checks: ruff reports all checks passed;
`repo_map.py check` reports the map is current (its CRLF warning is about
tracker/runner.py's working copy, not this change); `vocab_report.py check`
reports the report is current; `node --check` is clean on pilot.js,
pilot-content.js and harness/stub.js. Dead code: none in the changed files.

Hands-on Windows steps (section 12.3): type only spaces and see the button
stay greyed; type a name and accept; reopen Help, Terms and see the
signature.
