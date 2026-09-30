# Review - lane 1 (P115): the firm view's cache and speed work

Reviewer: Opus 5.5, a separate agent (did not build this and did not write its SPEC).
Branch `claude/firm-cache`, head `3e55bdb`, 5 commits on main `877c7a2`, 22 files.
Reviewed against `pilot/SPEC-firm-cache.md` (P118-P123) and the standing rules.
Date: 2026-09-30. Nothing was committed, pushed or edited in tracked files. The only
file written in the worktree is this review, and it is not committed.

## Verdict

**0 MUST, 4 SHOULD, 5 NIT.**

The cache never gave a different reply from the whole walk in any ordinary case I could
make: 21 kinds of change, on both interpreters, all byte-identical to the whole walk and
to main's code. I did find one way to make it stale: a journal rewritten at the same size
with its old modification time put back (SHOULD-2). That takes a tool that deliberately
keeps a file's time, and the SPEC does not name it as a limit. The P119 rewrites gave the
same answers as the old rules over 3,400 random inputs. The two biggest practical
problems are both about speed, not correctness:

- one folder named with `_` (for example `_Archive`) turns the cache off for good
  (SHOULD-1);
- every scheduled pass empties it (SHOULD-4).

## Findings

### MUST

None.

### SHOULD

**SHOULD-1 - A folder in the firm's tree whose name the layout refuses turns the cache off for
every reply, for good.**
`tracker/api.py:5622` calls `layout.client_household_dir(private.parent, folder.name)`. It
does this for every folder `registry.household_positions` returns (`tracker/registry.py:414`),
and that function does not leave out the folders the walk skips. So a folder starting with a
prefix in `layout.MACHINE_PREFIXES` (`.`, `_`, `~$`) makes the call raise `LayoutError`. So
does a name that `segment_problem` refuses, such as `Smith.`. The error is caught by the
general `except` in `_firm_cached`. Every reply then falls back to the whole walk, and
`log.warning` plus a full traceback (`errors.keep`) go to the error log each time.
- Probe P19: `J Park & Associates\_Archive` read 9 of 9 rows on every warm reply, and the log
  said "The firm view's cache was set aside (LayoutError)". Probe P16 did the same with `~$lock`.
- `_Archive` or `_Templates` folders are ordinary in a firm's tree. One of them brings back
  the 7.6 s-plus Overview, and nothing on screen says why.
- `household_positions`' docstring says it finds households "exactly as `_walk_root`",
  which it does not.

Fix: in `household_positions`, leave out the folders `_skip()` leaves out, as `_walk_private`
does through `_walk_one_household`. For a folder where `layout.segment_problem(name)` is not
None, fingerprint only its private folder: give `fingerprints` a pair whose second half is
`None`, or skip `client_household_dir` for it. The walk turns that folder into a misfit and
gives no returns, so keeping it is harmless. Add `_Archive` and `Smith.` cases to
`tests/test_registry.py::test_household_positions_are_the_walks_households_in_the_walks_order`,
and add a `_Archive` folder to the practice in
`tests/test_api.py::test_the_firm_view_from_its_cache_is_the_whole_walks_reply_through_every_change`,
asserting that a warm reply reads no row.

**SHOULD-2 - The fingerprint is only names, sizes and times, so a rewrite that keeps both the
size and the time gives a stale status. The SPEC does not name this limit.**
`tracker/firm_cache.py:188-211`. Probe P15, the same on 3.14 and 3.11: I changed
`"active": true` to `"active":false` in one return's `_ledger.jsonl`, at the same byte length,
and then put its modification time back.
- The whole walk says **Could Not Be Read**, because the hash chain is broken.
- The cached reply still shows the row as healthy (`waiting: 2`, no problem).

This is the "nothing is guessed / never stale" case the standard asks about. Ordinary writes,
sync clients and Explorer copies all change the size or the time. It takes a tool that keeps
a file's time, such as `robocopy /COPY:T`, a backup restore or a hand edit plus `touch`. That
is why this is SHOULD and not MUST. The SPEC's line "Equality is what is compared ... a sync
client that sets an older modification time still changes the fingerprint"
(`pilot/SPEC-firm-cache.md:173`) is true, but not the whole story.

Fix: add a digest of the **whole bytes** of every `_ledger.jsonl` under the household (the
return records and the household record) to its fingerprint.
- A digest of only the last part of the file is not enough. P15 changed an early line; the
  chain breaks there, but the bytes at the end stay the same.
