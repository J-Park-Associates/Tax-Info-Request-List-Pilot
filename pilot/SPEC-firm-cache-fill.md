# Pilot 0.3 - the firm cache filled at a pass's end (P201) - SPEC

Status: **written before the build** (2026-10-01, 01:07 PDT), branch
`claude/cache-fill` from `4534b30`. Decision **P201** asked for it
([`DECISIONS.md`](DECISIONS.md); Jason, 2026-10-01, as P198): the Windows
check's N4 (`wintest/RESULTS-0.3.md`) measured the first firm summary after a
change at 65 s cold for 750 returns while it builds the cache, against 1.6 s
warm and a 3 s budget (SPEC-shell 9.2). It is the open follow-up "fill the
cache at a pass's end" in `handoffs/landing-0.3.md` (Left, item 3). The
cache itself is P120 ([`SPEC-firm-cache.md`](SPEC-firm-cache.md), section 2);
nothing here re-opens a ruling there. The hand-back is
[`handoffs/cache-fill-build.md`](handoffs/cache-fill-build.md).

The rule above every ruling here is P120's: **a cache may never make a
status wrong.** Nothing here reads a document or touches routing, so the
backtest baseline cannot move.

## 1. Why the first Overview is still cold

The cache's head (`firm_cache.head`) carries the day and the program. So the
whole cache is cold, every household read again, on **the first firm reply
of every day** and **the first after any upgrade**, whatever the pass did;
and each household a pass changed is read again on the next reply. Today
the person who opens Overview first pays for all of it. The scheduled pass
already runs before anyone is in (its first run of the day is the morning
one), so it is the place to pay instead.

## 2. Rulings

**R1. The pass fills the cache by asking the firm summary itself, in a
child process: `firm`, the app's own command.** `runner` may not import
`api` at load or at call time (`tests/test_layers.py`, line 440: "runner
never imports scheduling or api"), and the rows the cache keeps are built by
`api._firm_row` and the practice-wide pass over them (`api._firm_from_cache`,
`tracker/api.py:6005`). A second builder of those rows in a lower layer
would be a second place a status could be decided - rejected (P120: the
reference path stays one). Moving the firm view out of `api` is a refactor
of the module lane B is changing, and rejected for that and for its size. A
child process is a process boundary, not an import: the child is exactly
what Overview runs (`python -m tracker.api firm` from a checkout, the
packaged executable with `firm` in the app), with the pass's own
environment (settings folder, store, data folder), its stdout, stdin and
stderr closed (the reply names clients; nothing of it is kept), no window,
and its own error log (`api.main` opens it). `runner.FIRM_COMMAND` names the
command once; a test holds it to `api.COMMANDS` and
`api.HELD_READING_COMMANDS`, so a rename cannot leave the fill asking for a
command that is gone.

**R2. The whole cache, with the firm summary's own staleness rules - not
"only what the pass changed".** The fill is the next Overview, run early: it
reads every household whose fingerprint changed (those the pass touched,
any a person changed meanwhile, all of them on a new day or program) and
keeps the rest untouched; an unchanged practice writes nothing (P120). A
fill limited to the pass's households would be wrong on a new day or after
an upgrade - exactly the cold cases N4 measured - and would need a second
writer of the cache's shape. Every staleness rule holds because it is the
same code: the head (format, program, root, data folder, day, settings),
the racy window (`RACY_SECONDS`, 5 s: a household the pass wrote in its
last 5 s is not kept, and the next Overview reads it - one household,
milliseconds), links and junctions never kept, the status page and folder
times left out.
*Changed by the engine review's rulings (`pilot/reviews/lanes-rulings.md`,
Engine, SHOULD-3): the scheduled pass fills the whole firm as above; a
person's Sort fills only the households its pass touched.* A Sort asks the
summary only while the cache already holds today's head
(`runner._fills_the_cache`), when the summary reads just the households
whose fingerprint changed - the one the Sort touched, and any a person
changed meanwhile - and keeps the rest. On a cold head (a new day, an
upgrade, a settings change) the summary would read every household - 65 s
at 750 on the office PC (N4) for one household's Sort, with nothing on the
screen - so it is not asked, and the next Overview reads every household as
it would have before P201. Still one writer of the cache's shape: no
household-limited mode was added to the summary, since the household a Sort
just wrote is inside the 5 s racy window and could not have been kept.

