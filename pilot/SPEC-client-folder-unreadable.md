# A household whose record cannot be read is never laid out again - SPEC

Status: written 2026-10-13 for a separate builder and a separate reviewer.
Decision **P296** (`pilot/DECISIONS.md`; the row is added by the session that
lands this, not by the builder - another build edits that file at the same
time). Source: `pilot/AUDIT-2026-10-13-error-handling.md`, finding E1,
reproduced there against commit `e8661e9`. No version number changes.

**Not in this SPEC:** E2 to E7 of the same audit.

**Hard rules kept.** Nothing new is written into the tree a client is shared
with on a read failure. No generative AI reads a client document. No layer
moves: `households` keeps its imports; `runner`, `scaffold` and `registry`
import `households` already.

## What staff will notice (plain English)

A household the firm marked shared, whose `Clients\<name>` folder has gone
and whose record the app cannot read, is held back by the pass with one
sentence that says both things - the folder is missing and the record could
not be read, with the record's own reason - instead of getting a new, empty,
unshared `Clients\<name>` made under the old name. New return and Roll
forward refuse with the same sentence. Once the record reads again (runbook
section 6), the usual "Was the household renamed or moved?" verdict applies.

---

## 1. The finding

`tracker/households.py` `client_side_expected(household_dir, returns)`
answers whether the household *had* a client folder: the record says it was
shared (`shared_on`), or a recorded original of one of its returns rests
under `Clients\<name>`. Both reads are wrapped in `except Exception`
(`pass`, then `continue`), so a record the ledger refuses - an unlinked line,
a malformed line, a sync conflict - falls through to `False`: "never had
one". `client_folder_missing` then answers `""`, and the pass
(`tracker/runner.py`, the held-back block before `_worth_a_pass`) goes on to
`tracker/scaffold.py`, which makes `Clients\<name>` again
(`may_make_household`), while the same pass warns that the household's
record could not be read (`FEEDS_UNREAD`). `create` in the same state refuses
on the record, so the pass and the dialog disagree. Decision 188 and
SPEC-162 ruling 2: nothing is made again under the old name when the
household had one.

## 2. R1 - "cannot tell" is an answer of its own

In `tracker/households.py`:

- `class ClientSideUnknown(RuntimeError)`: raised when the household's
  client-side history cannot be read. Its message is the sentence below.
- `CLIENT_SIDE_UNKNOWN = ("`Clients\\{name}` is missing and the household's record could not be read ({problem}), "
  "so the app cannot tell whether the household was renamed or moved. Nothing is made under the old name "
  "until the record reads again (runbook section 6).")`
- `client_side_expected` keeps its signature and its `True`/`False` answers
  for a record that reads. A read failure in either half (`shared_on`, or
  `store.documents` of any return) is kept on the error log
  (`errors.keep("households: the client-side history", exc, name=folder.name)`)
  and raises `ClientSideUnknown(CLIENT_SIDE_UNKNOWN.format(name=folder.name,
  problem=errors.said(exc, (ManifestError, LedgerError, StoreError))))` -
  the same sanitiser the runner uses for `FEEDS_UNREAD`, so a sentence the
  firm wrote is quoted and anything else is named by class. No `except` in
  the function swallows anything any more.
- `client_folder_missing(household_dir, returns=None)` **looks at the disk
  first**: when `layout.client_household_dir(root, name).is_dir()` it returns
  `""` without reading the record (nothing is to be decided, and the pass
  asks this of every household). Only when the folder is gone does it ask
  `client_side_expected`; `ClientSideUnknown` passes through to the caller.
  `door.client_folder_missing` is unchanged.

## 3. R2 - the three callers each say what they do with it

- `tracker/runner.py`, the held-back block: wrap the
  `client_folder_missing(...)` call; on `ClientSideUnknown`,
  `held_back = str(exc)` and `held_code = CODE_RECORD_UNREADABLE` (the code
  the pass already uses for a record it cannot read; the remedy is the same).
  Every run of the household carries it, as the folder-missing case does.
