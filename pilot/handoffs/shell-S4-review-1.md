# Shell S4 - the pages: review 1

Reviewer: a separate opus session (high effort) that did not build S4, 2026-09-29.
Branch `claude/shell-s4-pages`, reviewed at `2006aad` (final state; the WIP commit
`86910d1` was judged only through what the tip holds). Diff read: `git diff afd566d...HEAD`.
Against: SPEC-shell 2.4-2.5, 3.6, 6, 9.2, 13, 14, 16 (`claude/admiring-lamport-bp1sse`,
identical to the branch's copy), `pilot/handoffs/shell-S3*.md`, and Jason's rulings
(`claude/amazing-maxwell-b4hdzo:pilot/handoffs/shell-rulings.md`: the tour's and pilot's
keydown listeners stand; focus tooltips and the 300 ms delay are S7's; failure text stays).

## What I ran

- Tests, each file its own process, 3.11 (`/tmp/v`) then 3.13 (`/tmp/v313`), one version after
  the other: `test_shell` 41, `test_pilot_ui` 11, `test_tour` 8, `test_pilot` 18,
  `test_single_source` 165, `test_layers` 29, `test_api` 368, `test_pilot_installer` 12,
  `test_row_columns` 26, `test_repo_map` 80 - **all pass on both**. `ruff check .` clean;
  `repo_map.py check` current.
- `interact.mjs`: "all interactions pass". `shoot.mjs`: 125 shots, the real `app.js` with
  0 page errors, 0 logged, no visible error. I looked at every page scenario, light and
  dark, 1100x700 and 1400x900, and set the Overview, Needs review, Reminders and return
  pages beside `mockup-shell.html` in the same Chromium at both sizes: layout, rows,
  groups, spacing and colours match the mock-up (one exception, F7).
- My own Playwright probe on the **real** `app.js` in the harness: every loud failure
  drawn as a notice (below), keyboard on a return's listboxes, a state with one item
  missing its `group`, the lock notice with the API's own lock words, the Clients page
  with an unreadable return, the Set aside fold across a visit elsewhere, dark and
  contrast theme (forced-colors emulated) on the Overview and a return, and every string
  the pages draw on all seven levels in both the double and the real app.
- Mutation checks on a scratch copy (a `git init` copy, so the git-reading tests run
  as on the branch). Caught: an H1 on the Overview; an H1 typed by hand on Clients; the
  folder-renamed notice dropped; its Accept dropped; a group-less item put in Waiting; the
  step not `aria-hidden`; an empty Received left out; a "Look again" button back in the
  notice template. **Not caught**: see F8.

### Loud failures, each seen as a visible notice in the browser (real `app.js`)

| Failure | On screen | Buttons |
|---|---|---|
| reader warning | "Install folder name too long" | close |
| machine warning | "Drive not signed in" | close |
| after-install failure | "Setup needs attention" (err); its lines went to the error log | close |
| folders skipped | "3 folders skipped" | Show, close |
| live lock | "In use on OFFICE-PC" | close |
| stuck lock | "Stuck lock from OFFICE-PC" (Clear stuck lock enabled in the menu) | close |
| two years open | "Two years open" | close |
| folder renamed | "Folder renamed" - on the household, the year **and** the return page | Accept, close |
| feed that does not resolve | "Feeds a return that is not there" | close |
| counts failed | "Counts not available" | Retry, close |
| last sort failed | the side panel foot, "Sort failed" in `--st-error` (SPEC E29/8.3: kept, moved; not a notice) | - |
| clients folder set | gone (E27) | - |

All show - **but every one of the first seven words in this table is the harness stub's,
not the API's** (`stub.js` 63-72, 235-236, 280-281 lay SPEC-short words over the real
vocabulary). With the words the real API sends, four of them are long sentences, one with
a path: F2 and F3.

## Findings

### F1. One item without `group` blanks the return page, and would make a write that worked say it failed

- **Where:** `app/renderer/pages.js:503` and `:581` (throw), `app/renderer/shell.js:246-248`
  (`pagesTally` outside any `try`), `app/renderer/app.js:367` (`render` calls it last),
  `pages.js:656-662` (`pagesDraw`'s catch).
- **SPEC:** 9.1 (group from the API, nothing guessed); 6 "Failed read: ... the page keeps
  what it last drew; with nothing drawn yet, it draws only its frame". The brief: loud and
  safe, and one bad row must not blank a page.
- **What the code does (seen in the browser):** a `state` with one item lacking `group`
  throws in `pagesTally` from `shellStateArrived`, which escapes `render()`, `renderFor()`
  (skipping `applyLock()` and `outlineRefused()`) and lands in `showReturn`'s catch: the page
  becomes the H1 alone, with "The app met an error of its own (Error)..." and a Retry that
  fails the same way. Every other row of the return - the parked files included - is gone.
  The same escape after a **write** (every write reply goes through `renderFor`) would put the
  write's own failure notice on a write that succeeded. Separately, any throw inside
  `pagesBuild` (e.g. `pagesReason` for a code the table lacks, `pages.js:97`) makes
  `pagesDraw` replace the page with nothing - not even its frame. Nothing is guessed, and it
  is loud; it is not safe.
- **Smallest fix:** in `pagesReturnGroups` and `pagesTally`, set an item with no known group
  aside (drawn in no group, counted in none) and collect it; `pagesDraw` draws the rest and
  raises one notice for the set-aside items (the page-error sentence) with their identifiers
  in the error log. In `pagesDraw`'s catch, keep the children already on the page (or draw
  the frame, `drawTitleOnly`) instead of `replaceChildren()` with nothing. Pin it with a node
  test: a state with one group-less item draws the other rows and says one notice.

### F2. The lock notice appends two of the API's sentences to "In use on {host}"

- **Where:** `app/renderer/app.js:1668-1670`; masked by `pilot/harness/stub.js:70-72`.
- **SPEC:** 2.2 E31 "Notice, one line: In use on {host}"; `wording-shell.tsv` row 80 cuts
  `lock.greyed` ("the greyed controls show it").
- **What the code does:** `said.push(fill(words.on, lock.pass))` and `said.push(words.greyed)`,
  joined. The stub sets `on` and `greyed` to "" so the harness shows the short line. S1's API
  still sends `LOCK_ON` ("It is on {household}: {name}.") and `LOCK_GREYED` (a 19-word
  sentence). With those words restored in the browser the notice reads: "In use on OFFICE-PC
  It is on Smith Family: 1040 - John & Jane Smith. This return's buttons are greyed while it
  runs and come back by themselves the moment it lets go." (28 words.)
- **Smallest fix:** say only the `running` / `running_other` line (delete the two pushes);
  drop `on: "", greyed: ""` from the stub's override so the harness shows what the app will.

### F3. Four notices draw the API's own sentence where SPEC section 2 names a short line; one carries a path

- **Where:** `app/renderer/app.js:1862` (reader), `:1864` (machine warnings),
  `app/renderer/pages.js:601-603` (folder renamed), `:605` (feeds). Masked by
  `pilot/harness/stub.js:235-236` and `:280-281`.
- **SPEC:** 11.1 (five words, no path of any kind); E28 "Notice, no path: Install folder
  name too long"; E30 "Notice, one line each; details to the error log"; E47 "Folder
  renamed" · "Accept"; 6.5 (feeds notice).
- **What the code does:** draws the reply's sentence verbatim. With S1's API
  (`claude/sharp-goldberg-jmfynk`): the reader warning is `ocr.READER_PATH_WARNING`, "Move the
  app to a shorter folder, for example C:\JPA Tracker; ..." (a path on screen); a machine
  warning is a full sentence (`_machine_warnings`, a `SettingsError` text can name a folder)
  and nothing goes to the error log; the pause is `households.HOUSEHOLD_PAUSED`, about 45
  words; a feed is `households.FEED_UNRESOLVED`, "this drop folder is set to feed {household}
  / {return_name}, which has no active return for {year}". The folder-renamed notice is the
  one that pauses a household's sorting, so it must stay loud - it does - but in the SPEC's
  words. `test_api::test_the_first_screen_says_every_machine_warning_in_a_notice_of_its_own`
  and `test_shell::test_the_household_pages_notices_are_two_years_folder_renamed_and_feeds`
  pin the verbatim drawing, so they pass.
- **Smallest fix:** as `renderAfterInstall` already does: show a vocabulary word and send the
  sentence to `window.tracker.logError`. Words needed (S6 adds the keys to S1's vocabulary; S4
  reads them, loud if missing): the reader's "Install folder name too long", a machine
  warning's short line (only `screen.notices.drive` exists; the API should send each warning's
  code - `left_behind_warnings` already yields one - so each has its line), "Folder renamed",
  a line for the year pause (`HOUSEHOLD_PAUSED_YEAR`, no Accept), and one for an unresolved
  feed. Make the stub carry the API's real sentences so the harness shows the truth, and
  change the two pinning tests to assert the word on screen and the sentence in the log.

