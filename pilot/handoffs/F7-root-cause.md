# Handoff: F7 root cause and SPEC (2026-09-30, 10:00 PM Pacific)

## Done

- **F7's root cause is found** (decision **P193**, `pilot/DECISIONS.md`): the
  Windows-check session started the app from inside the Claude desktop app,
  and Windows silently redirects `%LOCALAPPDATA%` writes from programs started
  there into a private copy for the Claude package
  (`%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\tax-document-tracker-pilot`).
  That copy was last current at 11:13 PM on 9/29, before the samples were
  first sorted, so the app read a day-old store and refused every return. The
  real store is not known to be damaged. Evidence, rulings, files and tests:
  [`../SPEC-F7-redirected-data-folder.md`](../SPEC-F7-redirected-data-folder.md).
- **The handoff's lead was wrong:** the admission bump re-judges rows and
  deletes nothing.
- **F6 does not share the cause:** `after_install.launch()` never asks whether
  the scheduled task still exists. It keeps its own SPEC.
- The read-only check ran at Jason's word ("Yes, read-only"). Every read from
  this session's shell landed on the private copy, not the real folder. A read
  of the real folder through WMI was refused by the session's safety check and
  was not retried.
- Side effect: the read-only queries made an empty `tracker.db-wal` (0 bytes)
  and `tracker.db-shm` in the private copy at 9:38 PM. They hold no data and
  were left alone.
- `pilot/wintest/RESULTS-0.3.md`, `PROMPT-0.3.md` and
  `pilot/handoffs/wincheck-0.3.md` were copied unchanged from the main clone
  (branch `claude/after-0.3`, uncommitted there) and committed here.
- Nothing was built, pushed or opened as a pull request.

## Left, in order

1. **Jason: R6's check** (SPEC R6). Close the app the check session started,
   start Tax Document Console from the Start menu, and open Overview. The 27
   returns should read normally. Then SPEC Q1: move the private copy to the
   Recycle Bin (recommended).
2. **Build and review SPEC-F7** (SPEC Q2, recommended (a)): builder in its own
   worktree, separate reviewer, the SPEC's tests only, plus the Windows proof
   the SPEC names.
3. **F6** (`pilot/handoffs/wincheck-0.3.md`, "Left", item 2): its own SPEC.
   Its Windows check starts the app through Explorer (SPEC-F7 R4).
4. **New from Jason, 2026-09-30, looking at Overview's Work Waiting** (a renderer
   job, lane 4's look, alongside handoff item 3):
   - "Return type is redundant, keep the chip, drop the return type from long
     name": the form chip (`1040`) stays, and the link reads `Chidi & Ada
     Okafor (2025)` rather than `1040 - Chidi & Ada Okafor (2025)`.
   - "Year and long name need to be separate columns": the tax year gets its
     own column beside the return's name.
   - "Add a setting to hide 'Under Construction' sections from sidebar."
   Each needs a SPEC; none touches the engine.
5. The rest of `pilot/handoffs/wincheck-0.3.md` "Left" (items 3-6), unchanged.

**Noticed, not acted on:** the same redirect area holds
`LocalCache\Roaming\Tax Document Tracker Pilot` (the app's window settings
from Claude-started runs) and `LocalCache\Roaming\Tax Document Tracker`, the
firm's **production** tracker's. The production tracker's 9:00 PM pass on
9/30 failed with `checkpoint-left-behind`
(`%LOCALAPPDATA%\tax-document-tracker\last-pass.json`). That belongs to the
production repo and is worth one look for the same cause; nothing there was
touched.

## Files the next session needs

- `pilot/SPEC-F7-redirected-data-folder.md` (all of it).
- `tracker/settings.py` 614-690, `tracker/api.py` 3543-3561,
  `tests/test_settings.py` 376-495, `tests/conftest.py` 686-735.
- `pilot/wintest/make_samples.py`, `pilot/wintest/run_checks.ps1` (215 onward).
- `docs/runbook.md` 39-50.
