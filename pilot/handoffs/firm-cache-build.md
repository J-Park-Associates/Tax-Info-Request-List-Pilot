# Lane 1 (P115) - the firm view's cache and a faster repository - build hand-back

Branch `claude/firm-cache` (worktree `C:\Users\User\pl\cache`, from main
`877c7a2`). Builder: Opus 5.5, lane 1 of Pilot 0.3 (P140). Not pushed, no
pull request, not reviewed: a separate reviewer takes it from here.
SPEC: [`pilot/SPEC-firm-cache.md`](../SPEC-firm-cache.md). Decisions:
P118-P123 in [`pilot/DECISIONS.md`](../DECISIONS.md).

## What was built

- **P118, one reading.** `settings.one_reading()` holds, for one read-only
  reply, where the data folder is, where the program is, what the settings
  file says and what each path resolves to. `firm`, `list` and `state`
  (`api.HELD_READING_COMMANDS`) run inside it; nothing else does. The
  store's three resolvers ask `settings.resolved()`.
- **P119, four quadratic loops made lookups**, each pinned against the old
  rule: `registry.mark_superseded` (`_Priors`), the client-folder check in
  `discover_engagements`, `registry._two_claims`, `api._firm_key`. Helpers
  `layout.tail_names` / `common_tail` / `folder_name_key` keep each rule
  worded once.
