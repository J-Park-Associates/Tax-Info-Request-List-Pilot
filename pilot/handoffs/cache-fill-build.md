# P201 - the firm cache filled at a pass's end - build hand-back

Branch `claude/cache-fill` from `4534b30`, one commit (hash in the reply).
SPEC: [`pilot/SPEC-firm-cache-fill.md`](../SPEC-firm-cache-fill.md). Not
pushed, no pull request. Next: a separate reviewer.

## Rulings, where they landed

| Ruling | Where |
|---|---|
| R1 the app's own `firm` in a child (runner never imports `api`) | `tracker/runner.py:579` `FIRM_COMMAND`, `:590` `fill_firm_cache()` |
| R2 the whole cache by the summary's own staleness rules | same function; no new cache logic |
| R3 after the locks and `watch.close`, before log, page, final line | `tracker/runner.py:3047-3057` in `_pass()` |
| R4 every real pass over the saved root; not dry run, typed root, unproved checkpoint | `tracker/runner.py:3054` |
| R5 never fatal: pass warning `cache-not-filled`, four reasons by kind | `tracker/runner.py:706-713` (`CACHE_NOT_FILLED`, `FILL_*`), `:808` code |
| R5a `api` writes today's head even when it keeps nothing | `tracker/api.py:6092-6096` - **the only api lines changed** (a 4-line comment and the condition `if keep != kept or not kept:`) |
| R6 packaged schedule names the product for the child only | `tracker/scheduling.py:186-196` (`runner_arguments`), `tracker/runner.py:584` `PRODUCT_FLAG`, `:2728` parser |
| R7 layers | `runner` imports `firm_cache` (L0) and `subprocess`; `tracker/firm_cache.py:322` `holds()` |
| R8 tests stand in for the fill unless asked | `tests/conftest.py:253-281` (`REAL_FILL`, autouse `fills_asked`) |

R5a was not in the first SPEC draft: the first real-child test showed a
practice with nothing keepable (every household changed under 5 s ago, or
none) wrote no file, so every such pass would have said "not filled". The
SPEC was amended before the code was finished.

## Measured (150 households, suite fixtures, temp folders, Python 3.14, this PC under other lanes' load)

| | Before | After |
|---|---|---|
| First Overview after a pass, cache empty | 4.32 s | 1.45 s / 1.57 s |
| Overview after that | 1.37 s | 1.26 s / 1.57 s |
| First Overview after a second pass (all 150 rewritten) | - | 1.33 s |
| Added to the pass by the fill | 0 | 4.04 s / 5.39 s cold, 4.26 s second pass |

The fill moves the first Overview's cost into the pass. 750 was not
measured here (no PilotTest; building 750 with fixtures is ~10 min); the
Windows check should time the morning pass and the first Overview.

## Dead code

ruff clean; no unused constants (every `FILL_*` reason is returned and
tested); the temporary measurement test was deleted, never committed.

## Gate

Each file its own process, in parallel.

- Python 3.14 (`C:\Python314`): test_runner 204 passed (1 old runpy warning);
  test_api 444 passed; test_firm_cache 31 passed, 1 skipped; test_scheduling
  115 passed; test_layers 29; test_single_source 179; test_repo_map 80.
- Python 3.11.15 (private venv, hash-checked locks): test_runner 204 passed (same runpy warning); test_api 444 passed; test_firm_cache 31 passed, 1 skipped; test_scheduling 115 passed; test_layers 29; test_single_source 179; test_repo_map 80.
- `python -m ruff check .`: All checks passed.
- `python tools/repo_map.py check`: Map is current (415 nodes).

## Not done / for the reviewer and the Windows check

- The packaged path (`api.exe firm` as the child, `--product` on the task
  line) is unit-tested only; the Windows check should run a scheduled pass
  from the installed build and confirm `firm-view.json` is fresh and the
  run log has no `cache-not-filled`. A task registered before this build
  says `cache-not-filled` until the app is started once (after_install
  re-registers; lane A owns that file and it was not touched).
