# Shell S8a rebuild 2 (review 2's two findings)

Builder: Sonnet 5.5, on `claude/shell-s8a-links` at `209e655`. Only the two
findings of `shell-S8a-review-2.md` were touched.

## Finding 1: a parked read document's Open

`_shown_copy_key` (`tracker/api.py`) now returns the row's `review_copy` key
when it has one (`_review_copy_key(entry) or "shown_copy ..."`), so a path is
never reported under two kinds: a parked PDF's `shown_key` equals its
`open_key`, and `open(path, "reveal")` already shows a `file`. Rows without an
opening copy (set aside, email, zip, docx) keep their `shown_copy` key.

Tests (`tests/test_api.py`, a shared `_parked_read_pdf_state` helper on a real
scan; last year's W-2 is the parked read PDF):

- `test_a_parked_pdfs_shown_key_is_its_open_key_so_no_path_is_named_twice`:
  `shown_key == open_key`, and no path in `state.paths` appears under two keys
  of different kinds (nor twice at all).
- `test_a_real_state_paths_still_opens_a_parked_pdfs_review_copy_through_the_shell`:
  the real reply's `paths` (own order) and `PATH_KINDS` through the real
  `app/main.js` under node: plain open of the review copy opens it, reveal
  shows it, a shown-only docx is refused on a plain open and shown on reveal.

Mutation check on a scratch copy (fix reverted to the bare `shown_copy` key):
both new tests fail; restored, both pass.

## Finding 2: ruling 14 paperwork

Approved by Jason, ruling 14: `paused` "Two Years Open; Sorting Paused", `feed`
"Prior Year Data Not Found" (changed from the proposed Feed Return Not Found),
and `machine` "Machine Needs Attention" as the one line for all three machine
warnings. The PROPOSED marks are removed from `pilot/wording-shell.tsv` (feed
word count now 5), the comment in `tracker/api.py`, and
`shell-S8a-rebuild-1.md`.

## Gate

Dead code: none in the changed lines. Each file in its own process, Python
3.11 then 3.13: test_api, test_shell, test_layers, test_single_source,
test_repo_map; `ruff check .`; `repo_map.py check`. Results in the report.
test_build's OCR scratch-roots failure is the known base failure, not run.

## Files

`tracker/api.py`, `tests/test_api.py`, `pilot/wording-shell.tsv`,
`pilot/handoffs/shell-S8a-rebuild-1.md`, this file, and the regenerated map.
