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
