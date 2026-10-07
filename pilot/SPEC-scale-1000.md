# Pilot 0.3 - 1,000 households a year: what is slow, and what holds or skips - SPEC

Status: **written and built in one session** (2026-10-07), branch
`claude/cool-brahmagupta-a45s9n` from `f9acc0d`. Jason, 2026-10-07: "what
components are slow? lets create caches for each component that could
benefit down the line. this software should be able to scale to 1000
households per year", then "write the SPEC when the timings finish and
build the spec in this session. no handoff is needed." New decision rows:
**P207-P211** ([`DECISIONS.md`](DECISIONS.md)). The review is a separate
agent that did not build it (section 7).

The rule above every ruling here is P120's: **a cache may never make a
status wrong.** Nothing here reads a document, changes a routing rule, a
catalog word or the matcher, so the backtest baseline cannot move. Every
change below either holds an answer only while nothing can change it, or
skips work only when the result would be byte for byte the same.

## 1. How it was measured

In the cloud sandbox (Linux, 4 cores, Python 3.13), never on a client's
document: a made-up firm built by the suite's own sample builder
(`tests/samples.py`) - **1,000 households, each one 1040 return and the
same 13-file pile in its inbox** (15,000 files; every household named
`Smith NNNN Family`, so none claims another's name, which is why the
Windows check's 750 copies could not time a pass). Then a second year:
every household rolled to 2026 and a fresh 2026 pile dropped in, so 2,000
returns. Each command ran as the app runs it (`python -m tracker.api ...`,
`python -m tracker.runner --settings ...`), and the profiles are
`cProfile` (standard library). The "before" figures are the code at
`f9acc0d`, run from a clean worktree of it; the "after" figures are this
branch, on the same firm in the same state, run straight after.

**What Linux hides.** A question to the disk (`stat`, `lstat`) costs about
0.1 ms on the office PC (SPEC-firm-cache section 1: 221,571 of them took
22.1 s) and a few microseconds here. The same `firm` command took 6.7 s in
an earlier sandbox and 53.8 s on the office PC. So a count of disk
questions is the figure that carries to Windows; the seconds below are
this sandbox's.

## 2. Where the time goes at 1,000 households (before)

| Component | 1,000 returns (1 year) | Disk questions | What it is |
|---|---|---|---|
| The first pass of a season (every inbox full) | 760 s under the profiler | 11.1 million | reading 11,000 new documents (266 s, the reader's child, the first standing rule's path - left alone), the store's durable writes (188 s, fsync - left alone), and **the same few machine questions asked again and again** |
| **A pass with nothing new** (most passes, every 2 hours) | **78.7 s** | **6.9 million** | about 40% of its time, and 91% of its disk questions, are repeats: where the data folder is (37,014 times, each re-proving it is not inside the program: 1.26 million `samefile` stats), what a return's folder resolves to (380,000 times: 5 million `lstat`s), what the settings file says (every store key) |
| A draft-day pass | 92.6-104.9 s | - | the same, plus the drafts |
| Every pass, every return's Status Report | 1,000 files rewritten | - | only its "Generated" time changed; Drive for desktop uploads each one |
| Roll Forward, one household | **7.5 s** (0.56 s at 20 households) | - | grows with the firm: `registry.held_back` walks the whole firm and reads every return's record to learn whether *this* household is stopped (3.6 s alone), then the reply's list walks it again |
| New Return, Edit, Edit Household, Accept Folder Name, Roll Forward | each reply carries the whole Clients list | - | the list is walked *outside* the held reading `list` itself uses |
| `firm` (Overview), warm | 4.3-4.5 s | 47,000 | the fingerprint walk reads every record's whole bytes (P120, ruled so) - 28.6 MB of records after one sorted year |
| `firm`, cache empty | 8.9 s | | |
| `list` (Clients) | 1.8 s | | inside P118's held reading already |
| `state` (one return) | 0.38 s | | |
| `import tracker.api` | 0.29 s | | |

A pass with nothing new does not grow the records (measured: the journals
were byte-identical after one), and a draft day adds a little to each. The
screens show 50 rows a page (`pagesPaged`, SPEC-lists 14), so drawing a
1,000-row list in the app is not a cost.

**Projection for the office PC.** The pass with nothing new asked the disk
6.9 million times; at 0.1 ms that is about 11.5 minutes of disk questions
alone, every 2 hours, before the second year adds its returns. The schedule
runs every 120 minutes by default and Task Scheduler stops a pass at 2 hours
(`locking.RUN_TIME_LIMIT_SECONDS`); a season's first full pass on Windows
(11.1 million questions, about 18.5 minutes of them, plus the reading) is
the one that would reach for that limit as the firm grows.

## 3. Rulings

### P207 - the pass holds the machine's answers for one household at a time

`settings.one_household()` is a second hold beside P118's `one_reading()`,
over the same answers - `data_home()`, `app_dir()`, `program_folders()`,
the settings file (`_read`) and `resolved(path)` - and the pass serves each
household inside one (`runner.run_registry`'s `serve()`), dropped before
the next.

**Why it is safe while the pass writes** - the doubt P121 left open ("holding
the data folder's answer across a pass is not proven safe"):

1. **The pass changes none of the answers.** It sets no environment variable
   once it has started (`main()` sets `ENV_SETTINGS_DIR` before anything
   reads settings), never writes the settings file (no function the pass
   calls reaches `settings._write`), and moves neither the program nor the
   data folder.
2. **A path is held only once it is there.** Inside a household's hold,
   `resolved(path)` keeps its answer only when `os.path.lexists` says the
   resolved path exists. A path resolves differently once it exists -
   Windows gives the folder's own case, a link is followed - and the pass
   makes folders (the scaffold), so a store key taken before a folder
   existed is never reused after it does. A reading keeps P118's rule
   (everything held), because a reading makes nothing.
3. **One household, then nothing held.** A person who saves the settings or
   renames a folder in the app between two households is seen by the next
   one. Within one household the pass holds that household's locks, which
   is what already keeps the app from changing its returns underneath it.
4. **A write to the settings file inside a household's hold is refused**
   (`settings._write`, `WRITE_WHILE_HOLDING`; the review's SHOULD-3). Every
   setter writes back what `_read()` handed it, which inside a hold is the
   copy held since the household began, so a save the app made meanwhile
   would be undone in silence. Nothing the pass runs reaches a setter; one
   that ever did fails loudly rather than losing a save.
5. **A household's hold never refuses a write.** `refuse_a_write_while_reading`
   refuses only inside a reading (`_HOLDING == HOLD_READING`). Nested holds
   are the outer one: a household inside a reading is still a reading and
   still refuses; a reading inside a household is the household's.
6. **An error is never held**, as in P118.

**Rejected:** holding for the whole pass (a person's change between
households would go unseen for up to two hours); holding inside
`run_household` itself (the suite and other callers call it directly; the
pass's own loop is the one place every household of a pass goes through,
Run now included, since decision 203 runs it through `run_registry`);
holding `content_check._key`'s own resolve (52,000 a pass, the reader's
path - left alone, as P121 left the reader).

### P208 - whether one household is stopped, without reading a return

`registry.held_back(household)` - the question every New Return and every
form of Roll Forward asks before writing - asked `discover_engagements(root)`
for its `stopped` map, and that walk read every return's record in the
firm. Whether a household is stopped depends on every *household* (two
folders claiming one household by their names and their records' names,
wherever they are) but never on a return.

`registry.stopped_households(root)` is that map from the same walk
(`_walk_root`) and the same two rules - `_households_kept` and `_stopped_of`,
split out of `_kept` and used by it, so there is one rule - without
`engagement_from` or `mark_superseded`, inside `settings.one_reading()`.
`held_back` asks it. A root that is not a folder raises `RegistryError` as
the walk does (`held_back` already answers that as nothing stopped); a root
holding nothing stops nothing, where the walk raised `EmptyRoot`, which
`held_back` answered the same way.

The test pins it as equal to `discover_engagements(root).stopped` on a firm
holding every kind of stop, and pins that no return is read.

### P209 - the list a write carries is one reading

`api._listing` - the Clients list each `LIST_CHANGING` reply carries
(decision 194) - runs inside `settings.one_reading()`. The write is done
before it is called (`_with_list` is the reply's last step), and what it
does is the `list` command's own read, which already runs inside one
(`HELD_READING_COMMANDS`), so the same code is proven under it. A write
inside it would now raise `WRITE_WHILE_READING` rather than answer from
held answers: loud, never stale.

### P210 - a Status Report that would say the same is not written again

`view.write_view` (every pass, every return) first draws the page at the
time the page on disk says it was generated (`_kept_stamp`, from
`read_stamp`); when that is the page on disk word for word (`_says`: read as
text, so a page written on Windows with CRLF line ends compares by what it
says), it writes nothing and returns `ViewResult.unchanged`. Otherwise it
draws and writes as before.

- **The status cannot go wrong.** The comparison is the whole page: any row,
  status, count, warning, date or name that would differ makes a different
  page, which is written. The record digest in the page is the head the
  readers read first (decision 152), so `view_state()` says `CURRENT` for a
  page left alone exactly when it would for one rewritten.
- **What changes for a person:** the page's "Generated" time is when the page
  last said something new, not when the last pass ran. The run's own "last
  looked at" is unchanged (the app's last-pass line and the practice page).
- **A caller that names `now`** asks for a page drawn at that time, and it is
  written (none does today but tests).
- A page that cannot be read, has no readable generated time, or was edited
  by hand is drawn again.

**Why not a cache file.** The page on disk *is* the cache: comparing with it
needs no second store of what a page said, and no second place a status
could go stale.

### P211 - what is measured and not built

1. **Overview (`firm`) warm, 4.3-4.5 s here at 1,000 returns.** The
   fingerprint reads every record's whole bytes, as P120's review ruled
   (MUST-R1: a restore that keeps a file's size and time still changes its
   bytes). It is linear in the records' total size, which grows with
   documents and years. Not changed here: the cheaper fingerprint (size,
   time and file id, without the bytes) is a ruling only Jason can reverse.
   **Open for Jason, Q1.** The office PC measured 1.2 s for 750 returns
   after the fold; the Windows check of this branch measures it again at
   1,000 (section 6).
2. **The reader's per-document child round trip** (24 ms a document, 266 s of
   a full season's first pass) and **the store's durable writes** (fsync per
   record, 188 s) - the first standing rule's path and the record's
   durability. Left alone, as P121 left them.
3. **A tool that builds the 1,000-household firm on Windows.** The
   generator used here is section 8; a Windows `make_samples`-style tool
   with its refusal rules is a SPEC of its own if Jason wants the Windows
   check to time the pass (**Q2**).

## 4. Files, functions and owning tests

| File | What changes | Owning test file |
|---|---|---|
| `tracker/settings.py` | `one_household()`, `_holding()`, `_HOLDING`, `HOLD_READING`, `HOLD_HOUSEHOLD`; `refuse_a_write_while_reading` refuses only a reading; `resolved` holds a household's path only once it exists; `_write` refuses inside a household's hold (`WRITE_WHILE_HOLDING`) | `tests/test_settings.py` |
| `tracker/runner.py` | `run_registry` serves each household (`serve()`) inside `one_household()` | `tests/test_runner.py` |
| `tracker/registry.py` | `stopped_households()`; `_households_kept()` and `_stopped_of()` out of `_kept()`; `held_back` asks `stopped_households` | `tests/test_registry.py` |
| `tracker/api.py` | `_listing` inside `one_reading()` | `tests/test_api.py` |
| `tracker/view.py` | `write_view` leaves a page that says the same; `_kept_stamp`, `_says`; `ViewResult.unchanged`; `VIEW_NOTE` says the page is redrawn whenever anything on it changes (the review's SHOULD-1) | `tests/test_view.py` |
| `tracker/api.py` (comment), `docs/runbook.md`, `README.md`, `docs/ROADMAP.md` (the tree diagram) | "redrawn by every pass" becomes "redrawn whenever it changes" | `tests/test_single_source.py` |
| `docs/repo-map.curated.json`, then `tools/repo_map.py update` | the notes of the five modules | `tests/test_repo_map.py` |
| `pilot/DECISIONS.md` | P207-P211 | - |

Tests added, each named as its claim: `test_one_household_asks_the_data_folder_once_and_drops_it_after`,
`test_one_household_lets_the_pass_write_its_records_and_the_store`, `test_a_settings_write_inside_a_household_is_refused_and_never_undoes_a_save`,
`test_one_household_holds_a_path_only_once_it_is_there`, `test_one_household_never_holds_an_error`,
`test_a_household_inside_a_reading_is_the_reading_and_still_refuses_a_write`;
`test_the_pass_holds_the_machines_answers_for_one_household_at_a_time`;
`test_stopped_households_is_the_walks_own_answer`, `test_stopped_households_reads_no_return`,
`test_stopped_households_is_one_reading`, `test_stopped_households_of_an_empty_root_stops_nothing_and_a_missing_one_is_an_error`,
`test_held_back_names_a_copied_household_without_the_whole_walk`;
`test_the_list_a_write_carries_is_one_reading_after_the_write`;
`test_a_page_that_would_say_the_same_is_not_written_again`, `test_a_page_with_anything_new_is_written`,
`test_a_page_changed_by_hand_is_drawn_again`, `test_a_page_whose_time_cannot_be_read_is_drawn_again`,
`test_a_page_written_on_windows_compares_by_what_it_says`, `test_a_caller_that_names_the_time_gets_a_page_drawn_at_it`.

The gate (decision 207, Jason 2026-09-29): those five test files, the
files of the modules that call the changed functions (`tests/test_rollover.py`
for `held_back`, `tests/test_store.py` for `resolved`, `tests/test_firm_cache.py`
for the reading), and the guards `tests/test_layers.py`,
`tests/test_single_source.py` and `tests/test_repo_map.py`, under Python
3.11 (the floor) and 3.13; then `ruff` and both `check`s.

## 5. Measured after the build

