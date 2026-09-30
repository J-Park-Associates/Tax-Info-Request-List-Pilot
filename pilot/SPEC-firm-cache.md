# Pilot 0.3 - the firm view's cache and a faster repository - SPEC

Status: **written before the build** (2026-09-29, 23:52 PDT), lane 1 of
Pilot 0.3 (P140). Decision P115 asked for it (Jason, 2026-09-29: "build a
cache, optimize the repo for speed ... see if any other components could
use a cache to improve efficiency"). New decision rows: **P118-P123**
([`DECISIONS.md`](DECISIONS.md)). Built in the same worktree
(`claude/firm-cache`); the hand-back is
[`handoffs/firm-cache-build.md`](handoffs/firm-cache-build.md).

The one rule above every ruling here: **a cache may never make a status
wrong.** The standing rules (`STANDING_RULES`, `tracker/__init__.py`)
outrank speed. Nothing here reads a document, changes a routing rule, a
catalog word or the matcher, so the backtest baseline cannot move.

## 1. What was measured, and where the time goes

All on the office PC (Windows 11, Python 3.14, the worktree's `.venv`), on
`%USERPROFILE%\PilotTest\Clients-750`: the Windows check's copy of one
sorted sample household (made-up data) to 750 households, both trees; 6,003
folders and 22,500 files. `TRACKER_SETTINGS_DIR` names
`PilotTest\settings-750`. No document was opened or read by anyone; only
the engine ran on it.

| Command, 750 returns | Time |
|---|---|
| `firm`, Windows check (F1) | 131.2 s first run, 53.8 s warm |
| `firm`, this session, warm, twice | 52.2 s, 53.3 s (reply 2,343,016 bytes) |
| `list` (the app's first call), warm | 28.5 s |
| `state` for one return, warm | 1.5-1.8 s |
| `import tracker.api` alone | 0.81-0.88 s |

**The profile** (`cProfile`, standard library; one in-process run of
`firm`, 70.2 s under the profiler) says the time is not the reading of
records. It is the same few questions asked thousands of times:

| Where | Calls | Time (profiled) | Why |
|---|---|---|---|
| `settings.data_home()` | 6,752 | 35.4 s | every `store.connect()` asks where the data folder is; each answer re-proves it is not inside the program (`_inside` walks each folder's parents with `os.path.samefile`: 108,059 calls, 216,118 `stat`s) |
| `store.key_root()` / `_recorded_root_over()` | 14,250 | 14.3 s | every store read re-reads `settings.json` (14,254 reads) and resolves the clients root and the return folder (`Path.resolve`, 66,009 calls, 132,026 `_getfinalpathname`) |
| `registry.discover_engagements` | 1 | 26.8 s | mostly the two rows above, from inside `household_from` / `engagement_from`; plus `names_one_folder` 281,625 times (every client folder against every household: quadratic) and `_two_claims` (every household against every other) |
| `_firm_row` x 750 | 750 | 41.7 s | the same `data_home` / `key_root` questions from its readers |
| `_firm_key` | 3,000 | 0.8 s | a key shared by every return (`shown_copy 3`) is suffixed ` #2`, ` #3`... by trying every earlier suffix: quadratic |

A `stat` costs about 0.1 ms on this PC (221,571 of them took 22.1 s), which
is why the repeats hurt far more here than on Linux (the S8a review's
sandbox measured 6.7 s for the same command).

**What each fix is worth**, measured with scratch scripts that wrapped the
functions at run time (no repository code changed for the measurement):

| Change | `firm`, warm |
|---|---|
| none | 52.2-53.3 s |
| the answers to "where is the data folder" and "what does `settings.json` say" held for the one reply | 26.4 s |
| ... and each path resolved once per reply | 9.0 s |
| of which: import 0.9-1.2 s, discovery 2.4-3.2 s, the 750 rows 3.7-4.5 s | |
| a stat-only walk of both trees (every folder listed, every entry's size and time, nothing opened) | 1.0-1.2 s |

**A cost the sample does not show.** After a Roll Forward season every new
return names the one it was rolled from, and `registry.mark_superseded`
resolves that path against every other return's path, each time from the
disk. A synthetic measurement (the sample's 750 real return folders as the
priors, 750 made-up next-year paths naming them; nothing read or written):
50 + 50 returns 0.60 s, 150 + 150 returns 7.03 s - quadratic, so about
three minutes at 750 + 750. Every pass, every `list` and every `firm` walks
the registry, so this would have been the next Windows check's finding.

So the 3 s budget (SPEC-shell 9.2) cannot be met by removing the repeats
alone (9 s; import plus discovery is already 3-4 s). It needs the repeats
gone **and** a cache that answers an unchanged household without reading
its records.

## 2. Rulings

### P118 - one reply asks each machine question once

A read-only API command (`firm`, `list`, `state`: `HELD_READING_COMMANDS`
in `tracker/api.py`) runs inside `settings.one_reading()`. Inside it:

- `settings.data_home()`, `settings.app_dir()` and
  `settings.program_folders()` are answered once and then from memory;
- `settings.json` is read once (`settings._read`; each caller gets its own
  copy of the dict, so none can change another's);
- `settings.resolved(path)` answers `Path.resolve()` once per spelling;
  the store's three resolvers (`_recorded_root_over`, `engagement_path`,
  `_positional_root`) ask it.

**Why this is safe.** A read-only command changes none of these: no
environment variable, no settings file, no folder rename of its own. The
answers are the ones the first question got, so the reply is as of one
moment, which it already was in practice. Outside `one_reading()` nothing
is held: `data_home()` keeps its documented rule "not cached, so an
override takes effect at once" for every writer, the pass and the tests.
An error is never held: a question that raised is asked again.

**Why an explicit list, not "every command not in `WRITING_COMMANDS`".**
Some commands outside that set still write (the pilot record, the after-
install jobs). A command joins the list only when it writes nothing;
`tests/test_api.py` pins that the list and `WRITING_COMMANDS` do not meet.

**Rejected:** caching `data_home()` for the whole process (the suite
changes the environment between calls in one process, and a writer must
see an override at once); passing the root and the store down every
signature (the store's own docstring says why it is module level).

### P119 - four quadratic loops become lookups, answers unchanged

Each keeps its exact answer, order and wording; each is pinned by a test
that compares it with the old rule on the same input.

1. **`registry.mark_superseded`**: every return's path is resolved once,
   into a map from resolved path to positions; a Rolled From is resolved
   once and looked up. The first position in walk order still wins, a path
   that cannot be resolved still matches nothing, and a problem return is
   still never a prior. The folder-name fallback compares precomputed
   names (`layout.tail_names`, `layout.common_tail`; `layout.shared_tail`
   is now those two, so the rule is still worded once).
2. **`registry.discover_engagements`**, the client-folder check: the
   households' names are put in a set by `layout.folder_name_key` (what
   `names_one_folder` compares: `os.path.normcase`), and each client folder
   is looked up once.
3. **`registry._two_claims`**: households that share a key are joined by a
   map from key to the first household holding it, instead of comparing
   every pair; each group is listed in walk order, as before, so the
   sentence names the same folders in the same order.
4. **`api._firm_key`**: the spellings already given for a key are kept by
   that key, so the next ` #n` is found without retrying every earlier one.
   A key that already contains ` #` (none does today) takes the old loop.

### P120 - the firm view's cache

**What it holds.** One file, `firm-view.json`, in the tracker's data folder
(`settings.data_home()`, decision 186) - never in either client tree,
never beside the program, never in a checkout. Per household folder of the
private tree it keeps:

- `fingerprint`: a digest of every folder and file under the household's
  private folder **and** under its client folder (`layout.client_household_dir(root,
  name)`, the folder that holds its inbox), each entry's name, kind, size and modification time, from
  one `os.scandir` listing per folder. Nothing is opened. On Windows the
  listing carries size and time itself, so this costs no `stat` per file;
- `kind` (`household`, `record_missing` or `none`) and the household's
  name, as the registry reads them;
- per return, the facts the practice-wide step needs - `path`, `problem`,
  the record's `active`, `tax_year` and `rolled_from` - and, when the
  return was shown, its whole firm row, its files and its paths **as
  generic JSON**, exactly as `_firm_row` built them.

And once for the whole file, a **head**: the cache's format (`1`), the
program's stamp (every `tracker/*.py` file's name, size and time on a
source install; the executable's on the packaged app; plus the Python
version), the clients root, the data folder, today's date and the
`settings.json` file's size and time.

**How it knows a return changed.** Everything a firm row reads is in one of
three places, and each is covered:

| What the row reads | Where it is | Covered by |
|---|---|---|
| the record (the journal) and the store rows built from it | the return's folder; the store is rebuilt from the journal by its head digest (`store.follow_the_journal`) | the household's fingerprint (the journal's size and time) |
| the index, the working copies' rows, the reminder draft and its approval | the return's folder | the household's fingerprint |
| the files still in the inbox (`reminder.unsorted_in_inbox`) | the household's client folder | the household's fingerprint |
| the household's record (its name, and P141's links when lane 4 adds them) | the household's private folder | the household's fingerprint |
| the draft week and the stage | today's date | the head |
| the clients root, the settings, the program | - | the head |
| whether a prior was rolled forward, whether a household has two open years | every household's facts | recomputed every time from the cached facts (below) |

A fingerprint is taken **before** anything is read, so a change that lands
while the row is being built makes the next fingerprint differ: the cache
can be one reply behind a change that is still being written, never more.
Equality is what is compared, not order, so a sync client that sets an
older modification time still changes the fingerprint (the size or the
time differs from the one kept).

**What is recomputed every time.** The practice-wide facts: which returns
a Roll Forward retired (`registry.mark_superseded`), which returns are
skipped (`runner.why_skipped`), which households have two open years
(`households.open_years`, ruling 21's `paused`), the firm-wide ` #n` key
spellings, the totals and `next_sort`. They are computed by the same
functions the registry uses, over light `Engagement` and `Household`
objects made from the cached facts, so one rule answers both paths.

**What is never cached.** A household any of whose returns has a problem
(`Could Not Be Read`, a stopped household's sentence, a record the store
refused): it is read fresh on every reply, so its detail reaches the error
log every time, as today. A household the walk found a link or junction in,
or could not list: read fresh every time. A return the practice-wide step
now shows but whose row was not kept (it was a retired prior until now):
its household is read fresh.

**How a changed household is read.** `registry.households_named(private,
names)` - the practice walk's own per-household walk and reading (decision
192) - for just the changed households, then `_firm_row` for each shown
return, exactly as today. The order of `returns[]` and `files[]` is the
registry's: households in the walk's order, returns in year and name
order, and the returns of households whose record is missing last.

**The reference path stays.** The whole reply as built today
(`_firm_fresh`, which is today's `_cmd_firm` body) is kept, and it is what
answers whenever the fast path is unsure: the private tree cannot be found
by the layout's own test or there are two, the private tree cannot be
listed, `households_named` raises, or anything unexpected happens while the
cache is read. `tests/test_api.py` compares the fast reply with the fresh
one, field for field, over a practice built to hold every case above.

**Missing, damaged, or from another program.** Missing: every household is
read fresh and the file is written. Not JSON, the wrong shape, another
format, another program's stamp, another root or another day: said once on
the error log (`log.warning`, its class only - the file names clients),
then treated as missing and replaced. A cache that cannot be written (a
full disk, a lock held by another reader): said on the error log; the
reply is still answered, since the cache only makes the next reply faster.
Writes are atomic (`fsio.write_text_atomically`); two replies racing each
write a whole file whose every entry is true for its fingerprint.

**New fields from another lane (P141).** Rows are kept as the JSON
`_firm_row` returned, so a field lane 4 adds to a row flows through with no
change here. A code change always changes the program's stamp, so the
first reply after any upgrade rebuilds the cache with the new fields. The
format number changes only when this file's own shape changes (the head,
the per-household keys, the per-return facts), and `FORMAT` is the one
constant that says it.

**What the screen shows while it fills.** Nothing new. The first Overview
after an upgrade, a new day or a sort that touched many households reads
those households fresh (about 9 s for all 750 on this PC after P118 and
P119, instead of 53-131 s), and meanwhile every firm page shows the loading
state it already has (`shellLoading` in `app/renderer/shell.js`: the
title, then outline rows). No new words, no shell change.

**Racily clean.** A file rewritten twice within one tick of the disk's
clock, at the same size, would keep its fingerprint. So a household with
any entry modified within `RACY_SECONDS` (5 s) of the fingerprint, or dated
in the future by a clock ahead of this one, is read fresh and not kept until
it has been still that long (the rule `git` uses for the same case).

**What `firm` writes.** SPEC-shell 9.2 said `firm` writes nothing. It now
writes this one file in the data folder, and only when what is kept
changed: an unchanged practice writes nothing at all. It still writes
nothing in either client tree, takes no lock and reads no document.
`tests/test_api.py::test_firm_is_read_only` now excepts that one file and
nothing else.

**Known limits.** (1) A store damaged while its journals stay the same is
not seen by a kept household's row until that household changes; the
return's own page, the pass and `verify` still see it at once, and the
status the row shows is still the journal's. (2) Every file under a
household counts, so a pass that rewrites a return's `Status Report.html`
makes that household read again on the next Overview; after a scheduled
pass that touched every household, the first Overview is a fill (about
9-11 s at 750 on this PC). Filling the cache at the end of the scheduled
pass would hide that, but the runner may not import the API
(`tests/test_layers.py`); it is named in the hand-back, not built. The
sample could not show which files a pass rewrites: its 750 copies all
claim one household name, so the pass stops every one of them.

**Rejected:** one digest over the whole practice (any drop into any inbox
would make the next Overview read all 750 households); watching the folders
for changes (a watcher must run all the time and misses changes made while
it is not running, which is exactly when the scheduled pass writes); keying
on folder modification times alone (Windows changes a folder's time when an
entry is added or removed, not when a file inside is rewritten); keeping
the cache in the return folders (decision 186: client-derived data never
sits in a synced client tree); caching the registry's own objects with
`pickle` (loading a pickle runs code, and the objects change shape when
another lane adds a field).

### P121 - the other components: build, or not

| Component | Measured | Ruling |
|---|---|---|
| `list` (the app's first call; the Clients page) | 28.5 s at 750 | **Build P118 and P119 for it** (it is in `HELD_READING_COMMANDS`; P119's registry fixes are its own). No cache of its own now: its payload is the registry's, and after P118/P119 it is measured in the hand-back. If it is still over 3 s, it is the next SPEC, with the same fingerprints. |
| `state` (one return's page) | 1.5-1.8 s | **P118 only.** One return; a cache would save a few hundred milliseconds and add a second place a status could go stale. |
| The pass (`runner`) | not run on the sample: a pass moves files, and this lane does not change the sample | **P119 applies to it for free** (its registry walk). No cache: the pass is the writer, and a cache in the writer's path is how a status goes wrong. P118 is not applied to the pass: it writes the store, the checkpoint and the run log, and holding the data folder's answer across a pass is not proven safe. |
| The reader (OCR, `content_check`) | not in `firm`'s path | **Do not build.** It reads documents; the store already keeps what it learned, and the first standing rule is best served by touching that path least. |
| Reminder drafts | 0.8 s of 70 s profiled (`unsorted_in_inbox`, `last_drafted`) | **Do not build** beyond P120, which already keeps each draft's state per household. |
| `import tracker.api` | 0.81-0.88 s per command, `pypdf` 0.20 s of it | **Do not build now.** Moving the PDF library's import into the functions that read PDFs touches `validators`, the reader's gate, for 0.2 s; not worth the risk in this lane. Named in the hand-back as a candidate. |

### P122 - the repository faster

No change to the tests in this lane; see section 4.

### P123 - the owner question

The cache keeps client names in the data folder; see section 6.

## 3. Files, functions and owning tests

| File | What changes | Owning test file |
|---|---|---|
| `tracker/settings.py` | `one_reading()`, `resolved()`, `_held()`; `data_home`, `app_dir`, `program_folders`, `_read` answered once inside a reading | `tests/test_settings.py` |
| `tracker/store.py` | `_recorded_root_over`, `engagement_path`, `_positional_root` resolve through `settings.resolved` | `tests/test_store.py` |
| `tracker/layout.py` | `tail_names`, `common_tail` (and `shared_tail` as the two), `folder_name_key` (and `names_one_folder` as it) | `tests/test_layout.py` |
| `tracker/registry.py` | `mark_superseded` resolves once; the client-folder set; `_two_claims` by key; `household_positions(root)` for the fast path | `tests/test_registry.py` |
| `tracker/firm_cache.py` (new, layer 0) | the file: `FORMAT`, `program_stamp`, `fingerprint`, `load`, `save`, `head` | `tests/test_firm_cache.py` (new) |
| `tracker/api.py` | `HELD_READING_COMMANDS` and `main()`; `_cmd_firm` = the fast path with `_firm_fresh` as reference and fallback; `_firm_key` | `tests/test_api.py` |
| `tests/test_layers.py` | `firm_cache` in layer 0 | itself |
| `tests/test_store.py` | `ADMISSION_PIN[2]` re-pinned: the admission reaches `settings._read` and the store's resolvers, whose source changed and which refuse nothing new (the test's own instruction for that case) | itself |
| `tests/test_api.py::test_firm_is_read_only` | excepts `firm-view.json` in the data folder, and nothing else | itself |
| `docs/repo-map.curated.json`, then `tools/repo_map.py update` | the new module's purpose and artifact; `api`'s new artifact | `tests/test_repo_map.py` |
| `docs/runbook.md` | the data folder paragraph names `firm-view.json` | `tests/test_single_source.py` |

The SPEC's tests: `tests/test_firm_cache.py`, `tests/test_api.py`,
`tests/test_settings.py`, `tests/test_store.py`, `tests/test_layout.py`,
`tests/test_registry.py`, and the guards `tests/test_layers.py`,
`tests/test_single_source.py`, `tests/test_repo_map.py`, plus
`tests/test_errors.py` (new log wording), on the 3.14 and 3.11
interpreters.

## 3a. Measured after the build

Same PC, same sample, the worktree's `.venv` (3.14). The measurements
before were taken with `PYTHONDONTWRITEBYTECODE=1` set in the agent's shell,
which makes Python compile the program on every start (about 0.85 s); the
installed app and a normal source install keep the compiled files, so the
after-figures are with it unset. Every reply below is byte-identical to the
old code's reply (2,343,016 bytes).

| `firm`, 750 returns | Before | After |
|---|---|---|
| warm, cache kept | 52.2-53.8 s | 1.85-2.33 s |
| cache empty (first reply of a day, after an upgrade) | 131 s first run, 53 s warm | 9.3-11.2 s |
| one household changed | - | 2.8 s |
| 75 households changed | - | 4.3 s |
| P118 and P119 only, no cache | - | 7.6 s |
| `list` | 28.5 s | 3.3-4.9 s |
| Roll Forward season, 750 + 750 (synthetic) | about 175 s (7.0 s at 150 + 150) | 0.93 s |

The cold figure of 131 s was the first run after the sample was copied; a
cold disk cache cannot be reproduced here without a restart, so the "cache
empty" row is warm-disk.

## 4. The repository faster (P122)

Measured on this PC before any change (two files at once, so each is slower
than alone; the Windows check measured them alone at 598 s and 268 s):

| File | Tests | Time | Slowest test |
|---|---|---|---|
| `tests/test_api.py` | 407 | 1,049 s | spread evenly; no test over a few seconds dominates |
| `tests/test_runner.py` | 194 | 339 s | 7.6 s (`test_every_failure_and_skip_is_logged_as_a_code`); the top 40 are all 2.4-7.6 s |

A profile of the slowest runner test (21 s under the profiler) says where a
test's time goes: SQLite statements 3.7 s, deleting files 2.8 s, opening
files 2.7 s (creating a file costs about 17 ms here: each new file is
scanned when it is opened), resolving paths 1.3 s, listing folders 1.3 s.
It is the disk work each test's own fixture does - a real store, real
records, real folders, made and removed per test - and not a question a
cache could answer: `data_home()` is not even on the list, since the suite
names its data folder in the environment.

**Ruling: no change to the tests in this lane.** What was weighed:

- *Run the files in parallel.* Already done by `pilot/wintest/run_checks.ps1`
  and the daily landing; the wall time is then the longest file,
  `test_api.py`. Splitting it into four files by subject would cut that to
  about a quarter and keeps every assertion, but every lane of 0.3 edits
  `test_api.py`, so moving its tests now would conflict with all of them at
  the landing. **Proposed for after 0.3 lands**, as its own SPEC.
- *Share one practice between tests.* Would change what each test proves
  (a test would see another's rows). Rejected.
- *A faster disk for the suite's temporary folders* (a Windows Dev Drive,
  or leaving the temporary folder out of the virus scan) would help most,
  but it is a change to the PC's security settings, which is a person's
  decision and not this lane's. Named in the hand-back.
- P118 and P119 already make every `firm`, `list` and `state` a test runs
  cheaper; the after-times are in the hand-back.

## 5. What staff will notice

- Overview (and every firm page) opens in about 2 s on the office PC at 750
  returns once the day's first reply has filled the cache, instead of about
  a minute.
- The first firm page of a day, after an upgrade, or after a sort that
  touched many households, still shows the loading outline for a few
  seconds while the changed households are read.
- The Clients page (`list`) opens several times faster.
- Nothing else: no new words, buttons, settings or files in any client
  folder. Deleting `firm-view.json` is always safe; the next Overview
  rebuilds it.

## 6. Open for Jason

**Q1 (client data): the cache keeps client names in the data folder.**
Like `tracker.db`, `firm-view.json` holds household names, return folder
paths and the names of files waiting for a person, in this Windows
account's private data folder on the office PC (never synced, never in a
client folder).
- **(a) Recommended:** allow it, as for `tracker.db` (decision 186).
- (b) Keep only counts in the cache; names are read fresh each time (the
  page would take about 9 s again, since the names are most of the work).

Built meanwhile: (a).

## 7. What this makes true in the docs

- `docs/runbook.md`, the data folder paragraph: `firm-view.json` sits
  beside `tracker.db`, holds the Overview's last answer per household, is
  never synced, and is safe to delete (the next Overview rebuilds it).
- `docs/repo-map.curated.json`: `tracker/firm_cache.py`'s purpose and its
  artifact; `tracker/api.py` reads and writes `firm-view.json`.
- No README, build-script or installer line changes: the file is made on
  first use in a folder the installer already provides.
