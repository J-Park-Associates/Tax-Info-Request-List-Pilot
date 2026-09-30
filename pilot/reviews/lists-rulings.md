# Orchestrator rulings on the lane 4 / 4b review (SPEC-lists, P135-P139, P170-P180)

Review: `pilot/reviews/lists-review.md` (1 MUST, 5 SHOULD, 5 NIT), against `0d941d5`. Ruled 2026-09-30 by the orchestrator session that runs v0.3.

| Finding | Ruling |
|---|---|
| M1 - `_mirror_related` (tracker/api.py:4109-4129, called at :4176) compares only the saved household's own list before and after, so a save interrupted after its first record write leaves a one-sided link that neither side's re-save can repair | **Fold.** When a household's related list is saved, rebuild the link on both sides from what the person saved: add this household to every household it now names, and remove it from every household whose record names it but which it no longer names (include households whose records name this one, not only this one's old list). Re-saving either side must repair a one-sided link. Add the reviewer's probe as a test (Park names Lee, Lee does not; save Lee without the link; save Park) that fails on 0d941d5. SPEC 9.1 and P170 stay as written; say in the SPEC how a half-finished save is repaired. |
| S1 - the mirror reads the other household outside its lock, so a change made there in between could be lost | **Fold.** Read-modify-write the other household inside its own lock (one lock held at a time, as now); test that a change to the other household made between the two steps survives. |
| S2 - any redraw closes the link panel and loses keyboard focus | **Fold.** A redraw keeps the panel open for the same household if it is still shown, or closes it and returns focus to that row's link icon; never loses focus to the page. |
| S3 - focus can be invisible on the link panel (`outline: none`) | **Fold.** Visible focus on every control in the panel, including forced-colors. |
| S4 - the Related Households picker has no accessible name | **Fold.** Give it a label ("Related Households"). |
| S5 - no test covers Escape closing the panel | **Fold.** Test Escape closes it and returns focus to the icon. |
| NIT 1-5 | **Fold all as written.** Also list the link icon on its hover background (5.56:1) in the SPEC's contrast table. |
| Jason's answers to Q10-Q14 | Pending; keep the recommendations as built. |

One fold commit with the review and this rulings file. Rerun only the test files the fold touches (tests/test_api.py, tests/test_households.py or tests/test_records.py as the map owns the change, tests/test_shell.py), on both interpreters, with pass lines and exit codes. The reviewer then re-checks M1 and S1.
