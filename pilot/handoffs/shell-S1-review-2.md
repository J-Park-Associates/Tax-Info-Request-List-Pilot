# Shell S1 review 2 (opus, high effort)

Branch `claude/sharp-goldberg-jmfynk`, reviewed at `6672dc5` (rebuild 1)
against the session's base `0776ea6` (`git diff 0776ea6...HEAD`) and the
rebuild against `21dc9c4` (`git diff 21dc9c4...HEAD`). The reviewer built
neither S1 nor its rebuild.

## What was checked

1. **Review 1's F1-F9, in the code, not in the rebuild's file.**
   - F1: `api.SCREEN` was flattened by script and compared key by key with
     the 11.4 table: all 78 keys and words are equal. `sort.stop`,
     `sort.firm`, `sort.locked`, `sort.stopping` and `filters.all` are now
     one level down. The table's 79th row, `schedule.move_warning`, is in
     `vocab.schedule`, where 11.2 puts it. The test asserts the key set.
     Fixed.
   - F2: `_firm_row` extends `files[]` with every moved-by-hand row
     (`file_group` Needs you and `FILE_MOVED`, code `file-moved`, which has
     the short reason "Moved by hand"). `row["files"]` and `oldest` are taken
     from that one list. `_cmd_firm` buckets a return as need on
     `counts[needs_you] or files or problem`. The new test covers a return
     whose requests are all received, with one parked and one moved file.
     Fixed.
   - F3: every `files[]` entry carries `path` (`str(one.path)`), and both
     firm tests pin it. Fixed.
   - F4: both branches (a discovery problem and an exception while reading)
     say `FIRM_UNREADABLE` ("Could not be read": four words, no "record",
     no path). The detail goes through `errors.keep`, which logs it and
     writes no file, so the shell appends it to the error log as before.
     A problem row is counted as need. Fixed.
   - F5: `ready` = drafted this draft-week and
     `approval_state(..., since=week) != APPROVED_NOTE`. This is the same
     read `_return_reminder` makes, so a draft that was edited after
     approval counts as ready again. `held` = the held rows plus
     `reminder.unsorted_in_inbox`, which only lists the inbox (the filer's
     `iter_drops` / `unfinished_drops` / `unreachable_drops` /
     `unlistable_folders`; none opens a file). A hold no longer stops a
     draft from being ready. Fixed.
   - F6: `shell.page_error` is `PAGE_ERROR` on both branches.
     `PAGE_ERROR_NO_LOG` is gone from `tracker/`, `tests/`, `app/` and the
     docs. Only the decision-186 row of the ROADMAP still names it, and
     that row is history. Fixed.
   - F7: `errors.keep("api: add issuer", exc)` and a plain
     `ISSUER_NOT_RESCANNED` ("Next sort rechecks it"). Fixed.
   - F8: `test_firm_is_read_only` also takes a snapshot of
     `store.store_path()`, its `-*` side files and everything under
     `settings.data_home()`. Fixed.
   - F9: the `#:` comment sits on `WRITING_COMMANDS` again. The comments at
     `SHELL_NO_LOG` and in `_error_log_said` now say that without a data
     folder the details are not kept. Fixed.
2. **The rebuild changed nothing beyond the findings.** The diff
   `49ddf9f..6672dc5` touches only `tracker/api.py` (the hunks above),
   `tests/test_api.py` (the F1, F2, F3, F4, F5, F6, F7 and F8 tests),
   one row of `pilot/shell-test-pins.md` (the F6 pin), its handoff file and
   the regenerated map. There is nothing else.
