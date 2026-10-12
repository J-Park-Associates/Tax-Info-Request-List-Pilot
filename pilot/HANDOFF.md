# Pilot handoff

The pilot is Tax Document Console for a first batch of test firms: the
tracker, the Electron app that fronts it, and the Windows installer and check
kit in this folder. [`README.md`](README.md) says what it is and the rules for
this repository; [`SPEC.md`](SPEC.md) says what it builds.

## Where the record is

- **`main` is pull request #52** (the security review's prompt corrections)
  on `597ed0f6` (pull request #51, this handoff) on `d39b92e7` (pull request
  #50, P285, the preparation of every scan and photo before the reader reads
  it) on `41723e0d` (pull request #49, P286, the bench's Needs Review count
  asks the firm summary itself). No lane is open. The Mac console in
  `/Applications` and in `~/Desktop/Apps/Published` is the `d39b92e7` build,
  which is the same program: everything since changed prompts and records only.

- **Decisions live in [`DECISIONS.md`](DECISIONS.md), rows P1 to P286.** The
  badge reads **Pilot 0.4** (P281, 2026-10-11): 0.3 plus the UI review's work. Code
  and tests cite those numbers, so a row is never renumbered or removed. Why
  a thing is the way it is: search the row, do not guess.
- **Pilot decisions never go in `docs/ROADMAP.md`**, which stays the
  original's log.
- **A SPEC is built from, not read for history.** The SPECs beside this file
  are cited by section from the code; each names the P-rows that built it.

## Current work

Nothing is in flight. What landed on 2026-10-12, in the software's words:

- **P285 ([`SPEC-ocr-prepare.md`](SPEC-ocr-prepare.md), sections 1-9.5).**
  Every scanned page and photo is prepared in memory before the reader sees
  it: drawn at 300 dots per inch, held to a letter page's long side, turned
  level if it leans up to five degrees (left alone when no angle plainly
  wins), made black and white by a threshold that follows the paper's own
  shading, cleared of lone specks and of a form's box lines while type is
  left whole. The file is never touched and nothing is written. The reader's
  detector works on its own smaller copy of the page, so a 300 dpi page
  reads inside the reading child; the processor child's memory limit is 4 GB
  (it was 2 GB; the card's 6 GB is unchanged). The verdict cache moved, so
  the first pass after the install reads every document again (slow once; a
  row already in Needs Review stays there). The reader bench shrank from 36
  to 21 variants: prepared against raw at 300 and 144 dpi, and the shipped
  settings with each step turned off one at a time. Built by Sonnet in three
  rounds against the SPEC and reviewed twice by Opus in sessions that did not
  build it; the measurements (memory peaks, seconds per step, what the
  levelling saw on drawn pages) are the SPEC's section 9. Drawn made-up
  pages only.
- **P286 ([`SPEC-review-codes-pipe.md`](SPEC-review-codes-pipe.md)).** The
  bench's Needs Review count (`review-codes`) starts the firm summary itself
  instead of reading it from a pipe, so the count never waits on a terminal
  and never mistakes a progress line for the reply; a failure is said by kind
  and exit code only. Three Opus reviews.
- **The security review (2026-10-12, by the orchestrating session on Fable,
  at Jason's instruction).** Everything landed since `dcb02c3` was read
  against the standing rules and the deny list: nothing in code; the office
  bench prompt wrote the photo corpus's file list under a name the deny rule
  does not cover and then did not name it to the bench, and did not say the
  session runs under the schedule's account with the deny list in place; the
  Mac prompt called 144 dpi "today's". All three corrected in pull request
  #52.

**Next for the reader lane.** The office PC runs
[`PROMPT-reader-bench.md`](PROMPT-reader-bench.md) on the firm's own sorted
documents; P284 then ships the settings its counts favour. Until that report
exists, the gain from P282 and P285 is a design argument, not a measured one:
the drawn pages read the same before and after.

## How a session hands over

**In the pull request description**, not in a file. The folder
`pilot/handoffs/` is gone: what a session decided is a P-row, what it built
is its commits, and what is left is the pull request's checklist. A job's
description says its branch, its commits, what it did and skipped, the
commands it ran with their last line, and what the reviewer should look at
first.

## Open for Jason

- **The office bench session's account.** `PROMPT-reader-bench.md` has the
  session run under the account that runs the schedule (its step 1 requires
  the clients root, which `review-codes` and the backtest need), while the
  working notes say the firm's AI tooling runs under a separate account that
  cannot see the client drive. The prompt now says the deny list must be in
  place in that account; whether the session may run there at all is your
  call.
- **The processor child's memory limit, 4 GB (P285).** Decision 169 set 2 GB
  for a reader at 144 dpi; a 300 dpi page needs about 2.3 GB on a Mac, and
  Windows counts committed memory, so 4 GB is the orchestrating session's
  assumption held for Jason's word. One constant reverses it.
- **A row for the Mac's OpenCV.** The arm64 wheel (`opencv-python-headless`
  5.0.0.93) crashes inside its resize for about one page size in twenty, with
  or without P285; in the child that parks the document as a crash. The
  office's Windows wheel does not show it, and the Mac never runs a clients
  root. Whether to pin a different wheel on the Mac is his.
- **Four branches on GitHub hold work that never landed** (`build-d`, the
  Mica window material, 2026-09-29; `claude/amazing-maxwell-b4hdzo` and
  `claude/friendly-gauss-7mglv6`, Windows-check wording and a plain-English
  library, 2026-09-30; `orchestrator/board`, the coordination board, pull
  request #5 marked never merge). Every merged branch was deleted on
  2026-10-12; these wait for his word.
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

- `python -m tracker.api firm` still waits on a terminal's input if someone
  types the old pipe's left-hand side by itself; stopping the reading
  commands from reading a terminal is a follow-up with its own SPEC (P286).
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
