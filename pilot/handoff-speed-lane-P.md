# Speed round - Lane P (Python) handoff

Builder: Lane P, 2026-10-08. Contract: `pilot/SPEC-speed-round.md` section
5.1, in its build order, with the contracts of 5.3 and the Q1 answer of
section 7. Worktree branch `worktree-agent-aa01a74ff2a0f423b`, from
`51187f6` (the SPEC commit on `claude/cool-brahmagupta-a45s9n`). Made-up
data only; the shared firm under the scratchpad was not touched.

## Commits

| Commit | Row |
|---|---|
| `4abf313` | P214 - the record checkpoint keeps a write-ahead log, one connection a command |
| `ab77000` | P215 - answers kept for one hold: the walk, the key, the record's reads |
| `07762de` | P216 - the digest cache's key from the held folder |
| `61ee57f` | P217 - the pass-order hint: a one-line mark, the whole written once |
| `fb5b813` | P218 - S1 (a Sort leaves the cache to the app), S3 (setup readies the Overview), Q1 (the pilot installer) |
| `9cfe945` | P219 - smaller repeats |
| `67b9780` | P220 - the warm spare, Python half |
| `219fc68` | P222 - Python half: count lines, the two words and their wording rows |
| `c91ac5c` | P223 - the budget in counts |
| `3886b0e` | derived map refresh and the vocabulary report's input hashes |
| (this file) | the handoff, with its own map refresh |

## Per row

### P214 - write-ahead log, one connection a command

- `tracker/checkpoint.py`: `CHECKPOINT_WAL_FILENAME`, `CHECKPOINT_SHM_FILENAME`;
  `_write_ahead(conn)` (WAL, then `synchronous = FULL` on every connection;
  a busy switch is no error) called at the end of `_opened` (after any
  set-aside reconnect); docstring paragraph and the journal comment rewritten.