3. **The rebuild's new words and semantics.**
   - "Could not be read" (`api.FIRM_UNREADABLE`) is not in the approved
     `wording-shell.tsv`. It follows the approved row 101 ("Reminder could
     not be read"). The rebuild's file says it is proposed for Jason's
     approval (see F1 below for where that belongs).
   - The F5 meaning of `draft.ready` / `held` is what SPEC 6.3 says: "whose
     draft for this week is ready and not yet approved", and "Held" when
     "files or rows hold it". Unsorted inbox files hold the whole draft, as
     reminder.py's decision 133 says. It needs no new approval.
4. **Standing rules.** `firm` is still in `COMMANDS` and not in
   `WRITING_COMMANDS`. It takes no lock and makes no network call, and
   nothing is sent. The new reads are all of the firm's own data: the
   draft file (its fingerprint), the store's last approval event, and a
   listing of the inbox. None of them reads a client document, and none
   of them writes. `load_manifest` already opened the store connection
   before the rebuild. `FIRM_UNREADABLE`, `ISSUER_NOT_RESCANNED` and
   `PAGE_ERROR` are five words or fewer. No path is on screen:
   `files[].path` is a join key, like `returns[].path`.
5. **SPEC 9.x for `firm` after the changes.** 9.1's grouping is
   unchanged, and `counts` still equals the item tally of `state`
   (`test_firm_counts_match_the_return_pages_groups`). The 9.2 fields are
   all present. `files` is parked plus moved. `problem` is a short line
   with zero counts, and it never fails the reply. The 6.1 figures still
   add up to the active returns. `totals.drafts` is the 6.3 row count. A
   root that cannot be walked still raises `PRACTICE_NOT_WALKED`, as 9.2
   says.

## Gate, as run by the reviewer

Each file ran as its own process, in parallel, under Python 3.11.15
(`/tmp/v`) and Python 3.13.12 (a venv with the pinned set). The results
were the same on both versions: `test_api` 380 passed, `test_names` 6,
`test_reminder` 204 (1 skipped), `test_reasons` 57, `test_review` 67,
`test_runner` 193, `test_view` 34, `test_layers` 29, `test_repo_map` 80,
`test_tripwire` 19, `test_errors` 83. `test_single_source` had 162 passed
and 6 failed, and the six are exactly the `app/main.js` ones that wait for
S2: `test_the_shells_default_words_are_the_apis_word_for_word`,
`test_a_pass_killed_at_its_own_limit_ends_with_the_killed_sentence`,
`test_the_shells_kill_follows_the_limit_the_pass_reported_and_says_where_it_was`,
`test_the_shell_never_puts_stderr_on_screen_and_appends_it_to_the_error_log`,
`test_with_no_error_log_the_shell_says_stderr_in_the_reply_and_writes_no_file`,
`test_a_failed_spawn_is_said_by_its_code`. `python -m ruff check .`: all
checks passed. `python tools/repo_map.py check`: current.

## Findings

**F1. The S1 handoff still records the old `draft.ready` as a decision for
S6 to log, and the new word is not among the proposed rows.**
`pilot/handoffs/shell-S1.md:13-14` says "`draft.ready` = drafted this
draft-week and nothing holds it". Its first proposed decision row (line
104) says a draft is "`ready` only when written this draft-week and
unheld". Since rebuild 1 (F5), the code does the opposite: a hold does not
stop a draft from being ready, an approved draft is not ready, and
`held` includes the inbox. HANDOFF.md says S6 logs its decisions from these
proposed rows, so as written S6 would log a decision that contradicts
both the code and SPEC 6.3. The rebuild's request for approval of "Could
not be read" (`FIRM_UNREADABLE`) is in prose under its F4, not in a
proposed row, so S6 can miss it. **Fix:** in `shell-S1.md`, correct the
`draft.ready` line and the first proposed row to "ready = drafted this
draft-week and not yet approved (an approval the letter was edited after
does not count); `held` = the holding rows plus the unsorted inbox files;
a hold does not unmake ready (SPEC 6.3)". Then add a proposed row: "A
return the firm view cannot read says 'Could not be read'
(`api.FIRM_UNREADABLE`), the detail to the error log, and counts as
needing a person". This is a handoff-only change, with no code and no
test.

A note, not a finding: `_firm_draft` now reads the draft file's letter
fingerprint and lists the household inbox for every active return, and it
does both even when nothing was drafted this week. A household with several
returns has its inbox listed once per return. The 750-returns-in-3-seconds
budget (9.2) is measured in the Windows check. If that budget fails there,
this is the first place to look.

1 finding.
