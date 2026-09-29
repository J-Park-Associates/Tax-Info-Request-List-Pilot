# Shell S1 review 3 (opus, high effort)

Branch `claude/sharp-goldberg-jmfynk`, reviewed at `013f2c3` (rebuild 2)
against review 2's commit `9adc653` (`git diff 9adc653..HEAD`). The reviewer
built neither S1 nor either of its rebuilds.

## What was checked

1. **The rebuild's scope.** The diff touches only
   `pilot/handoffs/shell-S1.md`, `pilot/handoffs/shell-S1-rebuild-2.md`,
   `docs/repo-map.json` and `docs/repo-map.md`. Nothing under `tracker/`,
   `tests/` or `app/` changed.
2. **Review 2's F1, checked against the code.** `tracker/api.py`
   `_firm_draft` sets `ready = this_week and approval_state(..., since=week)
   != APPROVED_NOTE`. `approval_state` returns `APPROVED_THEN_EDITED` when
   the letter was edited after the approval, so that approval does not
   count. `held = held_rows + reminder.unsorted_in_inbox(engagement)`, where
   `held_rows` is `len(triage(...)[2])`, the rows that hold the draft.
   `held` does not enter `ready`. This matches SPEC-shell 6.3: rows are
   drafts "ready and not yet approved", and "Held" is shown beside a row
   when "files or rows hold it". Both places in `shell-S1.md` now say this:
   the `draft.ready` note and the first proposed decision row. The new
   proposed row names "Could not be read" (`api.FIRM_UNREADABLE`, which
   equals that string in the code). It says the detail goes to the error log
   (`errors.keep` on both branches of `_firm_row`) and that the return counts
   as needing a person (`_cmd_firm` counts `row["problem"]` as need). It
   also says the words await Jason's approval. Fixed.
3. **The rest of `shell-S1*.md` against the code.** Each claim below was
   checked in the code, and none contradicts it:
   - `api.MENU` has 44 keys, and `reasons.SHORT_REASONS` has 60.
   - `PATH_KINDS["clients_root"]` is `"folder"`, and `_list_paths` is
     `{clients_root, status}`.
   - `_last_pass` adds `ok` and `when`.
   - `firm` is in `COMMANDS` and not in `WRITING_COMMANDS`.
   - The seven `api.SHELL_*` words are the ones the handoff tells S2 to put
     in `main.js`.
   - `Stage.short` exists, and `follow=False` is used in `runner.py`.
   - `wording-shell.tsv` has 67 reword, 5 merge and 10 error-log rows, and
     78 `api._vocab` cut rows.

   The review and rebuild files for rounds 1 and 2 describe the code as it
   stands.

A note, not a finding: an approval recorded before decision 190 has no
letter fingerprint, and `approval_state` reads it as
`APPROVED_THEN_EDITED`, so that draft also counts as ready. This agrees with
the handoff's "not yet approved". The handoff's parenthesis names only the
edited-after case.

## Gate, as run by the reviewer

Python 3.11.15 (`/tmp/v`), each command its own process, run in parallel:
`python tools/repo_map.py check` is current (270 nodes), `tests/test_repo_map.py`
80 passed, `tests/test_api.py` 380 passed. After this file was added,
`repo_map.py update` and then `check` also reported current.

## Findings

No findings.
