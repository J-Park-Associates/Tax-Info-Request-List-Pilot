# Sort & Scan speed - Lane P (Python) handoff

Builder: Lane P, against [`SPEC-sort-speed.md`](SPEC-sort-speed.md) section 5.1,
with Jason's answers of section 7.1 (P227 yes, P228 yes, list skip no, P229
yes - build it now, "Updating, as of {time}" approved). Base `b894a32`.
Rows built: **P225, P226, P227, and P229's API half.** P228 and P229's window
half are Lane R's (`app/*`, `tests/test_shell.py`, `tests/test_single_source.py`
pins). Not pushed. DECISIONS rows P225-P230 are the orchestrator's, at merge.

## Commits (landing order)

| Commit | Row |
|---|---|
| `5b4b1c0` | P225 - Roll Forward's name match by its last three names |
| `75e85e4` | P226 - the practice page's report inside one reading |
| `2fa919a` | P227 - the page's read rows kept under each record's own token |
| `8335c60` | P229 (API half) - `firm-last` and `updating_as_of` |
| this file | the handoff |

## P225 - discovery's Roll Forward match asks only its own group

- `tracker/registry.py`: `_Priors.by_tail()` groups the readable returns by
  their last `layout.ROLLED_FROM_TAIL` (3) `tail_names`, once, the first time
  the fallback is needed. `_prior_of`'s fallback refuses a Rolled From of
  fewer than three names (as the floor always did) and compares only with
  the returns of its own group. The longest tail, the tie rule and the
  candidate's own exclusion are computed over the same candidates that
  could ever win.
- Tests (`tests/test_registry.py`):
  `test_the_name_match_retires_the_same_prior_as_comparing_every_pair`
  (a word-for-word reference of the pre-P225 `_prior_of` kept in the test;
  12 generated practices over the same-depth, a deeper and a shallower old
  root, a real tie, Rolled From of one and two names, a candidate whose own
  folder is the best match, a problem return; and a case-only difference
  with `os.path.normcase` patched to fold case) and
  `test_a_moved_root_compares_each_rolled_return_only_with_its_own_group`
  (200 rolled households after a move: at most 2 `common_tail` calls a
  rolled return, every prior retired).

## P226 - the report inside one reading

- `tracker/runner.py` `status_report`: `records_needing_a_person` and every
  un-run return's `_engagement_status` run inside `one_reading()`; the
  `RunReport` is built after the hold, and the page is written after it.
  The failed fill's redraw is the same function.
- Tests (`tests/test_runner.py`):
  `test_the_practice_pages_report_asks_each_machine_question_once`
  (machine questions actually asked during `status_report` over three
  households: each `resolved` spelling once, `data_home` at most once -
  it was 30 and 10 without the hold) and
  `test_the_practice_page_is_written_after_its_readings_end`.
- P223's budget, measured again after P226 and P227 (one idle scheduled pass
  over three households): statements a household **90** (was 89 -
  `read_tokens`' one statement a page; the kept parked rows save the index
  reads), rules per return 1, checkpoints 1, hint writes 1, unheld machine
  questions **3** (unchanged; `open_kept` runs inside a reading). Both are
  inside the 1.2x budget, so `IDLE_PASS_MEASURED` is unchanged (it did not
  fall, and a budget rises only with a row).

## P227 - the page's read rows kept between passes

