# Orchestrator rulings on the lane 2 review (SPEC-email-zip-tag, P116/P125)

Review: `pilot/reviews/email-zip-tag-review.md` (no MUST; two SHOULD, four NIT). Ruled 2026-09-30.

| Finding | Ruling |
|---|---|
| SHOULD-1 - a keyboard user never hears or sees the tag's full words | **Fold now, smallest fix:** in `pagesRow`, when a tip is set, add it to the row's `aria-description` (`[words, tip].filter(Boolean).join(", ")`), and assert it in the new `tests/test_shell.py` test. The visible tip on keyboard moves goes to lane 4 (`claude/column-order`), which is rebuilding these rows. |
| SHOULD-2 - no test proves `pagesNeedsReview` and `pagesReturnGroups` pass the reason code | **Fold now:** extend the two tests the review names so deleting either `reason:` line fails a test. |
| NIT-1 - HANDOFF, SPEC-shell and wording-shell.tsv still say the old words are cut | **Fold now:** say they were cut in the cloud's font and fit on Windows (131px). |
| NIT-2 - SPEC-shell 11.5's intro does not mention the tip table | **Fold now:** the one sentence the review proposes. |
| NIT-3 - `test_single_source.py` exits 1 in a worktree that has a `.venv` (decision-185 tripwire), and the hand-back reported pass counts only | **No change in this branch.** Flagged for the daily whole-suite run, which runs from a checkout with a `.venv`. Hand-backs report exit codes as well as pass counts. |
| NIT-4 - P125 sits after P114 in the decision log | **At the landing:** keep both sides and put P125 after P116. |

The fold is one commit; only the test files it touches run again, on both interpreters.