- `tracker/scaffold.py`, the `may_make_household is None` branch: on
  `ClientSideUnknown`, `raise ClientFolderMissing(str(exc)) from None`, so
  `create` and every Roll forward refuse with the sentence and make nothing.
- `tracker/registry.py`, the household's pause sentence
  (`household_pause(folder) or client_folder_missing(folder)`): on
  `ClientSideUnknown` return `str(exc)`, so the list and the household's card
  show it where they show the folder-missing sentence today.

## 4. R3 - the runbook

`docs/runbook.md` has an entry for the "`Clients\<name>` is missing. Was the
household renamed or moved?" hold-back (find it by that phrase). Add one
paragraph after it: the variant sentence above, that it means the record is
the first thing to repair (section 6), and that no folder is made meanwhile.
`tests/test_single_source.py` may quote the layout's sentence; keep whatever
it pins passing.

## 5. Tests

- `tests/test_households.py`
  - `test_a_household_whose_record_cannot_be_read_is_not_said_to_have_had_no_client_folder`:
    a household record with one line appended that breaks the ledger's link,
    its client folder removed → `client_folder_missing` raises
    `ClientSideUnknown` whose message is `CLIENT_SIDE_UNKNOWN` filled with
    the household's name and the ledger's own sentence; the error log holds
    the exception.
  - `test_a_client_folder_that_is_there_is_never_a_reason_to_read_the_record`:
    with the folder present and `shared_on` monkeypatched to raise,
    `client_folder_missing` returns `""`.
- `tests/test_runner.py`
  `test_a_shared_household_whose_record_cannot_be_read_is_held_back_and_its_client_folder_is_not_remade`:
  the audit's reproduction - a household marked shared, its client folder
  removed, one unlinked line in its record, a pass → every run of the
  household has `error == CLIENT_SIDE_UNKNOWN.format(...)` and
  `code == CODE_RECORD_UNREADABLE`, nothing is filed, and
  `Clients\<name>` does not exist after the pass. The existing
  `test_a_household_renamed_in_the_firm_tree_pauses_and_makes_no_client_folder`
  and `test_a_new_return_or_a_roll_forward_never_makes_a_gone_client_folder_again`
  keep passing unchanged.
- `tests/test_scaffold.py`
  `test_the_scaffold_refuses_to_lay_out_a_household_whose_record_cannot_be_read`:
  `ClientFolderMissing` with the sentence; no folder made.
- `tests/test_registry.py` (if the household pause sentence is tested there;
  else `tests/test_households.py`)
  `test_a_household_whose_record_cannot_be_read_says_so_where_its_pause_is_said`.

## 6. Files

Code: `tracker/households.py`, `tracker/runner.py`, `tracker/scaffold.py`,
`tracker/registry.py`. Docs: `docs/runbook.md`. Tests: `tests/test_households.py`,
`tests/test_runner.py`, `tests/test_scaffold.py`, `tests/test_registry.py`.
Then `python tools/repo_map.py update`. **Not** `pilot/DECISIONS.md` (the
landing session adds P296) and not any file the form-inputs build owns
(`tracker/{api,records,layout,door,manifest,templates,store,settings,filer}.py`
and their tests).

## 7. The gate

Dead code first. Then one process per file, in parallel: `test_households`,
`test_runner`, `test_scaffold`, `test_registry`, `test_door`, `test_layers`,
`test_single_source`, `test_repo_map`. Then `python -m ruff check .` and
`python tools/repo_map.py check`. Another build runs in the same checkout;
if the map check or `test_repo_map` fails only on its half-edited files, run
`update` again and retry once, and say so in the handoff. Never the whole
suite; the router and the readers are untouched.

## 8. Handoff

`pilot/HANDOFF-client-folder.md`: what was built against R1-R3, the gate's
counts file by file, anything done differently and why, the files the
reviewer needs. The reviewer reads this SPEC, the diff and that handoff, and
writes numbered findings under "## Review".