### F4. The Clients page calls a household whose record cannot be read "Complete"

- **Where:** `app/renderer/pages.js:357-360`.
- **SPEC:** 9.2 / 6.1: a return whose record cannot be read is never counted complete (the
  Overview and the household page do this right through `pagesCounts`).
- **What the code does (seen in the browser):** with one return set to `problem: "Could not
  be read"` and zero counts, its household is listed under Work waiting (`work` is true) with
  the status "Complete" in `--st-done` green.
- **Smallest fix:** when no return needs you and one has `problem`, say that return's
  `problem` in the `needs` tone (as `pagesCounts` does); add the case to
  `test_the_overview_puts_each_return_in_one_bucket` or its own test.

### F5. The Set aside fold stays open when the person comes back to the return

- **Where:** `app/renderer/pages.js:563-570` (`pagesSetAsideFor` is reset only by another return).
- **SPEC:** 6.7 "a `details` element, shut each time the page opens".
- **What the code does (seen):** open the fold, go to the Overview, open the same return:
  the fold is open.
- **Smallest fix:** in `pagesDraw`, clear `pagesSetAsideFor` when the route drawn is not the
  return drawn last (kept across redraws of the same page, as now).

### F6. Contrast theme: the focused row's step keeps the page's link colour on Highlight

- **Where:** `app/renderer/shell.css:415` (`.row-step:not(.hidden) { color: var(--link) }`,
  specificity 0,2,0) outranks the forced-colors rule at `:656` (`.row-step { color: inherit }`,
  0,1,0); the focused row has `forced-color-adjust: none`.
