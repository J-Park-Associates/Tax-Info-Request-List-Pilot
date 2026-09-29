# Shell S4 - rebuild 1 (fixes for review 1)

Session: S4 rebuild, sonnet, 2026-09-29, resuming after the first attempt stopped early
(its WIP commit `6f34779` was audited, not trusted). **Branch: `claude/shell-s4-pages`**
(worked on locally as `rebuild-s4b`, pushed to the branch after every finding).
Fixes review 1's F1-F8 and nothing more. The last commit is named on the last line.

## Findings, each with how it was fixed

Status: F1 done; F2-F8 follow in this file as they land.

### F1 - one bad row no longer blanks the return page (fixed)

- `pages.js`: every row, group and page section is built through `pagesSafe` /
  `pagesEach`. A row that cannot be built (an item with no known `group`, a reason
  code or stage the vocabulary lacks, a bad household) is left out, collected in
  `pagesBroken`, and `pagesReportBroken` raises one keyed notice per row -
  "{row name}: The app hit an error" (`vocab.notices.about` and `vocab.shell.page_error`,
  both the API's) - with the error's own message and stack going to the error log
  (`syncNotices` now logs a wanted entry's `detail`). Every other row and group is drawn.
- `pagesReturnGroups` no longer throws for a group-less item; `pagesTally` counts it in
  no group (it never throws, so `shellStateArrived` cannot fail on it).
- `pagesDraw`: a whole-page failure keeps what the same page held (and its row tokens),
  or, with nothing drawn yet, draws the page's frame (its H1); it never replaces the
  page with nothing. A failure of the household notices or of the notice report is
  its own try, so it cannot stop the page being drawn.
- `shell.js` `shellStateArrived` catches anything after the state has arrived and says it
  with `failed(err)` (a notice, details to the error log). It never escapes to the write
  that brought the state, so a write that worked is not reported as failed.
- Tests (`tests/test_shell.py`): `test_one_item_without_a_group_is_named_in_a_notice_and_every_other_row_is_drawn`,
  `test_a_row_that_cannot_be_built_is_left_out_and_named_on_every_page`,
  `test_a_page_that_cannot_be_built_whole_keeps_what_it_held_or_draws_its_frame`,
  `test_an_error_after_the_state_arrives_never_reaches_the_write_that_brought_it`.

### F2 - the lock notice says one short line (fixed)

`showLock` (`app.js`) draws only the API's `running` / `running_other` words ("In use on
{host}"); the `on` and `greyed` sentences are no longer drawn. The harness stub no longer
blanks them: it carries S1's real `LOCK_ON` and `LOCK_GREYED` (and a `pass` on the locked
scenario, so `on` would be filled if it were drawn).

### F3 - reader, machine, pause and feed notices are short words, the sentences go to the error log (fixed)

- New `shortNotice(key)` (`shell.js`): the vocabulary's word `vocab.screen.notices[key]`; where
  it is missing, the approved setup line `vocab.after_install.wait` ("Setup needs attention",
  S1's `AFTER_INSTALL_WAIT`). No word is invented.
- `renderMachineNotices` (new, `app.js`): the reader warning and the machine warnings are one
  notice each (`reader`, `machine`), the API's sentences to `window.tracker.logError` when
  the notice first shows. `syncNotices` now takes an optional `detail` per notice and logs it.
- `pagesHouseholdNotices` (`pages.js`): a pause with a scope is `renamed` (with Accept), a year's
  pause (no scope) is `paused`, the feeds are one notice `feed`; the sentences go to the log.
  The two-years notice reads `vocab.household.two_open_years` as before (S1's is already five words).
- A keyed notice is now its own line even when another says the same words (`notice()` matches
  on the key too), so the fallback word on two different failures never merges into "(2 times)".
- The stub (`pilot/harness/stub.js`) carries S1's real long sentences constant for constant:
  `READER_PATH_WARNING` (with `C:\JPA Tracker`), `LEFT_BEHIND` and `PROGRAM_ON_REMOVABLE` as
  the two machine warnings (made-up paths), `HOUSEHOLD_PAUSED`, `FEED_UNRESOLVED`,
  `FINDINGS_WAIT`, `LOCK_ON`, `LOCK_GREYED`, and S1's `after_install.heading` ("After installing:
  needs a person") and `wait`. `app-stub.js` mirrors the two `notice` changes.
- Tests: `test_no_notice_draws_more_than_five_words_or_a_path_even_over_the_apis_long_sentences`
  (runs the stub in a vm and the app's own notice functions; every drawn notice five words at
  most, no drive letter or backslash or slash, each long sentence in the log and never drawn),
  `test_a_notice_shows_the_vocabularys_short_word_when_it_has_one`,
  `test_a_notice_falls_back_to_the_setup_line_for_a_word_the_vocabulary_lacks`,
  the two household-notice tests, and `interact.mjs` (the same rule over four scenarios in the
  real `app.js`). `test_api`'s machine-warning test now pins the short-line form.

### Missing vocabulary keys (for S6 / S1; the app reads them, and falls back until they exist)

All under `vocab.screen.notices` (SPEC 11.4 lists only `drive` there):

| Key | Read by | Words SPEC names |
|---|---|---|
| `reader` | the reader warning | "Install folder name too long" (E28) |
| `machine` | machine warnings (S1 sends sentences only; a code per warning, as `left_behind_warnings` already yields, would let each have its own line, e.g. `drive` = "Drive not signed in") | E30 |
| `renamed` | a pause with a scope (with Accept) | "Folder renamed" (E47) |
| `paused` | a year's pause (no Accept) | none named |
| `feed` | a feed that resolves to nothing | none named (6.5) |

### F4 - Clients never says Complete for a household with an unreadable return (fixed)

`pagesClientSpecs`: when no return needs a person and one has `problem`, the household's status
is that return's `problem`, in the needs tone, before Waiting and Complete (as `pagesCounts`
does for a return). Test: `test_a_household_with_an_unreadable_return_is_never_complete_on_the_clients_page`.

### F5 - Set aside is shut each time the page opens (fixed)

`pagesDraw` keeps the key of the page it drew last (`pagesDrawn`); when the route drawn is not
that page, `pagesSetAsideOpen` is reset. It is kept across redraws of the same page. The old
`pagesSetAsideFor` (reset only by another return) is gone. Test:
`test_the_set_aside_fold_is_shut_each_time_the_page_opens` (open, redraw, go to the year page, come back).

### F6 - contrast theme: a focused row's text is HighlightText (fixed)

`shell.css`, forced-colors block: `.rows:focus-visible .row.is-active` name, detail, status, date
and step take `HighlightText` (the step's link colour and the status tones outranked the
`inherit` rule; status had the same fault). Measured with Playwright's forced-colors emulation on
the return page, focused row with its "Check" step: light contrast theme, all parts white on the
Highlight navy, 19.04:1; dark contrast theme, black on the Highlight cyan, 13.76:1 (step text
included). Looked at the shot in both. Pinned in `test_the_contrast_theme_fills_and_rings_follow_spec_10_4`.

### F7 - the year page's rows start 24px below the H1 (fixed)

`pagesYear` puts a `page-gap` (`--sp-6`) between the H1 and the list, as Reminders does. Measured:
H1 bottom 100, first row top 124 (24px), the same as Reminders under its page top. Test:
`test_the_year_page_leaves_a_gap_under_its_h1_before_its_rows`.

### F8 - the tests that were missing (added; each proved by mutation on a scratch copy)

- `tests/test_shell.py`: the skeleton test's `gone` list adds `review-deck`, `review-mode`,
  `mode-toggle`, `deck`; `test_the_renderer_defines_none_of_the_names_section_13_removes` (every
  removed name, the deck's stored key, `.mode-toggle` / `.deck` / `--radius-pill` / `.chip` in
  the stylesheets);
  `test_no_page_draws_a_path_as_text_or_as_a_tooltip` (all seven pages drawn in node from data
  whose paths hold `\` and `/`, one return the list does not know; no drawn text, attribute or
  tooltip holds either, and the names that must be there are);
  `test_every_loud_failure_of_the_old_screen_reaches_a_notice` (the call sites: reader and
  machine warnings, after-install, folders skipped, names shortened, lock, the household notices);
  and the F2/F3 tests above, which run the harness stub's long sentences through the app's own
  notice functions (dropping the reader, folders-skipped, names-shortened or after-install
  notice, or drawing a long sentence or a path, fails).
- Mutations (scratch copy of the tree, `git init`; each run over `test_shell`,
  `test_single_source`, `test_pilot_ui`, `test_api`): see the table at the end of this file.

## Fields `pages.js` reads (SPEC 9.2; for the job that fixes the real `firm` reply)

- `list`: `households[].{name, path, contact, returns[].{path, return_name, label, year, active, superseded_by}}`
  (through `shellHousehold` / `shellReturn`).
- `firm`: `returns[].{path, household, counts.{needs_you, waiting, received, set_aside}, oldest, due,
  draft.{ready, stage, held, drafted}, problem}`, `files[].{return, name, code, received, suggestion, handle}`,
  `totals.{need, waiting, complete, files, drafts}`, `next_sort`. `files[].return` is read as the
  return's **path** and `files[].handle` must exist (both differ in S1's real reply, review 1's list).
- `state`: `paths.engagement`, `engagement.due`, `household.{path, shared_on, open_years, pause.{sentence, scope},
  feeds[].warning}`, `items[].{identifier, document, short_name, group, status_key, manual_override, year,
  period, file_count, expected_count, received_date}`, `index[].{handle, original_name, decision, code,
  received, bucket, identifier, answered}`, `review[].{handle, shortlist[].identifier}`,
  `moved[].{handle, original_name, identifier, in_request}`.
- Vocabulary: `vocab.screen.*` (SPEC 11.4), `vocab.reasons[code]` (`{short}` or a string),
  `vocab.reminder.stages[].{number, short}`, `vocab.labels[key].label`, `vocab.decisions`,
  `vocab.review_labels.{bucket_order, buckets, dismiss}`, `vocab.household.{two_open_years,
  accept_folder_name}`, `vocab.notices.about`, `vocab.shell.page_error`, `vocab.after_install.{heading,
  wait}`, `vocab.lock.{running, running_other, left_behind}`, `vocab.room.heading`, `vocab.menu.{new_household,
  add_return}`, and (new, optional until S6) `vocab.screen.notices.{reader, machine, renamed, paused, feed}`.

## Not done (out of scope, left for S5 / S6)

Link kinds and the year on return names (rulings 8-13) are S5's. The real `firm` reply mismatches
(review 1's list for S6) are another job's.