## 9. Decision row (added by the landing session)

| P296 | 2026-10-13 | A household whose client folder is gone and whose record cannot be read is held back with one sentence saying both (`households.ClientSideUnknown`), never laid out again under the old name; the pass, New return, Roll forward and the household's card all say it, and a client folder that is there is never a reason to read the record (SPEC-client-folder-unreadable). | The error-handling audit of 2026-10-13 (E1): a swallowed read failure answered "never had one" and the pass remade `Clients\<name>` while warning the record could not be read. |

---

## 10. Amendments after the first review (Opus, 2026-10-13)

Findings F1-F4 are in `pilot/HANDOFF-client-folder.md` under "Review". The
deviation (a journal file that does not exist is skipped, not "cannot tell")
is accepted: the old code skipped it too, a household with no record is
stopped before this check on every path, and the SPEC's literal wording broke
three runner tests. All four findings are built.

**R1, amended (F1).** The sentence names whose record failed, so a person
repairs the right one:

`CLIENT_SIDE_UNKNOWN = ("`Clients\\{name}` is missing and the record of {whose} could not be read ({problem}), "
"so the app cannot tell whether the household was renamed or moved. Nothing is made under the old name "
"until that record reads again (runbook section 6).")`

`whose` is `the household` when `shared_on` failed, and
``its return `<folder name>` `` (the return folder's own name in backticks)
when a return's `store.documents` failed. The error-log entry carries the
same name (`errors.keep(..., name=<the folder whose journal failed>)`).
The runbook paragraph says "the household's record, or one of its returns'",
and that the sentence names which. Tests: the households test checks both
spellings, one for each half.

**F2 (nit): kept as built.** When one part of the record will not read, the
answer is "cannot tell" even if another return proves the folder existed:
both answers stop the household, and "cannot tell" sends a person to the
broken record first. Say so in `client_side_expected`'s docstring.

**F3 (nit).** A households-level test for the deviation:
`test_a_journal_that_does_not_exist_is_skipped_and_only_one_that_will_not_read_is_cannot_tell`.

**F4 (nit).** `registry.held_back`'s docstring names the "cannot tell" answer;
the registry test's docstring says who reads `held_back` (New return and Roll
forward), not the list and the card.

Gate after the rebuild: `test_households`, `test_runner`, `test_scaffold`,
`test_registry`, `test_single_source`, `test_repo_map`, ruff, the map check.
The builder appends `## Rebuild 1 (Sonnet, 2026-10-13)` to the handoff.

---

## 11. Amendments after the second review (Opus, 2026-10-13)

Findings G1-G4 are in `pilot/HANDOFF-client-folder.md` under "Review 2", and
a fifth item comes from the form-inputs lane's third review, which ran
`tests/test_errors.py`. None survived a rebuild, so the rebuild is Sonnet's.
All five are built.

