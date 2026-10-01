# Handoff: F7, the firm columns, Taxpayer words and the Under Construction setting (2026-10-01, 12:51 AM Pacific)

Branch `claude/zen-easley-93548b` (worktree `.claude/worktrees/zen-easley-93548b`), tip `c729b24`, from `main` at `fe6fedf`. **Not pushed; no pull request** (Jason has not asked for one in this session).

## Done

- **F7's root cause (P193):** the Windows-check session started the app from inside the Claude desktop app, and Windows silently redirects `%LOCALAPPDATA%` writes from programs started there into a private copy for the Claude package (`%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\tax-document-tracker-pilot`), last current at 11:13 PM on 9/29. The real store is not known to be damaged. Evidence: `pilot/SPEC-F7-redirected-data-folder.md`. F6 has its own cause (`after_install.launch()` never asks whether the task exists).
- **Four builds, each reviewed by an agent that did not build it, all combined here with merge commits:**
  - **P193, the F7 guard** (`ae5219f`, merged `d51cac3`): the engine refuses a redirected data folder and says so on the first screen and in the pass; it names a stale redirected copy for a person to remove; `make_samples.py` uses a throwaway data folder; `run_checks.ps1` never starts the app (orchestrator ruling 3) and says how. Hand-back `pilot/handoffs/F7-build.md`.
  - **P194/P195, one field per column** (`61901ba`): Overview and Reminders read Tax Year, Taxpayer, Form Type, Status, Date; the household is in the Taxpayer link's tooltip; Needs Review headings and the household and year pages say each field once. `pilot/SPEC-firm-columns.md`, hand-back `pilot/handoffs/firm-columns-build.md`.
  - **P196, Taxpayer words** (`9e20f2c`, merged `2ee1dce`): "Client" becomes "Taxpayer" where a person is meant and "Household" where a household is meant (the Households page); folders on disk, reminder emails, standing rules and code names keep "client". `pilot/SPEC-taxpayer-words.md` (its Q1-Q5 built as recommended), hand-back `pilot/handoffs/taxpayer-words-build.md`.
  - **The combined review** (`pilot/reviews/combined-review.md`: 1 MUST, 5 SHOULD, 5 NIT), the rulings (`pilot/reviews/combined-rulings.md`) and the fold (`e8d872e`, `pilot/handoffs/combined-fold.md`). The MUST (the editor's "this client is not chased by email") was re-checked by the orchestrator: fixed, its test passes.
  - **P197, View > Show Under Construction** (`73160a1`, fold `bbf2d16`, merged `c729b24`): hides the side panel's five Under Construction items and the Workspace heading, kept on this PC, shown on a new install. `pilot/SPEC-hide-under-construction.md`, review and rulings in `pilot/reviews/hide-under-construction-*.md`, hand-back `pilot/handoffs/hide-under-construction-build.md`.
- Jason's answers, all logged in `pilot/DECISIONS.md` P193-P197: F7 Q1 (a), Q2 (a); household in the tooltip; "apply to all windows"; "Taxpayer" across the app; folders keep their names; emails unchanged; the page is "Households"; the Under Construction setting.
- Tests: each build's own test files passed on Python 3.11 and 3.14, each file its own process; ruff clean; map current (413 nodes). **The whole suite has not run on this branch** (the daily landing's job).

## Landed (2026-10-01, 4:20 AM Pacific)

Everything above, and the four further lanes (P198 F6, P199 the check notes, P200 the check scripts and the flake, P201 the cache fill), consolidated and then reviewed as a whole, plus two faults the hands-on check found (P202 a tooltip that outlived its page, P203 the minimum window's page), landed in pull requests #23, #24 and #25 with merge commits. `main` is `6a2d87f` and its build is installed on the office PC. The landing is P204; the hands-on results are `pilot/wintest/RESULTS-0.3-followup.md`; the status page is `pilot/HANDOFF.md`.

- SPEC-F7 R6 passed (the Start-menu app read every return; the real store is whole) and Q1 (a) was done by Jason.
- The whole suite ran once on this PC on both interpreters; its failures were the test environment's and every failing file passed in a fixed environment (P204).
- GitHub Actions is off for the repository; no online check ran.
- What is still open is on the status page (`pilot/HANDOFF.md`, top), not here.
