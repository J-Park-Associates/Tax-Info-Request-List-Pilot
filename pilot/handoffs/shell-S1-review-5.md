# Shell S1 review 5 (of rebuild 4)

Branch `claude/sharp-goldberg-jmfynk`, reviewed at `9df1151` (diff
`24203c1...HEAD`). The reviewer did not build S1 or any of its rebuilds.
Read: CLAUDE.md, `shell-S1-review-4.md`, `shell-S1-rebuild-4.md`. No code
changed.

## What changed

`tests/test_api.py` (+7 lines), `pilot/handoffs/shell-S1-rebuild-4.md` (new)
and the regenerated `docs/repo-map.json` / `docs/repo-map.md` (the new
handoff node and the test file's hash and line count). Nothing in
`tracker/`; no other file. No extras.

## Review 4's F1, checked

In `test_firm_lists_every_file_it_counts_and_buckets_a_return_with_only_a_file`
the test now runs `state` on the same return, maps each `original_name` to
its handle (`index` rows, then `moved` rows), asserts the names are exactly
`{"setup.exe", "w2.pdf"}`, and for every `firm` file asserts
`year == 2025` and a non-empty `handle` equal to `state`'s for that name. So
both the parked `setup.exe` and the moved `w2.pdf` are pinned. Fixed.

Mutations on a scratch copy outside the repo (`git archive HEAD`), `-k firm`
(14 tests), Python 3.11:

| Mutation at `tracker/api.py` 5263-5264 (moved rows) | Result |
|---|---|
| `handle` `""` and `year` `None` | fails the test above (1 failed, 13 passed) |
| `handle` `""` only | fails the test above |
| `year` `None` only | fails the test above |
| real code | 14 passed |

## Gate

Each file its own process, one after the other: `tests/test_api.py` 384
passed on 3.11 and 384 passed on 3.13; `tests/test_repo_map.py` 80 passed on
both. `ruff check .` clean; `repo_map.py check` current (274 nodes).

## Findings

No findings.
