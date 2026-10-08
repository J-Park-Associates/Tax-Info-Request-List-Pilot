# Pilot 0.3 - the speed round: fewer repeats, an honest wait - SPEC

Status: **written 2026-10-08**, branch `claude/cool-brahmagupta-a45s9n` at
`8e18570` (main). Jason, 2026-10-08, ruled on the four investigations of the
same day (section 2). New decision rows: **P213-P224**
([`DECISIONS.md`](DECISIONS.md)), written at merge (section 5.5). It is built
in two lanes at once, in two worktrees, with no file in common (section 5),
and reviewed by a separate agent that built neither.

The rule above every ruling here is P120's: **a cache may never make a
status wrong.** Nothing here reads a document, changes a routing rule, a
catalog word or the matcher, so the backtest baseline cannot move. Every
change below does one of four things: holds an answer only while nothing
can change it (and proves that with the record's own head), does the same
work fewer times with the same result, does it in a cheaper form with the
same durability, or tells a person more truthfully what the screen is
showing while they wait.

## 1. What was measured

Four investigations ran on 2026-10-08 in the cloud sandbox (Linux, 4
shared cores, Python 3.13, Node 22), on made-up firms only: the shared
1,000-household firm (2,000 returns, read-only commands only) and each
agent's own 50-household firm. Their reports are scratch inputs, not
repository files: `findings-1-code.md`, `findings-2-database.md`,
`findings-3-payload.md` and `findings-4-ux.md`, with
`ARTICLE-WEIGHED.md` (an outside article on performance, weighed against
this codebase), in the session's scratch folder `opt/`. On the office PC a
question to the disk costs about 0.1 ms (SPEC-scale-1000 section 1), so
counts carry to Windows and the seconds below are this sandbox's.

| Where | Measured | Report |
|---|---|---|
| A pass with nothing new, 50 households | 131,559 disk questions, 4.1-4.5 s (3 runs). With code items 1-7 together: **41,200 (-69%)**, 2.8-3.1 s; a filing pass 204,385 -> 111,746 (-45%); the printed line for every return and the folder tree identical | findings-1 |
| - discovery and the practice page's parked-file read outside any hold | 16.5 s and 5.2 s of the 193 s profile at 1,000 households; on 50: 2,900 unheld `resolved`, 854 settings-file opens. Inside `one_reading()`: -38% of the pass's disk questions | findings-1 #1 |
| - the digest cache's key resolves the whole path | 39,400 of 131,559 `lstat` (30%) on 50 households; 2,600 of 2,600 keys identical when built from the held folder | findings-1 #2 |
| - the progress file rewritten for every request scanned | 27,002 rewrites a pass at 1,000 households, 14.7 s of 193 s (9.0 s in `replace`) | findings-1 #3 |
| - pure name and path functions recomputed | 432,000 `is_invisible` calls in one `list`; `parts_below` 242,004 calls, 16.0 s of the pass profile; `list` 2.97-3.17 s -> **2.01-2.13 s**, reply byte-identical | findings-1 #4 |
| - the scan's owner check | 5.28 M `matches_identifier` calls, 16.2 s of 193 s at 1,000 households | findings-1 #5 |
| - every command imports pypdf | `import tracker.api` 0.21-0.25 s -> 0.136-0.16 s with the PDF and HEIC readers deferred (6 runs); pypdf with cryptography 136 ms by `-X importtime` | findings-1 #6, findings-3 #6 |
| - the pass-order hint rewritten whole before each household | 1,001 whole writes, about 176 MB and 2,000 syncs a pass at 1,000 households | findings-1 #7, findings-3 #8 |
| - the same record rebuilt about 10 times a household | `load_manifest` 39.3 s, `read_index` 13.1 s of 193 s; reusing it while the head is unchanged answered 400 of 500 from memory, -9% profiled | findings-1 #8 |
| The record checkpoint (`record-heads.db`) | 56.8 of 66.8 s of SQL time in a first pass at 1,000 households; on a real 50-household first pass 5,206 syncs (65% of every sync) and 1,301 journal create/deletes. WAL, one connection: **1,307 syncs, 9 deletes**, 0.64-0.73 ms a record against 2.8-3.0, the pass 23.7/23.0 s -> 21.7/21.7 s, results identical | findings-2 #1 |
| The engagement row's key | 97,000 `_engagement_row` calls in an idle pass at 1,000 households (32.5 s cumulative, 3 s of it SQL); a memo inside the hold: -9% of the 50-household pass (3 runs) | findings-2 #2 |
| The app's reply reader (`main.js`) | 176 ms of main-process time per 3.9 MB `firm` reply on a real spawn against 9 ms read linearly; 0.45-1 s in simulated small pieces | findings-3 #3 |
| One Sort's tail | up to three firm-wide walks: Run now's own fill, the app's `firm`, and a second `firm` queued against stale counts | findings-3 #1, #2 |
| A waiting spare process | `state` 306-368 ms -> 90-98 ms; `templates` 261-313 -> 34-39 ms (4 runs, identical bytes); about 0.85 s a command on the office PC | findings-3 #4 |
| What a person sees | launch to first Overview 9.2 s at 2,000 returns (list 3.2 s, then firm 6 s); about 35 s after an upgrade; firm pages redrawn with old counts unmarked for 5.5-9 s after every Sort, F5 or count-moving write; the reminder sheet showing the previous client's letter, Copy enabled, while the next loads | findings-4 |

**Measured for this SPEC** (this session, the same sandbox):

- **The pass-order hint is already unreadable at 1,000 households.** The
  shared firm's `pass-order.json` is 176,040 bytes, and
  `runner.PASS_ORDER_MAX_BYTES` is 65,536 (`runner.py:785`). `_read_order_hint`
  (`runner.py:1970`) refuses a file past the cap, so every pass at that size
  says `ORDER_HINT_UNREADABLE` and runs in folder order: decision 189's
  least-recently-completed order is lost from about 370 households up. P217
  fixes it.
- **Where a cold Overview's time goes** (cProfile, one run, a private copy
  of a 50-household firm, cache deleted): 0.81 s in all, of which the
  fingerprints 0.18 s, `households_named` (the records) 0.19 s and the rows
  (`_firm_row`, what `state` reads) 0.40 s. So a progress count that ticks
  only while records are read would sit at its end for half the wait;
  P222's count covers both (section 3.10).