- `tracker/store.py`: `_CHECKPOINT`, `_CHECKPOINT_PATH`, `_CHECKPOINT_FILE`
  (the per-connection answer of `_checkpoint_file`), `_held_checkpoint(where)`,
  `_drop_the_checkpoint()`; `_beside` yields the held connection and drops it
  on any `CheckpointError`; `prove_the_root`, `foreign_lines`,
  `acknowledge_foreign` use it (dropping it on a checkpoint error, the first
  still raising the checkpoint's own error); `close()` closes the checkpoint
  first, a failure being a warning by class. `record()`'s two transactions
  are unchanged.
- Named everywhere: `after_install.CHECKPOINT_UNIT` (+ `_CHECKPOINT_SIDE_FILES`
  in the unit rule: a journal, log or shared memory without its checkpoint
  moves nothing), `runner.left_behind` and `_to_move`, `build.yml`'s
  `$names`, `tests/test_build.py`, `tests/conftest.py` `real_places`,
  `tests/test_tripwire.py`, and `.gitignore` (see departures).
- Tests: `test_checkpoint.py` - `test_the_checkpoint_keeps_a_write_ahead_log_at_full_sync`,
  `test_a_switch_another_connection_refuses_leaves_the_checkpoint_working_in_its_own_mode`,
  `test_a_held_checkpoint_sees_what_another_process_advanced_since`,
  `test_the_read_only_open_reads_a_checkpoint_in_its_write_ahead_log`, and
  `test_a_busy_checkpoint_is_said_as_busy_and_never_as_one_to_set_aside`
  rewritten (the holder blocks `advance`). `test_store.py` -
  `test_one_command_opens_the_checkpoint_once`,
  `test_closing_the_store_closes_the_checkpoint_and_takes_its_side_files`,
  `test_a_checkpoint_error_drops_the_held_connection_and_the_next_question_opens_it_again`,
  `test_expect_is_on_disk_before_the_journal_line_and_advance_after_it`.
  `test_after_install.py` - `test_the_checkpoint_its_log_and_its_shared_memory_move_as_one`,
  `test_a_write_ahead_log_without_its_checkpoint_moves_nothing` (and the
  fabricated unit gained a `-wal`). `test_runner.py` -
  `test_the_checkpoints_side_files_beside_the_store_in_use_are_never_named_left_behind`,
  `test_a_checkpoint_log_left_beside_the_program_is_named_to_move_never_to_delete`.
  `test_build.py`'s list test extended.
- Existing tests that overwrite, rename or byte-compare the checkpoint now
  call `store.close()` first, as the runbook tells a person to close the
  app first (`test_a_checkpoint_that_will_not_open_is_that_returns_problem_by_name`,
  `test_a_pass_serves_no_household_while_the_old_checkpoint_sits_beside_the_program`).

### P215 - one hold-scoped memo

- `tracker/settings.py`: `held(key, answer, *, there=None)` replaces `_held`
  (its three callers moved); kept for a reading, for a household's hold only
  once `there` resolves to a held answer; never an error.
- `tracker/runner.py`: `discover_engagements` in `_pass` and `_parked_files`
  in `write_status_page` each run inside `one_reading()`, the call alone.
- `tracker/store.py`: `_engagement_row` asks its key through `settings.held`;
  new `held_read(conn, engagement_dir, what, build)`.
- `tracker/manifest.py` (`load_manifest`, `load_engagement_info`) and
  `tracker/filer.py` (`read_index`) follow the journal as before, then build
  through `store.held_read`.
- Tests: `test_settings.py` - `test_held_keeps_an_answer_for_the_hold_and_only_once_its_path_is_there`,
  `test_held_never_keeps_an_error`. `test_store.py` -
  `test_an_engagements_key_is_worked_out_once_per_hold`,
  `test_a_key_asked_before_its_folder_existed_is_asked_again_after`,
  `test_a_record_read_is_never_kept_past_a_rebuild_of_its_row`.
  `test_manifest.py` - `test_a_held_reading_builds_the_list_once_per_record_head`,
  `test_a_held_list_is_built_again_once_the_journal_moves`,
  `test_a_line_another_process_appends_is_seen_by_the_next_read_in_the_hold`,
  `test_nothing_is_kept_once_the_hold_ends`. `test_filer.py` -
  `test_a_held_index_is_read_again_after_a_file_is_recorded`. `test_runner.py` -
  `test_the_passs_discovery_and_its_page_read_hold_the_machines_answers`,
  `test_the_page_is_written_outside_the_reading`.
- The admission pin (`tests/test_store.py` `ADMISSION_PIN[3]`) re-pinned: the
  closure now reaches `settings.held`; nothing newly refused, so
  `ADMISSION_VERSION` stays 3.

### P216 - the cache key

- `tracker/content_check.py`: `ContentCache._key` is
  `str(settings.resolved(file.parent) / file.name).lower()` for a plain name
  that is not a link, else the whole resolve. Imports `os` and `settings`.
- Tests (`test_content_check.py`): `test_a_files_cache_key_is_its_folders_held_answer_and_its_own_name`,
  `test_a_file_that_is_a_link_is_keyed_by_where_it_leads`,
  `test_the_key_is_the_one_a_whole_resolve_gives`.

### P217 - the pass-order hint

- `tracker/runner.py`: `PASS_ORDER_VERSION = 2`, `PASS_ORDER_MAX_BYTES = 4 MiB`,
  `_PASS_ORDER_READ = (1, 2)`; `_read_order_hint` returns `(path, hint, settled)`
  through new `_parsed_order_hint` and `_hint_households`; `run_registry`
  settles an unsettled hint before the first household and marks only when
  settled; `_mark_started` appends one synced line; `_write_order_hint`
  writes the compact ASCII line 1 through `write_text_atomically` and says
  whether it did. New `LAST_PASS_MAX_BYTES` (see departures).
- Tests (`test_runner.py`): `test_a_hint_for_a_thousand_households_is_read_back_whole`,
  `test_each_household_start_is_one_appended_line_and_the_hint_is_written_once_a_pass`,
  `test_a_pass_killed_in_a_household_leaves_its_mark_and_the_next_pass_puts_it_last`,
  `test_a_torn_last_mark_is_skipped_without_a_warning`,
  `test_an_earlier_versions_hint_is_read_and_settled_before_the_first_mark`,
  `test_a_hint_that_cannot_be_settled_takes_no_marks`. The existing pass-order
  tests pass with their version 1 bodies.

### P218 - the Overview made ready once

- S1, `tracker/runner.py`: `_fills_the_cache` returns `household is None`
  after its guards (no warm-head check; its now-unused `root` parameter
  removed); docstring bullet rewritten.
- S3, `tracker/after_install.py`: `OVERVIEW_READY`, `OVERVIEW_NOT_READY`,
  `AfterInstall.overview_sentence`, `_ready_the_overview(root, reason, check)`
  - setup door only, a saved root not refused, a store file present; it
  calls `store.close()` first (this process's store and checkpoint let go
  of before another process reads), then `runner.fill_firm_cache(str(root))`;
  never a failure; its line is the last of `lines`, before any failure.
- Q1: `tracker/runner.py` `SETUP_MODE_FLAG = "--after-install-setup"`;
  `api_entry.py` `run_setup_step(argv)` (`--settings`, `--product`, both
  required; put in the environment before `tracker.after_install` - and so
  `tracker.scheduling` - is imported; then `after_install.main(["--reason", "setup"])`).
  `pilot/installer/setup.iss` `[Run]` gains, before the launch entry:
  `{app}\resources\tracker-api\tracker-api.exe` with
  `--after-install-setup --settings "{app}" --product "Tax Document Console"`,
  `StatusMsg: "Making the Overview ready..."`, `Flags: runhidden waituntilterminated`.
- Tests: `test_runner.py` - `test_a_sort_leaves_the_overview_to_the_app`
  (replaces `test_run_now_fills_only_the_households_it_touched_so_only_while_the_cache_is_warm`;
  `test_a_fill_that_fails_is_a_pass_warning_and_never_the_exit_code`'s Sort
  half now expects no warning). `test_after_install.py` -
  `test_setup_makes_the_overview_ready_after_its_other_jobs`,
  `test_a_fill_that_fails_never_fails_the_step`,
  `test_the_launch_root_and_repair_doors_leave_the_overview_to_the_app`
  (`test_a_finding_is_not_a_failure` now reads the Overview's line last).
  `test_pilot_installer.py` - `test_the_pilot_installer_makes_the_overview_ready_before_it_launches_the_app`,
  `test_the_packaged_setup_mode_is_the_entrys_own_door`. `test_api_entry.py` -
  `test_the_setup_mode_runs_the_after_install_step_with_what_its_command_line_names`.

### P219 - smaller repeats

- `tracker/layout.py`: `name_key`, `segment_problem`, `is_invisible` under
  `functools.lru_cache(maxsize=8192)`; `parts_below` delegates to
  `_parts_below_of(outer_kind, outer_text, inner_kind, inner_text)` (cached;
  the `""`/`"."` rule asked only of a `str` outer, as `outer in ("", ".")` was).
- `tracker/store.py` `has_rules`; `tracker/registry.py` `engagement_from` asks it.
- `tracker/scanner.py`: an `owners` dict per scan behind `belongs_to`; the
  scan line's step is `progress.SCAN_STEP`.
- `tracker/progress.py`: `SCAN_KEPT_EVERY_SECONDS`, `SCAN_STEP`, `Watch(clock=...)`;
  `_keep` skips a scan line within a second of the last line kept (reads
  the clock per kept line); docstring sentence as the SPEC words it.
- `tracker/validators.py`: `_pdf_reader()` and a module `__getattr__("PdfReader")`;
  `pillow_heif` registration untouched.
- `tests/test_store.py`'s `admission_closure` follows a remembered rule
  through `__wrapped__` (otherwise the cached `segment_problem` dropped out
  of the pin); `ADMISSION_PIN[3]` re-pinned, version unchanged.
- Tests: `test_layout.py` - `test_the_name_rules_answer_from_memory_as_they_answer_fresh`,
  `test_parts_below_never_answers_one_spelling_with_anothers_case`;
  `test_store.py` - `test_has_rules_is_whether_rules_has_any`; `test_registry.py` -
  `test_a_legacy_folder_is_still_found_by_whether_it_has_rules`;
  `test_scanner.py` - `test_each_names_owner_is_worked_out_once_per_scan`;
  `test_progress.py` - `test_a_scan_line_is_kept_at_most_once_a_second_and_every_other_line_at_once`,
  `test_a_sort_line_is_always_kept`, `test_every_line_is_still_printed`;
  `test_validators.py` - `test_the_pdf_reader_is_imported_only_when_a_pdf_is_opened`,
  `test_a_reader_a_test_puts_in_place_is_the_one_used`; `test_api.py` -
  `test_importing_the_api_loads_no_pdf_reader`.

### P220 - the spare (Python half)

- `tracker/api.py`: `SPARE_FLAG = "--spare"`, `SPARE_LINE_MAX = 64 * 1024`,
  `spare(stream=None)` per contract 5.3.1; `__main__` runs `spare()` for
  `[SPARE_FLAG]`. `api_entry.py` likewise (`argv == [SPARE_FLAG]`).
- Tests: `test_api.py` - `test_a_spare_runs_the_one_command_it_is_handed_and_replies_as_a_fresh_process_does`,
  `test_a_spare_handed_nothing_exits_quietly`,
  `test_a_spare_handed_a_malformed_line_says_the_usage_and_runs_nothing`,
  `test_importing_the_api_opens_no_file_but_the_programs_own`,
  `test_only_the_task_name_and_the_programs_own_place_are_fixed_at_import`;
  `test_api_entry.py` - `test_the_entry_given_the_spare_flag_waits_for_its_command`.

### P222 - the Python half

- `tracker/progress.py`: `COUNT_EVENT = "households"`, `count_line(done, total)`.
- `tracker/api.py`: `FIRM_READ_BATCH = 25`, `_say_count`; `_firm_from_cache`
  reads the unkept households in batches, prints a count line before the
  first and after each, builds each batch's would-be-shown rows into
  `early`, and the final loop uses `early` or builds the row. The `short`
  re-read and `_firm_fresh` print none. `SCREEN["updating"]`,
  `SCREEN["reading_households"]`; two `pilot/wording-shell.tsv` rows exactly
  as 5.3.4 gives them (after the `screen.notices.*` block).
- Tests: `test_api.py` - `test_a_cold_overview_says_each_batch_of_households_it_reads`,
  `test_a_warm_overview_prints_no_count`,
  `test_an_overview_read_in_batches_is_the_whole_walks_answer` (batch 1 and
  2, a Roll Forward and a household whose record is gone),
  `test_the_speed_round_words_are_in_the_screen_vocabulary`;
  `test_progress.py` - `test_a_count_line_carries_no_pass_and_no_name`.

### P223 - the budget

- `tests/test_runner.py` `test_an_idle_pass_stays_within_its_budget` (helper
  `_an_idle_pass_counted`, `IDLE_PASS_MEASURED`). Measured after the build,
  identical on 3.11 and 3.13: 89 store statements a household (budget 107),
  `store.rules` 1 a return (at most 2), 1 checkpoint connection a pass, 1
  whole hint write, 3 machine questions outside a hold a pass (budget 4).
  The same counter on `51187f6`: 123 statements a household, 9 `rules` a
  return, 4 checkpoint opens, 111 unheld questions.

## Departures from the SPEC, and why

1. **`.gitignore` gains `record-heads.db-wal` and `record-heads.db-shm`.** The
   SPEC said `record-heads.db-*` already covers both, so no change; but
   `tests/test_tripwire.py::test_the_ignore_file_knows_every_place_the_tripwire_guards`
   requires each guarded name exactly once, and the tripwire now guards both
   (as the SPEC asked). The glob stays.
2. **`LAST_PASS_MAX_BYTES = 64 KiB`** (new, `runner.py`): `last_pass_line`
   read the last-pass file under `PASS_ORDER_MAX_BYTES`; raising that to 4 MiB
   for the hint would have widened the last-pass cap too, so the last-pass
   file keeps its own 64 KiB.
3. **`store.held_read`'s token adds `built_at` and a process counter of
   deleted engagement rows (`store._REPLACED`, bumped by `forget` and
   `rebuild_engagement`).** The SPEC's token (id, path, head, seq, digest)
   is unchanged by a rebuild from the same journal (SQLite may reuse the
   id), so a held read could have answered from the rows a rebuild
   replaced. Safer; one extra integer.
4. **Fixed at import: four names, not three.** The AST scan finds
   `api.SCREEN` too - its `side.product` is `product_name()` at import. It
   reads the same environment variable `TASK_NAME` does, which the shell
   gives a spare and a fresh command alike, so it is safe; the test allows
   exactly `TASK_NAME`, `SCREEN`, `PACKAGE_JSON`, `CHECKOUT`.
5. **Q1 is a new entry mode, not an argument to the API's `after-install`
   command.** A packaged API started by the installer has neither
   `TRACKER_PRODUCT_NAME` (so `import tracker.api` fails at
   `scheduling.TASK_NAME`) nor `TRACKER_SETTINGS_DIR` (a frozen API would use
   `resources\tracker-api\` as its settings folder). So `api_entry.py` reads
   `--after-install-setup --settings <folder> --product <name>`, sets both,
   and only then imports `tracker.after_install`. The constant lives in
   `tracker/runner.py` beside `RUNNER_MODE_FLAG` because the entry must read
   it before anything imports `tracker.scheduling`. The API's `after-install`
   command is unchanged (the launch door only).
6. **The installer's status line "Making the Overview ready..."** is
   installer text (Inno Setup's `StatusMsg`), not app vocabulary; the
   installer already types its own words ("Launch Tax Document Console").
   Jason may want to word it.
7. **The setup door's Overview line comes last in `lines`** (after the test
   cache's sentence), so `test_a_finding_is_not_a_failure` now reads
   `FINDINGS_WAIT` as the last line before it.
8. **`docs/vocab-coverage.json` refreshed** (input hashes only:
   `tracker/manifest.py` and `tracker/content_check.py` are its inputs);
   `docs/vocab-coverage.md` unchanged, no routing word, case or matcher
   changed, so the backtest baseline cannot move.
9. **The admission pin's closure follows `__wrapped__`** (in
   `tests/test_store.py`), so P219's caches did not drop `segment_problem`
   and its rules out of decision 209's pin.
10. The P220 import probe was first written with an unarmed child; the
    suite's tripwire said so, and the probe now runs with `child_env` and
    allows the tripwire folder (folded into the P222 commit).

## Gate (section 5.4)

- `python -m ruff check .`: all checks passed (dead code removed as found:
  `_fills_the_cache`'s unused `root`; no debug prints left).
- The whole suite, one process per test file, `xargs -P 3`, on the commit
  before this handoff (`3886b0e`):
  - Python 3.13 (`python3`): 4,310 passed, 27 skipped, **6 failed**.
  - Python 3.11 (scratchpad `venv311`): 4,309 passed, 28 skipped, **6 failed**.
  - Every failure is the sandbox's, and fails identically on a clean
    `51187f6` under the same interpreter: the OCR reader cannot run here
    (`ModuleNotFoundError: No module named 'antlr4'`) -
    `test_build.py::test_the_scratch_roots_scan_is_filed_by_the_reader_and_by_nothing_else`,
    `test_ocr.py` (four: `test_a_scan_is_read_by_rapidocr`,
    `test_a_photo_is_read_by_rapidocr`, `test_a_sideways_page_keeps_its_words`,
    `test_a_full_read_opens_no_socket_writes_no_temporary_file_and_fetches_nothing`),
    and one in `test_real_corpus.py` (3.13:
    `test_an_image_row_in_the_expectations_is_routed_or_skipped_by_name_without_the_engine`;
    3.11: `test_corpus_rows_are_named_by_number_in_ids_messages_and_the_cache`).
  - Lane R's files (`test_shell.py`, `test_shell_menu.py`,
    `test_single_source.py`, `test_pilot.py`, `test_pilot_ui.py`) pass
    against this Python, both interpreters. No tripwire report.
- `python tools/repo_map.py update` then `check`: current (re-run after this
  file was added; see the last commit).

## What the orchestrator must write at merge (5.5), and what this lane adds

Everything in 5.5 stands. Additions and corrections found while building:

- **`pilot/DECISIONS.md` P218** should also name Q1: the pilot installer
  runs the after-install step through its setup door, via the packaged
  executable's new setup mode (`--after-install-setup --settings --product`).
- **P214's row**: `.gitignore` now names both side files outright (departure 1).
- **P215's row**: the held-read token also carries `built_at` and the
  count of rows this process deleted (departure 3).
- **P217's row**: `LAST_PASS_MAX_BYTES` keeps the last-pass file at 64 KiB.
- **P220's row**: what is fixed at import is four names (`api.SCREEN` too).
- **`docs/repo-map.curated.json`**, beyond 5.5's list: `api_entry.py` (the
  setup mode for the installer, the spare); `tracker/runner.py`
  (`SETUP_MODE_FLAG`, `LAST_PASS_MAX_BYTES`, `_fills_the_cache` without
  `root`, the two readings); `tracker/after_install.py` (the setup door's
  Overview job lets go of the store first); `tracker/progress.py`
  (`SCAN_STEP`, `Watch(clock=)`, `count_line`, `COUNT_EVENT`);
  `tracker/settings.py` (`held` replaces `_held`); `tracker/store.py`
  (`held_read`, `_REPLACED`, `_held_checkpoint`, `has_rules`);
  `tracker/api.py` (`spare`, `SPARE_FLAG`, `FIRM_READ_BATCH`, the count
  lines, the two words); the installer if it has a node or artifact.
- **`docs/runbook.md`**: besides 5.5's edits, the install section should say
  the pilot installer now makes the Overview ready before it offers to
  launch the app (and that a step that fails there is run again at the
  app's first launch). No one-time-step wording (decision 209).
- **The merged test** of 5.5.2 can read `api.SPARE_FLAG`,
  `api.HELD_READING_COMMANDS`, `api.WRITING_COMMANDS`,
  `progress.COUNT_EVENT` and `runner.FIRM_COMMAND`; all exist as named.
- **Lane R** must hand the spare `{"argv": [...]}` then the payload, as 5.3.1
  says; the reply and exit code are byte for byte a fresh process's
  (pinned). A count line has exactly `v`, `event`, `done`, `total` under
  `progress`.
- **Windows check**: P214's held handle and P216's key are the `windows`
  label's reasons; add the pilot installer's new `[Run]` step to the
  hands-on steps (install over a 22-household sample with a saved root and
  see the first Overview open warm).