**R3. When: after the households' locks are released and the progress file
is closed, before the run log, the console report, the practice page and
Run now's final line** (`runner._pass`, after the `watch.close` block,
`tracker/runner.py:2949-2961`). After the locks, because a lock file in a
household folder is an entry its fingerprint would take. Before the log and
the page, so a fill that failed is said in both, as every pass warning is.
The store is open but idle in the pass at that point; the app's own firm
replies already run beside a scheduled pass, so this is no new concurrency.
*Changed by the engine review's rulings (NIT-4): the fill now runs after the
run log's line and the practice page are written, not before them*, so a
fill that runs long - up to its 300 s, after a pass that may already be near
the task's two-hour limit - can never cost the pass its record. A fill that
failed is then said after the fact: the pass warning is added as before, its
code goes into the run log as a codes line of its own just below the pass's
(as `page-not-written` already does), the page is written again with its
sentence (if that second write fails, the first page stands and the class is
on the debug log), and the sentence is on the console or in Run now's final
line. The pass line's own `warnings=` count does not include it.

**R4. Which passes fill: every real pass that walked the saved clients
root** - the scheduled job and a person's Sort (Run now) alike, as P201
says. Not a dry run (it writes nothing, this included), not a pass whose
record checkpoint could not be proved (it served no household), and not a
pass given a clients root on its command line (a person running one folder
by hand; the firm summary only ever answers for the saved root, so filling
for it would be filling a cache that pass did not touch). ~~The pass that
stopped early, ran out of time or lost its app still fills: the summary
describes the folders as they are, whatever the pass finished.~~
*Changed by the engine review's rulings (SHOULD-1, "Stop means stop"): a
pass a person stopped does not fill*, nor one that lost its app (it is
stopped the same way). The household work has ended, and a fill would keep
Stop waiting - up to 65 s cold at 750 returns, 300 s at the cap - with
nothing on the screen; the next Overview fills the cache as it did before
P201. A pass that ran out of time, or whose own code failed, still fills. A
person's Sort fills only while the cache is warm (R2, as changed).

**R5. A fill that fails never fails the pass: it is said, loudly, and the
pass's exit code is unchanged.** One pass warning through `_warn`, the one
way a pass warning is added (decision 186): the code `cache-not-filled` in
the run log's codes line (counted in `warnings=`), the sentence on the
practice page's Problems list, in the console report, and in Run now's
final line. The sentence names why by kind only, never a client's words:

- the child could not start (`OSError` class),
- it stopped with a non-zero code (the child's own error log has why, as
  for any `firm` reply),
- it ran past `FILL_TIME_LIMIT_SECONDS` (300 s, over four times the 65 s
  cold fill N4 measured at 750 on the office PC; the child is then stopped
  and the old file stands whole, since every write is atomic),
