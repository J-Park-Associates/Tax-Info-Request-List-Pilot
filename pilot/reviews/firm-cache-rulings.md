# Orchestrator rulings on the lane 1 review (SPEC-firm-cache, P115, P118-P123)

Review: `pilot/reviews/firm-cache-review.md` (0 MUST, 4 SHOULD, 5 NIT), against `3e55bdb`. Ruled 2026-09-30 by the orchestrator session that runs v0.3.

| Finding | Ruling |
|---|---|
| SHOULD-2 - a record rewritten at the same size with its old time put back still shows a healthy row, while a fresh walk says "Could Not Be Read" | **Fold (treated as a MUST: "nothing is guessed" outranks speed).** Fingerprint each return's record (`_ledger.jsonl`) by its content (a fast digest), not by size and time alone. Measure the cost at 750 returns warm and first-run and report it; if it pushes warm `firm` over 3 s, say so and stop for a ruling rather than weakening the check. Add the reviewer's probe as a test that fails on today's code. State in the SPEC which files the fingerprint still judges by size and time, and why that cannot change a status. |
| SHOULD-1 - one `_`, `.` or `~$` folder in the firm's tree turns the cache off for every reply and logs an error each time (`tracker/api.py:5622`) | **Fold.** A folder the layout does not own affects only its own household (or is ignored where discovery already ignores it); the cache stays on for the rest; log once per change, not per reply. Test it. |
| SHOULD-3 - the "write nothing" test for one-reading commands compares two lists only | **Fold.** Refuse any settings or store write inside a read-only command outright (fail loudly), and test that a write attempted there raises. |
| SHOULD-4 - every scheduled pass rewrites each return's `Status Report.html` and moves folder times, so the first Overview after each pass re-reads every household | **Fold, builder's choice of the smaller correct fix:** (i) the fingerprint ignores the tracker's own derived outputs (the status report) where that provably cannot hide a status change, or (ii) the scheduled pass refills the cache as its last step (the SPEC's named follow-up). Either way, measure the first Overview after a pass at 750 returns and report it. |
| NIT 1-5 | **Fold all as written.** |
| The `firm-view.json` the review's timing runs left in settings-750's data folder | **Leave it.** It is test data on this PC only. |

One fold commit (plus the review and rulings files); only the test files the fold touches run again, on both interpreters, with pass lines and exit codes. The reviewer then re-checks SHOULD-2.
