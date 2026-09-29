# Shell S4 - the pages (built)

Session: S4 builder (sonnet), 2026-09-29, **resumed** after a container restart cut
the first session off mid-build. **Branch: `claude/shell-s4-pages`**, built on S3's
clean tip `afd566d` (S3's review 3 said "No findings"). The last code commit is named
on the last line of this file. Nothing here is reviewed yet.

How this went: the first session left a work-in-progress commit (`86910d1`) with no
handoff. This session treated all of it as unchecked, audited it against the SPEC,
found and fixed what was wrong (below), finished what was missing and gated it.

## Done, in plain English

Every page of SPEC section 6 is drawn by the new `app/renderer/pages.js`, and the
old cards that drew them are gone. You open the app on the Overview (three figures
and "Work waiting", one row per return); Needs review (one group per return with
files waiting); Reminders (one list of drafts ready); Clients (a two-option switch,
Work waiting or All, and one row per household - 500 draw in one pass); a household
(its years, newest first, or "No returns yet" with "Add a return..."); a year; and a
return (Needs you, Waiting on client, Received, and a closed Set aside, each from
the API's `group`; only Received is drawn when empty). Firm pages have no H1; the
household, year and return pages open with one. Every row is the row of SPEC 3.6:
name, detail, one status word in its colour, and an end column that holds the date
and, on hover or focus, the row's one step. Each group is one listbox (one Tab stop,
Up/Down/Home/End/PageUp/PageDown, Enter runs the step, click selects, click on the
step or double-click runs it).

The old screen lost: the toolbar and the return picker, the banners, the request
table with its chips, the household card, the setup card, the misfits and room
cards, the after-install box, the lock box, `#banner`, and the review deck (the
Cards/List toggle and everything behind it). Every loud failure that lived in those
boxes is now a notice: the reader warning, each machine warning, the after-install
failure ("Setup needs attention", its lines to the error log), the lock ("In use on
{host}", or the stuck-lock one), folders skipped (with Show), names shortened to
fit, two years open, folder renamed (with Accept), and feeds that do not resolve.
The result banner is gone (a toast, or nothing: what went well shows in the rows);
"Clients folder set to..." is gone (SPEC E27); the last-pass line is the side
panel's "Sorted 6:00 AM" / "Sort failed" (SPEC E29 - it is kept and moved, not a
notice, and the failed sort's own notice with Retry stays).

| SPEC section 16, S4's row | Where |
|---|---|
| `pages.js`: every page and state of section 6 | `app/renderer/pages.js` (loaded between `tooltip.js` and `shell.js`) |
| the one row and group of 3.6 (listboxes, shared date-or-step end column) | `pagesRow`, `pagesGroup`, `pagesList`, `pagesKey`; rules in `shell.css` |
| grouping of state by `group` | `pagesReturnGroups` (an item with no `group` throws: nothing is guessed), `pagesTally` |
| card renderers out of `app.js`, markup out of `index.html` (section 13's table) | `app.js` (about 1,000 lines fewer), `index.html`, `style.css`, `pilot-ui.css` |
| the tests 14.2 lists that follow the cards, and 14.1's node tests of the pages | see "Tests" |

Also done, from S3's list for S4: `RETIRED` in `test_shell.py` is now `(".review", ":root")`;
`app.js` and `index.html` are in `TITLE_FREE`, `pages.js` in `SHELL_FILES`; the notice
template's buttons are Retry and the close icon; `--radius-pill` and the `.chip` rules are gone.

## What I found wrong in the first session's attempt, and fixed

- A household page never read its return's `state` when the active return already
  belonged to it, so its notices (two years, folder renamed, feeds) never appeared and
  "Shared" never showed. `shellOpenState` now reads the state unless the one on screen
  is one of that household's.
- The bucket sub-headings drew the API's long sentences ("Emails and zips - opened,
  if at all, ..."). SPEC 2.5 E68 wants the words alone. The renderer is right (it draws
  `vocab.review_labels.buckets`); S1 must cut those strings (see "For S6"); the harness
  stub now carries the short ones.
- `applyVocabulary` still set the deck's two buttons after their markup was deleted:
  the real app died at start-up ("The app met an error of its own"). Fixed; new test
  `test_every_element_the_renderer_looks_up_by_id_is_in_the_page_or_built_by_it` finds any such id.
- A return whose record could not be read (a `firm` row with `problem`) had zero
  counts and so was left off the Overview. It now leads the "Need a person" rows,
  saying its problem.
- The Edit step was silently a no-op while a return is locked. The row now simply does
  not offer it (as the menu's Edit request list is grey).
- A row's detail and status were cut with "..." and no tooltip; all three text columns
  now carry the full text when cut.
- The deck (`renderDeck`, `deckCard`, `acceptCard`, `skipCard`, the review mode and
  its stored key, `.deck*` and `.mode-toggle` rules, `#review-mode`, `#review-deck`)
  was still in `app.js`; removed (SPEC 13, 14.3).
- Several tests still read the removed cards (listed under "Tests").

## Tests

Python 3.11 (`/tmp/v`) and 3.13 (`/tmp/v313`), each file its own process, in parallel:

| File | Result on both |
|---|---|
| `test_shell` | 41 passed (was 32; 9 new) |
| `test_pilot_ui` | 11 passed |
| `test_tour` | 8 passed |
| `test_pilot` | 18 passed |
| `test_single_source` | 165 passed |
| `test_layers` | 29 passed |
| `test_pilot_installer` | 12 passed |
| `test_row_columns` | 26 passed |
| `test_api` | 368 passed (six card tests of the 14.2 table were fixed first). On 3.13 one test, `test_every_command_that_reads_the_root_rechecks_it`, hit a `/tmp/Real root` name clash with the 3.11 run going at the same time; alone it passes |
| `test_repo_map` | passes on the final tree, after `repo_map.py update` and `check` (run last, so the map covers this file) |

`python -m ruff check .` is clean. `interact.mjs`: "all interactions pass" (now 51
checks; it drives the rows by keyboard and mouse, the Clients switch, a household's
notices, and a locked return). `shoot.mjs`: 125 screenshots, "0 page errors, 0 logged,
no visible error" on the real `app.js`. I looked at Overview (full, empty, no
clients), Needs review (full, empty), Reminders, Clients (Work waiting, All, none
waiting, empty), household (full, no returns, with three notices), year, return
(four groups, Set aside open, active row with its step, nothing received, locked,
stuck lock), light and dark, 1100x700 and 1400x900, and the Overview against
`mockup-shell.html` in Chromium. `test_build`'s OCR scratch-roots test fails on the
base; not run.

New tests in `tests/test_shell.py` (each names its claim):
`test_a_return_page_draws_its_groups_in_order_and_leaves_out_empty_ones_but_received`,
`test_a_returns_needs_you_group_holds_parked_files_then_moved_then_requests_then_the_buckets`,
`test_the_pages_groups_and_the_firms_tally_of_them_cannot_disagree`,
`test_the_overview_puts_each_return_in_one_bucket`,
`test_a_row_carries_one_step_and_its_status_word_and_no_sentence`,
`test_long_names_are_cut_and_carry_their_full_name_as_the_tooltip` (60 and 80 characters),
`test_only_the_household_year_and_return_pages_draw_an_h1`,
`test_the_household_pages_notices_are_two_years_folder_renamed_and_feeds`,
`test_every_element_the_renderer_looks_up_by_id_is_in_the_page_or_built_by_it`.
They run pages.js's own functions in node against a small fake DOM
(`run_pages_dom`, `FAKE_DOM`), and `run_pages` lifts plain functions.

**Mutation checks (each made a test fail, then was undone):** (1) drop the "a group with
no rows is left out" rule for Waiting on client - the return-page test fails; (2) offer
the Edit step while locked - the row test fails; (3) sort a problem return like any
other on the Overview - the bucket test fails; (4) name a deleted id in `app.js` - the
id test fails.

Tests changed on purpose (14.2): `test_shell` (skeleton, icons, RETIRED, TITLE_FREE);
`test_single_source` (`_run_renderer` lifts `tipped`; the status-label test reads
`pages.js`; the side-sentence and Accepted-word tests run `pagesReturnGroups`; the
one-call-site counts drop the deck; the review-mode key test goes, 14.3);
`test_api` (schedule dialog and Repair are menu items; machine warnings are notices;
the settings phone box is the setup page's; the chip-class test becomes "every status has
its row label"; the folded-rows test reads `pages.js`).

## What is left

- **S5** (sheet and dialogs): `openCheck(ret, name, handle)`, `openReminder(ret)`,
  `openMisfits()`, `pagesMenu(id, token)` and the right-click wiring. Until they exist a
  Check or Draft reminder step raises one notice through `unanswered()` (never silence;
  `interact.mjs` checks it). `pagesRowFor(token)` and `pagesFiles()` are for S5: the row
  behind a right-click token, and the Check steps in the order drawn (the sheet's next
  arrow). The reminder, moved, review and filed cards are still hidden in `#legacy`, drawn
  from `state` by `renderReminder`, `renderMoved`, `renderReview`, `renderUnfileList` so
  `reviewRow` and `movedRow` can be lifted into the sheet; S5 deletes each with its rules
  (`.review`, `.dismissed`, `.rem-*` in `style.css` / `pilot-ui.css`, and `RETIRED`). The
  roll fold is likewise still in `#legacy` for the roll dialog.
- Shift+F10 / the menu key on a row is the right-click wiring (S5); `pagesKey` handles the rest.
- Nothing about `pages.js` was run in Electron; the Windows check covers that.

## Things a reviewer should know

- A `firm` reply is the harness's stub; the shape follows SPEC 9.2 field for field.
  `pagesFirm()` throws if a firm page is drawn before the reply, and `shell.js` never draws
  one before it (it draws the loading state).
- Household caption: "Contact {name}" from `list`; "Shared" / "Not shared" from `state`, so it
  fills in when the household's first state arrives (a blink at most).
- The stuck-lock notice and the live lock notice are both keyed `lock`; a stale lock leaves
  Clear stuck lock enabled in the menu (`lockStale`), as SPEC 2.2 E32 asks.
- The status column is 160px; a long short-reason such as "Came in email or zip" is cut with "..."
  (full text in the tooltip). SPEC 11.5 sets those words; if Jason wants them uncut, either the
  words shorten or the column widens (the 1100px budget in 3.6 is exactly full).
- The two "For Jason" departures from S3 stand, unchanged: `tour.js` and `pilot.js` keep their own
  keydown listeners (SPEC 14.1 says one); no tooltip shows on a focused text box (SPEC 8.5).
- The last-pass line is not a notice (SPEC E29, "kept, moved"); the S4 brief listed it among the
  banners to turn into notices. If Jason wants a notice as well, it is one call in `loadEngagements`.

## Proposed decision rows (S6 logs them from the next free number after S3's)

1. Every group on a return's page is filled from the API's `group`; an item without one is a loud
   failure ("nothing is guessed"), never a guess from status.
2. The page is redrawn from data and never asks a question of the DOM it drew: `pagesDraw` keeps
   the listbox and row position across a redraw, so a write does not lose the person's place.
3. The Overview lists a return whose record cannot be read, first, saying its problem; it is
   never counted as complete.
4. The Edit step is not offered while a live lock holds the return.
5. A household's notices (two years, folder renamed with Accept, feeds) come with its state, so
   opening a household or year page reads the state of one of its returns when the state on
   screen is not one of theirs.
6. The review deck (Cards/List) is removed with its stored key and its API labels are unused
   (`CARD_MODE_LABEL`, `LIST_MODE_LABEL`, `card_position`, `accept`, `skip`, `open_in_list`).

## For S6 (join)

- `vocab.review_labels.buckets` must be the two words "Emails and zips" and "Not documents"
  (SPEC E68); today it holds long sentences. Also unused now: the deck's keys (list above) and
  `review_labels.card_mode`, `list_mode`; `test_api` and `test_single_source` still assert
  them until S1's wording change lands.
- `vocab.reasons[code]` is read as `{short}` or a string; `vocab.reminder.stages[i].short`;
  `vocab.household.two_open_years` and `accept_folder_name`; `vocab.room.heading`;
  `vocab.after_install.heading`; `vocab.lock.running`, `running_other`, `left_behind`, `on`, `greyed`.
- Docs that mention the removed screen (README, runbook, Tester Guide) are S1's/S6's.

## Files the next session needs

`pilot/SPEC-shell.md` (3.6, 5.3, 6, 7), this file, `app/renderer/pages.js` (its head comment lists
what it offers S5), `app/renderer/shell.js`, `pilot/harness/` (README, `stub.js`, `sheet-stub.js`),
`tests/test_shell.py`.



Last code commit: `92df828` on `claude/shell-s4-pages` (the commit after it only refreshes the repository map and this file).
