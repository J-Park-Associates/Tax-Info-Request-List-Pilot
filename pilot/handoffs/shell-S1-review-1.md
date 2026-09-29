# Shell S1 review 1 (opus, high effort)

Branch `claude/sharp-goldberg-jmfynk`, reviewed at `21dc9c4` against its base
`0776ea6` (`git diff 0776ea6...HEAD`). The reviewer did not build S1.

## What was checked

- S1's row of SPEC-shell 16: sections 9 (9.1-9.4) and 11 (11.1-11.6), the
  approved wording in `pilot/wording-shell.tsv`, and the tests of 9.4 and 14.2
  (Python side).
- The approved wording, one row at a time, by script: every `api._vocab`
  row with the verdict reword, merge or error-log (56 + 4 + 10; the other 11
  reword rows and 1 merge row are `pilot-content.js`, which is S3's) was read out of
  `api._vocab()` and compared with the `proposed` column. All 70 match,
  except the four that are right to differ: `override_reasons[0..2]` (the
  stored values stay, and the words are in `override_labels`, P77) and
  `rules[0].headline` (the words are in `rules[].short`, 11.6).
- `api.MENU` against the 11.3 table (44 keys, all equal), `reasons.SHORT_REASONS`
  against the 11.5 table (60 codes, all equal, and exactly `BY_CODE` plus
  `PLAIN_CODES`), stage shorts and `SAFEGUARDS` against 11.6 (equal),
  `api.SCREEN` against the 11.4 table (see F1).
- Every string in `_vocab()` over five words is a `cut` or `exception` row
  of the TSV, apart from the branch in F7.
- Docs that quote changed words: README, CLAUDE.md, ROADMAP, runbook,
  docs/tools.md and pilot/*.md were searched for every old sentence of the
  table. What is left is the standing rules (unchanged on purpose), a
  ROADMAP history row quoting `review.SET_ASIDE_NOTE` (still in use), and
  the old tour lines in `pilot/SPEC.md` (S3's).
- The four standing rules: `firm` reads no document (`review.triage` and
  `reminder.triage` read only the index and the rows, and
  `unsorted_in_inbox` is not called). It files nothing and sends nothing,
  and makes no network call. It takes no lock and is not in `WRITING_COMMANDS`.
  An extra ad-hoc run (not committed) that
  took a snapshot of the store and the data home before and after `firm`
  found them byte-identical.

## Gate, as run by the reviewer

Each file ran as its own process, in parallel, under Python 3.11.15 (`/tmp/v`) and
Python 3.13 (a fresh venv, since the system `python3.13` has no pytest):
`test_api` 378 passed, `test_names` 6, `test_reminder` 204 (1 skipped),
`test_reasons` 57, `test_review` 67, `test_runner` 193, `test_view` 34,
`test_layers` 29, `test_repo_map` 80, `test_tripwire` 19, `test_errors` 83.
The results were the same on both versions. `test_single_source`: 162 passed and
6 failed on both. The six failures are the ones the handoff names, and each
one drives `app/main.js` (`_run_the_shell`, or its pinned defaults):
`test_the_shells_default_words_are_the_apis_word_for_word`,
`test_a_pass_killed_at_its_own_limit_ends_with_the_killed_sentence`,
`test_the_shells_kill_follows_the_limit_the_pass_reported_and_says_where_it_was`,
`test_the_shell_never_puts_stderr_on_screen_and_appends_it_to_the_error_log`,
`test_with_no_error_log_the_shell_says_stderr_in_the_reply_and_writes_no_file`,
`test_a_failed_spawn_is_said_by_its_code`. No other test fails.
`python -m ruff check .`: all checks passed. `python tools/repo_map.py check`:
current (266 nodes).

## Findings

**F1. `vocab.screen` nests four sort keys and one filter key a level too deep.**
`tracker/api.py:1220-1227` and `1253-1257`. SPEC 11.4 names the keys
`sort.now / sort.stop / sort.firm / sort.locked / sort.stopping` and
`filters.work / filters.all`, the key shape that S3's harness and renderer
are built against. The code builds `screen.sort.sort.stop`, `.firm`,
`.locked` and `.stopping`, and `screen.filters.filters.all`. So
`screen.sort.stop` and `screen.filters.all` are undefined. No test catches
it: `test_every_short_word_the_engine_adds_is_five_words_or_fewer` walks
whatever shape is there. **Fix:** flatten them to
`"sort": {"now": ..., "stop": ..., "firm": ..., "locked": ..., "stopping": ...}`
and `"filters": {"work": "Work waiting", "all": "All"}`. Then add an assertion
to `test_the_vocabulary_carries_the_menu_the_screen_and_the_short_words` that
`screen["sort"]["stop"] == "Stop sorting"` and
`screen["filters"]["all"] == "All"`, or compare the flattened key set with
the 11.4 table.

**F2. `firm` counts moved-by-hand files but does not list them, and it
buckets a return without its files.** `tracker/api.py:5246-5253` and
`5296-5301`. SPEC 9.1 says: "Files: parked for a person and moved by hand
are `needs_you`". 9.2 says `"files": n  # of needs_you, the files (parked + moved)`.
6.1 puts a return under Need a person when there is "anything in its Needs
you group". 6.2's count is the number of files on the page.
The code has two problems:
(a) `returns[].files` and `totals.files` count the moved rows, but
`files[]` lists only the parked ones. So the count on Needs review (and
each group's caption) disagrees with the rows under it.
(b) `counts.needs_you` counts request rows only, and the bucket in
`_cmd_firm` reads only `counts`. A return whose only work for a person is a
parked file that holds no row (for example a program with no shortlist), with
every row received, is counted as Complete and is left out of Work waiting.
**Fix:** (a) append a `files[]` entry for each moved row, with its code
(`file-moved`) and an empty suggestion. (b) Bucket as need when
`counts[needs_you] or row["files"]`, or add `row["files"]` into
`counts["needs_you"]` as 9.2's comment reads. Then extend
`test_firm_counts_match_the_return_pages_groups` with a return whose only
needs-you item is a parked file.

**F3. `files[].return` is a display label, so a file cannot be tied to its
return.** `tracker/api.py:5246`. In 6.2, Check on a file opens the sheet,
"which loads that return's `state`". Its groups are the returns of
`returns[]`, which are keyed by `path`. The code gives each file only
`one.label`, a sentence for display. `state` cannot be called with a label,
and joining a label back to a path through `list` is parsing. **Fix:** carry
`"path": str(one.path)` on each `files[]` entry, beside `return` (or make
`return` the path). Pin it in the counts test.

**F4. A return that cannot be read is said in a long engine sentence and
counted as Complete.** `tracker/api.py:5227`, `5241` and `5296-5301`. SPEC
9.2 asks for `problem` as "a short sentence". 11.1 caps every notice at
five words, bans the word "record", and allows no path. The code says
`runner.RECORD_UNREADABLE`: "the record could not be read: {problem}". That
is seven or more words, and it contains "record". At 5227, `{problem}` is
`Engagement.problem`, which can be a whole `ManifestError` message or
`HOUSEHOLD_RECORD_MISSING` naming a folder. Separately, a problem row has
zero counts, so it falls into `totals["complete"]`. A return nobody can read is
then counted as Complete on the Overview, which hides a failure. **Fix:** an
api-owned short line of five words or fewer with no "record" (for example
"Could not be read", proposed for Jason's approval in the handoff), with the
detail sent to the error log (`errors.keep`, as at 5239). Count a problem row
under `need`, not `complete`, and assert that in
`test_firm_says_an_unreadable_record_as_its_own_row`.

**F5. `draft.ready` cannot drive the Reminders page 6.3 describes.**
`tracker/api.py:5203-5212` (`_firm_draft`). 6.3 lists a return "whose draft
for this week is ready and not yet approved", with the status "Held" when
"files or rows hold it". The `firm` reply is the page's only source.
(a) `ready` ignores approval, so a draft already approved this week is
still listed as ready and counted in `totals.drafts`.
(b) `held` counts only the rows that hold it, not files still in the inbox.
`_reminder_payload` reports those separately (`unsorted`), and 6.3 names
them.
(c) `ready` is forced false whenever `held` is non-zero, so the "Held"
status can never be shown.
**Fix:** `ready` = drafted this draft-week and
`reminder.approval_state(...) != reminder.APPROVED_NOTE`, read the way
`_return_reminder` reads it. `held` = the holding rows plus
`len(reminder.unsorted_in_inbox(engagement))` (a directory listing, not a
document read). Do not gate `ready` on `held`.

**F6. `shell.page_error` is still a 27-word sentence when there is no
error log.** `tracker/api.py:448-449` and `1636`. TSV row 145 approves
`shell.page_error` = "The app hit an error" (error-log verdict). 11.1 caps
every error at five words, and 11.2 says that without an error log the
details "are no longer printed on screen". `_vocab()` sends
`PAGE_ERROR_NO_LOG`, "The app met an error of its own ({kind}); there is no
error log to hold the details, because the tracker has no data folder - the
first screen says why.", whenever `_error_log_said()` is empty. That is on
the same key, on exactly the first-start path 11.2 is about. **Fix:** send
`PAGE_ERROR` on both branches and delete `PAGE_ERROR_NO_LOG`, or give it the
approved words. Then update `tests/test_api.py:2493-2494`.

**F7. The kind of error behind "Next sort rechecks it" is dropped instead of
sent to the error log.** `tracker/api.py:4457`. TSV row 117
(`review_labels.issuer_not_rescanned`, verdict error-log): "Error kind to
error log". 11.2 says: "the detail goes to the error log; a short line
stays". The code still calls `.format(kind=errors.error_class(exc))` on a
constant that has no `{kind}`, so the kind reaches neither the screen nor
the log. **Fix:** `errors.keep("api: add issuer", exc)` (or a
`log.warning(... %s, errors.error_class(exc))`) beside the note, and a plain
`scan_note = ISSUER_NOT_RESCANNED`.

**F8. `test_firm_is_read_only` does not check the store.**
`tests/test_api.py:8148-8161`. SPEC 9.4 says: "the root's files, **the store**
and the record are byte-identical after `firm`; no lock file appears". The
test takes its snapshot only under `demo_root`. The store is in the test's app
folder (`store.store_path()`, `tmp_path/app/tracker.db`), and the data home
is beside it, so neither is compared. The reviewer's ad-hoc run found them
unchanged, so this is a gap in the pin, not a write. **Fix:** add
`store.store_path()` (and its `-wal`/`-shm`, if present) and
`settings.data_home()` to the snapshot.

**F9. Two comments now say the opposite of the code.** First,
`tracker/api.py:5199-5202`: the `#:` comment that documents `WRITING_COMMANDS`
("The commands that write a record, a file or the store...") now sits
above the new `_firm_draft`, and `WRITING_COMMANDS` has lost its
comment. Second, `tracker/api.py:439-441` and `2907` still say that without
an error log "a failed command's stderr is said in its own reply". SPEC
11.2, and the new `SHELL_NO_LOG` ("Tracker failed; no error log"), say the
details are no longer shown. **Fix:** move `_firm_draft`, `_firm_row`,
`_cmd_firm` and `_next_sort` above that comment, so it sits on
`WRITING_COMMANDS` again. Reword the two comments to say that with no data
folder the details are not kept (11.2).

9 findings.
