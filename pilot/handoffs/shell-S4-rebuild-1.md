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
