# Pilot 0.3.1 - Sort & Scan, and what the window waits for after it - SPEC

Status: **written 2026-10-08**, branch `claude/cool-brahmagupta-a45s9n` at
`483ec80` (main; the speed round P213-P224 merged). Not built. New
decision rows: **P225-P230**, written at merge into
[`DECISIONS.md`](DECISIONS.md). P225-P228 are built in two lanes with no
file in common (section 5); P229 waits for Jason's ruling (section 7, Q3);
P230 is the measured-and-not-built row.

Jason, 2026-10-08: *"Sort and scan feels slow. Revisit the two held items
and the status overview page."* Decision 203 stands: a Sort writes the
practice page at once, exactly as the schedule does.

The rule above every row here is P120's: **a cache may never make a
status wrong.** Nothing here reads a document, changes a routing rule, a
catalog word or the matcher, so the backtest baseline cannot move.
Nothing is skipped that a person sees: every row either does the same
work fewer times with the same answer (P225, P226), keeps a read answer
only while the record's own head proves it unchanged (P227), or stops
one reply from waiting for another it does not need (P228). P229 alone
would show a count before it is proved, marked, and only if Jason
agrees.

## 1. What was measured

The cloud sandbox (Linux, 4 shared cores, Python 3.13), on a private copy
of the made-up 1,000-household firm (2,000 returns: a 2025 return rolled
forward into a 2026 one in every household), `scale/t1k-y2-unsorted`,
copied to `scratchpad/sortspeed/firm`, its settings and checkpoint pointed
at the copy (`checkpoint move-root`), then one first pass (637 s). Code at
`483ec80`, unedited: every "after" figure below is a prototype applied in
memory by a scratch script (`scratchpad/sortspeed/tools/`), never a repo
edit. The copy was deleted when done. Seconds are this sandbox's; on the
office PC a question to the disk costs about 0.1 ms and Python's start
about 0.85 s (SPEC-speed-round section 8), so the counts carry and the
seconds do not.

### 1.1 Where one Sort & Scan's time goes

`python -m tracker.api run-now --engagement ".../Smith 0500 Family/2026/1040 - John A. Smith"`,
nothing new in the inbox: **5.95, 6.70, 6.27 s** wall (the speed round's
bench said 7.0 on a fresh copy). Split by wall-clock wrappers around each
step, in the process (`phases.py`, 3 runs; cProfile agrees on the shares
and inflates the totals about 2.7 times):

