# Review E3 - the fixes to review E2 (commit `ee29076`)

Reviewer: the session that wrote reviews E1 and E2, which built nothing in
Build E or its fixes. Date: 2026-09-29.

All three nits from E2 are fixed, and there are no new findings.

## E2's three nits

1. **The first toolbar row ends 12px short of the right edge - fixed, as an
   accepted limit.**
   - `pilot-ui.css:354-359` now records the limit and why CSS cannot avoid it.
   - HANDOFF's "Review E2" paragraph records it too, naming 1440, 1536 and 1920.
   - The rule itself is unchanged, which is what E2 recommended.
2. **`after-review-cards.png` was stale - fixed.**
   - The committed file is now pixel-identical to my own render of the
     rebuilt page: no difference over the whole 1366x3551 image.
   - "Open the draft file" is drawn in the disabled grey.
3. **The run-gap comment gave the wrong number - fixed.**
   - It now reads "16px between runs (the 4px gap plus a 12px right margin on
     the last button of the run before)", which matches SPEC 6.2 and the
     measured 16px.

## New findings

None. Apart from the fixes above, the commit changes three things:

- It edits a comment only in `pilot-ui.css`, so there is no rule change.
- It adds two HANDOFF paragraphs. Their open questions (SPEC 5.7, the empty
  260px setup picker, and the tour's primary sitting between Back and Close)
  match E1's notes for Jason.
- It refreshes the map.

## Gate

- `ruff check .` is clean.
- `repo_map.py check` was current (199 nodes) before this file was added.
- `tests/test_pilot_ui.py` passes, 10 tests.
