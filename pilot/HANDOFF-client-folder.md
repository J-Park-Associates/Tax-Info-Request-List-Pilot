# Handoff - a household whose record cannot be read is never laid out again (P296)

Builder's handoff for `pilot/SPEC-client-folder-unreadable.md`. The reviewer reads
the SPEC, the diff and this, and writes numbered findings under "## Review".
`pilot/DECISIONS.md` is untouched: the landing session adds P296.

## Built, against R1-R3

- **R1** (`tracker/households.py`): `ClientSideUnknown(RuntimeError)` and
  `CLIENT_SIDE_UNKNOWN`, worded as the SPEC has them. `client_side_expected`
  keeps its signature; a failure in either half (`shared_on`, or `store.documents`
  of any return) is kept (`errors.keep("households: the client-side history", exc,
  name=folder.name)`) and raised as `ClientSideUnknown`, the problem named by
  `errors.said(exc, (ManifestError, LedgerError, StoreError))`. No `except` in the
  function swallows anything any more. `client_folder_missing` looks at the disk
  first (`layout.client_household_dir(...).is_dir()` -> `""`, record unread) and
  lets `ClientSideUnknown` pass through. `door.client_folder_missing` unchanged.
  The new imports are call-time (`errors`, `ledger`, `LedgerError`, `StoreError`);
  no load-time import was added and no layer moved.
- **R2**: `runner.py` held-back block sets `held_back = str(exc)` and
  `held_code = CODE_RECORD_UNREADABLE` on `ClientSideUnknown` (every run of the
  household carries it); `scaffold.py` raises `ClientFolderMissing(str(exc)) from
  None`; `registry.held_back` returns `str(exc)`.
- **R3**: `docs/runbook.md`, one paragraph (a new bullet) right after the
  "`Clients\<name>` is missing. Was the household renamed or moved?" entry.
  `test_single_source` still passes.

## Done differently, and why

One deviation from the SPEC's letter. Three existing runner tests
(`test_a_missing_folder_is_recorded_not_raised`,
`test_a_missing_folder_is_said_without_its_path`,
`test_every_failure_and_skip_is_logged_as_a_code`) pass a pass an engagement whose
folder does not exist at all, so there is no `_ledger.jsonl` anywhere. Under the
SPEC's wording ("a read failure in either half") "no record here" counted as a
failure and they got the new sentence instead of `FOLDER_NOT_FOUND`. A journal
that is absent has said nothing - there is nothing to refuse - and a household
whose record is gone while its returns hold theirs is already *stopped* by the
registry with its own sentence before anything asks this. So `client_side_expected`
skips a household or a return whose `ledger.path_for(...)` is not a file; only a
journal that is there and will not read is "cannot tell". The docstring says so.
The audit's reproduction (an unlinked line) is still caught. The reviewer should
confirm this reading.

## Tests added (each fails without its fix; checked by reverting the fix)

- `tests/test_households.py`: `test_a_household_whose_record_cannot_be_read_is_not_said_to_have_had_no_client_folder`,
  `test_a_client_folder_that_is_there_is_never_a_reason_to_read_the_record`
- `tests/test_runner.py`: `test_a_shared_household_whose_record_cannot_be_read_is_held_back_and_its_client_folder_is_not_remade`
- `tests/test_scaffold.py`: `test_the_scaffold_refuses_to_lay_out_a_household_whose_record_cannot_be_read`
- `tests/test_registry.py`: `test_a_household_whose_record_cannot_be_read_says_so_where_its_pause_is_said` (tests `registry.held_back`)

## The gate (venv python, `-p no:cacheprovider`, one process per file, parallel)

| file | result |
|---|---|
| test_households | 18 passed |
| test_runner | 230 passed |
| test_scaffold | 55 passed |
| test_registry | 42 passed, 2 skipped (as before) |
| test_door | 7 passed |
| test_layers | 31 passed |
| test_single_source | 218 passed |
| test_repo_map | 82 passed |

`python -m ruff check .`: all checks passed. `python tools/repo_map.py check`: map is current (after the final `update`).
The first run of `test_single_source` and `test_repo_map`
failed only on the other build's half-edited files (`COL_ISSUER`, `tracker/api.py`);
they passed on the re-run after `update`, as the SPEC allows. The router and the
readers were not run.

## For the reviewer

`tracker/households.py` (`ClientSideUnknown`, `CLIENT_SIDE_UNKNOWN`,
`client_side_expected`, `client_folder_missing`), `tracker/runner.py` (held-back
block, ~line 1358), `tracker/scaffold.py` (`scaffold_household`),
`tracker/registry.py` (`held_back`), `docs/runbook.md` (the bullet after the
"Was the household renamed or moved?" entry), the five tests above.

Not done: `docs/repo-map.curated.json` was not edited (outside SPEC section 6);
the households node's `notes` could name P296 when the landing session adds the row.