- it finished but the cache file in the data folder does not carry today's
  head for this root (`firm_cache.holds`): the firm summary gave way to the
  whole walk (its own error log says why, once - P120's SHOULD-1) or the
  file could not be written.

**R5a. The summary leaves today's head even when it keeps nothing** - the
one line this needs in `api` (`_firm_from_cache`, `tracker/api.py:6096`,
was `if keep != kept:`, now `if keep != kept or not kept:`). Before it, a
practice with nothing keepable - every household changed in the last 5 s,
as a one-household practice is just after its pass, or no household at all
- wrote no file, so the fill could not tell "answered, nothing to keep"
from "could not write" and would have said every such pass failed. Found
by this SPEC's own first test, which did exactly that. ~~The cost: while
nothing is kept, each reply rewrites a file of about a hundred bytes; once
any household is kept, an unchanged practice writes nothing, as P120 says.~~
*Changed by the engine review's rulings (NIT-1): written only when the head
changes* - `if keep != kept or (not kept and not firm_cache.holds(where,
[head])):` - so while nothing is kept the file is written once per head (a
day, a program, a settings change), not on every reply; once any household
is kept, an unchanged practice writes nothing, as P120 says.

The words: *the Overview could not be made ready after the pass ({why}); the
first Overview after it reads every household again* - lower-case, as the
page's other pass warnings are. Not a failure of the pass because the cache
only makes the next reply faster (P120: "the reply is still answered").

**R6. The packaged scheduled job is told the product's name.** The child
imports `tracker.api`, which imports `tracker.scheduling`, whose `TASK_NAME`
is read at import from `settings.product_name()`; a frozen build has no
`package.json` (`tests/test_build.py`, "the shell's two variables are how
it is told"), and Task Scheduler passes no environment. So the packaged
schedule's command line gains `--product "<name>"` (`runner.PRODUCT_FLAG`,
written by `scheduling.runner_arguments(frozen=True)` from
`settings.product_name()`, which the API that registers the task always
has), placed before `--settings` so the line still ends as decision 131's
does. The runner hands it to the fill's child only, as
`TRACKER_PRODUCT_NAME`; the pass itself still never needs it, so its page
heading is unchanged (`_page_title`) and `api_entry.py`'s reason stands.
The source job's line is unchanged (a checkout reads `app/package.json`),
and so is the README's quotation of it. Run now inherits the shell's
environment. A task registered before this change has no `--product`; the
first app start after the upgrade registers it again (`after_install`, the
schedule job, decision 209), and until then the fill is said as failed
(R5), never silently skipped.

**R7. Layers.** `runner` (layer 4) imports `firm_cache` (layer 0) for
`holds` and `cache_path`: downward, allowed (`tests/test_layers.py`
`LAYERS`). `runner` still imports neither `api` nor `scheduling`.
`firm_cache` gains `holds(path, heads)`: whether the file at `path` is
whole JSON whose head is one of `heads` (today's, and the day the fill
began, so a fill across midnight is not called failed). It reads no
household and logs nothing (the child's reply already said any surprise).
`subprocess` joins `runner`'s imports; it is already on the allowed
standard-library list (`tests/test_layers.py:211`).

**R8. Tests do not start a real child unless they ask.** A suite-wide
autouse fixture in `tests/conftest.py` (as `no_task_scheduler_unless_faked`
does for `schtasks`) stands in for `runner.fill_firm_cache`, recording what
it was asked and answering "filled"; the fill's own tests put the real one
back. Otherwise every test that runs the scheduled job's line would start
a second Python and write `firm-view.json`.

## 3. Files, functions and owning tests

| File | What changes | Owning test file |
|---|---|---|
| `tracker/runner.py` | `FIRM_COMMAND`, `PRODUCT_FLAG`, `FILL_TIME_LIMIT_SECONDS`, `CACHE_NOT_FILLED` and its four reasons, `CODE_CACHE_NOT_FILLED` (constants beside `PAGE_NOT_WRITTEN`, lines 629-632, and the codes, 723-728); `fill_firm_cache()` (new, after `run_now_arguments`, 561-571); `_parser()` (2611-2649) gains `--product`; `_pass()` calls the fill after the `watch.close` block (2949-2961) | `tests/test_runner.py` |
| `tracker/firm_cache.py` | `holds(path, heads)` (new, after `load`, 293-320) | `tests/test_firm_cache.py` |
| `tracker/scheduling.py` | `runner_arguments` (175-188): the frozen line names the product | `tests/test_scheduling.py` |
| `tests/conftest.py` | the autouse stand-in for the fill (R8) | the suite |
| `tracker/api.py` | `_firm_from_cache`: the save condition (6092-6096, R5a) and its comment; nothing else | `tests/test_api.py` (its firm and cache tests) |
| `docs/repo-map.curated.json`, then `tools/repo_map.py update` | `runner` writes (through its child) `firm-view.json`; `firm_cache`'s `holds` | `tests/test_repo_map.py` |
| `docs/runbook.md` | the data-folder paragraph (line 31-37) and the Problems paragraph (1307-1333) | `tests/test_single_source.py` |

The SPEC's tests: `tests/test_runner.py`, `tests/test_firm_cache.py`,
`tests/test_scheduling.py` (its line changes), and the guards
`tests/test_layers.py`, `tests/test_single_source.py`,
`tests/test_repo_map.py`, each its own process, under 3.11 and 3.14.
`tests/test_api.py` runs because of R5a (`-k "firm or cache"` while
building; the whole file once per interpreter at the gate). The new tests:

- `test_the_pass_fills_the_firm_cache_so_the_next_overview_reads_no_household`
  (real child: after the scheduled job's line, the cache holds today's head
  and a `firm` reply reads no household fresh),
- `test_run_now_fills_the_cache_too` and
  `test_a_dry_run_a_typed_root_and_an_unproved_checkpoint_do_not_fill`,
- `test_a_fill_that_fails_is_a_pass_warning_and_never_the_exit_code`
  (each reason: on the page, the run log's codes line and Run now's final
  line; exit 0),
- `test_the_fill_asks_for_the_apps_own_firm_command` (`FIRM_COMMAND` in
  `api.COMMANDS` and `HELD_READING_COMMANDS`),
- `test_the_product_name_reaches_the_fill_and_never_the_page`,
- `tests/test_firm_cache.py::test_holds_only_a_whole_file_under_one_of_the_heads`,
- `tests/test_scheduling.py`: the packaged line names the product before
  the settings folder; the source line does not.
- `tests/test_api.py::test_a_practice_with_nothing_to_keep_yet_still_leaves_todays_head` (R5a).

## 4. Measured

Before and after, with the suite's own fixtures (`tests/test_runner.py`'s
`build_engagement`, one return per household, nothing in the inboxes) in
pytest's temporary folders - never `PilotTest` - on this PC under Python
3.14, while other lanes ran tests (so timings are noisy by a second or so).
150 households; the scheduled job's line (`--settings ... --log`); each
Overview is `python -m tracker.api firm` started 6 s after the pass (past
the racy window, as a person opening the app later would be).

| | Before (no fill) | After (P201) |
|---|---|---|
| First Overview after a first pass (cache empty) | 4.32 s | 1.45 s, 1.57 s (two runs) |
| The Overview after that | 1.37 s | 1.26 s, 1.57 s |
| First Overview after a second pass (every household's record rewritten) | - | 1.33 s |
| Time the fill adds to the pass | 0 | 4.04 s, 5.39 s (cold); 4.26 s (second pass, all 150 changed) |

The fill costs what the first Overview would have cost, moved into the pass.
At 750 returns that is the P120 fill time on the office PC (9-11 s
measured then; 65 s in the 0.3 Windows check's cold run, N4), inside the
300 s limit; a pass that changed few households adds about the warm reply
(1.6-2.3 s at 750).

## 5. What staff will notice

- The first Overview after a scheduled pass - including the first of the
  day, and the first after an upgrade once the morning pass has run - opens
  warm (about 2 s at 750 returns) instead of reading every household.
- A Sort (Run now) takes the firm summary's time longer to finish only while
  the cache is warm for today (about the warm reply, a second or two at
  750), and Overview after it is warm. On the first Sort of a day before any
  scheduled pass, it takes no longer (engine review, SHOULD-3); a Sort that
  is stopped ends at once (SHOULD-1).
- If the fill ever fails, the practice page's Problems list and the Sort
  result say *the Overview could not be made ready after the pass (...)*;
  nothing else changes, and the next Overview is simply slower.

## 6. What this makes true in the docs

- `docs/runbook.md`, the data-folder paragraph: each real pass over the
  saved root fills `firm-view.json` at its end, so the first Overview after
  a scheduled pass is warm.
- `docs/runbook.md`, the Problems paragraph: what *the Overview could not
  be made ready after the pass* means (`cache-not-filled` in `runs.log`)
  and what to do (nothing; if it repeats, look at the error log; a schedule
  registered before this version names no product until the app has been
  started once).
- No README line: the source job's command line is unchanged. No build
  script or installer line: the packaged task is registered again at the
  first start after the upgrade (decision 209).

Nothing is open for Jason: no money, client wording, client data or season
question. The one visible wording is a staff-facing problem line.