- **SQLite's write-ahead log, checked by probe:** `journal_mode` persists in
  the file, `synchronous` does not (it must be set on every connection); a
  switch to WAL while another connection holds a read transaction is
  refused `SQLITE_BUSY` after the timeout; the last writing connection's
  close removes `-wal` and `-shm`; a read-only connection to a WAL file can
  leave both behind (the store's `verify` already does).

## 2. Jason's rulings of 2026-10-08

Given in this session, quoted as given:

**Approved (build):**

- **E1** Checkpoint `record-heads.db` held open, one connection per command
  (closed by `store.close`), WAL at `synchronous=FULL` (findings-2 #1). The
  `-wal`/`-shm` files must be named everywhere the checkpoint is moved, set
  aside, kept, or listed (`after_install.CHECKPOINT_UNIT`,
  `runner.left_behind`, runbook rename step, `test_build` file lists,
  anything else you find). The switch happens by itself at open (decision
  209).
- **E2** Reuse record reads (`load_manifest`, `read_index`,
  `load_engagement_info`) inside a hold while the store row's `ledger_head`
  is unchanged; the journal is still read/hashed every time (findings-1 #8).
- **E3** Digest-cache key built from the held folder answer + file name,
  same key string (findings-1 #2).
- **S1** Sort & Scan (Run now for one household) no longer fills the firm
  cache itself (findings-3 #1).
- **S2** The pass-order "started" mark becomes a light append/one-line mark,
  whole hint written once at pass end; decision 189's crash mark still lands
  before the household's work (findings-1 #7 / findings-3 #8). Choose the
  precise design.
- **S3** `after_install` fills the firm cache as a job in
  `after_install.run()` (findings-4 #10), so the first Overview after an
  upgrade is paid at install.
- **A1** A warm spare tracker process: still one command per process;
  `main.js` keeps one spare started, hands it the command on stdin, starts
  the next; never used for a pass; restarted when the program changes;
  killed on quit (findings-3 #4). A test pins that nothing besides
  `TASK_NAME` is read at import time (or whatever the true list is).
- **A2** Ask `firm` alongside `list` at launch (findings-4 #7).
- **W1** "Updating" marker while a firm page shows held counts during a
  refresh (findings-4 #1). New word "Updating" approved by Jason.
- **W2** Visible "Reading {n} of {total} Households" progress with a
  determinate `role=progressbar` for a firm wait over about 2 s
  (findings-4 #8). Approved wording as given; it needs `firm` to emit
  progress lines and the renderer to show them.

**Declined / held (do not build):** trusting a record's size+time inside a
pass (findings-2 #3); Sort leaving the practice page to the schedule
(findings-3 #7a, decision 203 stands); skipping the list after a Sort
(findings-3 #9); showing last counts "as of" (findings-4 #9).

**Safe items (no ruling needed; build):** findings-1 #1, #3, #4, #5, #6;
findings-2 #2 (reconciled with findings-1 #4, one owner); findings-2 #1a is
subsumed by E1; findings-3 #2, #3; findings-4 #2 (first), #3, #4, #5, #6;
and, from the article, a local performance budget in counts if it can be
made stable (it can: P223).

## 3. Rulings

### P213 - the reminder sheet never offers another return's letter (findings-4 #2, built first)

**What happens today.** `openReminder` (`app/renderer/sheet.js:274`) frames
the sheet (`sheetFrame`, `sheet.js:47`, which clears only `#sheet-check`)
and, when the return is not the one on screen, awaits `showReturn`. Until
that lands, `reminderCard` (`app/renderer/app.js:407`) still holds the
previous return's card, drawn in the sheet, and `#reminder-actions` is
shown by `sheetFrame` (`sheet.js:55`). `copyReminder` (`app.js:626`) checks
only `!reminderCard`, so Copy in that window puts **another client's
letter** on the clipboard. `sheetNextDraft` (`sheet.js:302`) has the same
window, which the findings did not name. Approve is already safe: the API
refuses a stale fingerprint.

**The change** (Lane R):

1. `app.js` gains `forgetReminderCard()`: `reminderCard = null`; the
   card's body is replaced by `shellSkeleton(3)` beside the visually hidden
   `screenWords().loading`; `#reminder-actions` is hidden; `#sheet` gets
   `aria-busy="true"`. `drawReminder` and `drawReminderLine` clear
   `aria-busy` on `#sheet`.
2. `openReminder` calls it before awaiting `showReturn` whenever the return
   is not on screen; `sheetNextDraft` calls it before every `showReturn`.
3. `sheetFrame` no longer shows `#reminder-actions` for a reminder; the
   card's own draw shows them (`app.js:548`'s toggle), so the buttons
   appear only with the letter they act on.
4. `drawReminder` records `reminderCardFor = active`; `copyReminder` and
   `approveReminder` return at once unless `reminderCard` is set and, while
   the sheet is a reminder sheet, `reminderCardFor === sheetNow.ret` and
   `sheetNow.ready`.
5. `sheetShow` (`sheet.js:197`) keeps `shellSkeleton(3)` beside the hidden
   word, as `sheetFrame` already does, so a check sheet waiting on a read is
   an outline, not blank.

**Why no status can go wrong.** Nothing is read or written that was not
before; the sheet shows less, for the fraction of a second the read takes.

**Tests** (`tests/test_shell.py`):
`test_the_reminder_sheet_offers_nothing_to_copy_until_its_own_return_is_read`,
`test_next_draft_offers_nothing_to_copy_until_its_return_is_read`,
`test_copy_refuses_a_card_drawn_for_another_return`,
`test_a_check_sheet_waiting_on_its_return_is_an_outline`.

**Docs:** none besides the row.

### P214 - the record checkpoint keeps a write-ahead log, one connection a command (E1)

**What happens today.** `store._beside` (`store.py:2702`) opens the
checkpoint with `checkpoint.open` for every question and closes it after;
`prove_the_root` (`store.py:2886`), `foreign_lines` (`:2928`) and
`acknowledge_foreign` (`:2940`) open their own through `checkpoint.opened`.
The file keeps SQLite's default rollback journal (`checkpoint.py:77-81`), so
each of `record()`'s two transactions (`expect` before the journal append,
`advance` after, `store.py:2272`) costs four syncs and a journal file made
and deleted. Decision 159's paragraph (`checkpoint.py:54-60`) says why it
was opened per question: "a connection held for the life of a process would
be one more handle Windows refuses to delete a folder under" - which the
store's own connection already is, and `store.close()` already lets go of.

**The change** (Lane P):

- **`tracker/checkpoint.py`.**
  - New constants `CHECKPOINT_WAL_FILENAME = CHECKPOINT_FILENAME + "-wal"`
    and `CHECKPOINT_SHM_FILENAME = CHECKPOINT_FILENAME + "-shm"`, worded as
    `store.STORE_WAL_FILENAME` is.
  - `_opened` (`:388`), once the version is read (and again after a
    set-aside reconnect), calls a new `_write_ahead(conn)`:
    `PRAGMA journal_mode = WAL`, then `PRAGMA synchronous = FULL` on every
    connection (it does not persist). A switch refused as busy
    (`CheckpointUnavailable.busy`) leaves the file in its mode for this
    connection and is not an error - the next open tries again; any other
    error closes the connection (`_close_after_failure`) and is raised as
    today. `open_read_only` (`:414`) is unchanged: a read-only connection
    reads a WAL file.
  - The module docstring's paragraph at lines 54-60 and the comment on
    `CHECKPOINT_JOURNAL_FILENAME` (lines 77-80) are rewritten: one
    connection a command, held by the store and closed by `store.close()`
    with the store's own; WAL at FULL, so each COMMIT is on disk before it
    returns; the rollback journal remains the name of a file an earlier
    version (or a refused switch) left, and moves with it.
- **`tracker/store.py`.**
  - `_CHECKPOINT: checkpoint._Connection | None` and `_CHECKPOINT_PATH`,
    beside `_CONNECTION` (`:960`). A new `_held_checkpoint(where)` returns
    the open connection for `where`, opening it (after
    `_checkpoint_may_be_made(where)`, as now) only when none is held or the
    one held is for another file (which is closed first).
  - `_beside` (`:2702`) yields `_held_checkpoint(where)` and no longer
    closes it. On any `CheckpointError` inside the block the held
    connection is closed and dropped before the error leaves (so a busy or
    damaged file is opened afresh at the next question, as today, and a
    refused checkpoint is never held open against the runbook's set-aside
    step), and the error is said as today (`StoreError`, the same sentence).
  - `_checkpoint_file(conn)` (`:2654`) is asked once per store connection:
    the answer is kept beside `_CHECKPOINT` and forgotten by `close()`.
  - `prove_the_root`, `foreign_lines` and `acknowledge_foreign` use
    `_held_checkpoint` instead of `checkpoint.opened`, keeping their own
    error rules (the first lets `CheckpointUnavailable` through
    unconverted, and drops the held connection first).
  - `close()` (`:1017`) closes the checkpoint first, then the store; a
    failure closing the checkpoint is a warning by class (as `_beside`'s
    `finally` logs it today) and never stops the store closing.
  - `record()`'s two transactions are unchanged in order and in number:
    `expect` committed before the journal line is appended, `advance` after.
    Nothing is batched (findings-2 #1a's single open is subsumed).
- **Everywhere the checkpoint is named** (the ruling's list, and what this
  SPEC found):

  | Place | Change | Lane |
  |---|---|---|
  | `tracker/after_install.py:259` `CHECKPOINT_UNIT` | add `CHECKPOINT_WAL_FILENAME`, `CHECKPOINT_SHM_FILENAME` | P |
  | `tracker/after_install.py:888-893` (the unit rule in `move_left_behind`) | a journal **or write-ahead log or shared memory** found without its checkpoint moves nothing (each would be replayed into a checkpoint not its own); a home holding any part of the unit moves nothing. `LEFT_BEHIND_JOURNAL_ALONE`'s words are kept: SQLite calls the `-wal` its write-ahead log journal, and a new sentence would be new wording for a case no earlier version can produce *(changed by the review, 9fbf844: the sentence now says "side file(s)", which fits all three; P214's row records it)* | P |
  | `tracker/runner.py:340-345` `left_behind`'s `beside` | add both names, so the live checkpoint's side files beside a store in use (the suite's fixture) are never named as left behind | P |
  | `tracker/runner.py:375-377` `_to_move` | add both names: to move, never to delete (the `-wal` holds committed writes) | P |
  | `.github/workflows/build.yml:206` `$names` | add `'record-heads.db-wal', 'record-heads.db-shm'` | P |
  | `tests/test_build.py:140-170` | the expected set adds both constants | P |
  | `tests/conftest.py:746` `real_places` and `tests/test_tripwire.py:88` | the tripwire guards the checkpoint's two side files beside the settings, as it guards the store's | P |
  | `tests/test_after_install.py:831-832` | the fabricated unit gains a `-wal` case | P |
  | `.gitignore:92` (`record-heads.db-*`), `.claude/settings.json:35-36` (`record-heads.db-*`), `tests/test_single_source.py:471` and `:634` | already cover both names: **no change** (and no agent edits `.claude/settings.json`) | - |
  | `docs/runbook.md` 568-582, 1975-1979, 1986-1995, 2267-2273; `docs/storage.md` 93-100; the curated node `artifact:record-heads.db` | section 5.5 | merge |

**Why no status can go wrong.** No status is read from the checkpoint; it
only proves records. Durability is unchanged: in WAL at `synchronous=FULL`
a COMMIT returns only after its log is synced, so `expect` is on disk
before the journal line is appended and `advance` lands after it, each
commit durable on its own, as before. Readers no longer wait for a writer
(WAL), so a read by the app while the pass writes no longer meets `BUSY`;
writers still take turns under the 5 s busy timeout. A connection held for
the command must never answer from an old snapshot: it runs in autocommit
with no open read transaction between questions, and a test pins that a
held connection sees what another process advanced since.

**Windows.** The handle the ruling accepts is the store's own pattern: one
process, one command, closed by `store.close()` in every entry point that
already closes the store (`api.main`'s `finally`, `api.py:6292`; Run now,
`api.py:3267`; `runner.main`, `runner.py:3164`; `after_install.main`,
`after_install.py:1384`). Tests that rename or delete the checkpoint inside
a test call `store.close()` first, as the runbook tells a person to close
the app first. The pull request carries the `windows` label.

**Tests** (Lane P):
`tests/test_checkpoint.py` - `test_the_checkpoint_keeps_a_write_ahead_log_at_full_sync`,
`test_a_switch_another_connection_refuses_leaves_the_checkpoint_working_in_its_own_mode`,
`test_a_held_checkpoint_sees_what_another_process_advanced_since`,
`test_the_read_only_open_reads_a_checkpoint_in_its_write_ahead_log`; and
`test_a_busy_checkpoint_is_said_as_busy_and_never_as_one_to_set_aside`
(`:211`) rewritten so the holder blocks a **write** (`advance`), since in
WAL a reader no longer waits.
`tests/test_store.py` - `test_one_command_opens_the_checkpoint_once`,
`test_closing_the_store_closes_the_checkpoint_and_takes_its_side_files`,
`test_a_checkpoint_error_drops_the_held_connection_and_the_next_question_opens_it_again`,
`test_expect_is_on_disk_before_the_journal_line_and_advance_after_it`.
`tests/test_after_install.py` - `test_the_checkpoint_its_log_and_its_shared_memory_move_as_one`,
`test_a_write_ahead_log_without_its_checkpoint_moves_nothing`.
`tests/test_runner.py` - `test_the_checkpoints_side_files_beside_the_store_in_use_are_never_named_left_behind`,
`test_a_checkpoint_log_left_beside_the_program_is_named_to_move_never_to_delete`.
`tests/test_build.py` - the existing
`test_the_package_is_proved_to_hold_no_store_log_task_file_or_settings`, extended.

### P215 - answers kept for one hold: the walk, the key, the record's reads (findings-1 #1, findings-2 #2, E2)

Three repeats inside P118's and P207's holds, with **one owner of
hold-scoped memory**: `tracker/settings.py`.

**1. The pass's two firm-wide reads run inside a reading** (findings-1 #1).
`runner._pass` calls `discover_engagements(root)` (`runner.py:2993`) and
`write_status_page` calls `_parked_files(report)` (`runner.py:2569`)
outside any hold. Each call is wrapped in `settings.one_reading()`; only the
call, never the page's write that follows. Both only read (discovery's
catch-ups are derivation, which a reading allows - `refuse_a_write_while_reading`
refuses only recorded events and the settings file); a write inside would
raise `WRITE_WHILE_READING`, loudly. The hold ends when the call returns,
so nothing the pass makes later is answered from it.

**2. `settings.held()`: the one hold-scoped memo.** `settings._held(key,
answer)` (`settings.py:953`) becomes public as

```python
def held(key: tuple, answer: Callable[[], T], *, there: Path | str | None = None) -> T
```

- Outside a hold: `answer()` every time.
- Inside a reading (P118): asked once, kept for the reading.
- Inside a household's hold (P207): asked once, and **kept only when
  `there` is None or `there`'s resolved answer is itself held** - which by
  P207 rule 2 means it was there when it was resolved. A folder the pass
  makes later is never answered from before it existed.
- An exception is never kept. `_held`'s present callers move to it.

**3. The engagement row's key once per hold** (findings-2 #2).
`store._engagement_row` (`store.py:1168`) computes
`engagement_path(key_root(folder, root), folder)` on every read: 97,000
times an idle pass at 1,000 households. It asks
`settings.held(("engagement key", str(folder), "" if root is None else str(root)),
lambda: engagement_path(key_root(folder, root), folder), there=folder)`.
The row itself is never held: its `applied_seq` moves whenever anything is
written. The key is a function of the settings file's root, the folder's
resolved spelling and the root's - each already held for exactly this hold
- so it cannot differ from asking again.

**Reconciled with findings-1 #4.** `layout.parts_below` also gets a pure
cache (P219). The two do not overlap in what they own: the held key skips
`key_root` and `engagement_path` entirely for a key asked again in a hold;
the pure cache serves every other caller of `parts_below` (and the first
ask in each hold). Lane P builds both, and the rule they share - a cache
keyed by text, never by a `Path`'s equality - is in P219.

**4. A record's reads once per head inside a hold** (E2).
`manifest.load_manifest` (`manifest.py:1232`), `manifest.load_engagement_info`
(`:1314`) and `filer.read_index` (`filer.py:1293`) each first bring the
store up to the journal (`_the_record`, `manifest.py:1211`;
`follow_the_journal`, `store.py:2597`), which reads and digests the journal
file **every time** - unchanged. Then, instead of rebuilding, each asks a
new `store.held_read(conn, engagement_dir, what, build)`:

```python
row = _engagement_row(conn, engagement_dir)
if row is None:
    return build()
token = (what, row["id"], row["path"], row["ledger_head"], row["applied_seq"], row["applied_digest"])
value = settings.held(("record read", *token), build, there=engagement_dir)
return list(value) if isinstance(value, list) else value
```

with `what` one of `"manifest"`, `"index"`, `"details"`, and `build` the
function's present body after the follow.

- **Why the token and not `ledger_head` alone:** `store.forget`
  (`store.py:1575`) deletes a row and a later create may reuse its id;
  `rebuild_engagement` (`:3146`) and `recover` (`:3744`) delete and insert.
  Path, head, applied seq and digest together name exactly one state of one
  record's rows.
- **Why it cannot make a status wrong.** Every table these three reads
  come from - `requests`, `statuses`, `learned_keywords`, `documents` and
  the engagement's columns - is written only by applying journal lines
  (`_apply`, then `UPDATE engagements SET applied_seq, ledger_head,
  applied_digest`, `store.py:2541`) or by deleting the row. So any change
  moves the token, and the next read builds afresh. The journal is still
  followed first on every call (`follow=True`), so a line another process
  appended is applied and moves the token before the memo is asked; a
  `follow=False` read (the practice page's) gets the token of the rows as
  they stand. Nothing is kept past the hold. The three types returned are
  frozen dataclasses whose fields are `str`, `int`, `float`, `bool`,
  `date`, `None` or tuples; each caller gets its own list.
- Memory: one entry per record, kind and head, dropped when the hold ends.

**Docs:** curated notes of `tracker/settings.py`, `tracker/store.py`,
`tracker/manifest.py`, `tracker/filer.py`, `tracker/runner.py` (section 5.5).

**Tests** (Lane P):
`tests/test_settings.py` - `test_held_keeps_an_answer_for_the_hold_and_only_once_its_path_is_there`,
`test_held_never_keeps_an_error`.
`tests/test_store.py` - `test_an_engagements_key_is_worked_out_once_per_hold`,
`test_a_key_asked_before_its_folder_existed_is_asked_again_after`,
`test_a_record_read_is_never_kept_past_a_rebuild_of_its_row`.
`tests/test_manifest.py` - `test_a_held_reading_builds_the_list_once_per_record_head`,
`test_a_held_list_is_built_again_once_the_journal_moves`,
`test_a_line_another_process_appends_is_seen_by_the_next_read_in_the_hold`,
`test_nothing_is_kept_once_the_hold_ends`.
`tests/test_filer.py` - `test_a_held_index_is_read_again_after_a_file_is_recorded`.
`tests/test_runner.py` - `test_the_passs_discovery_and_its_page_read_hold_the_machines_answers`,
`test_the_page_is_written_outside_the_reading`.

### P216 - the digest cache's key from the held folder (E3)

`content_check.ContentCache._key` (`content_check.py:2447`) is
`str(file.resolve()).lower()`, asked by `digest_of`, `remember_digest` and
`prune`: 30% of an idle pass's `lstat` on 50 households. It becomes:

- `str(settings.resolved(file.parent) / file.name).lower()` for a file
  whose name is a plain name (not `""`, `.` or `..`) and which is not a
  link (`os.path.islink(file)` - one `lstat`);
- `str(file.resolve()).lower()` otherwise, as today.

**Same key string.** `Path.resolve()` resolves the parent and appends a
final component that is not a link unchanged; on Windows it may give the
final name's on-disk case, which `.lower()` already folds. The 2,600 keys
of a 50-household pass were identical (findings-1). Inside a household's
hold the folder's answer is held (it exists); outside one, `resolved` asks
every time, as `resolve` did. The verdicts, digests and the reading are
untouched - the reader's path stays left alone, as P121 and P207 left it;
this is the cache's key only. Path handling: the pull request carries the
`windows` label.

**Tests** (`tests/test_content_check.py`, Lane P):
`test_a_files_cache_key_is_its_folders_held_answer_and_its_own_name`,
`test_a_file_that_is_a_link_is_keyed_by_where_it_leads`,
`test_the_key_is_the_one_a_whole_resolve_gives`.

### P217 - the pass-order hint: a one-line mark as each household starts, the whole written once (S2)

**What happens today.** `run_registry` (`runner.py:1840`) calls
`_mark_started` (`:2024`, called at `:1937`) before each household, which
rewrites the whole hint through `write_json_atomically` (two syncs);
`_keep_the_order` (`:2061`, called at `:1960`) writes it whole at the end.
At 1,000 households: 1,001 whole writes, 176 MB, about 2,000 syncs - and
the file (176,040 bytes, indented) is past `PASS_ORDER_MAX_BYTES` (65,536),
so the next pass cannot read it at all (section 1).

**The design.** One file, the same name - so no new name reaches the
deny list, `.gitignore`, the build's file list or `left_behind` - in a
version 2 shape of JSON lines:

- **Line 1** is the whole hint, `{"version": 2, "households": {...}}`,
  compact (`json.dumps` with `separators=(",", ":")`, ASCII), ending in a
  newline: about 125 bytes a household.
- **Each further line** is one start mark, appended:
  `{"started":"2026-10-08T09:00:00","household":"<folder name>"}`.
- **`PASS_ORDER_VERSION`** (`runner.py:781`) becomes 2.
  **`PASS_ORDER_MAX_BYTES`** (`:785`) becomes `4 * 1024 * 1024` - room for
  about 30,000 households - so a real hint is always read and a
  pathological file still is not parsed (the review's S1).
- **Reading** (`_read_order_hint`, `:1970`) returns a third value,
  `settled`:
  - the whole file parsed as one JSON object of version 1 (today's files,
    indented) or 2 is the hint; settled only when it is version 2 and
    one line;
  - otherwise line 1 must be a version 2 hint, and each further line that
    parses and names a string `household` and `started` is folded in order
    (`hint[name] = {**hint.get(name, {}), "started": at}`, the later
    winning); a line that does not parse - the torn end of an append the
    machine died in - is skipped with a debug line, never a warning;
  - anything else is unreadable, as today (`ORDER_HINT_UNREADABLE`).
- **Before the first household** (`run_registry`, writing, path known): a
  hint that is not settled (missing, version 1, or carrying marks) is
  written whole once, folding the marks a killed pass left. If that write
  fails, no mark is appended this pass (a mark on an unsettled file would
  make it unreadable); the end-of-pass write is still tried.
- **`_mark_started`** appends its one line - opened for appending, written,
  flushed and `os.fsync`ed - before the household does anything, and sets
  `hint[name]["started"]` in memory. An `OSError` is a log line, as now.
- **`_keep_the_order`** writes the whole hint once, as now, through
  `fsio.write_text_atomically`, which drops every mark (they are folded
  into line 1 already). A dry run reads and writes nothing, as now.

**Why decision 189's crash mark still lands.** The mark is on disk (fsync)
before the household's work begins, exactly as the whole rewrite was; the
next pass folds it and puts that household last. **Why no status can go
wrong:** the hint only orders households and counts the not-served; it
decides no status.

**Gain.** One whole write a pass (two after a killed one) instead of one a
household: linear in households, about 1,000 fsyncs of a few dozen bytes
in place of 2,000 syncs and 176 MB at 1,000 households - and decision 189's
order works again at that size.

**Tests** (`tests/test_runner.py`, Lane P):
`test_a_hint_for_a_thousand_households_is_read_back_whole`,
`test_each_household_start_is_one_appended_line_and_the_hint_is_written_once_a_pass`,
`test_a_pass_killed_in_a_household_leaves_its_mark_and_the_next_pass_puts_it_last`,
`test_a_torn_last_mark_is_skipped_without_a_warning`,
`test_an_earlier_versions_hint_is_read_and_settled_before_the_first_mark`,
`test_a_hint_that_cannot_be_settled_takes_no_marks`; the existing
pass-order tests (`:3145-3330`) keep passing with their version 1 bodies.

**Docs:** curated `artifact:pass-order.json` ("marked as each household
starts" becomes "a line appended as each household starts, folded into the
whole hint once a pass"); `runbook.md:793-800` stays true (a hint, safe to
delete).

### P218 - the Overview is made ready once (S1, findings-3 #2, S3)

**1. Sort & Scan leaves the cache to the app** (S1). `runner._fills_the_cache`
(`runner.py:644`) returns `False` when `household is not None`, before the
warm-head check it asks today (`:670-675`); its docstring's second bullet
says so. The app asks `firm` the moment the pass ends, and that reply fills
the cache as every Overview does. A Sort run by hand from the command line
leaves the cache to the next Overview. Cache only: no status can change.

**2. No second Overview after a Sort** (findings-3 #2, Lane R). Today the
list a finished Sort adopts starts a `firm` (`shellAdopt`, `shell.js:192`),
then the state read arrives and is compared with the **old** counts, so
`shellStateArrived` (`shell.js:310`) queues a second full `firm` whose answer
cannot differ. The change:

- `shell.js` keeps `shellFirmSentAt` (set by `shellLoadFirm`, `shell.js:206`,
  when it sends) and `shellWroteAt`, set by a new `shellWriteLanded()`.
- `app.js`'s `call()` (`app.js:167`) calls `shellWriteLanded()` when a reply
  to a command in `vocab.writing_commands` arrives, before the state is
  rendered; `passEnded` (`app.js:2280`) calls it first.
- `shellStateArrived`: while a load is in flight whose `shellFirmSentAt` is
  at or after `shellWroteAt`, a state whose counts differ is remembered, not
  queued; when that load lands, the remembered state is compared with the
  new counts and one more load is asked only if they still differ. A load
  sent before the write is followed by another, as today.

**3. Setup makes the Overview ready** (S3, Lane P). `after_install._run`
(`after_install.py:1089`) gains a last job before the record is written,
`_ready_the_overview(root, reason)`:

- runs only for `REASON_SETUP` (`after_install.py:181`), with a saved
  root that was not refused and a store file present (the check's own
  rule, `after_install.py:568`);
- calls `runner.fill_firm_cache(str(root))` (`runner.py:591`: the firm
  summary as its own process, the cache's own staleness rules, 300 s
  limit);
- is **never a failure**: a fill that did not finish is one console line
  and the step's identity is still recorded, so the app does not run the
  whole step again at every launch for a cache;
- two sentences, console only (Setup prints `lines`; the app's notice shows
  findings and failures, never this): `OVERVIEW_READY` - "Made the Overview
  ready, so the first one after this install opens at once." - and
  `OVERVIEW_NOT_READY` - "The Overview could not be made ready ({why}); the
  first one reads every household and takes a little longer." with `{why}`
  `fill_firm_cache`'s own kind sentence. `AfterInstall` gains
  `overview_sentence: str = ""`.

**Why only the setup door.** The launch door (`launch()`,
`after_install.py:1200`) runs in the background beside the app's own first
`firm`, which A2 now asks at once: a fill there would be a second cold walk
of the whole firm at the same moment. The root door (`set-root`) is
followed by the app's `list` and `firm` likewise; the Repair door has a
person waiting at the Schedule dialog. Each of those is followed at once by
an Overview that fills the cache, as S1's is. Setup is the one door with no
Overview after it. The pilot's own installer runs it too (Q1, section 7,
answered by Jason 2026-10-08).

**Tests:** `tests/test_runner.py` - `test_a_sort_leaves_the_overview_to_the_app`
(the existing warm/cold Sort-fill tests are replaced by it);
`tests/test_shell.py` - `test_after_a_sort_one_overview_is_asked_not_two`,
`test_a_write_that_lands_during_a_load_still_asks_again`;
`tests/test_after_install.py` - `test_setup_makes_the_overview_ready_after_its_other_jobs`,
`test_a_fill_that_fails_never_fails_the_step`,
`test_the_launch_root_and_repair_doors_leave_the_overview_to_the_app`.

**Docs:** `runbook.md:44-48`, `SPEC-firm-cache-fill.md` R2's changed
paragraph (lines 62-74), R4 (lines 95-112) and its staff note (lines
253-255): section 5.5.

### P219 - smaller repeats (findings-1 #3, #4, #5, #6)

**1. Pure answers remembered** (findings-1 #4, Lane P).

- `layout.name_key` (`layout.py:461`), `layout.segment_problem` (`:362`) and
  `layout.is_invisible` (`:308`) - pure functions of one `str` - take
  `@functools.lru_cache(maxsize=8192)`.
- `layout.parts_below` (`layout.py:759`) delegates to
  `_parts_below_of(outer_kind, outer_text, inner_kind, inner_text)` under
  `lru_cache(maxsize=8192)`, called with `type(x).__name__` and
  `os.fspath(x)` of each argument. **Never keyed by the `Path` itself:** on
  Windows `PureWindowsPath("C:/Root/Smith") == PureWindowsPath("C:/Root/SMITH")`
  with the same hash (checked), and the answer carries the inner path's own
  spelling, which becomes a store key - a cache keyed by `Path` equality
  would answer one spelling with another's case.
- `store.has_rules(conn, engagement_dir) -> bool` -
  `SELECT 1 FROM requests WHERE engagement_id = ? LIMIT 1` on the row,
  `False` for no row - and `registry.engagement_from` (`registry.py:583`,
  the call at `:599`) asks it instead of `store.rules(...) or []`, which
  parsed every rule to learn `not rules`.

**2. The scan's owner worked out once per name** (findings-1 #5, Lane P).
`scanner.scan_engagement` (`scanner.py:771`; the `belongs_to` lambda at
`:830-833`) keeps `owners: dict[str, str | None]` for the scan, filled by
`scaffold.owner_of(name, identifiers)` on first ask; the identifier list is
fixed for the scan, so the answer is the same.

**3. The progress file keeps scan lines at most once a second** (findings-1
#3, Lane P). `progress.Watch.say` (`progress.py:253`) still emits every
line on stdout (Run now's reader is unchanged); `_keep` (`:226`) writes
the file:

- at once for every event except `file` lines whose `step` is `"scan"`;
- for a scan line only when `SCAN_KEPT_EVERY_SECONDS` (1.0) has passed on
  the monotonic clock since the last line kept; `Watch` takes
  `clock: Callable[[], float] = time.monotonic`.

**A sort line is always kept** (departure from the findings, which
throttled every `file` line): a `step="sort"` line precedes a document's
reading, the slow step the lock notice exists to name, and a throttled one
would leave the notice naming the previous file for the whole read. Scan
lines are the 26-a-household rewrites measured. The docstring's "It holds
no clock of its own" becomes "it reads the monotonic clock only to space
the progress file's scan lines; the budget stays decision 189's".

**4. pypdf is imported when the first PDF is opened** (findings-1 #6,
findings-3 #6, Lane P). `validators.py:51` `from pypdf import PdfReader`
goes; a new `_pdf_reader()` returns `globals().get("PdfReader")` or imports
`pypdf.PdfReader` and keeps it there; `_pdf_error_uncached`
(`validators.py:399`, the call at `:401`) calls `_pdf_reader()(path)`; a
module `__getattr__("PdfReader")` returns `_pdf_reader()`, so
`monkeypatch.setattr(validators, "PdfReader", ...)` (`test_errors.py:814`)
and `validators.PdfReader = ...` (`tests/child_readers.py:81`) keep working.
`logging.getLogger("pypdf").setLevel(...)` stays at load (it imports
nothing). PyInstaller's analysis follows an import inside a function, so
the build still carries pypdf; `tests/test_build.py` keeps saying so.

**`pillow_heif` stays registered at import** (the safe choice). Pillow
learns HEIC from `pillow_heif.register_heif_opener()` at `validators`'
import (`validators.py:67-73`), and `content_check.py:1870` and
`ocr.py:1231` open photos with Pillow relying on that: a lazy registration
inside `_image_error` alone would let a HEIC photo reach either reader
before Pillow knows the format, and be refused as unreadable - the client's
fault for the firm's order of imports (findings-3's warning). It costs
about 7 ms; A1's spare pays it before the click anyway.

**Why none can make a status wrong.** Pure functions of their arguments,
the same question asked in a cheaper form, a hint written less often, and
the same reader loaded later.

**Tests** (Lane P): `tests/test_layout.py` -
`test_the_name_rules_answer_from_memory_as_they_answer_fresh`,
`test_parts_below_never_answers_one_spelling_with_anothers_case` (a
`PurePosixPath` subclass whose equality folds case, standing in for
Windows); `tests/test_store.py` - `test_has_rules_is_whether_rules_has_any`;
`tests/test_registry.py` - `test_a_legacy_folder_is_still_found_by_whether_it_has_rules`;
`tests/test_scanner.py` - `test_each_names_owner_is_worked_out_once_per_scan`;
`tests/test_progress.py` - `test_a_scan_line_is_kept_at_most_once_a_second_and_every_other_line_at_once`,
`test_a_sort_line_is_always_kept`, `test_every_line_is_still_printed`;
`tests/test_validators.py` - `test_the_pdf_reader_is_imported_only_when_a_pdf_is_opened`,
`test_a_reader_a_test_puts_in_place_is_the_one_used`;
`tests/test_api.py` - `test_importing_the_api_loads_no_pdf_reader`.

### P220 - a warm spare, and the shell reads a reply once (A1, findings-3 #3)

**1. The spare, on the Python side** (Lane P).

- `tracker/api.py`: `SPARE_FLAG = "--spare"`, `SPARE_LINE_MAX = 64 * 1024`,
  and `spare(stream=None) -> int`:
  - reads one line from `sys.stdin.buffer` (at most `SPARE_LINE_MAX + 1`
    bytes);
  - **end of input before a newline** (the app closed, or killed the spare)
    -> returns 0 and prints nothing;
  - a line that is not UTF-8 JSON of the shape `{"argv": [str, ...]}`
    with at least one string, or is too long -> `return main([])`, the usage
    envelope every unknown command gets (no new words);
  - otherwise `return main(argv)`. `main` is unchanged: its `_read_spec`
    (`api.py:1131`) reads the rest of stdin as the payload, as today.
- `api.py`'s `__main__` block: `spare()` when `sys.argv[1:] == [SPARE_FLAG]`,
  else `main(sys.argv[1:])`.
- `api_entry.py`: after `freeze_support()` and the runner-mode branch,
  `argv == [SPARE_FLAG]` imports `tracker.api` and runs `spare()`.
- **Still one command per process.** A spare runs exactly one command and
  exits; decision 171's dead-owner lock rule (ROADMAP row 171: "the desktop
  app starts one tracker process per command"), one store per process
  closed after the command, P118's holds per reply and the kill per command
  are unchanged. A pass is never handed to a spare (the shell's rule, 2
  below); the API does not refuse one, because a spare running `run-now`
  would be exactly a fresh process running it.
- **What is fixed at import.** Found by reading every module's top level
  (an AST scan of `tracker/*.py`): `scheduling.TASK_NAME = product_name()`
  (`scheduling.py:110`; the environment's `TRACKER_PRODUCT_NAME`, which the
  shell sets, else `app/package.json`), `settings.PACKAGE_JSON`
  (`settings.py:110`) and `after_install.CHECKOUT` (`after_install.py:174`),
  both the program's own location. Nothing else at module level reads the
  environment, the clock, the settings file, the data folder or the clients
  root. The spare is started with the same environment a fresh command
  gets, so `TASK_NAME` is the same either way, and it is restarted when the
  program changes. Two tests pin this (below).

**2. The spare, on the shell's side** (Lane R, `app/main.js`).

- `let spare = null` holds `{proc, stamp, stderr}`. `startSpare()` spawns
  `FROZEN_API ["--spare"]` or `SOURCE_PYTHON ["-m", "tracker.api",
  "--spare"]` with the same `env`, `cwd` and `windowsHide` as
  `spawnTracker` (`main.js:288`), collects stderr (capped as now), and on
  `exit` or `error` forgets it.
- The first spare starts **after the first `list` reply has been learned**
  (`learn()`, `main.js:225`, the first time `allowedCommands` is set), not
  at launch, so start-up does not gain a third process; after that, each
  time one is handed a command the next is started at once.
- `spawnTracker` takes the spare for any command that is **not a pass**
  (`isPass` false) when the spare is alive and its `stamp` equals the
  program's stamp now; otherwise it spawns as today. Handing over writes
  `JSON.stringify({ argv: args }) + "\n"`, then the payload body as today,
  then ends stdin; the kill timer is armed at the hand-over, not at the
  spare's start.
- **The program's stamp:** packaged, `FROZEN_API`'s size and `mtimeMs`;
  from source, the newest `mtimeMs` of `tracker/*.py` under `REPO_ROOT`. A
  spare whose stamp differs is killed and replaced, and the command spawns
  fresh.
- `app.on("will-quit")` (`main.js:800`) also kills the spare.
- About 50 MB of one idle Python process (findings-3's estimate).

**3. The reply is read once** (findings-3 #3, Lane R). The stdout handler
(`main.js:378-384`) today does `pending += d` and searches the whole
`pending` for every piece. It keeps the pieces in an array and searches
only the new piece for `"\n"`, joining once per line; `take()`, the
progress lines and the last-line-wins rule (decision 193) are unchanged,
and `close` still takes what is left.

**Why no status can go wrong.** The same command runs the same code in a
process that started earlier; the same lines are parsed.

**Tests:** Lane P - `tests/test_api.py`:
`test_a_spare_runs_the_one_command_it_is_handed_and_replies_as_a_fresh_process_does`
(a `state` and an `edit` with a payload, compared byte for byte with a fresh
process's reply), `test_a_spare_handed_nothing_exits_quietly`,
`test_a_spare_handed_a_malformed_line_says_the_usage_and_runs_nothing`,
`test_importing_the_api_opens_no_file_but_the_programs_own` (in a
subprocess, a `sys.addaudithook` on `open`, `os.listdir` and `os.scandir`
around `import tracker.api` with `TRACKER_PRODUCT_NAME` set: every path is
under the interpreter's prefix, its site-packages or the checkout's
`tracker/`), `test_only_the_task_name_and_the_programs_own_place_are_fixed_at_import`
(the AST scan, with exactly those three names allowed);
`tests/test_api_entry.py` - `test_the_entry_given_the_spare_flag_waits_for_its_command`.
Lane R - `tests/test_single_source.py` (its `main.js` harness, `:246-320`):
`test_the_shell_hands_a_waiting_spare_the_next_command_and_starts_another`,
`test_a_pass_is_never_handed_to_the_spare`,
`test_a_spare_from_before_the_program_changed_is_not_used`,
`test_quitting_kills_the_spare`, `test_no_spare_starts_before_the_first_list`,
`test_a_reply_in_a_thousand_pieces_is_read_once_and_whole`; and
`test_the_shell_runs_only_commands_the_api_has` (`:135`) keeps its pins
(`proc.on("close", (code)`, `proc.kill()`, the timeout).

### P221 - the Overview is asked beside the list at launch (A2)

**Today** `commandProblem` (`main.js:261`) allows only `BOOTSTRAP_COMMAND`
(`list`) until the first reply carries `vocab.commands`, so the renderer
asks `firm` only after `list` (3.2 + 6 s = 9.2 s at 2,000 returns).

**The change** (Lane R):

- `main.js`: `const EARLY_COMMANDS = new Set([BOOTSTRAP_COMMAND, "firm"]);`
  and `commandProblem` allows `EARLY_COMMANDS` before the allowlist is
  learned. Both are read-only replies (`api.HELD_READING_COMMANDS`,
  `api.py:6169`; neither is in `WRITING_COMMANDS`). The comment at
  `main.js:68-72` names P221 and decision 176.
- `shell.js`: `shellAskFirmEarly()`, called by `bootstrap` (`app.js:1906`)
  before it awaits the list, sends `window.tracker.call(["firm"])` itself
  (not `call()`, whose warnings need the vocabulary) and sets
  `shellFirmNow = { status: "loading", data: null }`. `shellLoadFirm`,
  when that early reply is still pending, adopts it instead of sending
  another: its warnings become notices and an error becomes the
  Counts Not Available notice once the vocabulary is there. A list that
  says `needs_root` discards it.
- The renderer's first `call([...])` in `app.js` stays `list`, which
  `test_the_shell_runs_only_commands_the_api_has` reads.

**Decisions touched:** 176 (what may run before the allowlist): the
allowance is widened by one read-only command. The two processes read the
same store in WAL, as `firm` and `state` already do after every write.

**Tests** (Lane R): `tests/test_single_source.py` -
`test_the_shell_allows_the_read_only_overview_before_the_first_reply`
(and the existing pin extended: every early command is in
`api.HELD_READING_COMMANDS` and not in `api.WRITING_COMMANDS`);
`tests/test_shell.py` - `test_the_overview_is_asked_beside_the_list_and_drawn_once_the_words_arrive`,
`test_an_early_overview_is_dropped_when_the_list_asks_for_a_folder`.

### P222 - a wait says what it shows (W1, W2, findings-4 #3-#6)

**1. "Updating"** (W1, Lane R; the word Lane P's). `drawPage`
(`shell.js:728`) treats a firm page as waiting only when no counts are
held (`:739-741`). Now, when it is a firm page and `shellFirmNow.status ===
"loading"` with `shellFirmNow.data` held:

- `#page` gets `aria-busy="true"` and the class `is-updating`;
- the page's first child is `h("p", { className: "page-updating", role:
  "status" }, screenWords().updating)`;
  *(Changed by the review, 9fbf844: the word sits instead in a permanent
  `#page-updating` element (`role="status"`) in the path bar `#bar`, its
  text set only when it changes, so no row moves and a redraw does not
  announce it again; P222's row records it.)*
- `drawCounts` (`shell.js:586`) gives each `.side-count` the class
  `is-held`;
- `shell.css` mutes the figures, the status pills and the side counts
  under those classes with existing tokens (`--text-muted`), and in the
  forced-colors block (`shell.css:1107`) gives them `GrayText`;
- all of it goes when the new reply is drawn. Rows stay usable: Open and
  Check read fresh, and every write is judged under the lock.

This is what SPEC-shell 4.2 already promised ("While it runs the firm pages
show their loading state") and the drawing did not do.

**2. "Reading {n} of {total} Households"** (W2). Lane P makes `firm` say how
far it is; Lane R shows it.

- **Lane P, `tracker/api.py`.** `_firm_from_cache` (`api.py:6013`) reads the
  households not kept in batches of `FIRM_READ_BATCH = 25`, in the walk's
  order: each batch through `_firm_read_households` (`api.py:6120`; one
  `households_named` call per batch), then at once the row of every return
  that batch's own facts would show (`mark_superseded` over the batch's
  returns and `runner.why_skipped`), kept in `early[(folder, path)]`. The
  practice-wide step is unchanged and stays the authority: the final loop
  uses `early` for a shown return when it has it and builds the row
  otherwise (as today), and a row built early for a return not shown is
  dropped. `_firm_row` is a function of the household's read and the day,
  not of the marks, so its row is the same whenever it is built; the
  fingerprints are still taken before anything is read. Batching
  `households_named` cannot change an answer the firm uses: it keeps only
  each read household's kind, name, feeds, related and each return's
  problem, active, tax year and rolled-from, none of which depends on
  another household (the two-claims stop is not read here; the
  superseded marks are worked out again over every fact).
- Before the first batch (when at least one household is read) and after
  each batch, `firm` prints one **count line** (`progress.count_line`,
  section 5.3), flushed; an `OSError` or `ValueError` printing it is
  ignored (the fill's child has no stdout). The `short` re-read
  (`api.py:6069-6083`) and the whole-walk fallback `_firm_fresh` print
  none.
- **Lane R.** `app.js`'s `onPassMessage` (`app.js:2206`) hands a message
  whose `args[0]` is `"firm"` to a new `shellFirmProgress(said)` before its
  pass check; `shellProgress` (`shell.js:464`) never sees one. `shellLoadFirm`
  starts a 2,000 ms timer when it sends; once it has fired and a count line
  has arrived, a firm page **waiting with no counts held** draws, in place
  of the visually hidden "Loading" in `shellLoading`'s group head
  (`shell.js:713`), the visible `fill(words.reading_households, {n: done,
  total})` and a determinate bar built as the last-sort bar is
  (`shell.js:431-438`: `role="progressbar"`, `aria-valuemin="0"`,
  `aria-valuemax`, `aria-valuenow`, a filled span, `aria-labelledby` the
  words' id). A page updating held counts keeps W1's word. Under 2 s, or
  with no line, the outline stays as it is. The timer and the count are
  cleared when the reply lands; a reply that ends after the fallback keeps
  the last count until it lands.

**3. Household and year pages follow the counts** (findings-4 #3, Lane R).
`shellLoadFirm`'s redraw (`shell.js:228`) also covers the `household` and
`year` levels. `pagesReturnSpecs` (`pages.js:1373`) marks a row `waiting`
while the firm's counts are loading with none held, and `pagesRow` draws an
`aria-hidden` outline bar in its status cell - never a pill, never a blank;
with the counts failed the cell is empty and the notice says so.

**4. The outline in its own page's grid** (findings-4 #4, Lane R).
`drawPage`'s busy path sets `page.dataset.list = pagesListOf(route)`
(`pages.js:719`; `""` for a return page, so a return no longer borrows the
last list's grid), and `shellLoading` adds, for Overview, three empty
`.figure` outlines and a group-head line, and for a return page one caption
line: no words, no numbers, no dots.

**5. Outline bars in a contrast theme** (findings-4 #5, Lane R). In
`shell.css`'s forced-colors block: `.row-skeleton > i { background:
GrayText; forced-color-adjust: none; }`.

**6. The outline at first paint** (findings-4 #6, Lane R). `index.html:86`'s
`<main id="page">` starts with `aria-busy="true"` and six `.row-skeleton`
rows; `shell.css` draws an outline bar for `.side-name:empty`; the setup
page's Start shows the outline while `set-root` runs. `shellDraw` replaces
all of it.

**Words** (Lane P adds them to `api.SCREEN`, `api.py:1295`, beside
`"loading"` at `:1486`; Lane P adds their `pilot/wording-shell.tsv` rows):
`"updating": "Updating"` and `"reading_households": "Reading {n} of {total}
Households"`, both approved by Jason on 2026-10-08. The renderer types
neither (`test_the_new_renderer_files_type_no_words_of_their_own`).

**Why no status can go wrong.** The marker and the count say what the page
is doing; no count is shown that was not read, and the batch rows are
built by the same function from the same reads (the suite's reference, the
whole walk, is the check).

**Tests:** Lane P - `tests/test_api.py`:
`test_a_cold_overview_says_each_batch_of_households_it_reads`,
`test_a_warm_overview_prints_no_count`,
`test_an_overview_read_in_batches_is_the_whole_walks_answer` (with
`FIRM_READ_BATCH` set to 1 and 2, on a firm with a rolled-forward
household and a household whose record is gone),
`test_the_speed_round_words_are_in_the_screen_vocabulary`;
`tests/test_progress.py` - `test_a_count_line_carries_no_pass_and_no_name`.
Lane R - `tests/test_shell.py`:
`test_a_firm_page_drawn_from_held_counts_while_they_are_asked_again_says_updating`,
`test_updating_goes_when_the_new_counts_are_drawn`,
`test_a_firm_wait_over_two_seconds_says_how_many_households_are_read`,
`test_a_firm_wait_under_two_seconds_shows_only_the_outline`,
`test_a_count_line_is_never_taken_for_the_passes`,
`test_household_and_year_pages_follow_the_counts_when_they_arrive`,
`test_a_return_row_waiting_for_its_counts_shows_an_outline_never_a_blank`,
`test_a_skeleton_stands_in_the_grid_of_its_own_page`,
`test_skeleton_bars_are_greytext_in_a_contrast_theme` (beside
`test_the_shells_stylesheet_ends_with_its_own_forced_colors_block`),
`test_the_first_paint_is_the_outline_not_a_blank_shell`. Vocabulary in
Lane R's tests is the stub's (`vocab.screen` with both keys), never read
from `tracker.api`, so the lane's gate does not wait for Lane P.

### P223 - a budget in counts, run on this machine (ARTICLE-WEIGHED)

**Built, in counts, not seconds.** A test that fails when a change quietly
undoes this round. Seconds are rejected (four shared cores, the office
PC's Defender and disk). Disk questions are rejected too: their count
depends on the platform (`Path.resolve` is one `lstat` a segment on Linux
and two handle opens on Windows) and on how deep the test's temporary folder
is. What is counted is decided by the code alone, the same on Windows and
Linux, Python 3.11 and 3.13:

`tests/test_runner.py::test_an_idle_pass_stays_within_its_budget`, on the
suite's own three-household made-up firm (`_three_households`), after one
settling pass, around one pass with nothing new:

| Counted | How | Budget |
|---|---|---|
| store statements per household | a counter around `store._Cursor.execute` | the count measured after the build, times 1.2, rounded up |
| record lists built per return | calls to `store.rules` | at most 2 |
| checkpoint connections opened in the pass | calls to `checkpoint._connect` | exactly 1 |
| whole writes of the pass-order hint | calls to `fsio.write_text_atomically` with the hint's path | exactly 1 |
| machine questions asked outside any hold | `settings.resolved` and `settings.data_home` called while `settings._HELD is None` | the count measured after the build, times 1.2, rounded up - per pass, not per household |

The measured figures go in the test's docstring. A change that needs a
higher budget raises it in the same commit with a decision row saying why.
It runs locally, in the gate, like every test (decision 207); CI runs
nothing per commit (decision 211).

### P224 - measured and not built

Section 4.

## 4. Not built, and why

**Declined or held by Jason (2026-10-08):**

| Item | Why |
|---|---|
| Trusting a record's size and time inside a pass's household (findings-2 #3) | A journal replaced mid-household at its own size and time would go unseen until the next pass. P212 accepted that trade for the Overview, which decides no status; the pass decides statuses. |
| Sort leaving the practice page to the schedule (findings-3 #7a) | Decision 203 stands: Run now writes the practice page exactly as the schedule does. |
| Skipping the list after a Sort (findings-3 #9) | Not proved that a one-household pass changes nothing the list carries (a household's problem, a misfit); 194's Q5 ruled the list is asked. |
| Showing the last counts "as of HH:MM" (findings-4 #9) | P120: a cache may never make a status wrong, and a count one pass old shown before the reply is that. W1 and W2 say the wait instead. |

**Not to be built, from the reports:**

| Item | Why |
|---|---|
| Trimming reply fields (findings-3) | Encoding, parsing and cloning the 3.9 MB firm reply is about 60 ms; trimming saves 10-20 ms against the wording tests that pin replies. |
| A long-lived worker serving every command (findings-3 #5) | Breaks decision 171's lock rule (a live worker's lock refuses clicks for 2 h 05 min), one store per process, P118's holds per reply, the kill per command and crash isolation; row 171 already rejected it. P220's spare gets most of the gain. |
| `mmap_size`, `cache_size`, `temp_store` (findings-2 #6) | No gain measured; a mapped file is one Windows must later rename or delete. |
| One store transaction per household (findings-2 #7) | Undoes decision 102 (one decision, one transaction) for about 3.6 s a first pass. |
| New and dropped indexes (findings-2 #4, #5, #8) | Each needs a schema step; they wait for the next one (`_ADDED_IN_PLACE`, `store.py:428`, reads every in-place statement as an `ALTER TABLE` and would need a line for a `CREATE INDEX`). |
| A one-open-per-`record()` checkpoint (findings-2 #1a) | Subsumed by P214. |
| Reading only each return's details in the scaffold (findings-1 #8, the smaller alternative) | Changes which returns count when a list cannot be read; P215's held reads cover it. |
| Deferring `after_install` and `runner` at the API's import (findings-1 #6, "later") | Not asked; touches the layering, and P220's spare pays the import before the click. |
| Registering `pillow_heif` lazily | P219: a HEIC photo could reach Pillow before it knows the format. |
| Skipping the scheduled practice page when only its times moved (findings-3 #7b) | The page's stamp is the one place on Drive that shows the schedule is running (security principle 6), and P210 relied on that. |
| A shimmer; optimistic UI after a save; hover prefetch of `state`; partial firm lists drawn as they arrive; keeping the old page on a route change; caching the vocabulary in local storage (findings-4) | SPEC-shell 6 forbids a shimmer; a write can be refused, so showing it early is guessing; a process per hover competes with the pass; partial totals are wrong part way through; another return's statuses would sit under new crumbs; words would live outside the API and go stale after an upgrade. |
| Anything from the article about networks, CDNs, bundlers, service workers, Redis or telemetry | There is no network in this app, and no telemetry by rule (ARTICLE-WEIGHED). |

## 5. Build lanes

Two lanes, each in its own git worktree from `8e18570`, built at the same
time. **No file is in both.** Each lane commits its own work, refreshes the
derived map in its own commits (`python tools/repo_map.py update`), and
does not touch `docs/repo-map.curated.json`, `pilot/DECISIONS.md`,
`docs/runbook.md`, `docs/storage.md`, `README.md`, `docs/ROADMAP.md` or any
`pilot/SPEC-*.md` - the orchestrator writes those at merge (5.5).

### 5.1 Lane P - Python

| File | Rows |
|---|---|
| `tracker/checkpoint.py` | P214 |
| `tracker/store.py` | P214, P215, P219 (`has_rules`) |
| `tracker/settings.py` | P215 (`held`) |
| `tracker/manifest.py`, `tracker/filer.py` | P215 (E2) |
| `tracker/content_check.py` | P216 |
| `tracker/runner.py` | P214 (`left_behind`, `_to_move`), P215 (the two readings), P217, P218 (S1) |
| `tracker/after_install.py` | P214 (`CHECKPOINT_UNIT`, the unit rule), P218 (S3) |
| `tracker/progress.py` | P219 (the scan-line spacing), P222 (`count_line`) |
| `tracker/layout.py`, `tracker/registry.py`, `tracker/scanner.py`, `tracker/validators.py` | P219 |
| `tracker/api.py` | P220 (`spare`, `SPARE_FLAG`), P222 (batches and count lines; `SCREEN` words) |
| `api_entry.py` | P220 |
| `.github/workflows/build.yml` | P214 (the package's forbidden names) |
| `pilot/wording-shell.tsv` | P222 (two rows) |
| `pilot/installer/setup.iss`, `tests/test_pilot_installer.py` (edits for it; Lane R still runs it) | P218 (S3, Q1) |
| `tests/test_checkpoint.py`, `test_store.py`, `test_settings.py`, `test_manifest.py`, `test_filer.py`, `test_content_check.py`, `test_runner.py`, `test_after_install.py`, `test_progress.py`, `test_layout.py`, `test_registry.py`, `test_scanner.py`, `test_validators.py`, `test_api.py`, `test_api_entry.py`, `test_build.py`, `test_tripwire.py`, `tests/conftest.py`, and any other test file whose module Lane P changed and that needs a fix (`tests/test_errors.py` for `validators.PdfReader`, for example) - except `tests/test_shell.py`, `test_shell_menu.py` and `test_single_source.py`, which are Lane R's | the rows' tests |

Build order inside the lane, one commit or more per row: P214, P215, P216,
P217, P218 (S1, S3), P219, P220, P222's Python half, P223 last (it
measures the others).

### 5.2 Lane R - the app

| File | Rows |
|---|---|
| `app/renderer/app.js` | P213, P218 (`shellWriteLanded` calls), P221 (`bootstrap`), P222 (`onPassMessage`) |
| `app/renderer/sheet.js` | P213 |
| `app/renderer/shell.js` | P218, P221, P222 |
| `app/renderer/pages.js` | P222 (3, 4) |
| `app/renderer/index.html` | P222 (6) |
| `app/renderer/shell.css` | P222 (1, 5, 6) |
| `app/main.js` | P220 (the spare, the reader), P221 (`EARLY_COMMANDS`) |
| `tests/test_shell.py`, `tests/test_single_source.py`, `tests/test_shell_menu.py` (only if its harness needs the spare's spawn) | the rows' tests |
| `pilot/harness/` (optional: an `interact.mjs` step for P213) | - |

Build order: **P213 first**, then P218's renderer half, P222, P221, P220.

### 5.3 The contracts between the lanes

1. **The spare (P220).** Flag `--spare`, the only argument. Started as
   `FROZEN_API --spare` or `python -m tracker.api --spare` (cwd the
   checkout), with the environment a fresh command gets. stdin: one line,
   UTF-8 JSON `{"argv": ["<command>", ...]}` and `"\n"`, at most 65,536
   bytes; then the payload bytes exactly as today (JSON or nothing); then
   end of input. stdout and the exit code: exactly what `main(argv)` gives a
   fresh process. End of input before the newline: exit 0, no output. A
   malformed line: the usage envelope `main([])` prints, exit 1.
2. **The early Overview (P221).** No Python change: `firm` is already a
   read-only reply. `main.js` allows exactly `list` and `firm` before the
   allowlist.
3. **The count line (P222).** One ASCII line on `firm`'s stdout, before
   its reply:

   ```json
   {"progress": {"v": 1, "event": "households", "done": 25, "total": 1000}}
   ```

   `v` is `progress.FORMAT_VERSION`; `event` is the new
   `progress.COUNT_EVENT = "households"`, which is not in `progress.EVENTS`
   (a `Watch` can never say it); `done` and `total` are integers,
   `0 <= done <= total`, `total >= 1`. The first line has `done: 0`, `done`
   never falls, and the last has `done == total`. No `pass`, `n`, `of`,
   `household`, `name` or `limit_seconds` key, ever. Printed only by `firm`
   while it reads households afresh on its cached path. `main.js` passes it
   on as it passes any progress line (`take`, `main.js:350-372`, on the
   `tracker-progress` channel as `{args: ["firm"], progress}`).
4. **The words (P222).** `vocab.screen.updating` = "Updating";
   `vocab.screen.reading_households` = "Reading {n} of {total} Households",
   filled with `n` = `done` and `total` = `total`. Wording rows (Lane P):

   ```
   api._vocab	screen.updating	(new)	reword	Updating	1	Firm pages and side counts, while held counts are asked again	P222; approved by Jason 2026-10-08	Updating	
   api._vocab	screen.reading_households	(new)	reword	Reading {n} of {total} Households	5	A firm page's loading state, after about 2 s	P222; approved by Jason 2026-10-08	Reading {n} of {total} Households	
   ```

### 5.4 The gates

Every gate runs first `python -m ruff check .` on the changed files and
deletes dead code in them (decision 207), then the tests, each test file
as its own process and the files in parallel, under **both**
interpreters:

```
PY311=/tmp/claude-0/-home-user-Tax-Info-Request-List-Pilot/6549e888-04ab-55c6-9702-4474437cf354/scratchpad/venv311/bin/python
PY313=python3
```

then `python -m ruff check .`, `python tools/repo_map.py update`, and
`python tools/repo_map.py check` (exit 0).

**Lane P runs the whole suite**: it reaches the engine (`manifest`,
`filer`, `scanner`, `store`), which is Jason's rule for the whole suite
(2026-09-29), and the modules it changes (`settings`, `layout`, `store`)
are imported by nearly every other. For each interpreter:

```
ls tests/test_*.py | xargs -P 4 -I{} sh -c '$PY -m pytest -q "{}" > "$OUT/$(basename {}).log" 2>&1; echo "$? {}"'
```

with `PY` and `OUT` (a scratch folder) set, and every line must start with
`0`. No routing word, typed case or matcher changes, so
`tools/vocab_report.py` and the backtest baseline are untouched.

**Lane R runs the files that drive what it changed:** `tests/test_shell.py`,
`tests/test_single_source.py`, `tests/test_shell_menu.py`,
`tests/test_api.py` (its `main.js` harness tests at `:8429` and `:9238`;
`test_shell.py` imports its helpers), `tests/test_pilot.py`,
`tests/test_pilot_ui.py` (the stylesheet rules `test_shell.py` borrows),
`tests/test_pilot_installer.py` (it reads `main.js`), and the guards
`tests/test_layers.py`, `tests/test_repo_map.py`, `tests/test_tripwire.py`
(tests change) - each as its own process, both interpreters.

### 5.5 The merge (orchestrator)

1. Merge Lane P, then Lane R, into the round's branch. The derived map
   (`docs/repo-map.json`, `docs/repo-map.md`) will conflict: take either
   side, `git add` the resolved sources, and run
   `python tools/repo_map.py update` (decision 151), then `check`.
2. Add the one test that joins the lanes, in `tests/test_single_source.py`:
   `test_the_shell_and_the_api_agree_on_the_spare_the_early_overview_and_the_count_line`
   - `main.js`'s spare argument is `api.SPARE_FLAG`; every early command is
   in `api.HELD_READING_COMMANDS` and not in `api.WRITING_COMMANDS`; the
   renderer routes `progress.COUNT_EVENT`'s lines by the `firm` command
   name `runner.FIRM_COMMAND`.
3. Write the docs:

   - **`pilot/DECISIONS.md`**, rows P213-P224 after P212, each in the
     house form (decision in bold, then why), pointing to
     `pilot/SPEC-speed-round.md`:
     - P213 **The reminder sheet never offers another return's letter** -
       found by findings-4: Copy put the previous client's letter on the
       clipboard while the next loaded.
     - P214 **The record checkpoint keeps a write-ahead log, one connection
       a command** - Jason, 2026-10-08 (E1): 65% of a first pass's syncs;
       durability unchanged (WAL at FULL); `-wal` and `-shm` named wherever
       the checkpoint is.
     - P215 **Answers kept for one hold: the walk, the key, the record's
       reads** - `settings.held`; Jason, 2026-10-08 (E2) for the reads,
       proved by the record's head and row.
     - P216 **The digest cache's key from the held folder** - Jason,
       2026-10-08 (E3): the same key string; the reader untouched.
     - P217 **The pass-order hint: a mark appended as each household
       starts, the whole written once a pass** - Jason, 2026-10-08 (S2);
       also found that the hint was unreadable past 64 KiB (about 370
       households).
     - P218 **The Overview is made ready once** - Jason, 2026-10-08 (S1,
       S3); the second `firm` after a Sort gone.
     - P219 **Smaller repeats** - pure caches keyed by text, `has_rules`,
       the scan's owners, the progress file's scan lines, pypdf on first
       use; `pillow_heif` stays at import.
     - P220 **A warm spare, still one command a process; the shell reads a
       reply once** - Jason, 2026-10-08 (A1).
     - P221 **The Overview is asked beside the list at launch** - Jason,
       2026-10-08 (A2); widens decision 176's early allowance by one
       read-only command.
     - P222 **A wait says what it shows** - "Updating" and "Reading {n} of
       {total} Households", approved by Jason 2026-10-08 (W1, W2); the
       household and year pages, the outline's grid, contrast themes and
       first paint.
     - P223 **A budget in counts, run on this machine** - counts, not
       seconds or disk questions.
     - P224 **Measured and not built** - section 4's two tables in one
       sentence each.
   - **`docs/runbook.md`**:
     - lines 44-48 ("A Sort does the same only while the file is already
       ready ... one household's Sort never waits for the whole firm."):
       "A Sort leaves it to the app, which asks the Overview the moment the
       Sort ends (pilot P218). Setup asks it once at its end too, so the
       first Overview after an install opens at once; the app's first
       Overview after an upgrade reads every household and says how many
       it has read." (No wording that tells a person to run a step once;
       `test_single_source`'s `ONE_TIME_STEP_DOCUMENTS` check reads it.)
     - lines 568-582: "the record checkpoint `record-heads.db` with its
       `record-heads.db-journal`, `record-heads.db-wal` and
       `record-heads.db-shm` if there are any"; "moves `record-heads.db`
       and its journal and write-ahead log together"; "The checkpoint, its
       journal, its write-ahead log and shared memory, and a `.damaged`
       copy move as one: a journal or write-ahead log found without its
       checkpoint beside it ... moves nothing".
     - lines 1975-1979: the record checkpoint "(and, while a command runs,
       its `-wal` and `-shm` beside it)".
     - lines 1986-1995: "With the app closed and the schedule off the
       checkpoint is one file; if a `record-heads.db-wal` is beside it
       (the machine stopped mid-write), copy it with it - it holds writes
       the file does not yet."
     - lines 2267-2273: "rename the file - and a `record-heads.db-wal` and
       `-shm` beside it, the same way - (for example to
       `record-heads.db.damaged`)".
   - **`docs/storage.md`** lines 93-100: the checkpoint is kept in SQLite's
     write-ahead log at full sync (P214), one connection a command; its
     `-wal` and `-shm` sit beside it while a command runs.
   - **`README.md`**: no change (checked: it names neither the checkpoint's
     journal, the Sort's cache fill nor the process model).
   - **`docs/ROADMAP.md`**: no change (pilot decisions live in
     `pilot/DECISIONS.md`).
   - **`pilot/SPEC-shell.md`**: 4.2 (lines 507-513): "`firm` at start,
     beside `list` (P221), and again after ...; while it runs a firm page
     with no counts yet shows its loading state, with "Reading {n} of
     {total} Households" after about 2 s (P222), and one drawn from counts
     already held says "Updating""; 6, states (lines 773-777): "a visually
     hidden "Loading" - visible, with its count and a bar, on a firm page
     whose wait passes about 2 s (P222)"; the vocabulary table (line 1565):
     `loading` "screen readers only, but for P222's wait", and two rows
     `updating` / Updating / firm pages and side counts while held counts
     are asked again, `reading_households` / Reading {n} of {total}
     Households / a firm page's wait over about 2 s.
   - **`pilot/SPEC-firm-cache.md`**: lines 268-273 ("No new words, no shell
     change.") gain "Since P222 the wait says how many households it has
     read, after about 2 s."; lines 436-438 ("still shows the loading
     outline for a few seconds") gain "and, past about 2 s, Reading {n} of
     {total} Households".
   - **`pilot/SPEC-firm-cache-fill.md`**: after R2's changed paragraph
     (line 74), R4 (line 112) and the staff note (lines 253-255), each:
     "*Changed by P218 (Jason, 2026-10-08): a Sort no longer fills the
     cache; the app's own Overview, asked the moment the Sort ends, does.*"
   - **`docs/repo-map.curated.json`** (then `update`): `tracker/checkpoint.py`
     notes ("opens this file per operation through store._beside()" ->
     one connection a command, held by the store, WAL at FULL, P214);
     `artifact:record-heads.db` (its `-wal` and `-shm` move with it);
     `tracker/store.py` (`_held_checkpoint`, `held_read`, the key memo,
     `has_rules`); `tracker/settings.py` (`held`); `tracker/manifest.py`
     and `tracker/filer.py` (reads held per head); `tracker/content_check.py`
     (the key); `tracker/runner.py` and `artifact:pass-order.json` (P217,
     S1); `tracker/after_install.py` (the setup door's Overview job);
     `tracker/progress.py` and `artifact:passes/` (scan lines spaced; the
     count line); `tracker/layout.py`, `tracker/validators.py`,
     `tracker/scanner.py`, `tracker/registry.py` (P219); `tracker/api.py`
     and `api_entry.py` (the spare; the count line); `app/main.js` (the
     spare, the reader, `EARLY_COMMANDS`); `app/renderer/app.js`,
     `shell.js`, `sheet.js` (P213, P218, P221, P222).
4. Run the union of both lanes' gates on the merged tree, both
   interpreters, then `ruff` and both `check`s. Open the pull request as a
   draft with the `windows` label (P214's held handle, P216's path key) and
   mark it ready once (decision 211).

**The Windows check** (Jason's rule of 2026-09-29, through
`pilot\wintest\run_checks.ps1`): the whole suite, because the change
reaches the engine. By hand, on the 22-household sample: open a return,
Sort, and see one Overview reply after it (the error log shows no second
`firm`); open the reminder sheet from Reminders on another client and press
Copy before it draws (nothing is copied); quit the app and see no
`python`/tracker process left; open Overview after deleting
`firm-view.json` and see "Reading n of N Households" once the wait passes
2 s; with the app closed, see `record-heads.db` alone in the data folder;
install the pilot installer over the 22-household sample with a saved
clients root, see "Preparing Overview..." before it offers to launch
the app, see no window, and see the first Overview open at once (Lane P's
handoff, Q1). The failure window (Jason, 2026-10-08) cannot be made to
appear by hand on a working install; its code is pinned by
`tests/test_pilot_installer.py` and its exit codes by
`tests/test_after_install.py`, and the installer build compiles it.
Optional: time `state` page changes before and after (the spare).

## 6. How to measure after

Made-up firms only; never a client's document, never the office's folders.
The shared 1,000-household firm under `scratchpad/scale/t1k` is read-only:
`list`, `state` and `firm` on it are allowed, a pass or any writing command
is not.

1. **A small firm of one's own:** 50 households, built by the existing
   generator into a scratch folder, with `TRACKER_SETTINGS_DIR` and
   `TRACKER_DATA_HOME` beside it:

   ```
   MY=<scratch>/after; mkdir -p $MY/settings $MY/data
   echo '{"clients_root": "'$MY'/root"}' > $MY/settings/settings.json
   TRACKER_SETTINGS_DIR=$MY/settings TRACKER_DATA_HOME=$MY/data python <scratch>/scale/make_firm.py $MY/root 50
   ```

   Then one settling pass (`python -m tracker.runner --settings $MY/settings`).
2. **Counts, before and after** (before = a clean worktree of `8e18570`,
   after = the merged branch, the same firm copied twice):
   - disk questions in a pass with nothing new, with `opt/code/count_io.py`
     (target: about 41,000 or fewer against 131,559);
   - store statements per household and `store.rules` calls per return (the
     P223 counters);
   - checkpoint syncs in a first pass on a fresh copy, by `strace -f -e
     trace=fsync,fdatasync -y` split by file (target: about 1,300 against
     5,206), and that none of `record-heads.db-wal`/`-shm` is left once the
     pass ends;
   - whole writes of `pass-order.json` a pass (1) and its size at 50
     households (about 6 KB);
   - progress-file replaces a pass (`replace` in `count_io.py`'s table);
   - `firm` lines on stdout for a cold Overview (`done` from 0 to the number
     of households, in steps of 25), and none warm.
3. **Read-only on the shared firm:** `list` three times alternating with
   the old worktree (target 2.0-2.1 s against 3.0-3.2 s, reply
   byte-identical), `firm` warm three times, `python -X importtime -c
   "import tracker.api"` (pypdf absent), and a spare's `state` against a
   fresh one (in a scratch script that starts `python -m tracker.api
   --spare` and writes the line).
4. **The answers are unchanged:** after one pass each on the two copies,
   the same files at the same sizes, the same line for every return, and
   `firm` and `list` replies equal byte for byte (the root path aside).

## 7. Open questions for Jason

- **Q1 - answered.** The pilot's installer (`pilot/installer/setup.iss`)
  ran no after-install step; only `Setup.bat` did. Jason, 2026-10-08:
  "Yes, add to pilot" - the pilot installer runs the step too, so testers
  get the warm first Overview. Built in Lane P (5.1): `setup.iss` `[Run]`
  gains one entry, before the launch entry, that runs the packaged API's
  after-install step with the setup door, `runhidden waituntilterminated`,
  so the fill happens while the installer is still on screen. If the
  packaged API's `after-install` command cannot name the setup door today,
  Lane P adds that argument to it (`tracker/api.py`, `api_entry.py`) and
  says so in its handoff. A failed step must not fail the install: the app
  runs the step again at its first launch, as it does today. *(Jason,
  2026-10-08, after the build: the status line reads "Preparing
  Overview...", and a step that fails says so in a small error window - the
  step moved to the installer's `[Code]` so it can read the setup mode's
  exit code, `runner.SETUP_STEP_FAILED` or `SETUP_OVERVIEW_NOT_READY`; a
  silent install shows no window. P218's row records it.)* Owning test:
  `tests/test_pilot_installer.py`
  (`test_the_pilot_installer_makes_the_overview_ready_before_it_launches_the_app`).

## 8. Measured before and after (2026-10-08)

The same script, on the same Linux sandbox (4 cores, Python 3.13), with
nothing else running, on two fresh copies of the made-up 1,000-household
firm (2,000 returns, a new pile of 13 sample files in every household's
inbox; the checkpoint told of each copy's root by the runbook's
`move-root`). After: `a3cf636`. Before: `8e18570`, run straight after it.
A first before-run an hour earlier agreed within 5%. Seconds, one run for
the passes, the median of three for the commands.

| Step | Before | After | Change |
|---|---|---|---|
| Start the engine (`import tracker.api`) | 0.28 | 0.20 | -30% |
| First pass, 1,000 new piles | 740 | 672 | -9% |
| Overview, kept copy current | 7.0 | 6.7 | -5% |
| Overview, kept copy gone | 14.4 | 12.2 | -15% |
| Client list | 4.0 | 3.0 | -24% |
| One return's page | 0.34 | 0.27 | -21% |
| Sort & Scan, one household | 19.4 | 7.0 | -64% |
| Scheduled pass, nothing new | 79.8 | 47.0 | -41% |
| Scheduled pass, draft day | 106.8 | 65.2 | -39% |
| Scheduled pass, draft day again | 86.7 | 51.6 | -40% |

The app's side, timed apart (the script above runs no window):

| Step | Before | After |
|---|---|---|
| A return's page, engine started cold vs. handed to the waiting spare (P220) | 0.27 | 0.08 |
| The form templates, likewise | 0.22 | 0.03 |
| The window reading a 3.99 MB Overview reply in 64 KB pieces (P220's reader; both loops copied from `main.js`) | 79 ms | 14 ms |
| The same in 8 KB pieces | 678 ms | 10 ms |
| The same in 4 KB pieces | 1,289 ms | 12 ms |

**The answers are the same.** After one first pass each, both copies hold
49,000 files and the same journal events, count for count (filed 14,000,
parked 8,000, moving 22,000, drafted 2,000 and the rest). The only names
that differ are two prepared copies per return (`A02 - 1 - TY2026.csv`
before, `A02 - 109 - TY2026.csv` after; `D01 - TY2026.xlsx`, `D01 - Ch -
TY2026.xlsx`): both end at exactly 218 characters, because the name is
shortened to fit the path limit and the after-copy's folder name is two
characters shorter. Not the code.

**Not measured here.** The Overview kept copy's walk is the Linux folder
listing (findings-1, "looked at"), which Windows answers from the listing
itself. The checkpoint's syncs (P214) and the hint's (P217) cost more on
Windows than here. Python's start-up is about 0.85 s on the office PC
against 0.2-0.3 s here, so the spare saves more there. The launch-time
gain of P221 and the second Overview a Sort no longer asks (P218) happen
in the window and are reasoned, not timed: after a Sort the window used to
wait for the Sort, a list, and two Overviews (about 19 + 4 + 7 + 7 s here),
and now waits for the Sort, a list and one (about 7 + 3 + 7 s).
