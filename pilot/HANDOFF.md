# Pilot handoff

The pilot is Tax Document Console for a first batch of test firms: the
tracker, the Electron app that fronts it, and the Windows installer and check
kit in this folder. [`README.md`](README.md) says what it is and the rules for
this repository; [`SPEC.md`](SPEC.md) says what it builds.

## Where the record is

- **`main` is `213d876`** (pull request #32, the Sort & Scan speed round,
  P216-P230); this branch is cut from it.

- **Decisions live in [`DECISIONS.md`](DECISIONS.md), rows P1 to P237.** Code
  and tests cite those numbers, so a row is never renumbered or removed. Why
  a thing is the way it is: search the row, do not guess.
- **Pilot decisions never go in `docs/ROADMAP.md`**, which stays the
  original's log.
- **A SPEC is built from, not read for history.** The SPECs beside this file
  are cited by section from the code; each names the P-rows that built it.

## Current work

[`SPEC-mac-check-fixes.md`](SPEC-mac-check-fixes.md): the fixes from Jason's
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
