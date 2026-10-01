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

## Left, in order

1. **Jason (SPEC-F7 R6 and Q1 (a)):** close any app the check session started; start Tax Document Console from the Start menu; open Overview (the 27 samples should read normally). Then move `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\tax-document-tracker-pilot` to the Recycle Bin. Not yet confirmed in this session.
2. **Landing:** this branch waits for Jason's word to push and land (merge commit, draft pull request marked ready once, the whole suite once on Windows first).
3. **Windows check after landing** (`pilot/wintest/PROMPT-0.3.md`, its note at the end): steps 19-21 with the app started outside Claude; the installer landing in the real `Programs` folder; one look at 1100 px; P197 by hand (on/off, Alt+V+U, focus, High Contrast, the choice kept after a restart); the new columns and words on every window.
4. **F6** (`pilot/handoffs/wincheck-0.3.md`, Left item 2): its own SPEC.
5. `wincheck-0.3.md` Left items 3-6 (lane 4's Date column and N2, the check scripts A1/N7/N8, the smaller notes). `test_shell_menu` has a timing flake on 3.11 that predates this work (`pilot/HANDOFF.md`).

**Noticed, not acted on:** the Claude package's redirect area also holds `LocalCache\Roaming\Tax Document Tracker` for the firm's **production** tracker, whose 9:00 PM pass on 9/30 failed with `checkpoint-left-behind` (`%LOCALAPPDATA%\tax-document-tracker\last-pass.json`). Worth one look in the production repo for the same cause; nothing there was touched.

## Files the next session needs

- `pilot/DECISIONS.md` P193-P197; the four SPECs and their hand-backs named above; `pilot/reviews/` (both reviews and both rulings files).
- `pilot/wintest/PROMPT-0.3.md` (the note at the end) for the next Windows check.
