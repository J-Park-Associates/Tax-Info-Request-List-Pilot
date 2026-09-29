# Shell S1 rebuild 1 (sonnet, default effort)

Branch `claude/sharp-goldberg-jmfynk`, built on `49ddf9f` (the review's
commit). The last commit is the one that adds this file; its sha is in the
final message of the session. Files changed: `tracker/api.py`,
`tests/test_api.py`, `pilot/shell-test-pins.md` (one row), and the regenerated
`docs/repo-map.json` / `docs/repo-map.md`. All nine findings were right; none
was rejected.

## Findings

**F1 - fixed.** `SCREEN["sort"]` now holds `now / stop / firm / locked /
stopping` flat, and `SCREEN["filters"]` holds `work / all`, as 11.4 names
them. `test_the_vocabulary_carries_the_menu_the_screen_and_the_short_words`
asserts the sort key set, `sort.stop == "Stop sorting"` and
`filters == {"work": ..., "all": "All"}`.

**F2 - fixed.** (a) `_firm_row` appends a `files[]` entry for each file moved
by hand (code `file-moved`, empty suggestion), so `files[]`, `returns[].files`
and `totals.files` agree, and `oldest` is taken from that one list. (b) The
bucket in `_cmd_firm` is Need a person when `counts[needs_you]` or the row's
`files` is non-zero (or the row has a problem, F4). New test
`test_firm_lists_every_file_it_counts_and_buckets_a_return_with_only_a_file`:
a return with every request received, one parked file and one moved file lists
both, counts 2, and is `need`, not `complete`.

**F3 - fixed.** Every `files[]` entry carries `"path": str(one.path)` beside
`return`. Pinned in the counts test and in the new test above.

**F4 - fixed.** A return that cannot be read says `api.FIRM_UNREADABLE`
("Could not be read", three words, no "record", no path) on both branches
(a problem found by discovery, and an exception while reading). The detail
goes to the error log through `errors.keep("api: firm", ...)`. A problem row is
counted under `need`. `test_firm_says_an_unreadable_record_as_its_own_row`
asserts the line, that it is five words or fewer with no "record", and the
totals (`need` 1, `complete` 1). **Proposed for Jason's approval:** the words
"Could not be read" (not in the approved TSV, as the review suggested).

**F5 - fixed.** `_firm_draft` reads the way `_return_reminder` does.
`ready` = drafted this draft-week and `reminder.approval_state(...) !=
APPROVED_NOTE`; it is no longer gated on `held`. `held` = the holding rows plus
`reminder.unsorted_in_inbox(engagement)` (a directory listing, no document
read). New test
`test_firm_says_a_reminder_draft_ready_only_until_it_is_approved_and_counts_the_inbox_as_a_hold`
(ready with a hold; not ready once approved; `totals.drafts` 0).

**F6 - fixed.** `shell.page_error` is `PAGE_ERROR` on both branches;
`PAGE_ERROR_NO_LOG` is deleted. `tests/test_api.py` (the no-data-home test)
asserts the short line and that the constant is gone. The one row of
`pilot/shell-test-pins.md` that named the constant is updated. The ROADMAP
decision-186 row still names `PAGE_ERROR_NO_LOG`; it is history and stays as
written. `app/main.js` and the docstring of a `test_single_source` test still
say the stderr is "said in its reply": those are S2's (main.js) and stay for
S2 to change with it.

**F7 - fixed.** `_cmd_add_issuer_and_file` calls `errors.keep("api: add
issuer", exc)` and sets `scan_note = ISSUER_NOT_RESCANNED` with no `.format`.
The existing test's expectation is now the plain constant.

**F8 - fixed.** `test_firm_is_read_only` snapshots the store
(`store.store_path()` and its `-wal`/`-shm` side files) and everything under
`settings.data_home()`, beside the clients root, and compares before and after.

**F9 - fixed.** `_firm_draft`, `FIRM_UNREADABLE`, `_firm_row`, `_cmd_firm` and
`_next_sort` now sit above the `#:` comment, which is back on
`WRITING_COMMANDS`. The comments at `SHELL_NO_LOG` and in `_error_log_said`
now say that with no data folder the details are not kept (11.2).

Dead code: `runner.RECORD_UNREADABLE` is no longer used by `api.py` (still used
by `runner.py`); ruff finds nothing unused in the touched files.

## Tests run

Each file its own process, in parallel, under Python 3.11 (`/tmp/v`) and Python
3.13 (a fresh venv): `test_api` 380, `test_names` 6, `test_reminder` 204 (1
skipped), `test_reasons` 57, `test_review` 67, `test_runner` 193, `test_view`
34, `test_layers` 29, `test_repo_map` 80, `test_tripwire` 19, `test_errors`
83, all passed on both. `test_single_source`: 162 passed and 6 failed on both,
exactly the six that read `app/main.js` and fail on purpose until S2:
`test_the_shells_default_words_are_the_apis_word_for_word`,
`test_a_pass_killed_at_its_own_limit_ends_with_the_killed_sentence`,
`test_the_shells_kill_follows_the_limit_the_pass_reported_and_says_where_it_was`,
`test_the_shell_never_puts_stderr_on_screen_and_appends_it_to_the_error_log`,
`test_with_no_error_log_the_shell_says_stderr_in_the_reply_and_writes_no_file`,
`test_a_failed_spawn_is_said_by_its_code`. `python -m ruff check .`: all
checks passed. `python tools/repo_map.py update` then `check`: current.
`test_build` was not run (its scratch-roots OCR test fails on the base too).

## For S2

`app/main.js` still has the old no-log behaviour (stderr said in the reply) and
its pinned defaults; the six failing tests are S2's to turn green.
