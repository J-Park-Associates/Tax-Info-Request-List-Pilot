# Re-check: lane 4b review fold (a640630, `claude/column-order`)

Reviewer: the same separate reviewer as `lists-review.md`. Date: 2026-09-30. I re-checked only
M1 and S1, as the orchestrator asked. No edits and no commits; this file is the only change.

Result: **M1 PASS, S1 PASS. One new MUST (N-M1)**, which the S1 fold brought in.

## M1: a link recorded on one side only

Probe: `scratchpad/probe/test_probe_recheck.py`, built on the `tests/test_api.py` fixtures with
made-up names. Setup:
- Lee has contact "Sam" and members ("Sam Lee").
- Lee and LLC are linked on both records.
- Park names Lee, but Lee does not name Park (the crash case).

| Case | Result |
|---|---|
| A. Re-save Park with [Lee] | exit 0. Lee's record gains Park. Lee's contact, members and LLC link are kept. |
| B. Save Lee with [LLC, Park] | exit 0. Both records name each other; the LLC link is kept. |
| C. Save Lee with [LLC] (Park removed on the side missing it) | exit 0. Park's record is cleared, and `list` shows Lee linked to LLC only. |
| D. Save Park with [] | exit 0. Both records are clear of each other; the LLC link is kept. |
| E. Save Lee with contact only (no `related` key) | exit 0. The link stays one-sided. This is expected, because the editor always sends `related`. |

Re-saving either side repairs the link, and nothing else is lost. The new test
`test_a_one_sided_related_link_is_repaired_by_saving_either_side` covers this. **PASS.**

## S1: each household read and written inside its own lock

- `_mirror_related` (`tracker/api.py:4110-4142`) takes `engagement_lock(other.path)`, reads the
  record fresh under it, and calls `save_household(..., lock_held=True)`.
- The command's own save (`api.py:4187`) takes and releases its lock before the mirror runs
  (`:4189`). No two locks are ever held at once, so there is no lock-order deadlock.
- Probe G: a lock held on a household with no link to the one being saved does not block the
  save (exit 0).
- The new test `test_the_other_households_record_is_read_and_written_inside_its_own_lock` covers
  this.

**PASS.**

## New MUST (N-M1): the refusal says "nothing was changed" after the save already happened

Probe F: Lee's lock is held (for example, a scheduled pass is sorting Lee). The person saves
Park's Edit Household with contact "John P" and related [Lee].
- The reply is exit 1, with `error` = "another pass holds this return's lock (taken 0 s ago);
  nothing was changed, and it is let go when that pass ends" (`tracker/locking.py:308`).
- In fact **Park's record was already written**: the contact is now "John P" and Park names Lee.
  Only Lee's side was not written.
- The sentence is false in two ways. It says nothing changed, and "this return's lock" points at
  the return the person is editing, not at Lee Family. A person would reasonably type the edit
  again, or think it was lost.
- Retrying after the lock is let go completes the link (exit 0).

**Is refusing right?** Yes, the refusal itself is right. The command must not wait on or skip a
lock, and the link shows on both ends from Park's record in the meantime. The words are what is
wrong.

**Fix** (`tracker/api.py:4187-4190`): catch `EngagementLockedError` from `_mirror_related`, then
choose one of:
- (a) Reply with the save as done, plus a warning. Suggested wording, a new vocabulary sentence:
  "Saved. {household} is being sorted, so its record will name this one when you save again
  after the sort."
- (b) Raise a new error with the same meaning, whose sentence does not say "nothing was changed".

Either way, add a `test_api` claim that a held lock on the other household returns that
sentence, and that the first record is saved.

A smaller point: because the editor always sends `related`, **every** Edit Household save now
takes the lock of each linked household. A pass sorting a linked household therefore returns
this message even for a contact-only edit. Wording (a) covers that case as well.

## Tests (`C:\Users\User\pl\order`, each file its own process)

| File | Python 3.14.3 (`.venv`) | Python 3.11.15 (`.venv311`) |
|---|---|---|
| tests/test_api.py | 412 passed, exit 0 | 412 passed, exit 0 |
| tests/test_households.py | 16 passed, exit 0 | 16 passed, exit 0 |