- These are the firm's records, not client documents, and the whole walk already reads each
  one. Measure it at 750 first.

If it costs too much, or the rulings keep "nothing is opened", add this case to the SPEC's
Known limits as (3) and to `docs/runbook.md` next to "deleting the file is always safe".
Jason should see it in the SPEC as an accepted limit. Either way, add a test that makes the
P15 rewrite and asserts the reply that follows.

**SHOULD-3 - `test_the_commands_held_to_one_reading_write_nothing` does not test writing, and
a settings write inside a reading would leave a stale answer held.**
`tests/test_api.py:8693` only checks that the two command sets do not overlap. Inside
`one_reading()`, `settings._write` (`tracker/settings.py:389`) does not clear
`_HELD[_SETTINGS_HELD]`, so a later `_read()` in the same reading would answer from before the
write. The resolved paths and `data_home` are held the same way.

My probe (`held_probe.py`) ran `list`, `state` on each of 11 returns, and `firm`, with a spy on
`_write`, and found **no** write inside a reading today. So this is a guard for later, not a
bug now.

Fix: in `settings._write`, if `_HELD is not None`, raise
`RuntimeError("a write inside one_reading()")`. That turns P118's rule into an assertion the
code checks every time. Then rename the test, or add a behavioural test that runs `list`,
`state` and `firm` with that guard in place.

**SHOULD-4 - Every scheduled pass empties the cache for every household it runs, so the 3 s
target holds only between passes.**
SPEC Known limit (2) says "the sample could not show which files a pass rewrites". I measured
it. On a practice with nothing changed, a pass (`python -m tracker.runner --reminders never`,
run a second and third time) changed these in every household it ran (4 of 4 running
households):
- each return's `Status Report.html` (size and time);
- the time of the return folder and of the household folder (lock and temporary files
  created and removed).

So the first Overview after each pass reads the whole practice again. The default schedule
runs every 120 minutes (`settings.DEFAULT_SCHEDULE_EVERY`), and a full reread is the builder's
own "9.3-12.9 s at 750". That is above SPEC-shell 9.2's 3 s several times a working day.
(This also rewrites 750 files that are synced, every pass, but that is outside this lane.)

Fix, choose one:
- (a) Leave folder times out of the digest. Hash only a folder's name and kind: its children
  are listed anyway, so an added or removed entry still changes the digest. Also leave out
  `Status Report.html` (`view.VIEW_FILENAME`), which the tracker writes and `_firm_row`
  never reads: none of the modules it calls names `VIEW_FILENAME`. Pin that rule
  with a test that fails if `_firm_row` ever reads it.
- (b) In a runner SPEC, have the pass write the status page only when its bytes differ, which
  also stops the sync churn.

(a) is inside this lane. Put the measured behaviour into the SPEC's limit (2) either way.

### NIT

- **NIT-1** `tracker/registry.py:894` and `:908`: `_two_claims` uses the name `first` for the
  key-to-index dict, then reuses it for a `Household` in the second loop. It works, because the
  dict is no longer used, but it reads as a bug. Rename the dict `holder`.
- **NIT-2** `tracker/firm_cache.py:207`: on Windows, `DirEntry.stat()` takes size and time
  from the directory entry, and NTFS updates that entry for an open file only when its handle
  closes. The SPEC's "one reply behind a change that is still being written" is true only once
  the writer closes the file. One sentence in P120's "How it knows a return changed" would say
  so.
- **NIT-3** `tracker/firm_cache.py:147`: the racy window is measured against this PC's clock.
  On a network share whose clock runs more than 5 s behind, a coarse-time rewrite can pass the
  window. Worth a clause in the `RACY_SECONDS` comment. No code change needed at 5 s on local
  NTFS.
- **NIT-4** `tracker/settings.py:309-330`: `_read()` returns `dict(data)`, a shallow copy. The
  docstring and SPEC P118 say "each caller gets its own copy", but a nested value in
  `settings.json` would be shared. Say "a shallow copy", or use `copy.deepcopy`.
- **NIT-5** `tests/test_firm_cache.py:102`: the only link test uses a symbolic link and is
  skipped on this PC (no Developer Mode). I checked a **junction** by hand (probe J1):
  `fingerprint()` returns `None`, reparse tag `0xA0000003`. Add a junction case made with
  `_winapi.CreateJunction` (no admin needed), so the Windows path is really tested here.