- **SPEC:** 10.4 (system colours in a contrast theme).
- **What it does:** in both emulated contrast shots the "Check ›" step on the focused row is
  navy (light) or pale blue (dark) on the Highlight fill - barely readable. S3 wrote the
  rule; S4's rows are what show it.
- **Smallest fix:** in the forced-colors block, `.rows:focus-visible .row.is-active .row-step
  { color: HighlightText; }`.

### F7. The year page's rows sit straight under its H1

- **Where:** `app/renderer/pages.js:435-441`.
- **SPEC / mock-up:** 3.6 (a group's rows start `--sp-6` below what precedes them); the
  mock-up's `yearPage` puts a `group-head first` spacer between the H1 and the list.
- **What it does:** the first row starts 8px under "2025"; every other page leaves 24px.
- **Smallest fix:** the Reminders page's `page-gap` between the title and the list.

### F8. The tests miss the removals and the no-path rule

- **Where:** `tests/test_shell.py:342-346` (the skeleton test's `gone` list) and the pages' node tests.
- **SPEC:** 13 (the deck removed), 14.3, 11.1 (no path), 2.2 (the loud failures are notices).
- **What the mutations showed:** these pass the whole affected set (test_shell,
  test_single_source, test_api, test_pilot_ui): putting back `#review-deck` and `#review-mode`
  in `#legacy` with a `renderDeck` and `REVIEW_MODE_KEY` in `app.js`; `pagesReturnName` falling
  back to the raw path; the household caption carrying `route.household` (a path); a file path
  appended to the lock notice; the reader-warning notice dropped; the misfits notice dropped.
  (Results for the machine, room and after-install notices dropped are in the note under
  "Notes for Jason".)
- **Smallest fix:** add `review-deck`, `review-mode`, `mode-toggle`, `deck` to the skeleton
  test's `gone` list and a test that `app.js` defines none of section 13's removed names; a
  node test that draws each page from list/firm/state data whose paths contain `\` and `/`
  and asserts no drawn text or tooltip holds either; one test that each loud failure of the
  table above reaches `notice`/`keyedNotice` (a static read of `loadEngagements`,
  `renderMisfits`, `renderShortOfRoom`, `renderAfterInstall`, `showLock`, `pagesHouseholdNotices`).

## For S6: where S1's real `firm` reply differs from SPEC 9.2 or from what `pages.js` reads

From `git show origin/claude/sharp-goldberg-jmfynk:tracker/api.py`, `_firm_row` and `_cmd_firm`:

1. **`files[].return` is the return's label, not its path.** S1: `"return": one.label` plus an
   extra `"path": str(one.path)`. `pages.js:304-326` groups by `file.return` and uses it as a
   path (`pagesFirmReturn`, `pagesReturnName`, the Check step's `ret`). On the real reply the
   Needs review headings would be the label ("Household · year · return"), the household
   caption would be lost, and Check would hand the sheet a label. Fix one side: S1 sends the
   path in `return` (the stub's shape), or `pages.js` reads `file.path`.
2. **`files[].handle` is missing.** `pages.js:323` reads `file.handle` for the Check step (the
   sheet needs it to find the file); 9.2 does not list it and S1 does not send it. S1 adds
   `handle` (and the row's `seq`, for the write), and 9.2 says so.
3. **`counts` count request rows only.** S1 fills `row["counts"]` from `items` alone, and adds
   parked and moved files only to `files` (and `totals.need` by `or row["files"]`). SPEC 9.1
   ("parked for a person and moved by hand are `needs_you`; set aside by a person ...
   `set_aside`"; "`firm` counts with it") and 9.2 (`files` is "of needs_you") count them in.
   `pages.js` follows the SPEC (`pagesTally` adds files). Seen in the browser with S1's shape:
   a return whose only work is two parked files is **missing from the Overview's Work waiting**
   and shows **"Complete"** on Clients and on its household page; and every `state` of a return
   with files differs from its `firm` counts, so `shellStateArrived` re-reads the whole firm
   (up to 3 s at 750 returns) each time one is opened.
4. `vocab.after_install.heading` is "After installing: needs a person" (SPEC E23: "Setup needs
   attention"); `vocab.review_labels.buckets` still hold the long sentences (E68; the S4
   handoff says so); the reader and machine warnings, pause and feed sentences have no short
   words (F3).
5. Field names that do match: `returns[].path, household, counts.{needs_you,waiting,received,
   set_aside}, files, oldest, due, draft.{ready,stage,held,drafted}, problem` (S1's word
   "Could not be read"), `files[].name, code, received, suggestion`, `totals.{need,waiting,
   complete,files,drafts}`, `next_sort` ("HH:MM"). `state.items[].group` and `state.index[].group`
   are sent; `pages.js` groups files by their `decision` and the `moved` list rather than by
   `index[].group` - consistent today, but a second rule; S6 may switch it to the API's field.

## Checked and found as the SPEC asks

- Every page and state of section 6: Overview (figures, Work waiting, empty with "Next sort"),
  Needs review (a group per return, caption household · count, empty), Reminders (one list,
  Held), Clients (switch at the keyline, Work waiting by default each visit, All with 500 rows
  from one fragment, both empties, the one New household... button), household (H1, "Contact
  ... · Shared", years newest first, Rolled forward / Inactive, No returns yet with Add a
  return...), year, return (the four groups in order, the bucket sub-headings, Received always
  with "Nothing received yet", Set aside a shut `details`), setup's frame, loading outline rows,
  sort failed, locked (Edit not offered, the notice), nothing waiting, empty groups left out.
- Firm pages draw no H1; household, year and return pages do (and wrap, never cut).
- Rows and groups of 3.6: `listbox`/`option`, one Tab stop, `aria-activedescendant`,
  Up/Down/Home/End/PageUp/PageDown and Enter (checked by key in the browser), click selects,
  step click and double-click run; `aria-hidden` step with `aria-description`; the date and the
  step share the 144px end column ("Draft reminder ›" measures 142px); `has-step`, the four
  tones. Grouping is by the API's `group`.
- Section 13: every removed name is gone (`chip`, `sideLine`, `requestTableRow`, `ruleTooltip`,
  `renderEngagements`, `returnReminderLine`, `renderSharing`, `banner`, the whole deck,
  `SCAN_LABEL`, `LOCKED_BUTTONS`, `--radius-pill`, `.chip`, `.mode-toggle`); the reminder,
  moved, review and filed cards and the roll fold are still in `#legacy` for S5.
  `setAsideHeading` stays because the request list editor uses it (right; 13 lists it for the
  card only). `cameFrom` stays inside `reviewRow`, which S5 lifts.
- Notice template: Retry and the close icon only. Icons: every icon-only control has
  `aria-label` and a tooltip. No `innerHTML`, no inline style, CSP unchanged, no network call,
  no document read, nothing sent. New CSS on grid steps and tokens; reduced motion holds.
- Five words: across all seven levels, the only strings over five words or holding a slash are
  made-up names (user data) - with the stub's words (F2 and F3 are what the API's words add).

## Notes for Jason

1. **Status column, "Came in email or zip".** In the cloud's Chromium the font is DejaVu Sans
   (no Segoe UI), about 12% wider; there the phrase measures 161px against the 160px column.
   In Segoe UI on the office PC it measures roughly 140px and fits. Of the 78 status words,
   21 measure over 160px in DejaVu; the longest ("Looks like wrong document", 217px here,
   about 190px in Segoe) will still cut on Windows, with the full words in the tooltip. My
   advice: **change nothing now**; look at the Needs you rows on the Windows check. If the
   cut is not acceptable there, the smallest change that keeps the 1100px budget is to take
   24px from the detail column and give it to status (detail 176, status 184) - not to widen
   the window's budget, and not to reword approved words.
2. **The last sort failing overnight** shows as "Sort failed" in red in the side panel foot
   only (E29 says kept and moved). SPEC 8.3's "(the notice has the rest)" could be read as a
   notice too; the builder asked. If you want one, it is one call in `loadEngagements`.
3. **A paused household is only visible on its own pages.** The folder-renamed notice (with
   Accept) shows on the household, year and return pages, as 6.5 says; nothing on the Overview
   or Clients says a household has stopped sorting. If that should be seen from the landing
   page, `firm` needs a `paused` flag per return (an S1/SPEC change, not S4's).
4. **The `/tmp/Real root` clash** (`test_api::test_every_command_that_reads_the_root_rechecks_it`)
   is not S4's: the test (unchanged since before the base) builds `demo_root.parent / "Real
   root"`, and `short_root` makes `demo_root` directly in the system temp folder, so two runs
   at once share that name. A per-run fix is one line (make `above` under a fresh
   `tempfile.mkdtemp(dir=demo_root.parent)`); I left it, as it is outside S4. Running the two
   Python versions one after the other avoids it.
5. The harness README's table does not list `interact.mjs` (it is run as the README's
   neighbour); a one-line row would help the next reader.
