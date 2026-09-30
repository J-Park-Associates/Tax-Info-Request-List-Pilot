# Re-check 2: MUST-R1 (737aa89, `claude/column-order`)

Reviewer: the same separate reviewer as `lists-review.md` and `lists-recheck.md`. Date: 2026-09-30.
Only MUST-R1 was re-checked. No edits or commits; this file is the only change to the tree.

**Result: MUST-R1 PASS. No new MUST.** Two NITs about wording, below.

## Probe

The probe is `scratchpad/probe/test_probe_recheck2.py`. It uses the `tests/test_api.py` fixtures and made-up names only.

Setup:
- Park and Lee are linked on both records.
- For the whole locked stretch, the probe holds Lee's household lock itself, the way a sort would.
- A spy on `api.engagement_lock` counts every attempt to take a lock.

| Step (Lee's lock held) | Result |
|---|---|
| 1. Contact-only save of Park (the editor still sends `related: [Lee]`) | exit 0, `warnings: []`, **0 attempts to take Lee's lock**, Lee's journal 2 -> 2 lines (nothing written there), Park's contact is saved |
| 2. Link removed on Park (`related: []`) | exit 0, no `error`, warning **"Link Pending: Lee Family Is Sorting"**; Park is saved `()`, Lee still names Park |
| 3. Link added back on Park | exit 0, no warning (Lee already agrees), Park names Lee again |
| 4. Link removed on Park again (locked) | Park `()`, Lee unchanged (pending) |
| After the lock is released: 5. Save Park again (`[]`) | exit 0, no warning, **Lee cleared**: the later save completes the link |
| 6. Save from Lee | exit 0, both records clear |

"Nothing was changed" never appears.

How the notice reaches the screen: `app.js` `call()` turns every warning in a reply into a notice (`app.js:163-171`). Edit Household's save goes through `call()`, so the person sees it.

The new tests in `tests/test_api.py` cover both cases: a contact-only save takes no lock, and a locked household leads to a saved edit with the notice.

## Words: "Link Pending: {household} Is Sorting" (`tracker/api.py` SCREEN.notices.related_pending)

Checked against SPEC-shell 11.1:
- **Length:** 4 words plus the placeholder, which counts as one word: 5, within the limit.
- **Title Case:** yes, including the capital after the colon.
- **Vocabulary:** "sort" is a word the rules allow; no forbidden word ("pass", "record", "manifest") and no path.
- **Truth:** it does not claim the edit failed.

Pass.

- **NIT-a:** the lock may be held by something other than a sort. It could be another write by the app to that household, or a lock left behind by a crash (which Tools > Clear Lock fixes). In those cases "Is Sorting" is not quite true. A wording such as "Link Pending: {household} Is Busy" would be true in every case, and is still five words.
- **NIT-b:** the notice does not tell the person to save again once the sort ends. Five words leave no room for that. A tooltip or the runbook line for this notice could say "Save again after the sort to finish the link".

## Tests (`C:\Users\User\pl\order`, each file in its own process, run in parallel)

| File | Python 3.14.3 (`.venv`) | Python 3.11.15 (`.venv311`) |
|---|---|---|
| tests/test_api.py | 414 passed, exit 0 | 414 passed, exit 0 |
| tests/test_households.py | 16 passed, exit 0 | 16 passed, exit 0 |