## What was checked and held (the orchestrator's list)

| Asked | Result |
|---|---|
| File added / removed / renamed / modified in the inbox, in a return, in `00 - Needs Review`, in `Prepared`, in the client-side year folder | P1-P3, P20: cached = whole = main's code |
| Household record changed (Edit Household contact; the record's name) | P4, P5: equal. Rows are kept as generic JSON, so lane 4b's new fields pass through, and a code change changes the program stamp (checked in `program_stamp`). |
| Return edited (switched off) | P6: equal |
| Household added / removed / renamed (both trees) | P7-P9: equal |
| A cross-household Roll Forward whose successor goes away (prior shown again, its row not kept) | P10: equal; the "short" reread path ran |
| Settings changed (firm name) | P11: the head changes and every household is reread; equal |
| Same-second / racy edit; mtime in the future | P12, P13: not kept, reread; equal |
| Cache garbage / wrong shape / other program / tampered row / empty | P14 (5 cases): each refused and rebuilt; equal |
| Store (tracker.db) changed, folders not | store probe: rows deleted from `requests` for one return, so the whole walk shows 0 waiting and the cached reply 5 (the journal's truth). This is SPEC Known limit (1), confirmed; the kept row matches the journal, not the damaged store. |
| Same-size, same-time rewrite | P15: **stale** -> SHOULD-2 |
| Folder at household position with `_` / `~$` prefix | P16, P19: cache off every reply -> SHOULD-1 |
| Nothing written in either client tree; cache not rewritten when nothing changed | P18: tree and cache time unchanged over two warm replies. The data folder holds only `firm-view.json` (plus the store's files where the store is). |
| Two processes at once | P21: 3 processes x 12 replies, each touching `settings.json` to force a rewrite. Every exit was 0, the final file loads, no temporary files were left, no warnings. |
| Link / junction | the symlink test is skipped here; junction probe J1: `None` (NIT-5) |
| When the whole walk takes over | `_firm_cached` falls back on: `household_positions` giving `None` (no private tree, or more than one, or an `OSError` listing the root or the tree); `_FirmUnsure` (a "short" household whose facts changed during the reply); and any other exception, logged. Seen in practice: `LayoutError` from a refused name (SHOULD-1). |
| Decision 186 | `cache_path()` = `settings.data_home() / "firm-view.json"`; P18 shows nothing written in either tree |
| Read-only commands stay read-only | the `held_probe` spy: no settings write inside a reading (SHOULD-3 hardens this) |
| Layers, network, dependencies | `firm_cache` imports only the standard library plus `errors`, `settings`, `fsio` (layer 0, pinned in `test_layers`). No network. `pyproject.toml` and the lock files are unchanged. |
| P119 behaves the same (order, ties, duplicates) | `p119_child.py` ran main's and the branch's `_two_claims` and `mark_superseded` on 400 seeded random practices: output identical byte for byte. That covered 264 seeds with two claims, 174 with a retired prior and 338 with an unmatched Rolled From, including ties, self-reference, problem returns and moved-drive fallbacks. `firmkey_probe.py`: 3,000 random key sequences, including literal ` #` keys, identical to the old `_firm_key`. The client-folder check is the same `normcase` key, as a set. |
| `firm` and `list` against main's code | every P0-P10 step: the branch's whole walk = main's `firm`; `list` = main's `list` (P0). Both interpreters. |
| `test_firm_is_read_only` | now leaves out only `firm_cache.cache_path()`; everything else in the data folder and both trees is still snapshotted. Correct. |
| `test_store` admission pin | **Not docstring-only**: the digests of `settings._read` and the store's three resolvers moved, and `_held`, `resolved` and `_SETTINGS_HELD` joined the pin. The test's own rule allows re-pinning under version 2 when nothing new is refused. `resolved` returns what `Path.resolve` returns, and errors are never held, so nothing new is refused. Acceptable. |

## Speed (750 returns, `%USERPROFILE%\PilotTest\Clients-750`)

Run only as told: `TRACKER_SETTINGS_DIR` pointed at `settings-750`, the command run with its
output thrown away. No file there was opened, printed or read by me. One `test_api` process
was running on the PC at the time.

| Command | 3.14 | 3.11 |
|---|---|---|
| `firm`, first reply (a fill: new day, or the other interpreter's program stamp) | 7.50 s | 9.24 s |
| `firm`, warm | 1.27, 1.06, 1.37 s | 1.64, 1.45 s |
| `list` (P118/P119 only) | 3.03, 3.09 s | - |

The claims hold, and are a little better than the hand-back's figures (warm 1.85-2.33 s;
fill 9.3-12.9 s; `list` 3.3-4.9 s). The SPEC-shell 9.2 target of 3 s is met warm. It is not
met on the first Overview of each day, nor after each scheduled pass (SHOULD-4), nor at all
with a `_` folder present (SHOULD-1). `list` sits right at 3 s, as P121 said it would.

These runs left `firm-view.json` in `settings-750`'s data folder, with made-up names. I did not
delete it (it is not mine to remove); the builder removed theirs.

## Tests (each file its own process, in parallel; `.venv` = 3.14.3, `.venv311` = 3.11.15)

Run with `-p no:cacheprovider`, so no `.pytest_cache` was written.

| File | 3.14 | 3.11 |
|---|---|---|
| tests/test_api.py | 415 passed in 729.99s (0:12:09), exit 0 | 415 passed in 1176.70s (0:19:36), exit 0 |
| tests/test_firm_cache.py | 22 passed, 1 skipped in 1.89s, exit 0 | 22 passed, 1 skipped in 10.99s, exit 0 |
| tests/test_layers.py | 29 passed in 26.46s, exit 0 | 29 passed in 24.73s, exit 0 |
| tests/test_repo_map.py | 80 passed in 44.23s, exit 0 | 80 passed in 66.67s (0:01:06), exit 0 |
| tests/test_settings.py | 54 passed in 3.30s, exit 0 | 54 passed in 18.56s, exit 0 |
| tests/test_layout.py | 48 passed in 2.20s, exit 0 | 48 passed in 4.53s, exit 0 |
| tests/test_store.py | 175 passed in 148.65s (0:02:28), exit 0 | 175 passed in 239.76s (0:03:59), exit 0 |
| tests/test_errors.py | 83 passed in 14.93s, exit 0 | 83 passed in 19.98s, exit 0 |
| tests/test_registry.py | 35 passed, 1 warning in 36.42s, exit 0 | 35 passed, 1 warning in 71.01s (0:01:11), exit 0 |
| tests/test_single_source.py | 172 passed in 48.29s, **exit 1** | 172 passed in 49.50s, **exit 1** |

- **The `test_single_source` exit 1 is only the known tripwire.** On both interpreters the one
  failure is decision 185's session check, "the suite reached a real place":
  `test_the_app_opens_one_window (call): open of the checkout's settings file`. All 172 tests
  pass. The branch changes nothing near that test: its diff in this file is only
  `CACHE_FILENAME` added to the owned-files set.
- The skip is `test_a_household_holding_a_link_is_never_fingerprinted` (no symlink privilege
  here; see NIT-5).
- The registry warning is a pre-existing `runpy` `RuntimeWarning` from the CLI test.

## Checks

- `python -m ruff check .`: All checks passed! (exit 0)
- `python tools/repo_map.py check`: Map is current (349 nodes, generated 2026-09-30). (exit 0)
- `git status`: clean before this file was written. The probes wrote only to `%TEMP%\fcp`,
  `%TEMP%\fcj3` and the reviewer's scratchpad.

## Probes (in the reviewer's scratchpad; not in the repo)

- `probe_cache.py`: builds a practice in `%TEMP%\fcp` from `tests/samples.py`
  (`build_scratch_root`) and `tests.conftest.make_engagement` (made-up names only). It has
  7 households, a Roll Forward inside one household, a cross-household Roll Forward, two open
  years, an inactive return, and a household whose record is gone.
  - Steps P0-P21 each compare: the cached `firm` twice, the whole walk (`_firm_cached`
    patched to `None`), and main `877c7a2`'s code (`git archive` into the scratchpad, run as
    a subprocess).
  - It counts `_firm_row` calls to show when the cache was used. Ran on 3.14 and on 3.11
    with the same results.
- `p119_child.py`, `firmkey_probe.py`: P119 old against new, on random inputs.
- `held_probe.py`: settings writes inside a reading.
- `store_probe.py`: a store-only change.
- Junction probe J1 (PowerShell `New-Item -ItemType Junction` in `%TEMP%\fcj3`).
- Pass-churn probe: a third `tracker.runner` pass over the unchanged practice, before and
  after snapshot of size and time (SHOULD-4).
