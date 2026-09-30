# Shell S4 - the pages: review 2 (of rebuild 1)

Reviewer: a separate opus session (high effort) that built neither S4 nor its rebuild, 2026-09-29/30.
Branch `claude/shell-s4-pages`, reviewed at `a89a2bf` (rebuild 1: code `50940f6`, docs `a89a2bf`; the WIP
commit `6f34779` judged only through the tip). Diff read: `git diff 977d7ae...HEAD`.
Against: SPEC-shell as synced (`claude/shell-spec-sync`: 6, 9.1-9.2, 10.4, 11.1-11.5, 14), review 1,
the rebuild handoff, S4's handoff, Jason's rulings and the ledger (link kinds, Title Case and the year on
return names are S5's; not reported), and S1's real API (`claude/sharp-goldberg-jmfynk`: `tracker/api.py`
`_cmd_firm`/`_firm_row`/`_state`, `ocr.py`, `households.py`, `runner.py`, `settings.py`,
`after_install.py`; `pilot/handoffs/shell-S1-rebuild-3.md`).

## What I ran

- Tests, each file its own process, 3.11 (`/tmp/v`) then 3.13 (`/tmp/v313`), one version after the
  other, at `a89a2bf`: `test_shell` 57, `test_pilot_ui` 11, `test_tour` 8, `test_pilot` 18,
  `test_single_source` 165, `test_layers` 29, `test_api` 368, `test_pilot_installer` 12,
  `test_row_columns` 26, `test_repo_map` 80 - **all pass on both**. `ruff check .` clean;
  `repo_map.py check` current. After my two fixes (F1, F3) the tests they touch were run again on both
  versions (listed at the end).
- `interact.mjs`: "all interactions pass". `shoot.mjs`: 125 shots, real `app.js`, 0 page errors, 0 logged.
  I looked at Overview, Needs review, Reminders, Clients, household, year, return (and its Set aside
  open), loading, locked, household notices and the contrast themes, light and dark, at 1100x700 and
  1400x900.
- My own Playwright probe of the **real** `app.js` on the harness, wrapping `window.tracker.call` to
  mutate `state` and `firm` replies and to answer two writes (`mark-shared`, `accept-folder-name`).
- 21 mutations on a scratch copy (`git init`), run against `test_shell` + `test_pilot_ui` (and
  `test_single_source` for two).

## Review 1's findings, re-checked in code and in the browser

| | Verdict | What I saw |
|---|---|---|
| F1 one bad row | **Fixed** | Browser, return page, each mutation alone: an item with no `group`, `group: null`, no name and no group, an unknown `status_key`, an unknown reason `code`, an index row with no `group` - each time 17 of 18 rows drawn (the index row: 18, it is set aside from the groups), every group heading kept, **one** notice naming the row (`"{row}: {page_error}"`, no Retry), the error with its stack in the error log, no page error. `pagesTally` never threw on those; a replaced `pagesTally` that throws, and a menu channel that throws, are caught in `shellStateArrived` (one notice, no Retry). After a **write** (`mark-shared`, `accept-folder-name`) whose reply carries a group-less item, a throwing tally or a throwing menu: the write returns normally, the page is drawn, the notice has **no Retry** - never the write's failure. A row with no name but a good group is drawn with an empty name (the engine never sends one). See the notes for a `null` row. |
| F2 lock | **Fixed** | "In use on OFFICE-PC" only, with the stub now carrying S1's real `on` and `greyed` sentences and a `pass`; "Stuck lock from OFFICE-PC" for the stale one. |
| F3 short words | **Fixed, one part survived (F1 below, fixed here)** | Every notice is at most five words with no path over S1's long sentences; each long sentence reaches the error log once. The stub's long sentences are S1's, constant for constant (`READER_PATH_WARNING`, `runner.LEFT_BEHIND`, `settings.PROGRAM_ON_REMOVABLE`, `HOUSEHOLD_PAUSED`, `FEED_UNRESOLVED`, `FINDINGS_WAIT`, `LOCK_ON`, `LOCK_GREYED`, `TWO_OPEN_YEARS_NOTE`, `ACCEPT_FOLDER_NAME_LABEL`) - **except** `after_install.heading` (F3 below, fixed here). Each notice is its own line (the key now counts in `notice()`), but see F2 for what those lines say. |
| F4 unreadable household | **Fixed** | Clients: "Lopez Household · Could not be read" in `is-attention`, listed under Work waiting; the Overview row leads with it and the figures count it under Need a person. |
| F5 Set aside | **Fixed** | Shut on first open; kept open across `shellDraw()` and across a write's redraw; shut again after Overview → return and after household → return. (An early probe that redrew in the same task as the click read it shut: the `toggle` event is queued; not a defect.) |
| F6 contrast | **Fixed** | Forced colours emulated, focused row on the return page: light theme, every part `rgb(255,255,255)` on Highlight `rgb(5,0,73)`; dark theme, every part `rgb(0,0,0)` on Highlight `rgb(0,230,255)`, "Check ›" included, at both sizes. Looked at both shots. (For the 150 ms `background-color` transition the text is HighlightText on the old fill; reduced motion sets it to 0.) |
| F7 year gap | **Fixed** | First row 24px under the H1. |
| F8 tests | **Fixed** | Re-ran 21 mutations; all caught (below). |
| Coordinator: files by `index[].group` | **Fixed** | Smith return: `pagesTally(state)` = the firm's counts `{needs_you 6, waiting 2, received 6, set_aside 4}`; opening it reads `firm` no second time (interact.mjs, and my own count); `lost-in-move.pdf` (a moved file marked missing, `group: "set_aside"`) is under Set aside, status "Moved by hand", **no step**; `old-scan.pdf` (Not requested) keeps Check. |

### The fields the pages read against S1's real `firm` reply

S1's `_firm_row`/`_cmd_firm` send `returns[].{path, household, year, counts.{needs_you, waiting,
received, set_aside}, files, oldest, due, draft.{ready, stage, held, drafted}, problem}`,
`files[].{return, year, name, handle, code, received, suggestion}` (`return` is `row["path"]`),
`totals.{need, waiting, complete, files, drafts}`, `next_sort`. `pages.js` and `shell.js` read
`returns[].{path, household, counts.*, problem, oldest, due, draft.{ready, stage, held, drafted}}`,
`files[].{return (as the path), name, suggestion, code, received, handle}`, `totals.{need, waiting,
complete, files, drafts}`, `next_sort`, and **not** `year` - the builder's claim holds. **No field the
page reads is missing from the engine's reply.** The join to the return name is through `list`
(`engagements[].path` → `return_name`, which S1 sends; `households[].name` is the folder's name, so
Clients' join of `firm.returns[].household` to `households[].name` is by a unique key). `state` fields
read (`items[].group`, `index[].{group, code, bucket, handle, decision, answered}`, `moved[]`,
`review[].shortlist[]`, `household.{pause.{sentence, scope}, feeds[].warning, shared_on, open_years}`)
are all sent by S1's `_state`/`_household_payload`/`_pause_payload`. The Needs you group draws moved
rows from `state.moved`, which S1 builds from exactly the entries `file_group` puts in Needs you with
decision File Moved (`FILE_MOVED and not marked_missing`), so the draw and the tally agree.

### Mutations re-run (scratch copy, each alone)

Caught: deck markup back in `#legacy`; return name falls back to the raw path; household caption carries
`route.household`; reader notice dropped; reader sentence not logged; reader notice draws the API's
sentence; names-shortened notice dropped; folders-skipped notice dropped (deleting the call); after-install
notice dropped; lock notice appends `greyed`; machine detail not logged; pause detail not logged; F5 reset
removed; `shellStateArrived`'s catch removed; tally counts by decision; Set aside draws only dismissed
files; F6 CSS removed; F7 gap removed; a failed draw empties the page; an unreadable household is Complete
on Clients; broken rows not reported. **Not caught**: the folders-skipped call left in place but guarded
(`if (0) keyedNotice("misfits", ...)`) - `test_every_loud_failure_of_the_old_screen_reaches_a_notice` is a
static substring read, so a guard or an early return passes it. Deleting the call is caught; I note it
rather than call it a finding.

