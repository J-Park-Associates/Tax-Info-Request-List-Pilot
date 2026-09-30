# Shell fix pass (answers final reviews A, B and C)

Builder: Claude Sonnet 5.5, on `fixpass` from `origin/claude/shell-join`
(`2e80090`), pushed to `claude/shell-join`. Rulings 23-29 (`shell-rulings.md`,
copied whole onto this branch) are applied. Exactly the findings named below
were fixed; nothing else was touched.

## What was fixed

| Finding | Fix | Pinned by (each mutation-checked: removing the fix fails the test) |
|---|---|---|
| A1 move-schedule warning never shown | `moveScheduleQuestion(host)` in `app.js` puts `move_warning` under `move_confirm` (each phrase five words or fewer) | `test_shell::test_the_move_schedule_question_carries_its_warning` |
| A2 / ruling 24 emails and zips | `_shown_copy_key` returns "" for the containers bucket, so `state` and `firm.paths` carry no key and the page draws plain text; programs unchanged | `test_api::test_a_set_aside_file_and_a_parked_document_are_shown_but_a_zip_or_email_is_plain_text` (state and firm) |
| A3 unreadable word | `FIRM_UNREADABLE = "Could Not Be Read"`; test_api and test_shell pins, wording table | `test_api::test_firm_says_an_unreadable_record_as_its_own_row` |
| A4 PROPOSED marks | removed from the API comment; wording table rows say "Approved by Jason (rulings 18/18a/23)"; "Bad Year" keeps "working word, Jason may change" | wording table |
| A5 kill at the 30-minute cap | `main.js` says "Sort Stopped: Ran Too Long" for a sort, "Change Stopped: Ran Too Long" + "It May Be Partly Done." for a write, "Stopped: Ran Too Long" for a read; the API sends `vocab.writing_commands` | `test_single_source::test_a_command_killed_at_the_cap_says_whether_it_was_a_sort_a_change_or_a_read` |
| A6 / rulings 25, 29 failure reason | `scan.problem_reason` = "Sort Failed: {reason}", `scan.reasons` keyed by the runner's `code` (added to each run in the final line); `scanFailed(run)` draws it | `test_shell::test_a_failed_sort_says_a_short_approved_reason_and_never_a_path`, `test_runner::test_the_final_line_carries_the_kind_of_a_failed_run_and_no_path` |
| A7 firm read-only | with a store that lags its journal (a journal write with the apply killed), no read of a return in `_firm_row` other than the details reader may follow the journal, and no document moves | `test_api::test_firm_is_read_only` (fails with `follow=True` on `load_manifest` or on `read_index`) |
| B1 start-up race | `bootstrap` starts through `startWhenLoaded` (DOMContentLoaded) instead of at the last line of `app.js` | `test_shell::test_the_app_starts_only_after_every_script_has_loaded` |
| B2 / ruling 28, C2 | the Sort Failed notice has no retry or action and clears when the record says a sort worked; `runScan` refuses when no return is chosen (so no flag or command-line sentence can reach a firm page) | `test_shell::test_a_failed_last_sort_is_a_keyed_notice_without_retry...` (real `list.last_pass` shapes), `test_a_sort_is_never_sent_without_a_return_chosen`; `interact.mjs` |
| B3 / ruling 27, B4 | `.row-wrap` (a return's or household's row, or a row with a marker) lets name and status wrap (the detail column, a household link, keeps its ellipsis); 40px for one line, 48px for two, on the 4px grid; a file's name keeps its ellipsis | `test_shell::test_a_return_or_household_row_wraps...`; `interact.mjs` checks 1100px on Overview, Needs Review, Reminders, Clients, Clients (All) and the household page: nothing cut, every return link shows its year, row heights on the grid, the paused words whole |
| B5 group named by its path | named by `pagesReturnName`; `pagesLabel` never falls back to a path | `test_shell::test_a_needs_review_group_that_cannot_be_built_is_named_by_its_return_and_never_its_folder` (scans the notices) |
| B6 links | `.row-link` always underlined (the colour is 1.4 to 1.5 against the text); statuses ("3 Waiting") never are; contrast themes keep `LinkText` and the underline | `test_shell::test_a_link_differs_from_plain_text_by_more_than_its_colour`; `interact.mjs` in light, dark and forced colours |
| B7 style | the two statements on one line split | - |
| C1 vocab report | `tools/vocab_report.py build`: the only change is the two input hashes (`tracker/manifest.py`, `tracker/templates.py`); no routing change | `test_vocab_report` |
| C3 / C4 | `shell-rulings.md` copied whole (rulings 1-29); `shell-ledger.md` rewritten (all rulings, status built/fixed); DECISIONS P92-P106 statuses updated and P108-P114 added | - |
| C6 | SPEC: preamble and text for rulings 15-29 (16, 17, 20/28, 24, 25/29, 27 in 3.5, 3.6, 5.2, 6.7, 8.4), "Mark Missing" and "Needs Review" in Title Case | - |
| C7 | `pilot/wintest/PROMPT-shell.md` rewritten: no Git, the failed scheduled sort by renaming the folder and running the task in Task Scheduler, how to switch a return off, where `Archive 2024` goes, the new checks | - |
| C8 | runbook and README describe the shell (side panel, right-click menus, menu bar, Folders Skipped, the Sort icon, Add a Return…, Roll Forward…, New Household…, Advanced switch, Open Error Log) | `test_single_source` (the "one-time step" wording rules pass) |
| C9 | mock-up: "Could Not Sort" and the other reasons in Title Case | - |
| C10 | SAFEGUARDS words and the ruling 22 runbook note pinned | `test_single_source` (two new tests) |

