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

- **Decisions live in [`DECISIONS.md`](DECISIONS.md), rows P1 to P280.** Code
  and tests cite those numbers, so a row is never renumbered or removed. Why
  a thing is the way it is: search the row, do not guess.
- **Pilot decisions never go in `docs/ROADMAP.md`**, which stays the
  original's log.
- **A SPEC is built from, not read for history.** The SPECs beside this file
  are cited by section from the code; each names the P-rows that built it.

## Current work

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
   engine normally, a second only during a Sort or an overlapping click), P278 (the engine pages the firm
   lists, last because its page turns become engine requests).

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