- **P120, the cache.** New module `tracker/firm_cache.py` (layer 0) and
  the cached path in `api._cmd_firm` (`_firm_from_cache`, with
  `_firm_fresh` = the old whole walk as reference and fallback).
  `firm-view.json` in the data folder (path from `settings.data_home()`,
  never a hard-coded folder name, per P155); per household a fingerprint of
  every entry under its private and client folders (listed eight households
  at a time), its facts, and its shown rows as generic JSON (P141's new row
  fields flow through; any code change changes the program stamp and
  rebuilds). Head: format, program, root, data folder, day, settings file.
  Never kept: a household with a problem, a link, or anything modified in the
  last 5 s (git's racily-clean rule). Practice-wide facts recomputed every
  reply. Written only when what is kept changed.
- **P121** survey and **P122** (no test change this lane) are rulings; see
  the SPEC. **P123** decided by Jason 2026-09-30 ("p123, allow"): the cache
  may hold client names in the data folder, never a client tree.
- Docs: `docs/runbook.md` names `firm-view.json` beside `tracker.db`; the
  curated map has the new module and artifact; map refreshed.

## Measured (750 returns, `%USERPROFILE%\PilotTest\Clients-750`, this PC)

| | Before | After |
|---|---|---|
| `firm` warm | 52.2-53.8 s (check: 53.8 s) | 1.85-2.33 s; 1.97-2.30 s with the PC at 85% CPU |
| `firm` warm, 3.11 | - | 2.64-2.71 s (85% CPU) |
| `firm` cold / cache empty | 131 s (check, first run) | 9.3-12.9 s (warm disk; a cold disk needs a restart to reproduce) |
| one / 75 households changed | - | 2.4-2.8 s / 2.75 s |
| `list` | 28.5 s | 3.3-4.9 s |
| Roll Forward season 750 + 750 (synthetic) | about 175 s | 0.93 s |

Every `firm` and `list` reply after the change is byte-identical to the old
code's (2,343,016 and 773,088 bytes). The "before" runs had
`PYTHONDONTWRITEBYTECODE=1` from the agent shell (about +0.85 s of
compiling per start); the "after" runs have it unset, as the app has.
No document under `PilotTest` was opened or read; the sample was not
changed. The pass could not be timed on the sample: its 750 copies all claim
one household name, so the pass stops every one.

## Tests (each file alone, `.venv` = 3.14.x, `.venv311` = 3.11.15)

After the last code change (`f404cdb`), the files the change touches:

| File | 3.14 | 3.11 |
|---|---|---|
| tests/test_api.py | 415 passed in 1089 s, exit 0 | 415 passed in 1338 s, exit 0 |
| tests/test_firm_cache.py (new) | 22 passed, 1 skipped, exit 0 | 22 passed, 1 skipped, exit 0 |
| tests/test_layers.py | 29 passed, exit 0 | 29 passed, exit 0 |
| tests/test_repo_map.py | 80 passed, exit 0 | 80 passed, exit 0 |
| tests/test_single_source.py | 172 passed, **exit 1** (tripwire, below) | 172 passed, **exit 1** (tripwire, below) |

The one skip: `test_a_household_holding_a_link_is_never_fingerprinted`,
"this machine cannot make a symbolic link" (no Developer Mode here). The
`test_api.py` times are with four test processes and another lane's tests
on the PC at once, so they are not a before/after for P122.

Before that change, on `5faff36` (the others, unchanged since):

| File | 3.14 | 3.11 |
|---|---|---|
| tests/test_settings.py | 54 passed, exit 0 | 54 passed, exit 0 |
| tests/test_layout.py | 48 passed, exit 0 | 48 passed, exit 0 |
| tests/test_registry.py | 35 passed, 1 warning, exit 0 | 35 passed, 1 warning, exit 0 |
| tests/test_store.py | 175 passed, exit 0 | 175 passed, exit 0 |
| tests/test_errors.py | 83 passed, exit 0 | 83 passed, exit 0 |

**`tests/test_single_source.py` exits 1 with every test passing** - the
decision-185 tripwire: `test_the_app_opens_one_window` runs the real
`app/main.js`, which starts `.venv\Scripts\python.exe` from the checkout,
and that child opens the checkout's settings file. **Pre-existing, not this
lane's:** the same test on the base commit `877c7a2` (a temporary worktree,
removed) passes only because it has no `.venv`; given the same `.venv`
through a junction it trips identically. Any checkout with a `.venv` (the
office PC's included) will show it. Worth its own fix (the test, or the
stub's environment).

Quick checks: `python -m ruff check .` All checks passed; `python
tools/repo_map.py check` Map is current; vocabulary not touched (no words
changed), so `tools/vocab_report.py check` was not needed. Dead code: none
left in the changed files (ruff F401/F841 clean; every new module-level
name is used).

## Commits (on top of `877c7a2`)

- `53f8e14` - **the whole build of P118-P120, the SPEC, P118-P123 rows,
  tests, runbook and map.** Made at 00:28 by a second copy of this builder
  that another session started by mistake (the orchestrator has stopped
  it), from the tree this builder had staged; its message describes only
  the SPEC. Content checked against this builder's work; not rewritten.
- `086b349` - package docstring lists `firm_cache`; prose names constants;
  `firm-view.json` an owned runtime file in `test_single_source`.
- `5faff36` - the settings file named by its constant in `settings.py`
  prose (admission re-pinned under version 2, comment only); P123 decided.
- `f404cdb` - the fingerprint walk eight households at a time.
- this hand-back.

## Changes a reviewer should look at first

- `tests/test_api.py::test_firm_is_read_only` now excepts `firm-view.json`
  in the data folder (the SPEC's P120 says `firm` writes that one file).
- `tests/test_store.py` `ADMISSION_PIN[2]` re-pinned twice: the store's
  admission reaches `settings._read` and the store's resolvers, whose source
  changed; they refuse nothing new (the test's own instruction).
- `tests/test_single_source.py` owned-files set gained `CACHE_FILENAME`.
- Known limits (SPEC P120): a store damaged while its journals stay the same
  is not seen by a kept row until that household changes (the return page,
  the pass and `verify` still see it); a pass that rewrites a return's
  files makes its household read again on the next Overview.

## What is left

- Review (separate agent), then the daily landing. Overlaps: `tracker/api.py`
  (lanes 2 and 3 edit words there; this lane touched only `_cmd_firm` and
  below, `main()` and the command lists), `tests/test_api.py` (appended
  after `test_firm_leaves_out_inactive_returns`), `pilot/DECISIONS.md`
  (rows appended after P114; P115-P117 are on another branch),
  `tests/test_store.py` (the admission pin), and the generated map.
- Not built, named for later SPECs: fill the cache at the end of the
  scheduled pass (the runner may not import the API); a `list` cache if
  `list` must be under 3 s; split `tests/test_api.py` into parallel files
  after 0.3 lands; a lazy PDF-library import (0.2 s per command); a faster
  disk for the suite's temporary folders (a Dev Drive, or leaving it out of
  the virus scan - a PC security setting, Jason's call).
- The Windows re-check (steps 5, 6, 9, 12, 13 per `wincheck-shell.md`) on
  the landed build: step 6 is this lane's.
- `%LOCALAPPDATA%\tax-document-tracker-pilot\firm-view.json` from this
  lane's measurements (made-up names) was removed; `PilotTest\Clients-750`
  and `settings-750` are kept for the re-check.

## Files the next session needs

`pilot/SPEC-firm-cache.md`; this file; `pilot/DECISIONS.md` rows P118-P123;
`python tools/repo_map.py show tracker/firm_cache.py` and `show
tracker/api.py`; tests `tests/test_firm_cache.py` and the firm-cache tests
in `tests/test_api.py` (search `the firm view's cache (P120)`).