**R1, amended (G1): the return is named year first.** Roll forward keeps a
return's name across seasons, so `1040 - X` alone cannot say which year's
record failed. `whose` is ``its return `<year>\<folder name>` `` - the return
folder's parent (the year folder) and its own name, joined by a backslash as
the layout's sentences write paths (`f"its return `{one.parent.name}\\{one.name}`"`).
The error-log entry carries the same (`name=f"{failed.parent.name}\\{failed.name}"`
for a return; the household's folder name for the household). The runbook
says ``its return `<year>\<folder name>` ``. Test: the existing
`test_the_sentence_names_the_return_whose_record_cannot_be_read` checks the
year is in the sentence.

**Tests (G2).** The same test asserts the exact log entry,
`"households: the client-side history (2025\\1040 - John)"` (the fixture's
year and folder), not the folder name anywhere in `caplog.text`, which the
store's own checkpoint warning already satisfies.

**Docstring and runbook (G3).** `client_side_expected`'s "one part that will
not read" paragraph says what the code does: the halves are read in order -
the household's record, then each return - and the first definite answer
wins, so a household whose own record says it was shared, or whose earlier
return proves the folder existed, gets the folder-missing sentence even if a
later return would not read; "cannot tell" is the answer only when the read
fails before any half has answered. The runbook paragraph says the same in a
sentence, and prints *the household* without backticks (only a return's name
is in backticks, as the sentence prints it).

**Test name (G4).** The F3 test either checks both halves (a journal that is
there and will not read raises `ClientSideUnknown`, beside the missing one
that is skipped) or is renamed to the claim it makes. Check both halves.

**`tests/test_errors.py::test_the_error_class_list_is_spelled_once`.** The
rule: no module turns a caught exception's words into a string except through
`tracker.errors`. The three `except ClientSideUnknown as exc:` handlers
(`registry.held_back`, `runner.run_household`, `scaffold.scaffold_household`)
use `str(exc)`; each becomes `errors.said(exc, (ClientSideUnknown,))`, the
form the runner already uses for `FEEDS_UNREAD`, which returns the sentence
whole for the firm's own class. `errors` is imported where it is not already
(a load-time import of `errors` breaks no layer; `tests/test_layers.py`
confirms). No wording changes.

Gate after the rebuild, one process per file: `test_households`,
`test_runner`, `test_scaffold`, `test_registry`, `test_errors`,
`test_single_source`, `test_layers`, `test_repo_map`, ruff, the map check.
The form-inputs lane's rebuild 3 runs in the same checkout and touches
`tracker/{manifest,filer,api}.py`, their tests and `pilot/DECISIONS.md`: this
build touches none of those, and retries the map check once if it fails only
on that lane's half-edited files. The builder appends
`## Rebuild 2 (Sonnet, 2026-10-13)` to the handoff.

---

## 12. Amendments after the third review (Opus, 2026-10-13)

Findings H1-H2 are in `pilot/HANDOFF-client-folder.md` under "Review 3".
Neither survived a rebuild, so the rebuild is Sonnet's. Both are built.

**R2, amended (H1): the pause check lets the "cannot tell" check run.**
`registry.held_back` asks `households.household_pause` before
`client_folder_missing`, and `household_pause` skips a return whose details
raise `ManifestError`, `ValueError` or `OSError` only, so a return record the
ledger refuses (`LedgerError`) or the store cannot use (`StoreError`) escapes
with its own sentence before the client-folder check is reached: New return
and Roll forward never say which record to repair, which is what R1 as
amended is for. Its docstring already says "a record that cannot be read
claims nothing here; the pass says its own problem", and
`load_household_info` in the same function is caught whole. So the return
loop's `except` becomes `(ManifestError, LedgerError, StoreError, ValueError,
OSError)`, with `LedgerError` and `StoreError` imported at call time inside
the function as `client_side_expected` already imports them (no load-time
edge; `tests/test_layers.py` stays as it is). No sentence changes.

Test, `tests/test_registry.py`
`test_a_return_whose_record_will_not_read_is_said_as_cannot_tell_where_a_new_return_asks`:
a household marked shared, its client folder removed, one unlinked line in
one return's record → `held_back` returns `CLIENT_SIDE_UNKNOWN` filled with
the household's name and ``its return `<year>\<folder>` `` (no exception
escapes). And the other half: the same broken return with the client folder
present → `held_back` returns `""` (the pause claims nothing, and a folder
that is there is never a reason to read the record). Both fail on 7df8b93:
the first with the ledger's own error escaping.

**Runbook (H2, nit).** The one line of the "same hold-back, when a record
cannot be read" paragraph that runs past about 80 columns is rewrapped; no
words change.

Gate after the rebuild, one process per file: `test_registry`,
`test_households`, `test_runner`, `test_scaffold`, `test_errors`,
`test_single_source`, `test_layers`, `test_repo_map`, ruff, the map check.
The form-inputs lane's fourth review runs in the same checkout and edits
`pilot/HANDOFF-form-inputs.md` only. The builder appends
`## Rebuild 3 (Sonnet, 2026-10-13)` to the handoff.