- Run now waits for the fill before its final line (P201 says "alike"); at
  750 that is about the warm reply. If Jason finds Sort slower, the option
  is a scheduled-only fill (not built).
- Docs: `docs/runbook.md` data-folder paragraph and the Problems paragraph;
  `docs/repo-map.curated.json` (runner, firm_cache, scheduling notes);
  `pilot/DECISIONS.md` P201 row status.

## Engine review fold (2026-10-01, branch claude/fold-engine from 7e90834)

Rulings from `pilot/reviews/lanes-rulings.md` (Engine); the SPEC's R2, R3,
R4, R5a and section 5 say what changed and why.

- **SHOULD-1 (Stop means stop):** `tracker/runner.py:643` `_fills_the_cache()`
  returns False when `outcome == "stopped"` (:667); a pass that lost its app
  is stopped the same way. Test `test_a_pass_a_person_stopped_does_not_fill`
  (tests/test_runner.py:5083).
- **SHOULD-3 (a Sort fills only what it touched):** `_fills_the_cache()`
  asks the summary for a person's Sort (`--household`) only while
  `firm_cache.holds()` says the cache carries today's head - then the
  summary reads only the changed households. On a cold head it is not
  asked (the whole firm's read is the next Overview's, as before P201).
  No household-limited mode was added to `api`: the household a Sort just
  wrote is inside the 5 s racy window and could not be kept anyway. The
  scheduled pass fills cold or warm. Tests
  `test_run_now_fills_only_the_households_it_touched_so_only_while_the_cache_is_warm`
  (:5049, replaces `test_run_now_fills_the_cache_too`) and
  `test_the_scheduled_pass_fills_the_whole_firm_on_a_cold_cache` (:5070).
- **NIT-1 (write once per head):** `tracker/api.py:6107`
  `if keep != kept or (not kept and not firm_cache.holds(where, [head])):`.
  Test `test_a_practice_with_nothing_to_keep_writes_the_cache_once_per_head_not_every_reply`
  (tests/test_api.py:8836).
- **NIT-4 (fill after the record):** the fill moved after the run log line
  and the page (`tracker/runner.py:3137`). A failed fill: `_warn` as
  before, its code appended to runs.log as its own codes line (:3144, as
  page-not-written does), the page written again with its sentence, the
  sentence on the console / in Run now's final line. The pass line's
  `warnings=` count no longer includes it. Test
  `test_the_fill_runs_after_the_run_log_line_and_the_page_are_written`
  (:5105); `test_a_fill_that_fails_is_a_pass_warning_and_never_the_exit_code`
  still passes (its Run now half warms the cache first).
- Docs: `docs/runbook.md` data-folder and Problems paragraphs; curated map
  notes (runner, firm_cache); map refreshed.
### Tests (fold), each file its own process, two at a time per interpreter

| File | Python 3.11.15 (private venv, hash-checked locks) | Python 3.14 (C:\Python314) |
|---|---|---|
| tests/test_runner.py | 207 passed, 1 warning | 207 passed, 1 warning |
| tests/test_firm_cache.py | 31 passed, 1 skipped | 31 passed, 1 skipped |
| tests/test_after_install.py | 99 passed, 3 skipped | 99 passed, 3 skipped |
| tests/test_scheduling.py | 118 passed, 4 warnings | 118 passed, 4 warnings |
| tests/test_api.py -k "firm or cache" | 28 passed, 417 deselected | 28 passed, 417 deselected |
| tests/test_layers.py | 29 passed | 29 passed |
| tests/test_repo_map.py | 80 passed | 80 passed |

Plus tests/test_single_source.py (the runbook changed): 179 passed (3.14).
`python -m ruff check .`: All checks passed. `python tools/repo_map.py check`:
Map is current (424 nodes). Dead code: none left (ruff clean; no unused names).
