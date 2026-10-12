# Pilot handoff

The pilot is Tax Document Console for a first batch of test firms: the
tracker, the Electron app that fronts it, and the Windows installer and check
kit in this folder. [`README.md`](README.md) says what it is and the rules for
this repository; [`SPEC.md`](SPEC.md) says what it builds.

## Where the record is

- **`main` is `401cdf4`** (pull request #36, the Mac re-run 1 fixes, P260-P263);
  this branch, `claude/ui-polish`, is cut from it and carries P264 (the UI
  review's no-brainers, built) and Jason's sixteen menu answers, P265-P280
  (recorded; their SPECs follow).

- **Decisions live in [`DECISIONS.md`](DECISIONS.md), rows P1 to P281.** The
  badge reads **Pilot 0.4** (P281, 2026-10-11): 0.3 plus the UI review's work. Code
  and tests cite those numbers, so a row is never renumbered or removed. Why
  a thing is the way it is: search the row, do not guess.
- **Pilot decisions never go in `docs/ROADMAP.md`**, which stays the
  original's log.
- **A SPEC is built from, not read for history.** The SPECs beside this file
  are cited by section from the code; each names the P-rows that built it.

## Current work

[`SPEC-ocr-scans.md`](SPEC-ocr-scans.md) Part A (P282), **built on
`claude/ocr-scans`** in commit `ff938b7`, not yet reviewed (the review is
Opus's, in a session that did not build it) and not pushed. Part B (P283) is
a separate build, stacked on this one, and is not started.

What Part A built, in the software's words: a scan or a photo that a request
accepts on its looser keywords now files under that request when the top of
the page shows the request's own form number, no other request accepted it,
the household's issuer rule passes, and the page names no other form as itself
and shows no other request's form number. The name on the page still has to
confirm a named request, and an unnamed one files by its keywords alone when
the page names nobody (Jason's ruling on Q1). Anything less parks as Read From
Scan Only, byte for byte as before. The reader's confidence floor is now the
product's own number (0.5, the same floor the reader already applied), and a
reading that comes back with no scores fails loudly. No keyword, catalog row,
store, event or cache version changed (`CACHE_VERSION` stays 13; the vocabulary
report rebuilt with no diff).

Gate, each file its own process, `.venv` (3.14) and `.venv311` (3.11), no
`-m "not corpus"`; every file passed under both:

| file | 3.14 | 3.11 |
|---|---|---|
| `test_router` | 89 passed | 89 passed |
| `test_filer` | 405 passed, 6 skipped | 405 passed, 6 skipped |
| `test_ocr` (the real reader ran, not skipped) | 44 passed, 4 skipped | 44 passed, 4 skipped |
| `test_backtest` | 21 passed | 21 passed |
| `test_content_check` | 114 passed, 1 skipped | 114 passed, 1 skipped |
| `test_api` | 505 passed | 505 passed |
| `test_runner` | 229 passed, 1 warning | 229 passed, 1 warning |
| `test_resident` | 39 passed | 39 passed |
| `test_reasons` | 58 passed | 58 passed |
| `test_layers` | 31 passed | 31 passed |
| `test_single_source` | 217 passed | 217 passed |
| `test_repo_map` | 82 passed | 82 passed |
| `test_tripwire` | 23 passed | 23 passed |
| `test_errors` | 83 passed | 83 passed |

Also: `ruff check .` clean; `repo_map.py update` then `check` exit 0 (the map
is in the same commit); `vocab_report.py build` (run with the `.venv`
interpreter, which has pytest) left no diff. The skips are the platform ones
already there (the Windows job object, `/proc`, a directory junction, and
the like). Not run here: the `pilot/mactest/run_checks.sh` sample-pile flow
(SPEC section 4's check that `Scanned forms.zip`'s scan files under its
1099-INT request with "name confirmed" in its reason) and a Windows check.

Where the SPEC and the code differed, none that stopped the build. Notes for
the reviewer:

- The SPEC's claim that `.gitignore` gains `.venv311/` in Part A's first
  commit was already done (`8a77916`); nothing to add.
- `test_a_scan_whose_form_number_is_only_below_the_title_parks_as_ocr_only`
  is built as the SPEC words it, but a verdict records only the best-placed
  of a row's matching looser keywords, so here it records `dividend` in the
  title and never `1099-div`. The test holds the park byte for byte, and it
  passes with guard 1 removed; guard 1's bite is shown by
  `test_a_sideways_reading_whose_title_lines_came_late_parks`, which fails
  when the title test is dropped. Each other guard was mutated once (guard 6
  both halves, the exactly-one test, the issuer exit) and its test failed.
- The two new filer tests each make two returns in separate roots: two
  image-only PDFs with no text are byte-identical, so a second scan dropped in
  the same return would be a Duplicate of the first, not a second reading.
- The real-reader test's quarter-turned page reads as "matched no request"
  here (the reader keeps the words but not the order); the test accepts
  parking or filing under the 1099-INT row and forbids the 1098 row, as the
  SPEC says.
- Tests added: router `test_a_scan_whose_title_shows_1099_int_files_on_the_rows_looser_keywords`,
  `test_a_scan_whose_form_number_is_only_below_the_title_parks_as_ocr_only`,
  `test_a_scan_two_requests_accept_on_their_titles_parks_with_both`,
  `test_a_scan_that_passes_the_title_guard_beside_a_loose_match_parks`,
  `test_a_sideways_reading_whose_title_lines_came_late_parks`,
  `test_a_scan_accepted_by_a_row_issuer_rows_narrow_parks_as_issuer_not_named`,
  `test_a_scan_of_last_years_1099_int_parks_and_never_files`,
  `test_a_scan_filed_on_its_form_number_carries_no_answers_and_no_split`,
  `test_a_scanned_1099_c_read_as_1099_g_beside_a_second_form_name_parks`,
  `test_a_scan_whose_page_shows_another_requests_form_number_parks`,
  `test_a_page_naming_only_its_own_form_files`,
  `test_a_page_naming_two_families_as_itself_is_decision_94s_and_never_reaches_the_scan_rule`
  (and the one rename); filer `test_a_scan_filed_on_its_form_number_still_needs_the_name_confirmed`,
  `test_a_scan_filed_on_its_form_number_into_an_unnamed_request_needs_no_name`;
  ocr `test_a_box_under_the_confidence_floor_is_not_read`,
  `test_a_box_at_the_confidence_floor_is_read`,
  `test_a_reading_without_confidence_scores_fails_loudly`,
  `test_a_real_scan_whose_title_shows_1099_int_files_on_the_rows_looser_keywords`.

**What the pass does with a row already parked as Read From Scan Only after
the install** (read from the code, for the office prompt's before-and-after
count): nothing. A pass decides only what is new - a drop in the inbox, or a
stray in the year's folder with no row - and the only road that routes a
document it already has on record again is a re-send whose earlier row was
set aside, filed with its copy gone, or marked missing
(`filer._sort_one`). A parked row's original has already left the inbox; the
same bytes sent again are a Duplicate of the parked row (`DUPLICATE_OF_PARKED`),
not a second reading, and the scanner only re-checks filed documents against
their request's rules. So every row parked as Read From Scan Only before the
install stays parked until a person files it; only scans that arrive after it
file by the new rule. The before-and-after count on the office PC therefore
moves only on documents dropped after Part A is installed.

[`SPEC-ui-polish.md`](SPEC-ui-polish.md): the UI and UX review of 2026-10-11.
Section 1, the no-brainers (P264), is built on `claude/ui-polish` in one
commit after a clean Opus review: one collator, keyed lookups, one draw per
page visit, no hidden letter rebuild, debounced search, timers that sleep
while the window is hidden, smaller hot paths, dead CSS gone, `color-scheme`,
no pager for one page, even filter cards, a notice's Details on its one line.
Measured on the 500-household harness: the Clients draw 31 -> 10 ms, a search
keystroke 9.7 -> 0.1 ms.

Section 2 is the menu Jason answered on 2026-10-11, one P-row per answer
(P265-P280; P269 re-decided the same day when the Date column's real content
came to light, and P272 reworded to one heading per return). Three SPECs are
written from them and build in this order, each item its own sonnet build and
Opus review:

1. `SPEC-ui-menu-small.md`: P265 (Soon tag), P266 (brand band), P267
   (underline on hover), P268 (Tax Year column only when years differ), P269
   ("Since Mar 3" / "Due Apr 15" cells), P270 (chevron at rest), P274 ("Sort Now" button), P280
   (the type stack by platform). **Built on `claude/ui-menu-small`** after
   three Opus reviews (the third with no findings); each named test file
   passed on this Mac under 3.14. Not run here: the floor interpreter (3.11),
   and `pilot/harness/interact.mjs` under real Playwright (through a
   puppeteer shim it passes every new check; nine older checks fail there
   and failed before this change: search typing, All lists 50/50, pause and
   feed, two ruling-21 checks, Show in Finder, the right-click menu). Both
   go on the next Windows check, with the SPEC's section 2 list.
2. `SPEC-ui-menu-layout.md`: P271 (Compact Rows), P272 (Needs Review as one
   flat list), P273 (notices in a right-hand panel), P275 (the household
   page's header card). **Built on `claude/ui-menu-layout`** after four Opus
   reviews (the first found Compact Rows not reaching the editor's fields,
   a CSS specificity miss; the fourth had no findings). The editor's
   Comfortable fields now draw at the 28px and 8px padding P52 wrote, where
   the general control rule had kept them at 32px and 16px. The five open
   questions (J1-J5) were built as the defaults. Not run here: the floor
   interpreter; interact.mjs under real Playwright (through the shim: no
   new failure).
3. `SPEC-ui-menu-speed.md`: P277 (the app watches the last-pass file;
   **built on `claude/ui-menu-speed-1`**, two Opus reviews, the second with
   no findings; write-to-message 263 ms on this Mac), P279
   (long lists draw only the rows in view; **built on
   `claude/ui-menu-speed-2`**, two Opus reviews, the second with no
   findings; return page at 1,050 rows 46 -> 18 ms, 10,178 -> 782 nodes), P276 (one engine process for the session; **built on
   `claude/ui-menu-speed-3`**, three Opus reviews, the third with no
   findings; a Sonnet rebuild then an Opus fix; passes, the after-install
   step, the schedule commands and set-root keep their own process; state
   296 -> 7 ms on this Mac; the office PC and the packaged build go on the
   Windows check, with: after an edit that re-reads, the error log has no
   "engine retired" and Task Manager shows the same tracker-api pid; one
   engine normally, a second only during a Sort or an overlapping click), P278 (the engine pages the firm lists; **built on
   `claude/ui-menu-speed-4`**, three Opus reviews, the third with no
   findings, a Sonnet rebuild then an Opus fix; a page turn 9-24 ms in the
   engine where the window rebuilt the whole 1.4 MB reply; the reply fell
   39%, and a leaner turn on the same view is left for Jason in SPEC §4).

Found by review 3 of P278, outside its build and older than it: a refused
clients folder's notice (SPEC-shell, Settings) is meant to carry a Retry, but
the window draws Retry only for a failed or stale notice, so none appears;
its test checks only that a retry function was handed over. Its own small
job: let `retryOf` honour a given retry for a refusal and pin the drawn button.

Left from review 1 of section 1, outside its build: after a failed return
read, Retry calls `showReturn` directly and the page keeps showing its title
only until the person moves to another page (`shellPageFailed` is reset only
in `shellGo`); its own small job.

Landed before this: [`SPEC-mac-rerun1-fixes.md`](SPEC-mac-rerun1-fixes.md), the
fixes from the Mac check's re-run 1 of 2026-10-10 (P260-P263, pull request
#36): the Login Items switch is told apart from a missing agent (P260), the
suite stands on the Linux floor's computer on a Mac (P261), an open return
page follows a scheduled pass (P262), the reader sends no telemetry (P263).
Re-run 2 of the Mac check on that build passed every fixed step.

Landed before this: [`SPEC-mac-check-fixes.md`](SPEC-mac-check-fixes.md): the fixes from Jason's
Mac check of 2026-10-10, built and landed on `claude/trusting-tesla-or0wm2`
(P256-P258), each job its own commit after a clean Opus review:

1. A running scheduled pass is drawn as "Sorting", never as Sort Failed,
   and the shell follows the last pass by itself (P256).
2. Notices carry a closed Details disclosure for the machine warnings and
   the setup findings; the schedule's registration is toasted at Start and
   at an upgrade's first open (P257).
3. The Mac check kit reads the run log's summary line, the sample pile gains
   a macro workbook, an email and a zip, and the prompt says what the app
   shows and what to record when a session's rules deny a folder (P258).
4. Jason's rulings on the SPEC's questions: Details open on the setup page;
   the household pause, the prior-year feed and the reader warning show
   their sentences under Details (P259).

What has not run: the next Mac check. Its list is the SPEC's "Not in this
SPEC" paragraph - the two Gatekeeper steps, the overnight run, a real Google
Drive folder, step 10 with the three new files, step 13, and H4-H10 named in
the prompt - plus the two cosmetic CSS points the review left (a notice with
Details has a shorter first line than its neighbours; Tab reaches Details
before Dismiss). Jason decided the SPEC's Q1-Q4 on 2026-10-11 (P259): Q1 stays
as built; Q2-Q4 landed as job 3, Details open on the setup page and the
pause, feed and reader sentences under Details.

`SPEC-cleanup.md` (P231-P237) landed before this in pull request #33.

## How a session hands over

**In the pull request description**, not in a file. The folder
`pilot/handoffs/` is gone: what a session decided is a P-row, what it built
is its commits, and what is left is the pull request's checklist. A job's
description says its branch, its commits, what it did and skipped, the
commands it ran with their last line, and what the reviewer should look at
first.

## Open for Jason

- Whether to turn GitHub Actions back on for this repository (it is off; the
  gate runs locally, `pilot/README.md` rule 4).
- The schedule stays off at Jason's word.
- Questions built as recommended meanwhile: P196 Q1-Q5
  (`SPEC-taxpayer-words.md`), P197 Q1-Q3 (`SPEC-hide-under-construction.md`),
  P199 Q1 (`SPEC-check-notes-0.3.md`).
- Check once by hand that a tooltip does not outlive its page (hover a name,
  press Ctrl+4; P202), and that a laptop at 125-150 % display scaling opens
  within its screen (older than P203).

## Left

- F6 by hand needs the schedule on.
- `run_checks.ps1` runs whole at the next Windows check.
- The production tracker's own private copy under the Claude package, and its
  `checkpoint-left-behind` pass, belong to its own repository.

## Environment notes for cloud sessions

`pip install -r requirements.lock` fails in the cloud container (a wheel will
not build) and the system `cryptography` breaks `pypdf`. Use a fresh virtual
environment and install only what the affected tests need:
`pytest==9.1.1 ruff==0.16.9 pypdf==6.19.0 openpyxl==3.1.5`, plus
`pdfplumber==0.11.10 pdfminer.six==20260107 pillow==12.3.0 pypdfium2==5.13.0
charset-normalizer==3.5.1 cryptography==50.0.1 cffi==2.1.1 pycparser==3.0`
(`test_api` and `test_build` fail without them).
