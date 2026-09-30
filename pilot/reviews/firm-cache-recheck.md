# Re-check - lane 1 (P115) fold, commit 92729ef

Reviewer: the same separate reviewer agent (it did not build or fold this). Re-checked
`claude/firm-cache` at `92729ef` against `pilot/reviews/firm-cache-rulings.md`. No edits and
no commits; this file is not committed.

## Verdict

| Item | Result |
|---|---|
| (1) SHOULD-2, ruled a MUST: a same-size rewrite with its time put back | **PASS**. The P15 case and every variant I made now match the whole walk. |
| (1b) The pin test really fails when an opened file is added | **PASS** (mutation-checked) |
| (2) SHOULD-4 choice (i): leaving out the status page and folder times | **FAIL: 1 new MUST (MUST-R1 below).** Folder times are safe. Leaving the status page out is applied too widely. |
| (3) The 21-kind byte-for-byte comparison on the fold | **PASS**. All 25 steps (P0-P20, P14 counted 5 times) match; P21 is clean. |

## New MUST

**MUST-R1 - The status-page exclusion hides a client's drop, so the held count goes stale.**

Where: `tracker/firm_cache.py:237` (`if entry.name in left_out: continue`), applied through
`fingerprint()` at `tracker/firm_cache.py:188`.

What is wrong: `FIRM_JUDGED.left_out = {"Status Report.html"}` (`tracker/api.py:5607`) is
applied:
- in the **client** folder as well as the private one;
- at **any depth**;
- to **folders** as well as files.

So a client file named `Status Report.html` in `Drop files here` never reaches the
fingerprint. Neither does a subfolder of that name, and neither does anything inside it. A
client forwarding the firm's own page back is plausible.

Probes on the folded code, in both cases after the practice had aged:
- **V5:** a client drop `Drop files here\Status Report.html`. The whole walk says
  `draft.held = 1`; the cached reply still says `held = 0`.
- **V6:** a subfolder `Drop files here\Status Report.html\` holding `w2.pdf`. Same result:
  `held` is 1 in the whole walk and 0 in the cache.

That is a status the cache answers wrong. `held` is what decides whether the reminder is
held.

Fix:
- Apply `left_out` only to **files** that sit **directly in a return folder** of the private
  tree: the private folder at depth household / year / return, where
  `view.VIEW_FILENAME` is written.
- Never apply it in the client folder, and never to a folder.
- Add V5 and V6 to
  `tests/test_api.py::test_the_first_overview_after_a_pass_reads_no_household_again`, or a
  new test, asserting that the cached reply equals `_firm_whole`.

## (1) Records rewritten at their size and time - details

Each probe changed the file's bytes at the same length, put its modification time back with
`os.utime(ns=...)`, then compared the cached `firm` with the whole walk:

- **V1**, the household's record (`_ledger.jsonl` in the household folder): equal.
- **V2 / P15**, a return's record, an early line changed from `"active": true` to
  `"active":false`: equal. Both now say **Could Not Be Read**; before the fold the cache
  said healthy.
- **V3**, the inbox `_README.txt` replaced by other bytes of the same size (a client's file
  of that name is a drop, per decision 179): equal.
- **V4**, a reminder draft approved through `approve` (after a `--reminders always` pass),
  then edited at the same size and time: equal.
- **P3**, inbox files judged by size and time only (renamed with the time kept): equal. The
  count depends only on the names, so a rewrite at the same size and time cannot change a
  status there.

**The pin test was mutation-checked**
(`test_every_file_a_firm_reply_opens_is_judged_by_its_bytes_and_never_the_status_page`). I
ran it through a scratch pytest plugin (`-p mut_plugin`) that wraps `api._firm_draft`, with
no tracked file edited:
- unmutated: 1 passed;
- mutation "open `extra-notes.txt` in the return": **1 failed**, at
  `assert where.name in judged.private_whole | judged.client_whole`;
- mutation "open `Status Report.html`": **failed**, at `assert where.name != VIEW_FILENAME`.

Two limits of the test, NIT:
- it watches only the whole walk, not the cached path;
- it sees only opens made through Python's `open` audit event.

## (2) Folder times left out - details

Dropping folder times cannot hide a change. Any entry added, removed or renamed changes the
recursive listing of names. These probes put every time back (`age()`) after each change:
- V7, a drop removed from an inbox: equal.
- V8, a file added to `00 - Needs Review`: equal.
- P1, P2 and P20: equal.

**V9, a scheduled pass over an unchanged practice:** the next Overview read 1 of 9 rows. That
one is the household whose record is gone, which is never kept. Before the fold it reread
every household the pass ran. So SHOULD-4's point is fixed.

The only failure in (2) is where the status page is left out (MUST-R1).

## (3) The 21-kind comparison - details

`probe_cache.py` ran on 3.14 at `92729ef`. P0-P20 all print `OK`, 25 lines with P14 counted
5 times: the cached reply twice, the whole walk, and main `877c7a2`'s code, byte for byte.
`list` also equals main's.

- **P16 (`~$lock`) and P19 (`_Archive`):** a warm reply now reads 1 of 9 rows. No warning is
  logged, where before every reply logged `LayoutError`. SHOULD-1 is fixed.
- **P21, three processes racing:** every exit 0, the file loads, no temporary files left over.
- **P17 (store only):** unchanged. Known limit (1) stands.

## NIT (new)

- **NIT-R1:** `client_whole` and `private_whole` also match by name at any depth
  (`tracker/firm_cache.py:251-256`). So a *client's* file named `_README.txt` in an inbox
  subfolder, or `reminder-draft.txt` parked in `00 - Needs Review`, is read whole and
  hashed.
  - Nothing interprets those bytes, and nothing breaks.
  - But it contradicts the SPEC's "a client's documents are never among them and are never
    opened".
  - Fix: match the README only at the inbox's top level (`inbox / README_NAME`, as
    `iter_drops` does), and the drafts and record only where they are written.

## Tests (each file its own process; `.venv` = 3.14.3, `.venv311` = 3.11.15)

| File | 3.14 | 3.11 |
|---|---|---|
| tests/test_firm_cache.py | 27 passed, 1 skipped in 7.87s, exit 0 | 27 passed, 1 skipped in 7.09s, exit 0 |
| tests/test_api.py | 418 passed in 874.61s (0:14:34), exit 0 | 418 passed in 1153.62s (0:19:13), exit 0 |

The one skip is the symlink test, as before. The junction case NIT-5 asked for is not
skipped. The suite passes even with MUST-R1 present, because no test drops a file named like
the status page into an inbox.

## Probes

In the reviewer's scratchpad:
- `probe_cache.py`: the original P0-P21 plus the re-check steps V1-V9.
- `mut_plugin.py`: the pin-test mutations.

The practice was built in `%TEMP%\fcp` from `tests/samples.py` and
`tests.conftest.make_engagement`, with made-up names only. Nothing was opened under
`PilotTest`. I did not time the fold on the 750-return sample: the fold now reads every
record whole on every reply, and that cost is unmeasured here.
