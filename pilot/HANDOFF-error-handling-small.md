# HANDOFF - SPEC-error-handling-small (E2 to E7, R1 to R5)

Built on `claude/admiring-goodall-vhomni` over `f2c0631` (the other lane's
document-gate commit landed while this ran; nothing of its files was touched).
Not committed, not pushed. `pilot/DECISIONS.md` untouched (P297-P300 rows are
the landing session's).

## 1. What was built

**R1 - E2, a rollover says when it could not look** (`tracker/rollover.py`)
- `_unfiled_last_year` returns `(lines, note)`. On any failure to read the
  index it keeps the exception (`errors.keep("rollover: last year's unfiled
  documents", exc, name=prior_dir.name)`) and returns `([], UNFILED_LAST_YEAR_UNREAD
  .format(problem=errors.said(exc, (FilingError, ManifestError, LedgerError, StoreError))))`.
- `RolloverReport.unfiled_last_year_unread: str = ""` holds the note.
- The trap: `report.warnings` is *assigned* in three places, not two. The
  SPEC names `_make_one` (rollover.py) and the CLI (`result.warnings = ...`);
  `tracker/api.py` `_cmd_rollover` has a third (`report.warnings = list(create_engagement(...))`),
  and that one feeds the `rollover` reply the page draws. All three now call
  `RolloverReport.carry_warnings(create_engagement(...))`, which sets
  `warnings` and then appends the note, so the note is last and cannot be
  overwritten by the next assignment (see section 5, "done differently").
- No page change: the reply already sends `warnings`, the page already draws them.

**R2 - E3 and E4, nothing swallowed without a log line**
- `api._undo_create`: `errors.keep("api: forgetting a failed return", exc, name=engagement.name)`.
- `rollover._unmake`: `errors.keep("rollover: forgetting a failed return", exc, name=target.name)`.
- `filer._details_of`: `errors.keep("filer: the return's details", exc, name=engagement_dir.name)`, still returns `None`.

**R3 - E5, a database that cannot be used is said as itself**
- `errors.error_code(exc)`: the code alone (`SAYS_ITS_CODE` class code, else the
  errno name, else the class name). Both `error_class` and `error_code` read
  the code through one private helper `errors._code_of` (so they cannot
  disagree); `error_class`'s output is byte-identical to before.
- `api.STORE_UNAVAILABLE` and `api.RECORD_NOT_WRITTEN` exactly as the SPEC words
  them; `_failure_of` keeps `kind = "failed"` (Retry stays).
- `docs/runbook.md`: see section 5 - an insertion, not the replacement the SPEC asked for.

**R4 - E6, the data home must be a folder or makeable** (`tracker/settings.py`)
- `DATA_HOME_NOT_A_FOLDER` and `_file_in_the_way(path)` (nearest existing part of the
  path; returns it when it is not a folder). Called in `resolve_data_home` after
  `answer` is chosen and before the program/synced/drive checks, for every branch.

**R5 - E7, the vocabulary sends only what something reads** (`tracker/api.py` `_vocab`)
- Dropped 14 keys (table in section 3), kept 5. Their now-unused imports in api.py
  were removed (ruff). The vocabulary comments over `not_asked_label` and
  `ask_the_client` were trimmed to match.

## 2. Each new test, before and after

"Before" is the new test run against the unchanged code (the test inserted
first). "After" is the finished build.

| Test | Before | After |
|---|---|---|
| test_rollover `test_a_rollover_that_could_not_read_last_years_index_still_rolls_and_says_so` | ImportError `UNFILED_LAST_YEAR_UNREAD` | pass |
| test_rollover `test_a_prior_year_whose_index_reads_adds_no_note` | AttributeError `unfiled_last_year_unread` | pass |
| test_rollover `test_the_note_about_an_unread_index_is_the_last_warning_of_each_rolled_return` (roll_household, 3 returns, the `_make_one` assignment) | ImportError | pass |
| test_rollover `test_a_household_rollover_that_reads_every_index_carries_no_such_note` | ImportError | pass |
| test_rollover `test_a_failed_rollover_that_cannot_forget_its_store_row_keeps_why_on_the_log` | AssertionError: log empty | pass |
| test_api `test_a_rollover_that_could_not_read_last_years_index_says_so_in_its_reply` (the `rollover` command, the api assignment) | ImportError | pass |
| test_api `test_a_failed_create_that_cannot_forget_its_store_row_still_cleans_up_and_logs_it` | AssertionError: log empty | pass |
| test_api `test_a_database_that_cannot_be_used_is_said_as_itself_with_its_code_and_keeps_retry` x2 (StoreUnavailable, RecordNotWritten) | AttributeError `api.STORE_UNAVAILABLE` / `RECORD_NOT_WRITTEN` | pass |
| test_api `test_a_broken_journal_is_said_in_the_firms_sentence_...` (its old-wording loop for the two classes now pins the new sentences) | AttributeError `api.RECORD_NOT_WRITTEN` | pass |
| test_filer `test_details_that_cannot_be_read_are_none_and_the_failure_is_kept_on_the_log` | AssertionError: log empty | pass |
| test_settings `test_a_data_home_override_naming_a_file_or_lying_under_one_is_refused_by_name` | AttributeError `DATA_HOME_NOT_A_FOLDER` | pass |
| test_settings `test_a_data_home_that_can_still_be_made_is_answered` | passed (a guard that the change does not over-refuse) | pass |
| test_errors `test_an_errors_code_alone_is_what_a_sentence_of_its_own_names` | AttributeError `errors.error_code` | pass |
| test_errors `test_a_code_alone_never_carries_a_message_or_a_third_partys_code` | AttributeError | pass |

Existing tests changed: `tests/test_errors.py` `ERRNO_NAMED_ON_PURPOSE` gains
`("errors.py", "_code_of")` (the one-definition test scans errors.py for a
function that reads an errno's name; the SPEC says errors.py is not scanned,
it is, for that check - the words-into-a-sink scan is the one that skips it).
`tests/test_api.py`: the 14 dropped keys' value pins were removed, and
`_TITLE_EXEMPT_BRANCHES` lost `example_root`, `default_extensions`,
`unscanned_key`, `not_asked_key`, `unknown_year_label`, `expected_pattern`.
All test_api edits were exact insertions/replacements (the file was never rewritten).

## 3. R5 evidence (one row per key)

Greps: `grep -rIF "<key>" app --exclude-dir=node_modules` (every file under app/,
any form: `vocab.<key>`, `words.<key>`, `["<key>"]`, destructuring, comments,
camelCase not tried separately but `grep -i` for `overrideLabel`, `notAskedKey`,
`unscannedKey`, `exampleRoot`, `periodPattern` etc. found only the unrelated
`overrideLabel()` function); `grep -rIF --include='*.py' "<key>" tracker`
minus `tracker/api.py`; same under `tests/` (counts are lines, taken after the
build, so test lines I removed are not counted). Dynamic access to the vocabulary
was also looked for: `vocab[`, `words[`, `Object.keys/entries/values(vocab)`, spread -
the only hits are `Object.values(vocab.overrides)` (a nested map) and `words[key]`
over nested sub-objects (`screenWords().paging`, `menuWords`); no top-level key
is reached dynamically. `pilot/harness`, `pilot/wintest`, `app/main.js`,
`app/preload.js` also hold none of the 19.

| Key | app/ | tracker/ minus api | tests/ (after) | Decision |
|---|---|---|---|---|
| statuses | 3 (comments only: app.js:35 names it in a comment, shell.js:372 uses the plain word) | 84 (`Status`...) | 172 | KEPT: bare-name hits exist under app/. No `vocab.statuses` read found, so a later decision may drop it |
| view | 368 (the word, `reply.view`, `held.view`) | 679 | 2209 | KEPT: hits; no `vocab.view` read found (the page draws `reply.view`, a different thing) |
| progress | 36 (`m.progress`, `letter.progress`) | 64 | 124 | KEPT: hits; no `vocab.progress` read found (`m.progress` is a progress line's payload) |
| evidence | 2 (comments, app.js:996, 1080) | 237 | 160 | KEPT: hits; no `vocab.evidence` read found |
| period_pattern | 0 | 0 | 0 | DROPPED |
| example_root | 0 | 0 | 2 (test_settings/test_single_source mention the *constant* `EXAMPLE_ROOT`, not the key) | DROPPED (`settings.EXAMPLE_ROOT` itself stays: tests and the README check use it) |
| default_extensions | 0 | 0 | 0 | DROPPED (value pin removed from `test_api`) |
| expected_pattern | 0 | 0 | 0 | DROPPED |
| year_note | 0 | 0 | 1 (`test_shell` asserts the key is NOT in app.js: "the dialogs' help lines are cut") | DROPPED; `pilot/wording-shell.tsv` row already says "cut" |
| keyword_default_note | 0 | 0 | 0 | DROPPED |
| extension_default_note | 0 | 0 | 0 | DROPPED; wording-shell.tsv says "cut ... no renderer use" |
| candidate_separator | 0 | 0 | 0 | DROPPED |
| unknown_year_label | 0 | 0 | 0 | DROPPED |
| origin_prior | 0 | 0 | 0 | DROPPED (`origin_new` and `origin_not_applicable` are read and stay) |
| override_labels | 0 | 0 | 2 (test_api only: a length pin that I left, see below; `test_no_word_the_window_draws_says_client`) | **KEPT, by doubt**: zero hits, but the Title Case labels (P77, approved wording) were meant for the editor's reason list, and the page draws the stored words (`vocab.override_reasons`, app.js:2956) instead. Dropping it would silently discard approved wording that the page was never wired to show. A person should decide: wire it, or drop it |
| not_asked_key | 0 | 0 | 0 | DROPPED (the chip class comes from `vocab.labels[...].key`) |
| unscanned_key | 0 | 0 | 1 (`test_single_source` `.replace("chip-${vocab.unscanned_key}", "")`, a no-op: the string is not in app.js) | DROPPED; the test line is harmless and in a file this build does not own |
| unscanned_label | 0 | 0 | 0 | DROPPED |
| ask_the_client_note | 0 | 0 | 2 (`test_shell` asserts it is NOT in app.js; a `test_single_source` JS fixture assigns it to a stub `vocab`, which the code under test never reads) | DROPPED |

The SPEC's note that `test_shell` ~1892 "lists `year_note` and
`ask_the_client_note` among keys the page draws" is the reverse: that test
asserts those keys are *absent* from app.js. Same for the
`test_single_source` ~1015 exclusion, which is a no-op. Neither contradicts the drop.

Dropped: **14** (`period_pattern`, `example_root`, `default_extensions`,
`expected_pattern`, `year_note`, `keyword_default_note`,
`extension_default_note`, `candidate_separator`, `unknown_year_label`,
`origin_prior`, `not_asked_key`, `unscanned_key`, `unscanned_label`,
`ask_the_client_note`). Kept: 5 (`statuses`, `view`, `progress`, `evidence` by
the bare-name rule; `override_labels` by doubt).

Left behind, outside this build's file list (reviewer/landing session to judge):
- `tracker/templates.py` `YEAR_NOTE`, `EXTENSION_DEFAULT_NOTE`, `KEYWORD_DEFAULT_NOTE`
  are now module-level names nothing uses (their only reader was `_vocab`). The
  other lane owns templates.py, so they were not touched.
- `api.ASK_THE_CLIENT_NOTE` stays because `tests/test_single_source.py` (not mine to
  edit) and `test_api` use it to assert the renderer does not type the cut sentence;
  a comment on it says so.
- `tests/test_single_source.py` `.replace("chip-${vocab.unscanned_key}", "")` and the
  `ask_the_client_note` JS fixture are stale but harmless.
- `pilot/wording-shell.tsv` rows for the dropped keys already read "cut" or are
  keyed by the constant; not edited.

## 4. The gate

Interpreter: the scratchpad venv, Python 3.13.16 (pytest 9.1.1, ruff). Only one
interpreter with the test dependencies exists here, so the "two Python versions"
were not both run; the changed files do compile under `python3.11 -m py_compile`
(the floor is 3.11), which is a syntax check only.

Dead code first (ruff F401 after the key drops: 11 unused imports in api.py and
one in tests/test_api.py, removed; nothing commented out). Then each file its own process in parallel:

| File | Result |
|---|---|
| test_rollover | 63 passed, **1 failed, 1 error**: `test_the_client_tree_is_byte_identical_after_a_roll_forward_whose_record_names_a_path` - **pre-existing, not from this build**: it fails identically on a clean `git archive` of `fce8c1e` (the base I started from), and it fails in the current tree (`f2c0631` + this build). It was not run on a clean `f2c0631`. The message it expects, "not one folder name", comes from the store's gate, which is what the other lane's commit touches, so the reviewer may want to run it on a clean `f2c0631` before attributing it. |
| test_api | 522 passed |
| test_filer | 408 passed, 6 skipped |
| test_settings | 86 passed, 1 skipped |
| test_shell | 326 passed |
| test_errors | 85 passed |
| test_tripwire | 23 passed |
| test_layers | 31 passed |
| test_single_source | 218 passed (after restoring `ASK_THE_CLIENT_NOTE`; a first run failed on `api_module.ASK_THE_CLIENT_NOTE` when I had deleted it) |
| test_repo_map | 82 passed (after `update`) |

`python -m ruff check .`: all checks passed. `python tools/repo_map.py update`
then `check`: "Map is current (301 nodes)". The other lane's commit landed
mid-build; `update` was run once, after it, and `check` passed first time, so
no retry was needed.

## 5. Done differently from the SPEC, and why

1. **Three `warnings` assignments, not two, and one method.** `api.py`
   `_cmd_rollover` assigns `report.warnings` too, and the `rollover` reply (the
   page's single-return Roll Forward) reads it. Rather than three copies of
   "append after the assignment", `RolloverReport.carry_warnings(said)` sets the
   warnings and appends the note. Same behaviour the SPEC asks for.
2. **`errors._code_of` helper.** `error_class` and `error_code` read the code once.
   `tests/test_errors.py` `test_the_class_an_error_is_said_as_is_defined_once`
   does scan errors.py for a function that reads an errno's name (the SPEC says
   errors.py is not scanned; only the words-into-a-sink test skips it), so the
   helper is named in `ERRNO_NAMED_ON_PURPOSE`. `error_code` falls back to
   `error_class(exc, with_code=False)` so it does not spell a class inline.
3. **Runbook: an insertion, not a replacement.** The clause the SPEC names
   ("by its kind and code alone - *StoreUnavailable (SQLITE_BUSY)* ...") sits in
   the paragraph on a *page line / a household that stopped*, which is the pass's
   wording and is unchanged (it keeps the class-and-code form). The paragraph
   never describes the dialog. Replacing it would make the runbook false, so
   the clause is kept and one sentence is added after "...which can name a
   client's folder.": the window says the two faults in words of their own with
   the code, keeps Retry, and the details are in the error log.
4. **`override_labels` kept** (section 3).
5. **The test the SPEC says to "keep" (it is about `error_class`)** is the
   `for raised, kind` loop inside `test_a_broken_journal_is_said_...`; it asserted
   the old FAILED wording through `said_by_class`, which is the behaviour R3
   changes, so its assertion now pins the new sentences. Nothing tests
   `error_class` less; `tests/test_errors.py`'s own `error_class` tests are untouched.
6. **Curated map text** (`docs/repo-map.curated.json`): three sentences added
   (rollover's unread-index warning, settings' file-in-the-way refusal, errors'
   `error_code`), because the role text for those nodes would otherwise be
   incomplete; `update` then regenerated the map.

## 6. What the reviewer needs

- Commit boundary: `git show f2c0631` (the other lane's commit) contains none of
  this build's hunks (checked: zero matches for `UNFILED_LAST_YEAR_UNREAD`,
  `STORE_UNAVAILABLE`, `error_code`, `DATA_HOME_NOT_A_FOLDER`, `carry_warnings`,
  `forgetting a failed return` in its diff of the six code/test files), so P297-P300's
  code is all in the working tree, uncommitted.
- One file is staged: `pilot/HANDOFF-error-handling-small.md` (`git add` of that
  path only), because `repo_map.py check` and `test_repo_map` refuse an untracked source file.

- SPEC `pilot/SPEC-error-handling-small.md`; this handoff; the diff of
  `tracker/{rollover,api,filer,settings,errors}.py`, `docs/runbook.md`,
  `docs/repo-map.curated.json`, and the five test files above.
- Re-grep the page for each of the 14 dropped keys (table in section 3), and
  decide on `override_labels` and on the four kept-by-rule keys.
- Check the third `warnings` assignment (`api._cmd_rollover`) and the household
  path (`roll_household` -> `_make_one`) both order the note last.
- The pre-existing `test_rollover` failure noted in section 4 is for the other lane / the landing session.
- Not verified: the Windows-only paths (no `windows` label needed; nothing here touches
  the engagement lock, the atomic replace or path handling beyond `Path.exists/is_dir`).
