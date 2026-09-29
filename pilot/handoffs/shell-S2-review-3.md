# Shell S2 review 3 (opus, high effort)

Branch `claude/shell-s2-menus`, reviewed at `ca64fcd`. The rebuild's diff is
`git diff 91bc194..HEAD`. The reviewer did not build S2 or either rebuild.
This review adds this file and runs `python tools/repo_map.py update`; it
changes nothing else.

## Verdict

One finding: the rebuild's commit left the map stale. The map refresh this
review must run anyway fixes it (finding 1). Review 2's finding 2 is fixed.
No code changed since review 2.

## What was checked, and holds

- **The rebuild touched no code.** `git diff --stat 91bc194..HEAD` lists only
  `docs/repo-map.curated.json`, the generated `docs/repo-map.json` and
  `docs/repo-map.md`, and `pilot/handoffs/shell-S2-rebuild-2.md`. Nothing
  under `app/`, `tracker/`, `tests/` or `tools/` changed.
- **The preload role now matches `app/preload.js`, and "Nothing else
  crosses" is true.** The preload exposes one object, `tracker`, with
  exactly these members:
  - `call` (`tracker-cmd`)
  - `open` (`open-path`)
  - `pickFolder` (`pick-folder`)
  - `logError` (`log-error`)
  - `onProgress` (`tracker-progress`)
  - `onAfterInstallDone` (`after-install-done`)
  - `menu.onCommand` (hears `menu`) and `menu.send` (sends on `menu`)

  The role names all eight, with the right channels. Its "kept only in the
  error log the API named" is true: the `log-error` handler
  (`app/main.js:362-364`) calls `keepInLog`, which returns without writing
  when the API named no log (`:121`) and never builds a path. The main
  process has four `ipcMain` entries (`tracker-cmd`, `open-path`, `log-error`,
  `pick-folder` by `handle`; `menu` by `on`, `:554`), and each has its
  preload member.
- **"One of three main-to-renderer channels" is true.** `app/main.js` sends
  to the renderer at three places and no more:
  - `tracker-progress` (`:356`, `event.sender.send`)
  - `MENU_CHANNEL` (`:467`, `webContents.send`)
  - `LAUNCH_DONE_CHANNEL`, `after-install-done` (`:643`, `webContents.send`)

  The preload listens on all three.
- **The branch is otherwise as review 2 left it.** The results below match
  review 2's, test for test.

## Findings

**1. The rebuild's commit left the map stale, and its handoff says the map
was current. Fixed here by the map update.**

- **What happened.** `ca64fcd` adds `pilot/handoffs/shell-S2-rebuild-2.md`,
  but its `docs/repo-map.json` does not list that file. The rebuild ran
  `update` before it wrote its handoff. Rebuild 1 did the same thing and
  needed a second commit (`7ffca7b`, "map covers the rebuild handoff").
- **What the reviewer saw at `ca64fcd`.**
  - `python tools/repo_map.py check` exits 1 with `added
    pilot/handoffs/shell-S2-rebuild-2.md`.
  - `tests/test_repo_map.py::test_the_committed_map_is_current` fails
    (79 passed, 1 failed) under 3.11 and 3.13.
- **Why it matters.** The rebuild's handoff says "`repo_map.py check`
  reports the map current. `tests/test_repo_map.py`: 80 passed." That was
  true only before the handoff was added. A builder should run `update`
  after writing its handoff, as the last step before the commit.
- **Fix, made in this commit.** The `python tools/repo_map.py update` that
  this review runs after it adds this file also takes in the rebuild's
  handoff. After it, `check` reports the map current and `test_repo_map`
  passes (80).

## A note, not a finding

The rebuild commit's trailer reads `Co-Authored-By: Claude Sonnet 5.5`.
`CLAUDE.md` says Opus 5.5 builds. The commit is on a shared branch and
`main` history is never rewritten, so it is left as it is. It is recorded
here for Jason.

## Gate run by the review

Each file ran as its own process, under Python 3.11.15 (`/tmp/v`) and 3.13.12
(`/tmp/v313`, with the pinned versions in the prompt). The results were the
same under both.

| Test file | At `ca64fcd` | After this review's update |
|---|---|---|
| `test_shell` | 20 passed | not rerun (no code changed) |
| `test_single_source` | 168 passed | 168 passed |
| `test_layers` | 29 passed | not rerun (no code changed) |
| `test_repo_map` | 79 passed, 1 failed (finding 1) | 80 passed |

`python -m ruff check .` passed. `python tools/repo_map.py check` was stale
at `ca64fcd` (finding 1), and it reports the map current after this review's
update.