The `Not asked` in the runbook's status table (C8) was left as it is: that
column is the record's own status name, and `test_the_runbook_status_table_is_the_label_table`
pins it.

## Words for Jason

Ruling 29 approved the reason words, so none is PROPOSED any more. Marked
"Approved by Jason (rulings 25, 29)" in `wording-shell.tsv`: Another PC Sorting
(lock-held), Two Years Open (household-paused), Folder Not Found
(client-folder-missing, folder-missing), Unexpected Error (any other kind).
The new killed-command words (Change Stopped: Ran Too Long; It May Be Partly
Done.; Stopped: Ran Too Long) are mine and follow A5's ask: say so if you want
them changed.

Could not be mapped, because the engine does not tell these apart in a
return's pass: **Drive Not Signed In** (it is a notice of its own, not a
failure kind of a run) and **Ran Too Long** (the shell's own sentence at the
30-minute cap, now "Sort Stopped: Ran Too Long"). A run held back by another
PC's lock is a skip, drawn as "Nothing Done", not "Sort Failed", so "Another
PC Sorting" is in the vocabulary for when the banner reaches it but not seen
on a return's banner today.

Found while fixing A7 (not changed, as A7 asked only for the test): the
walk that finds the returns (and the details reader) catches a lagging store
up, so `firm` does write the store when it lags; it never touches a document.
The test pins that the firm's own reads do not.

## Gate (each test file its own process; Python 3.11, then 3.13)

See the last commit's message and the report: the files for what changed
(`test_shell`, `test_shell_menu`, `test_pilot_ui`, `test_tour`, `test_pilot`,
`test_api`, `test_registry`, `test_runner`, `test_single_source`, `test_layers`,
`test_vocab_report`, `test_repo_map`, `test_tripwire`, `test_errors`) and, because
`api.py` and `runner.py` changed, `test_router`, `test_filer`, `test_scanner`,
`test_manifest`. `ruff` clean; `repo_map.py check` current; `interact.mjs` and
`shoot.mjs` run, and the shots at 1100px were looked at in light, dark and
the contrast theme.

# Fix pass 2

Findings NEW 1-5 of `shell-final-rereview.md`, fixed on `claude/shell-join`.

| Finding | Fix | Pinned by |
|---|---|---|
| N1 other returns' raw sentences | `scanSummary` draws, for every return in the reply, only the failure word with its approved reason (from `code`), or - only when `code` is `lock-held` - the approved word "Another PC Sorting" (asked return: "Nothing Done: Another PC Sorting."). Any other skip of the asked return is the bare "Nothing Done" (new word `scan.nothing_done_bare`, mine, Jason may change); any other skip of another return draws nothing. The long sentences stay in the error log. Other returns' own warnings are unchanged. | `test_shell::test_a_failed_or_locked_household_sort_draws_no_engine_sentence_and_no_path`: real `run-now` on a household of two returns, once with the client folder gone and once with one return's lock held; the final line's runs go through the page's own `scanSummary`; no path, backtick, "Clients", "missing", "another run" or "lock" reaches a drawn line. Mutation-checked both ways (raw sentence for the other return; raw skip for the asked return): each fails the test. |
| N2 PROMPT step 12 | Says to rename the folder chosen as the Clients folder in step 2 (the one holding `Clients` and `J Park & Associates`). Verified on a scratch tree with the real runner: the scheduled pass with that folder gone is refused (`PassFailed`, non-zero); renaming the inner `Clients` fails only after the household has been sorted once (exit 1) and succeeds (exit 0, no banner) for a household never sorted. Menu word is "Repair Schedule" (Tools menu). Step 13 now says a household sorted once, which folder, and that other returns get their own short line. Step 11 (Unfile box) had no such problem. | PROMPT text |
| N3 misfit rows | Nine rows say "Approved by Jason, ruling 30"; "Bad Year" says "Working word (ruling 18a), Jason may change". | TSV |
| N4 30-minute cap | Each kill phrase ends in a full stop: "Sort Stopped: Ran Too Long." / "Change Stopped: Ran Too Long." "It May Be Partly Done." / "Stopped: Ran Too Long." then "It Was on {household}: {name}." Five words or fewer each. | `test_single_source` (literal joined lines) |
| N5 README and runbook | README sentence split so "Its name" is the household's; the doubled "a" in the runbook is gone; "card" becomes row, page or side sheet in the runbook (the graphics card stays, and one quoted engine sentence, `reminder.py`'s "open it from its card", stays as the engine says it); "Routing rules fold" is the **Advanced** switch. Status names such as "Not asked" are unchanged. | `test_single_source` |

Words for Jason: "Nothing Done" (bare, for a skipped return with no approved
reason word). The reminder's own refusal in `tracker/reminder.py` still says
"card"; not changed here (engine wording, outside this pass).

Gate: ruff clean; `test_api`, `test_api_entry`, `test_shell`, `test_shell_menu`,
`test_pilot_ui`, `test_single_source`, `test_layers`, `test_registry`,
`test_vocab_report`, `test_repo_map`, each its own process, Python 3.11 then
3.13; `interact.mjs` passes. `runner.py` was not touched.