## Findings

### F1. A notice word the vocabulary lacks was replaced silently (review 1 F3's "loud if missing" survived) - **fixed here**

- **Where:** `app/renderer/shell.js:75-83` (`shortNotice`), read by `app.js:1890`, `:1894` and
  `pages.js:677`, `:682`.
- **SPEC / review 1:** review 1 F3's fix, "S4 reads them, loud if missing"; the pages' own rule (pages.js
  header) "a word the vocabulary lacks is a loud failure, never a guess".
- **What the code did:** with no `vocab.screen.notices.{reader, machine, renamed, paused, feed}` (none of
  the five exist in S1's vocabulary) it drew `after_install.wait` and said nothing anywhere that a word
  was missing - the long sentence went to the error log, but nothing told the reader of the log that
  "Setup needs attention" stood in for a missing key.
- **Fix made:** `shortNotice` keeps the fallback on screen (a thrown error would lose the notice itself)
  and writes the missing key (`vocab.screen.notices.reader`, ...) to the error log once per key while the
  app runs. `test_a_notice_whose_short_word_the_vocabulary_lacks_falls_back_to_the_setup_line_and_logs_the_sentence`
  now also asserts each missing key is logged once over two draws; deleting the log line fails it
  (checked on the scratch copy).

### F2. On S1's real vocabulary five different loud failures all read "Setup needs attention" - blocking before the Windows check (S6/S1, not S4 code)

- **Where:** `shell.js:75-83` (the fallback), `app.js:1888-1895`, `pages.js:675-682`; S1
  `tracker/api.py` `SCREEN["notices"]` (line 1297) holds only `firm_failed, skipped, show, no_log, drive`,
  and `AFTER_INSTALL_HEADING` (line 5005) is also "Setup needs attention".
- **SPEC:** 2.2 E28 "Install folder name too long", E30 "one line each", E47 "Folder renamed" · "Accept";
  6.5 (the feeds notice); 11.4 lists no key for any of them (only `notices.drive`, "the machine warning's
  short line", which would be false for S1's two machine warnings, both about files left behind or the
  program's drive).
- **What it does (seen, real `app.js`, S1's words):** a return page with the reader warning, machine
  warnings, an after-install failure, a year pause and an unresolved feed shows **five identical
  "Setup needs attention" lines** (one red, four amber) under "3 folders skipped"; on a household page
  the renamed-folder pause - the notice that means the household's sorting has stopped - reads "Setup
  needs attention" with a button "Accept the folder's name". A person cannot tell the lines apart or
  which to act on without opening the error log. Each is its own line, so nothing is lost, and no word is
  invented: acceptable while the pages are built, **not acceptable for the pilot**.
- **Smallest fix (S6 with S1's words, Jason approves them):** add `screen.notices.reader`
  ("Install Folder Name Too Long", E28), `renamed` ("Folder Renamed", E47), and words for `paused` (a
  year's pause), `feed` and `machine` to S1's `SCREEN` in Title Case, list the five in SPEC 11.4, and pin
  them with one test (every key `shortNotice(...)` is called with in the renderer exists in `api`'s
  vocabulary). Better for E30: S1 sends a code per machine warning (`left_behind_warnings` already has
  one) so each has its own line; until then the renderer's single machine line is the honest choice.

### F3. The harness stub said S1's after-install heading was "After installing: needs a person" - **fixed here**

- **Where:** `pilot/harness/stub.js:71` (now 71-72).
- **SPEC / review 1:** review 1 F3, "make the stub carry the API's real sentences so the harness shows the
  truth"; the stub's comment claims S1's words "constant for constant".
- **What it did:** S1's tip has `AFTER_INSTALL_HEADING = "Setup needs attention"` (api.py:5005), the same
  words as the fallback; the stub's older heading hid that the harness's `notices` scenario shows three
  identical lines, not two plus a different one.
- **Fix made:** the stub's heading is S1's. `test_shell` and `interact.mjs` pass with it.

## Notes for S5/S6

1. **Legacy renderers are outside F1's guard.** `render()` (`app.js:363-372`) runs `renderHousehold`,
   `renderMoved`, `renderReview`, `renderUnfileList`, `renderLock`, `renderReminder` before
   `shellStateArrived`. A `null` row in `items` or `index` throws in `renderMoved` (`app.js:672`) - on a
   read the return falls to its frame with the page-error notice and Retry; after
   `accept-folder-name` the **write's** failure notice with a Retry that would send the write again. The
   engine never sends a `null` row, so this is not reachable today; when S5 lifts those cards into the
   sheet, keep what runs after a write's reply inside the same catch as `shellStateArrived`.
2. **Stub shapes S5 will lean on:** the harness `firm` has no `files[].handle`, `files[].year` or
   `returns[].year` (S1 sends all three; `stub.js:282-283`), so a Check from Needs review in the harness
   passes `handle: undefined`; and its moved rows carry `identifier: ""`, so "northwind-2025.pdf" shows no
   request in its detail (SPEC 6.7 "detail = its request"). Add them when S5 builds the sheet on the stub.
3. **A menu channel that throws** (`window.tracker.menu.send`) escapes `shellGo` (`appRouteChanged` /
   `shellEnable` are outside any catch) and stops navigation; after a write it is caught. Electron's
   `ipcRenderer.send` does not throw in practice; S6 may wrap `shellEnable` if the join wants it.
4. `test_every_loud_failure_of_the_old_screen_reaches_a_notice` is a static read (a guarded call passes);
   the behavioural notice tests cover reader, machine, lock, after-install, pause and feed, not misfits
   or room. A vm run of `renderMisfits`/`renderShortOfRoom` would close that.
5. Review 1's notes still stand: the status column's "Came in email or z…" cut in DejaVu (look on
   Windows); a paused household is visible only on its own pages; the `/tmp/Real root` clash in
   `test_api` when two runs share the temp folder (running the versions one after the other avoids it).

## Gate after the fixes

Changed: `app/renderer/shell.js` (shortNotice), `tests/test_shell.py` (the fallback test),
`pilot/harness/stub.js` (one heading), this file, the repository map. Re-run on 3.11 then 3.13, each file
its own process: `test_shell`, `test_single_source`, `test_layers`, `test_pilot_ui`, `test_api`,
`test_repo_map`; `ruff check .`; `interact.mjs`; `repo_map.py update` and `check`.