- `tracker/store.py`: `read_token(row)` - the one definition (`id`, `path`,
  `ledger_head`, `applied_seq`, `applied_digest`, `built_at`); `held_read`
  now builds its key as `(what, *read_token(row), _REPLACED)`.
  `read_tokens(conn, path=None)` - every row's token in one `SELECT`, keyed
  by stored path, or one row's. `record_key(folder)` - the exact key under
  the recorded root (`_engagement_key`, split out of `_engagement_row`
  unchanged), else `None`. `test_store`'s admission pin re-pinned under
  version 3 (`_engagement_key` added, `_engagement_row`'s digest moved): it
  refuses nothing new, the same code moved into a helper.
- New `tracker/page_rows.py` (layer 0: stdlib, `settings`, `fsio`, `errors`,
  `firm_cache`): `ROWS_FILENAME = "page-rows.json"` in the data home,
  `page_head` (`firm_cache.head` + `rows_format`), `load`/`save`, `Kept`
  (`counts`, `parked`, `keep_counts`, `keep_parked`, `forget`, `save`, and
  `tokens` - the store's snapshot the runner fills once a report),
  `open_kept(root)` (`None` with no data home).
- `tracker/runner.py`: `_pass` opens the kept rows once a page, saved root
  only, never on a dry run, inside a reading; `status_report(..., kept=)`
  empties the token snapshot then hands `kept` to `_engagement_status`;
  `write_status_page(..., kept=)` hands it to `_parked_files` and saves the
  file after `status.html` (a failure is a log line by class). New
  `_page_token(kept, folder, again=)`: the snapshot (one statement) before a
  read, one row's token again after it; a fresh read is kept only when the
  two are equal, otherwise the entry is forgotten. A read that raised is
  forgotten and read again every page; a return outside the recorded root
  or without a store row is never kept. The page's drawing code is
  unchanged.
- Tests (`tests/test_page_rows.py`, new, owns the module):
  `test_the_practice_page_from_kept_rows_is_the_page_from_fresh_reads`
  (fresh, filling, all kept: three equal byte strings, and no record read
  on the last), `test_a_return_written_since_its_row_was_kept_is_read_again`
  (an override and a parked file: only that return read, the page equal to
  a fresh one), `test_a_record_rebuilt_from_its_journal_is_read_again`,
  `test_a_row_written_while_it_was_read_is_not_kept`,
  `test_kept_rows_from_another_day_program_or_root_are_set_aside`,
  `test_a_damaged_kept_rows_file_is_set_aside_and_said_by_its_class`,
  `test_a_return_whose_record_cannot_be_read_is_never_kept`,
  `test_a_sort_reads_only_its_own_households_records_for_the_page`,
  `test_a_dry_run_and_a_page_with_no_data_home_keep_nothing`,
  `test_the_kept_rows_are_kept_only_for_the_saved_root`.
  `tests/test_store.py`: `test_the_held_read_and_the_page_use_one_token`,
  `test_a_folder_outside_the_recorded_root_has_no_record_key`,
  `test_the_tokens_of_every_record_are_one_statement`.
  `test_only_the_practice_page_reads_the_store_without_following_the_journal`
  passes unchanged (no new `follow=False` text anywhere).
- Layer table: `page_rows` in L0 with a comment (`tests/test_layers.py`).

## P229 (API half) - `firm-last`

### The contract (for Lane R)

- **Command:** `firm-last`, no arguments, no stdin. In `api.COMMANDS` and
  `api.HELD_READING_COMMANDS` (never `WRITING_COMMANDS`). `main.js` must add
  it to `HELD_READING_COMMANDS` (and to `EARLY_COMMANDS`):
  `tests/test_single_source.py::test_a_read_handed_to_a_spare_that_had_died_is_asked_once_more_and_a_write_never`
  pins `main.js`'s set to the API's and **fails in this lane until Lane R's
  `main.js` lands** (it passes at `b894a32`).
- **When it answers:** exactly `firm`'s reply - `returns`, `files`, `totals`
  (`need`, `waiting`, `complete`, `files`, `drafts`), `paths`, `next_sort`,
  and `warnings` as on every reply - plus:
  - `"last": true`
  - `"as_of": "HH:MM"` - local time, 24-hour, two digits each, the same form
    as `next_sort`: the cache file's (`firm-view.json`) last modification,
    i.e. when those rows last **changed** (same day by construction). The
    window says it with `pagesTime` and fills `updating_as_of`.
  When nothing changed since, the reply minus `last` and `as_of` equals the
  real `firm` reply field for field (`test_the_last_counts_are_the_firm_reply_when_nothing_changed`).
- **When it refuses:** `{"last": null, "warnings": [...]}` - no other key -
  exit 0, whenever: no saved root or it is not a folder; the walk's
  positions cannot be listed; no cache file under **today's head**
  (`firm_cache.head`: format, program stamp, clients root, data home, day,
  settings file) or it keeps nothing; the kept households are not exactly
  the walk's household positions (one missing or one extra); a kept
  household has a problem; a return the practice-wide marks now show has no
  kept row. The refusal's name (`FIRM_LAST_REFUSALS`) goes to the error log
  at info level, never a client's words. A root the door refuses is the
  same error envelope `firm` gives.
- **What it never does:** take a fingerprint, read a record, list, index or
  detail, run `households_named`/`discover_engagements`, open the store, or
  write anything (no cache save) - pinned by
  `test_the_last_counts_read_no_record_and_take_no_fingerprint` and
  `test_the_last_counts_write_nothing`.
- **Vocabulary:** `api.SCREEN["updating_as_of"] = "Updating, as of {time}"`
  (reaches the app as `vocab.screen.updating_as_of`); `{time}` is the app's
  time words for `as_of`. Row added to `pilot/wording-shell.tsv`
  (sentence case kept as Jason approved it).

### Built

- `tracker/api.py`: `_cmd_firm_last`, `_firm_last`, `FIRM_LAST_REFUSALS`;
  the practice-wide step of `_firm_from_cache` split out unchanged into
  `_firm_order`, `_firm_marks`, `_firm_links`, `_firm_marked`, which
  `firm-last` reuses, so the last counts are decided by the same code as the
  fresh ones (paused households, retired priors, links worked out again).
  The module docstring lists the command.
- Tests (`tests/test_api.py`, appended; no existing test renamed or
  removed): `test_the_last_counts_are_the_firm_reply_when_nothing_changed`,
  `test_no_last_counts_after_a_program_change_another_root_or_another_day`,
  `test_no_last_counts_while_any_household_is_not_kept`,
  `test_the_last_counts_read_no_record_and_take_no_fingerprint`,
  `test_the_last_counts_write_nothing`,
  `test_the_last_counts_words_are_in_the_screen_vocabulary`.

## Departures, and why

1. **`page-rows.json` is two lines, written with `write_text_atomically`,**
   not one JSON document through `fsio.write_json_atomically`: the head and
   a digest of the second line, then the entries. The digest refuses a file
   damaged into other valid JSON (as the firm cache's does) without
   re-encoding 2 MB at every load. Still atomic, still the data home.
2. **A row rebuilt within the second it was first built keeps its token.**
   The SPEC says a rebuild in another process has a new `built_at`; it is
   to the second (`ledger.stamp`, one format by design) and SQLite may reuse
   the id, so a same-second rebuild is the same token. It is also the same
   rows - derived from the same lines by the same program, which the head's
   program stamp pins - so no status can differ; said in `page_rows`'s
   docstring and the test, which rebuilds in a later second. Changing the
   store's stamp or ids was judged out of this lane.
3. **The scheduled pass does not keep the counts of the returns it ran**
   (they come from the pass's own run, read at a moment the page does not
   control); it keeps their parked rows. So the first Sort after a
   scheduled pass reads the other returns' lists once, and Sorts after it
   read only their own household's records - the SPEC's steady state. The
   Sort test says so.
4. **`tests/test_single_source.py` touched by two lines** (Lane R's file):
   `ROWS_FILENAME` added to the runtime files the documents may name - the
   runbook names `page-rows.json`, as the SPEC requires. Merge both lanes'
   edits; they do not overlap Lane R's pins.
5. **`tracker/__init__.py`'s module list** gains `page_rows` (pinned by
   `test_single_source`); not named in 5.1, needed by the new module.
6. No CLI in `page_rows` - as `firm_cache` has none; the runner and the page
   are its only callers.
7. No P225 measurement on the 1,000-household firm was rerun here (section
   6 is at merge); the equivalence is held by the tests above.

## Gate (SPEC 5.3)

`python -m ruff check .` clean (no dead code in the changed files). Whole
suite, one process per test file, `xargs -P 3`, at `8335c60`:

| Interpreter | passed | failed | skipped |
|---|---|---|---|
| Python 3.13.16 (`python3`) | 4367 | 7 | 27 |
| Python 3.11.17 (`venv311`) | 4366 | 7 | 28 |

The failures, every one also failing at `b894a32` or explained:
- sandbox-only (antlr4): `test_build::test_the_scratch_roots_scan_is_filed_by_the_reader_and_by_nothing_else`;
  `test_ocr` (4: rapidocr scan, photo, sideways page, full read);
  `test_real_corpus` (3.13: `test_an_image_row_in_the_expectations_is_routed_or_skipped_by_name_without_the_engine`;
  3.11: `test_corpus_rows_are_named_by_number_in_ids_messages_and_the_cache` - both fail at `b894a32` on the same interpreter).
- cross-lane: `test_single_source::test_a_read_handed_to_a_spare_that_had_died_is_asked_once_more_and_a_write_never`
  - passes at `b894a32`; fails only because `main.js`'s held commands lack
  `firm-last` until Lane R's half lands.

`tests/test_api_entry.py` then `tests/test_shell.py` in one process: 201
passed on both interpreters. `python tools/repo_map.py update` then `check`:
current (443 nodes), refresh committed.

## What the merge must still change

- `pilot/DECISIONS.md`: rows P225-P230 (orchestrator).
- Lane R's `app/main.js` adds `firm-last` to `HELD_READING_COMMANDS` and
  `EARLY_COMMANDS`, and `tests/test_single_source.py` pins them; then the
  spare test above passes.
- `pilot/SPEC-sort-speed.md` section 8 (measured after, at merge).
- Already done here, check after merging Lane R: `docs/runbook.md` (the
  data-folder paragraph names `page-rows.json` and says what the launch
  shows with P229; the "after a Sort" sentence, P228's, is Lane R's to word
  if it says "then" - this lane found none to change),
  `docs/repo-map.curated.json` (`tracker/page_rows.py` and
  `artifact:page-rows.json` nodes, notes on runner, registry, store, api and
  `firm-view.json`). Re-run `python tools/repo_map.py update` after the merge.
- Windows check (5.3): `pilot\wintest\run_checks.ps1 -Tests tests\test_page_rows.py,tests\test_runner.py`,
  plus one timed Sort & Scan on the office copy before and after.
