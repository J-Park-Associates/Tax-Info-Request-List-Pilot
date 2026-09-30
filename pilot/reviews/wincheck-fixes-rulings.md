# Orchestrator rulings on the lane 3 review (SPEC-wincheck-fixes, P128-P134)

Review: `pilot/reviews/wincheck-fixes-review.md` (2 MUST, 5 SHOULD, 4 NIT), against `c712034`. Ruled 2026-09-30 by the orchestrator session that runs v0.3.

| Finding | Ruling |
|---|---|
| M1 - after Retry or dismiss, a Sort that fails again with the same sentence shows nothing (`forgetSortLine` leaves the key in `keyedNotices`; app.js:2272-2312, keyedNotice at app.js:253) | **Fold.** Forgetting a sort line also forgets its key in `keyedNotices`, so the same failure shows again. Add a test that drives the real `syncNotices` / `keyedNotice` (not a fake) through fail, dismiss, fail again, and fails on today's code. |
| M2 - the household page's Sort reports on the inactive return ("Nothing Done: Inactive.") though the active return sorted in the same pass (shell.js:257) | **Fold.** Prefer the active return that has not been rolled forward (`active`, `superseded_by`, as pages.js:622 reads them). Add a test with an active and an inactive return in one household. Correct SPEC section 7 (the list does carry the active flag) and the P134 row. |
| S1 - a pass failure drops `lock` and `identifier`, so a locked pass no longer calls `showLock` | **Fold.** Carry both through; test that a locked pass still shows the lock notice. |
| S2 - a good Sort of a return no longer on screen says nothing | **Record, no code change.** It follows F3 (a Sort's answer belongs to its return): say so in the SPEC as intended behaviour; the side panel's last-sort line still updates. |
| S3 - F4 has only a static test | **Fold.** Lift `createEngagement` with fakes and assert Create Return opens the new return. |
| S4 - `passEnded`'s answer-building is checked only by string matching | **Fold.** One behaviour test over the built answers (failed, skipped with each reason, succeeded). |
| S5 - `test_single_source.py` exits 1 in a checkout with a `.venv` (main.js:290-292 starts the checkout's .venv Python with `TRACKER_SETTINGS_DIR` at the repo root, main.js:41; decision-185 tripwire) | **Fold, as its own commit.** It blocks the daily whole-suite run from a checkout. Stub `child_process` in the Electron stand-in's module hook at tests/test_single_source.py:222, as the review says; prove test_single_source exits 0 with the `.venv` present on both interpreters. |
| NIT 1-4 | **Fold all as written.** |
| Jason's answer to the owner question Q1 | **Record:** Jason, 2026-09-30, chose (a) "Nothing Done: Names Too Long." (records branch P169). Mark Q1 decided in the SPEC and its DECISIONS row. |

The fold is one commit for M1, M2, S1, S3, S4, the NITs, S2's SPEC note and Q1; S5 is a second commit. Only the test files the fold touches run again, on both interpreters, with pass lines and exit codes. The reviewer then re-checks M1 and M2.