| Step | Seconds | Share |
|---|---|---|
| Start the engine (`import tracker.api`) | 0.17 | 3% |
| The door, the lock look, the root's proof, `pass started`, the hint | < 0.02 | - |
| **Discovery, the whole firm** (`registry.discover_engagements`) | **2.24-2.53** | 40% |
| - of which the Roll Forward match by folder names (`registry._prior_of`'s fallback: 1,999,000 `layout.common_tail` calls) | 0.84-0.94 | 15% |
| **The household's own work** (`run_registry`): nothing new | 0.20 | 3% |
| - the same with 13 new files in the inbox (a second household) | 2.05 | |
| The run log (`append_log`) | < 0.01 | - |
| **The practice page: the report** (`status_report`) | **2.29-2.47** | 39% |
| - 998 un-run returns' records read (`_engagement_status`: `load_manifest(follow=False)` + `summarize`) | 2.13-2.30 | |
| - copies beside records, other machines' lines (`records_needing_a_person`) | 0.31-0.34 | |
| **The practice page: the parked files** (`_parked_files`: 2,000 `read_index(follow=False)`) | **0.76-0.87** | 13% |
| The practice page: drawing (`table`, `page_text`) | 0.04-0.06 | 1% |
| The practice page: writing 2,178,676 bytes | 0.01-0.02 | - |
| `last-pass.json` | not written by a Sort (decision 159) | - |
| The firm cache fill | not run by a Sort (P218) | - |
| The store's close | < 0.01 | - |
| **Final line printed at** | **5.89-6.23** | |

So the practice page is **3.1-3.3 s of about 6.2 (half the click)**, and
of that, drawing and writing are 0.06 s: **the cost is reading 2,000
records the Sort did not touch.** Discovery is another 2.4 s, a third of
it a quadratic name match that runs only because every Rolled From names
the firm's old root (section 3, P225). The household's own work is 0.2 s
with nothing new and about 2 s for 13 new files.

### 1.2 What the window waits for after it

Today (`app.js:passEnded`, `app.js:2335`): the Sort's final line, then
`list`, and only when the list lands, `state` (the shown return) and the
list's own `firm` (`shellAdopt` → `shellLoadFirm`). Driven as the window
drives it, 2 runs:

| | Sort | list | state | firm | return page fresh | Overview fresh |
|---|---|---|---|---|---|---|
| Today's order | 6.25-6.61 | 2.49-2.60 | 0.22-0.26 | 5.15 | **about 9.1-9.5 s** | **13.9-14.4 s** |

The commands alone, warm: `list` 2.57-2.96 s (its own walk is the same
discovery); `firm` 5.0-5.7 s, of which the households' fingerprints are
3.8-4.1 s and the cache file's load 0.07 s.

One sandbox oddity, said so nobody builds on it: `firm` run beside `list`
took 2.5-3.7 s, against 5.3-5.6 s alone, every time. Not explained; the
office PC must be measured (section 6).

### 1.3 The prototypes (in memory, same copy, 3 runs unless said)

| Prototype | Sort & Scan, final line | Other replies | Same answer? |
|---|---|---|---|
| None (today) | 5.89-6.76 | list 2.53-2.58, firm 5.01-5.09 | - |
| P225 the name match by its last three names | 5.56-5.92 | **list 1.69-1.74, firm 4.26-4.42** | registry identical: 2,000 returns, 1,000 superseded, every `superseded_by`, `warning`, `problem` equal |
| P226 the report inside one reading | 5.07-5.44 | - | (no answer changes; P215's hold) |
| P225 + P226 | 4.36-4.53 | | |
| P225 + P227 (rows kept) | 2.86-3.17 | | |
| **P225 + P226 + P227** | **2.49-2.79** | | **page byte-identical**: 2,178,676 bytes, the same SHA-256 drawn from fresh reads, from a filling cache and from every row kept (`equiv_page.py`) |
| The same, 13 new files | 8.37 → 4.77 | | |
| P229's last counts (kept rows, no fingerprint walk) | | **1.20-1.33 s** (0.57-0.58 with P225), import included | equal to the real `firm` reply, `next_sort` aside, when nothing changed |

End to end, the window's wait after a Sort, with P225-P228 together
(3 runs):

| | Sort | state | list | firm | return page fresh | Overview fresh |
|---|---|---|---|---|---|---|
| Today | 6.3-6.6 | after the list | 2.5-2.6 | after the list, 5.2 | 9.1-9.5 | 13.9-14.4 |
| P228 alone (asked at once) | 6.4-6.8 | 0.24-0.31 | 2.9-3.0 | 3.7 | 6.7-7.1 | 10.1-10.5 |
| **P225-P228** | **2.58-2.75** | **0.23-0.25** | 2.00-2.05 | 3.37-3.72 | **about 2.9** | **6.13-6.31** |

**The click's answer drops from about 6.2 s to about 2.6 s; the sorted
return shows its new rows at about 2.9 s instead of 9.3; the Overview is
fresh at about 6.2 s instead of 14.** At launch, P229 would draw the
Overview at about 1.2 s (0.6 with P225) instead of 3.6 here.

## 2. Jason's rulings this SPEC keeps

- **Decision 203** (and the 2026-10-08 ruling declining findings-3 #7a):
  a Sort writes `status.html` before its final line, exactly as the
  schedule does. Kept by P227: the page is still drawn whole, from the
  same values, before the final line.
- **P120:** a cache may never make a status wrong. P227 keeps a row only
  under the record's own head and drops it at every other change; P229
  is the one place this would be loosened, and it is held for Jason.
- **194's Q5 / decision 203:** the list is asked after a Sort. Kept by
  P228 (asked, not skipped; only no longer waited for).
- **Held 2026-10-08:** skipping the list after a Sort (findings-3 #9),
  last counts "as of" (findings-4 #9). Revisited in P228 and P229, with
  the proof and the residual risk, for Jason (section 7).

## 3. Rows

### P225 - Discovery's Roll Forward match asks only the returns that end in the same three names (findings: this SPEC)

**What is slow.** `registry.mark_superseded` (`registry.py:684`) finds
each rolled return's prior with `_prior_of` (`registry.py:654`): by the
resolved Rolled From path first, and when that names nothing - every
Rolled From is written absolute, so **any clients root that has moved
since the Roll Forward** (another drive letter, the runbook's move to
another machine, every pilot tester's copied folders, this made-up firm)
- by comparing Rolled From's trailing folder names with **every** readable
return's (`layout.common_tail`). At 1,000 rolled returns that is
1,999,000 comparisons, **0.84-0.94 s**, paid by every discovery: each
Sort, each `list`, each scheduled pass, and twice in every `firm`
(`api._firm_from_cache` calls `mark_superseded` for each read batch and
again for the whole practice, `api.py:6037`).

**The change** (`tracker/registry.py`, one function and one method):
`_Priors` gains `by_tail()`: the readable returns grouped by their last
`layout.ROLLED_FROM_TAIL` (3) `tail_names`, made once, the first time a
Rolled From needs the fallback (as `names()` is). `_prior_of`'s fallback
compares Rolled From only with the returns in its own group.

**Why the answer cannot change.** A return whose path ends in at least
`ROLLED_FROM_TAIL` of Rolled From's names shares exactly its last three
(`common_tail` counts equal trailing names), so it is in the group; a
return outside the group ends in fewer than three and today's rule
already refuses every such match (`longest < ROLLED_FROM_TAIL`). The
longest tail, the tie rule ("two that tie decide nothing") and the
candidate's own exclusion are computed over the same set of candidates
that could ever win. A Rolled From shorter than three names matches
nothing, as today. The names are `os.path.normcase`d as today, so the
group key folds case where Windows does. Measured: the registry equal
field for field on the 2,000-return firm.

**Gain.** -0.9 s on every Sort, list and scheduled pass and -0.7 s on
every Overview at 1,000 rolled households **after a root move**; nothing
where every Rolled From still names a folder that is there (the resolved
path answers first). The office's real root has not moved, so measure
there before promising it (section 6); every pilot tester's has.

**Tests** (`tests/test_registry.py`):
- `test_the_name_match_retires_the_same_prior_as_comparing_every_pair` -
  a reference copy of today's pairwise `_prior_of` kept in the test,
  against the new one, over generated practices: a moved root, a deeper
  and a shallower old root, two candidates that tie, a Rolled From of
  one and two names, a candidate whose own folder is the best match, and
  a case-only difference (with `os.path.normcase` patched to fold case).
- `test_a_moved_root_compares_each_rolled_return_only_with_its_own_group`
  - `layout.common_tail` counted over 200 rolled households after a move:
  at most 2 calls a rolled return (its own group), not 399.

### P226 - The practice page's report is read inside one reading (P215's hold, findings-1 #1's remainder)

**What is slow.** `runner.status_report` (`runner.py:2797`) reads every
un-run return's record outside any hold, so every store read asks again
where the store is, what the settings say and what each folder resolves to
(`settings.resolved`, `data_home`, the engagement row's key). P215 put
`write_status_page`'s parked-file read (`runner.py:2676`) inside
`one_reading()`; the report beside it was left out.

**The change** (`tracker/runner.py`): `status_report` builds its report
inside `one_reading()`, with the same comment P215 gave the parked files:
the pass's work is done, every household's lock is gone, and the report
only reads; the page is still written after the hold ends. The second call
(a failed fill's redraw, `runner.py:3268`) is the same function, so held
the same way.

**Gain.** The report 2.3-2.5 s → 1.33-1.55 s: **-0.9 s a Sort**; a
scheduled pass's report is all its own runs and gains nothing.

**Tests** (`tests/test_runner.py`):
- `test_the_practice_pages_report_asks_each_machine_question_once` -
  `settings.resolved` and `settings.data_home` counted during
  `status_report` over the suite's three-household firm: once per folder
  and once in all, as P223 counts them.
- `test_the_practice_page_is_written_after_its_readings_end` -
  `settings._HELD is None` when `write_text_atomically` writes `status.html`.
- P223's `test_an_idle_pass_stays_within_its_budget`: its "machine
  questions outside a hold" budget is measured again after the build and
  lowered if it fell (a budget only rises with a row).

### P227 - The practice page's read rows are kept between passes, under each record's own head

**What is slow.** After P226, the page still reads, for every return the
Sort did not run, its whole request list (`load_manifest(follow=False)`,
998 returns, about 1.2 s) and, for every return, its index
(`read_index(follow=False)`, 2,000 returns, 0.76-0.87 s): about 2 s of a
Sort's 4.4 s, to draw rows that are the same as at the last page whenever
those records have not moved. Drawing them is 0.06 s, so keeping the
drawn rows would save nothing; the reads are what to keep.

**Options weighed (Jason's "find the fastest design that keeps 203"):**

| Option | Gain a Sort | Keeps 203? | Verdict |
|---|---|---|---|
| (a) Reuse the last pass's rows from the firm cache (`firm-view.json`) | about 2 s | yes | **No.** The firm rows are the API's, built for the Overview (groups, files, paths), not `summarize`'s counts and `read_index`'s parked rows; turning one into the other is a second place a status is decided (P120's review), and the firm cache is judged by folder size and time (P212), weaker than the record's head. |
| (b) Keep the drawn HTML rows per household | 0.06 s | yes | **No.** Drawing is 1% of the page. |
| (c) Write the page after the final line | about 2.2 s (after P225-P226) | **loosely** | **No.** The shell ends a pass when its process closes (`main.js` `close`, decision 203's contract), so the window would wait for the page anyway unless the final line became the end while the process runs on - a pass process the window no longer watches, still holding the store. The page would land about 2-3 s after the answer, while the window's `state`, `list` and `firm` run beside it on the same cores. A page that could not be written could no longer be said in the final line or change the exit code (`PAGE_NOT_WRITTEN`, decision 189's review S3). `list` and `firm` read nothing of `status.html` (it is `api.FIRM_JUDGED`'s one file left out), so no reply would be wrong - but the page would not land "at once". |
| **(d) Keep each return's read rows, keyed by the record's own head** | **about 1.9 s** | **yes** | **Build.** The page is drawn whole, before the final line, from the same values. |

**The change.**

1. **The key is the record's own token.** `store.held_read`
   (`store.py:1254`) already reuses a record's reads inside a hold while
   its token is unchanged: the row's id, path, `ledger_head` (the
   journal's hash), `applied_seq`, `applied_digest` (the applied chain) and
   `built_at`, because "every table those reads come from is written only
   by applying journal lines, which moves the seq, head and digest, or by
   deleting the row". The token gets one definition, `store.read_token(row)`,
   which `held_read` and the page both use; `store.read_tokens(conn)`
   returns every engagement row's token in **one** `SELECT`, keyed by the
   stored path; `store.record_key(folder)` is the key `_engagement_row`
   already computes (`store.py:1243`, the held key), and answers `None`
   for a folder outside the recorded root, whose row the store finds by
   its tail - such a return is always read afresh. (`_REPLACED`, the
   in-process count of deleted rows, stays in `held_read`'s own token: a
   row rebuilt in another process has a new `built_at`.)
2. **The file.** A new layer-0 module, `tracker/page_rows.py` (the
   standard library, `settings`, `fsio`, `errors` and `firm_cache`'s
   `head`), owns `page-rows.json` in the data home, beside
   `firm-view.json`: its head is `firm_cache.head(root, today)` - the
   program stamp, the clients root, the data home, **the day** and the
   settings file - plus its own `FORMAT`; each entry is one return's folder
   (as text) with its token, `statuses`, `outstanding` and its parked rows
   (`received`, `original_name`, `reason`, `candidates`, in index order).
   Damaged, foreign, another day's or another program's: set aside by
   `load` and said on the error log by its class, never its words, as
   `firm_cache.load` does. It holds client file names, so it lives in the
   data home (decision 186) and is never synced. Deleting it is always
   safe.
3. **The page uses it** (`tracker/runner.py`). `_pass` loads the kept rows
   once before the page (`page_rows.open_kept(root)`, `None` when there is
   no data home or no saved root, and on a dry run, which writes nothing)
   and passes them to `status_report(..., kept=)` and
   `write_status_page(..., kept=)`:
   - `_engagement_status`: `why_skipped`, the problem and the warning
     come from the walk, as now; then the token is read, a kept entry with
     the same token gives `statuses` and `outstanding`, and otherwise the
     record is read as now.
   - `_parked_files`: the same for the parked rows (the label from the
     walk, as now).
   - **A fresh read is kept only when the token read before it equals the
     token read after it**, so a record written by another process while
     it was read is never kept under the older token (the fingerprint
     taken before the read, as `firm_cache` does).
   - A return whose read raised, or whose row the store does not hold, is
     never kept, and is read (and its error kept on the error log) every
     page, as now.
   - The file is written once, after `status.html`, only when an entry
     changed, by `fsio.write_json_atomically`; a failure is a log line by
     its class and changes nothing else (the page already stands).
4. **Concurrency.** A Sort and the schedule writing the file together:
   the last whole write wins, and every entry in it is checked against the
   store's token before it is used, so an entry another process made
   stale is read afresh.

**Why it cannot make a status wrong.** An entry is used only when the
record's token now equals the token it was read under, and the page reads
the store "as the walk left it" (`follow=False`, decision 192) - so a kept
entry is exactly what a fresh `follow=False` read would return. The day
and the program stamp in the head mean every entry is read afresh at least
once a day and after every upgrade, as the firm cache is. The page's
drawing code is unchanged.

**Gain.** -1.9 s a Sort after P225-P226 (4.4 → 2.6 s; with P225 alone,
5.6 → 3.0); about -0.8 s on every scheduled pass's page (its parked rows),
and the day's first page reads everything, as today. The file is about
2.1 MB at 2,000 returns, loaded in 0.01-0.02 s.

**Tests** (`tests/test_page_rows.py`, new, owns the module;
`tests/test_runner.py`, `tests/test_store.py`):
- `test_the_practice_page_from_kept_rows_is_the_page_from_fresh_reads` -
  the suite's firm after a pass: the page drawn with `now` fixed, from
  fresh reads, from a filling file and from every row kept: three equal
  byte strings. (The prototype's check, `equiv_page.py`, on 2,000 returns.)
- `test_a_return_written_since_its_row_was_kept_is_read_again` - a file
  filed into one return after the rows were kept: that row shows the new
  outstanding count and parked rows; every other row comes from the file
  (`load_manifest` and `read_index` counted).
- `test_a_record_rebuilt_from_its_journal_is_read_again` - the store row
  deleted and followed again: a new `built_at`, so a miss.
- `test_a_row_written_while_it_was_read_is_not_kept` - the token moves
  between the two token reads: the page shows the read, and the file
  keeps nothing for that return.
- `test_kept_rows_from_another_day_program_or_root_are_set_aside` and
  `test_a_damaged_kept_rows_file_is_set_aside_and_said_by_its_class`.
- `test_a_return_whose_record_cannot_be_read_is_never_kept`.
- `test_a_sort_reads_only_its_own_households_records_for_the_page` -
  after one pass, a Sort's page calls `load_manifest` and `read_index` only
  for the returns of the household it ran.
- `test_a_dry_run_and_a_page_with_no_data_home_keep_nothing`.
- `test_the_held_read_and_the_page_use_one_token` (`test_store.py`) and
  `test_the_tokens_of_every_record_are_one_statement`.
- `test_only_the_practice_page_reads_the_store_without_following_the_journal`
  (`test_runner.py:4383`) still passes unchanged: no new `follow=False`
  caller.

**Docs.** `docs/runbook.md:31` names `page-rows.json` beside
`firm-view.json` (what it holds, never synced, safe to delete);
`docs/repo-map.curated.json` gains the module's node and the artifact; the
layer table in `tests/test_layers.py` puts `page_rows` in L0 with a
comment, as P120 did for `firm_cache`.

### P228 - After a Sort, the return and the Overview are asked at once, beside the list (findings-3 #9 revisited)

**What is slow.** `passEnded` (`app.js:2335`) awaits `list` (2.5-3 s)
before it asks the shown return's `state`, and the list's adoption is
what starts the Overview's `firm` (`shellAdopt`, `shell.js:201`). Neither
reply needs the list: `state` carries its own household and paths
(decision 194), and `firm` walks the tree itself.

**The change** (Lane R, `app/renderer/app.js`, `app/renderer/shell.js`):
- `passEnded` calls `shellWriteLanded()` (as now), then
  `shellAskFirmEarly()` - P221's early ask, whose pending reply the next
  `shellLoadFirm` adopts instead of sending another, so the list's own
  `shellAdopt` starts no second `firm`; then sends `state` (when the view
  is unchanged) and `list` at once, and draws each as it lands: the state
  behind the view generation, as now; the list adopted whenever it lands.
- The Sort's answer (`keepSortAnswer`) still waits for the state, as now.
- `shellAskFirmEarly` is renamed `shellAskFirmNow` (it is no longer only
  early) and keeps P218's rule: when a load sent before the write is still
  running it sends nothing, and the list's adopt queues one more, as today.

**Nothing is skipped.** The list is asked after every Sort, as 194's Q5
and decision 203 say; it is only no longer waited for. So this needs no
proof that a Sort changes nothing the list carries - and it takes most of
what skipping would have given (section 7, Q2).

**Gain.** The sorted return's new rows about 2.4-2.6 s sooner (9.1-9.5 →
6.7-7.1 s today; about 2.9 s with P225-P227); the fresh Overview about 3.5
s sooner (13.9-14.4 → 10.1-10.5; 6.1-6.3 with P225-P227). One more process
runs at once at the end of a Sort (three instead of two); the warm spare
(P220) takes one of them.

**Tests** (`tests/test_shell.py`, the `run_firm_load` harness):
- `test_after_a_sort_the_return_and_the_overview_are_asked_beside_the_list`
  - `state`, `list` and `firm` all sent before any lands.
- `test_after_a_sort_one_overview_is_asked_not_two` (P218's, kept): the
  list landing after the early `firm` asks none.
- `test_a_sorts_list_that_lands_last_changes_nothing_the_state_drew`.
- `test_a_return_chosen_during_the_sort_is_the_one_drawn` (the view
  generation, with the state now sent first).
- `tests/test_api.py::test_sort_and_scan_ends_with_one_list_then_one_state`
  (`:7572`) is renamed `test_sort_and_scan_ends_with_one_list_and_one_state`
  and its docstring updated; it still counts the pass's walk and the one
  list.

**Docs.** `docs/ROADMAP.md` is not edited (main's log); the runbook's
paragraph on what the window does after a Sort, if it says "then", is
corrected; `pilot/SPEC-speed-round.md` section 8's closing sentence stays
as history.

### P229 - At launch, the Overview shows the counts it last had today, marked, until the fresh ones land (findings-4 #9) - **needs Jason's ruling (Q3)**

**What is slow.** At launch the Overview waits for a whole `firm`: 3.6 s
here beside the list (5.3-5.6 s alone), most of it the households'
fingerprints (3.8-4.1 s of a warm 5.1 s). The answer it will most likely
give is already on disk: `firm-view.json`, today's, under this program.

**The change, if Jason agrees.**
- **API** (`tracker/api.py`): a new read-only command, `firm-last`, on
  `COMMANDS` and `HELD_READING_COMMANDS`: the `firm` reply built from the
  kept households **without taking any fingerprint and without reading
  any record**, plus `"as_of"`: the time the cache file was last written,
  said by the API in the app's time words. It answers `{"last": null}` -
  and the window shows today's wait - whenever any of these fails:
  1. the file's head is **today's head** (`firm_cache.head`): the same
     program stamp (never after an upgrade or any code change), the same
     clients root, the same data home, the same day and the same settings
     file;
  2. **every** household the walk's positions list
     (`registry.household_positions`, 0.01 s) has a kept entry, and the
     file keeps no household that is not there - no partial practice, no
     partial totals (findings-4's own "do not build");
  3. no kept household has a problem (`_firm_keepable` already refuses
     those).
  It writes nothing: no cache save, no log line but a refusal's class.
  `"as_of"` is the file's last write, which is when those rows were last
  **changed**; they were confirmed by every reply since, so the time shown
  is never later than the truth.
- **Shell** (`app/main.js`): `firm-last` joins `EARLY_COMMANDS` and
  `HELD_READING_COMMANDS` (pinned to the API by
  `tests/test_single_source.py`), never a writing command.
- **Renderer** (`app/renderer/shell.js`): at bootstrap, beside P221's
  `list` and `firm`, it asks `firm-last`. When it lands before the real
  `firm`, the firm pages draw it under P222's "Updating" marker - `#page`
  `aria-busy`, figures, pills and side counts muted - with the time:
  the new `api.SCREEN` word `updating_as_of`, proposed **"Updating, as of
  {time}"** (wording for Jason, P84). When the real `firm` lands it
  replaces it in place, as W1's refresh does. If the real one lands first,
  `firm-last`'s reply is dropped. If the real one **fails**, the last
  counts are taken down and the failure is shown with Retry, as today:
  held counts never outlive a failed refresh. A list that asks for a
  folder drops both, as P221 does.
- **What each action does while marked.** Exactly what it does during
  W1's "Updating" today: rows stay usable; **Open** reads the return's
  `state` afresh; **Check** opens the check sheet on a fresh `state`, and
  a file no longer waiting is not offered; the reminder sheet's **Copy**
  and **Approve** act only on a card drawn from the return's own fresh
  read (P213's `reminderCardReady`); every write is judged under the
  household's lock against the record (decision 193, the list head), so a
  marked count can never make a write land wrong. The totals and the
  urgency order are the marked counts' until replaced.

**What it loosens.** P120's rule, for the seconds between the launch and
the fresh reply: a count shown may be as old as the last time today any
reply or the scheduled pass's fill changed the file (up to about two hours
on a quiet day), marked as such. It never shows another day's, another
program's or another root's counts.

**Gain.** The Overview drawn about 1.2 s after the engine starts (0.6 s
with P225), against 3.6 s here beside the list, 5.3-5.6 s alone; the fresh
counts land no later than today. On the office PC the gain is the warm
`firm`'s whole time there less about 1.5 s (measure, section 6).

**Tests** (if ruled yes): `tests/test_api.py` -
`test_the_last_counts_are_the_firm_reply_when_nothing_changed`,
`test_no_last_counts_after_a_program_change_another_root_or_another_day`,
`test_no_last_counts_while_any_household_is_not_kept`,
`test_the_last_counts_read_no_record_and_take_no_fingerprint`,
`test_the_last_counts_write_nothing`;
`tests/test_shell.py` -
`test_the_last_counts_are_drawn_marked_updating_as_of_their_time`,
`test_the_fresh_counts_replace_the_last_in_place`,
`test_last_counts_that_land_after_the_fresh_are_dropped`,
`test_a_failed_refresh_takes_the_last_counts_down`;
`tests/test_single_source.py` - the early and held command lists;
a `pilot/wording-shell.tsv` row for the word.

### P230 - Measured and not built

Section 4.

## 4. Not built, and why

| Item | Why |
|---|---|
| Skipping the list after a Sort (findings-3 #9) | **Still held; recommended no** (Q2). The proof, for the record: by the code, a one-household pass writes journal lines into return records (filed, parked, moving, released, scanned, drafted), folders inside its own client folder and its return folders (`scaffold_household` makes only its own client folder, inbox and year folders, through the door), the README and the Status Reports - and the list carries none of these: its `returns` are the records' details (written only by `create`, `rollover`, `edit` - `LIST_CHANGING`), its `households` the household records (written only by `edit-household`), its `misfits` the top-level folders of the two trees. A Sort that parked 7 files on the copy left the list byte-identical (2,438,442 bytes). **Residual risk:** the list after a Sort is also the window's only refresh, between F5s, of what *others* changed - another machine's synced household, a folder renamed in Explorer, a scheduled pass's `last_pass` line, the time-based amber of that line, the machine and reader warnings, the after-install notice - and of a record a failing write left unreadable. Skipping it would show those late; after P228 nobody waits for the list, so skipping would save only background work. |
| A one-household `list` patched into the held list | 194's R5: two folders claiming one household, the walk's order and the households' links are practice-wide facts; a spliced list can disagree with the walk. |
| The page written after the final line | P227's option (c): the page would land seconds after the answer, a failure could not be said in the final line, and decision 203's end-on-close contract would change. |
| The drawn page rows kept | 0.06 s of the page. |
| The page's rows kept in a store table | A schema step for what a disposable file does; P224 holds schema changes for the next step. |
| A Sort following only its own household's journals in discovery | The page and the feeds read every household's record as its journal stands (decision 192); a record another machine extended would show the store's older rows. |
| `records_needing_a_person` once a pass instead of twice (0.15 s) | The page names the copies and lock markers as they are when it is drawn; a breaker marker's age changes during a pass. |
| Discovery's other 1.6 s | Every record's journal is followed by design (decision 192); P215 already holds its machine questions. |

## 5. Build lanes

Two worktrees, no file in common; the same gate as the speed round.

### 5.1 Lane P - Python (P225, P226, P227; P229's API half if ruled)

`tracker/registry.py` (P225), `tracker/runner.py` (P226, P227),
`tracker/store.py` (`read_token`, `read_tokens`, `record_key`;
`held_read` and `_engagement_row` call them), new `tracker/page_rows.py`,
`tests/test_registry.py`, `tests/test_runner.py`, `tests/test_store.py`,
new `tests/test_page_rows.py`, `tests/test_layers.py` (the L0 entry),
`docs/runbook.md`, `docs/repo-map.curated.json` (then `repo_map.py
update`). If Q3 is yes: `tracker/api.py` (`firm-last`, the word),
`tests/test_api.py`, `pilot/wording-shell.tsv`.

### 5.2 Lane R - the app (P228; P229's window half if ruled)

`app/renderer/app.js` (`passEnded`), `app/renderer/shell.js`
(`shellAskFirmNow`), `tests/test_shell.py`; `tests/test_api.py`'s one
renamed test (Lane R owns that line; Lane P touches `test_api.py` only if
Q3 is yes, and then rebases on Lane R). If Q3 is yes: `app/main.js`,
`tests/test_single_source.py`.

### 5.3 The gate

As CLAUDE.md's minimal-testing rule and decision 207 say: first
`python -m ruff check .` and dead code deleted in the changed files; then
the tests, each file its own process, in parallel, under **both**
interpreters:

```
PY311=/tmp/claude-0/-home-user-Tax-Info-Request-List-Pilot/6549e888-04ab-55c6-9702-4474437cf354/scratchpad/venv311/bin/python
PY313=python3
```

then `python -m ruff check .`, `python tools/repo_map.py update` and
`python tools/repo_map.py check` (exit 0).

- **Lane P runs the whole suite**: it reaches the engine (`store`,
  `registry`), whose importers are nearly every module - Jason's rule for
  the whole suite (2026-09-29). For each interpreter:
  `ls tests/test_*.py | xargs -P 4 -I{} sh -c '$PY -m pytest -q "{}" > "$OUT/$(basename {}).log" 2>&1; echo "$? {}"'`,
  every line starting `0`. No routing word, typed case or matcher
  changes: `tools/vocab_report.py` and the backtest baseline are untouched.
- **Lane R runs** `tests/test_shell.py` (P228's tests),
  `tests/test_api.py` (the renamed test, and the `main.js` harness tests
  `test_shell.py` borrows), `tests/test_single_source.py` (its pins on
  `main.js` and the renderer), `tests/test_shell_menu.py` and
  `tests/test_pilot_ui.py` (they read `shell.js`), and the guards
  `tests/test_layers.py`, `tests/test_repo_map.py`, `tests/test_tripwire.py`
  (tests change) - each as its own process, both interpreters.
- After review fixes, only the tests the fix touches run again.
- **Windows** (the `windows` label): not needed for P225, P226 and P228;
  P227 writes a new file atomically in the data home, so the Windows check
  runs `tests/test_page_rows.py` and `tests/test_runner.py` with
  `pilot\wintest\run_checks.ps1 -Tests tests\test_page_rows.py,tests\test_runner.py`
  and one hands-on Sort & Scan timed before and after on the office PC's
  copy (section 6).

## 6. How to measure after

Made-up firms only, never a client's document. The shared firms under
`scratchpad/scale/t1k*` are copied, never written.

1. **A private copy of the 1,000-household firm**, as this SPEC made
   it: `cp -a scale/t1k-y2-unsorted <scratch>/after`, its
   `settings.json` naming `<scratch>/after/root`,
   `python -m tracker.checkpoint "<scratch>/after/data" move-root "<scratch>/after/root"`,
   `TRACKER_SETTINGS_DIR` and `TRACKER_DATA_HOME` set, one first pass
   (`python -m tracker.runner --settings <scratch>/after/settings --reminders never`,
   about 11 min). Then one scheduled pass more, so the kept rows are
   filled. Delete the copy when done.
2. **The click** - `python -m tracker.api run-now --engagement "<root>/J Park & Associates/Smith 0500 Family/2026/1040 - John A. Smith"`,
   3 runs, wall time (target about 3 s against 6-7), and once split with
   `scratchpad/sortspeed/tools/phases.py` (no prototype argument): the
   discovery about 1.6 s, the report about 0.3 s, the page's parked rows
   about 0.05 s.
3. **The page is the same**: the `status.html` of a Sort before and
   after the build on two copies, the `Generated` and `Last pass` stamps
   aside, byte-equal; and `equiv_page.py`'s check on the built code
   (fresh reads against kept rows).
4. **The window's wait**: the sequence of section 1.2 (sort, then state,
   list and firm as the window now asks them), 3 runs: the return page
   at about 3 s, the Overview at about 6 s.
5. **The other replies**: `list` 3 times (target about 1.7-2.0 s against
   2.5-3.0, reply byte-identical), `firm` warm 3 times (about 0.7 s less).
6. **On the office PC** (Windows check): one Sort & Scan on its copy,
   timed by hand before and after, and the launch-to-Overview time; the
   office's own root, if it never moved, gains nothing from P225 - say so
   with the number.

## 7. Questions for Jason

Plain words; each with a recommendation. P225 and P226 need no ruling
(the same work fewer times, the same answer), as the speed round's safe
items did.

**Q1 - The status page after Sort & Scan (P227).** Today every Sort &
Scan rebuilds the firm-wide status page by re-reading all 2,000 returns,
though it only touched one household - that is half the wait on the
button. May the program keep, on this computer only, a private note of
each return's line on that page, and reuse a line only when the return's
record is provably unchanged since (each record carries a fingerprint of
its own history, and any change - a filing, a scan, a status - changes
it)? The note is thrown away every day and after every program update,
and the page is still rebuilt in full, at once, exactly as the schedule
builds it (your decision 203). Tested to give the same page, byte for
byte. **Recommendation: yes.** About 2 seconds off every Sort; with the
two rulings-free fixes (P225, P226), the button answers in about 2.6 s
instead of about 6.

**Q2 - The client list after a Sort (P228, and the held item).** After a
Sort the app now waits for the whole client list (about 3 s) before it
re-shows the return you sorted and before it starts the Overview.
(a) May it ask for the return, the Overview and the client list all at
once? Nothing is skipped; the sorted return shows its new rows about
2.5 s sooner and the Overview about 3.5 s sooner. **Recommendation: yes.**
(b) Should it skip the client list after a Sort altogether? I checked:
a Sort itself cannot change anything the list shows, and a test Sort left
it identical. But the list after a Sort is also how the app notices what
*others* changed meanwhile - a household added on another computer, a
folder renamed by hand, the scheduled run's last result - and after (a)
nobody waits for it anyway. **Recommendation: no - keep asking for it.**

**Q3 - Showing this morning's counts at start-up (P229, held on
2026-10-08).** When the app opens, the Overview is blank for a few seconds
(about 3.6 s here, more on the office PC) while it re-checks every
household. May it show the counts it last had **today**, greyed and
labeled "Updating, as of 9:14", and swap in the fresh counts the moment
they arrive? Safeguards: never yesterday's, never after a program update,
never for another clients folder, never a partial list; if the re-check
fails, the old counts are taken down; and every button (open a return,
Check, Copy, Approve, every change) reads the return fresh, so nothing can
be done on an old number. The cost: for those few seconds a count can be
up to about two hours old, marked as such - a loosening of your rule that
a saved answer may never show a wrong status. **Recommendation: yes, but
last and conditionally** - build it after Q1 and Q2 and only if the
office PC's start-up Overview still takes more than about 3 s; it is the
only item here that shows a number before it is proved. If yes, please
also approve the words "Updating, as of {time}".

### 7.1 Jason's answers (2026-10-08)

- **Q1 (P227): yes** - "Yes, build it."
- **Q2(a) (P228): yes** - "Yes, ask all at once."
- **Q2(b): no** - the client list after a Sort stays; held.
- **Q3 (P229): yes, build it now** - not after the office timing. The
  words "Updating, as of {time}" are approved with it. Built in this round,
  in both lanes (5.1, 5.2), with every safeguard P229 names.

## 8. Measured before and after

To be filled at merge, by section 6 on a fresh copy, beside the figures
of section 1.
