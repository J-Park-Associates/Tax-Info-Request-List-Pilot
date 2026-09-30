# Shell S6a - the first half of the join

Session: S6a joiner (sonnet), 2026-09-30. **Branch: `claude/shell-join`**, started from
`origin/claude/shell-s8a-links` (S2 menus, S8a, S1 rebuild 3). Merge commits only; nothing rebased,
nothing force-pushed. S5 is **not** merged: that is S6b, last.

## Merges done (in order)

| Branch | Result |
|---|---|
| `claude/shell-s8b-misfit-reasons` | merged clean |
| `claude/shell-s7-tooltips` | merged (S3 renderer foundation and S7 come in with it); conflicts below |
| `claude/shell-spec-sync` | merged; conflicts below |
| `claude/sharp-goldberg-jmfynk` (the latest S1 branch) | had 5 commits s8a lacked (S1 review 4, rebuild 4, review 5: the moved file's handle and year pinned on `firm`); merged; only the repository map conflicted |
| S3 (`claude/friendly-archimedes-33y9uk`, `claude/admiring-lamport-bp1sse`) | already contained after the S7 merge (`merge-base --is-ancestor`); nothing to merge |
| `claude/shell-s2-menus`, `festive-mayer`, `keen-keller`, `kind-fermi`, `practical-feynman`, `stoic-curie` | already contained |
| `claude/shell-s4-pages` | **not merged**, on purpose: S5 is built on its tip, so S6b's merge brings it |

## Conflicts and how each was resolved

- **`tests/test_shell.py` (S7 merge, add/add).** S2 wrote its menu half and S3/S7 wrote the renderer half
  under one name. Kept the renderer half (S3/S7) at `tests/test_shell.py`; S2's file kept whole as
  `tests/test_shell_menu.py`; `tests/test_api.py`'s two `from tests.test_shell import _run` now read
  `tests.test_shell_menu`. **S5's branch also edits `tests/test_shell.py`** (renderer side): expect S6b to
  merge S5's onto the renderer half, which is where it came from.
- **`docs/repo-map.json` and `docs/repo-map.md` (every merge).** Generated files: took this side each
  time and regenerated with `tools/repo_map.py update` at the end (check is current).
- **`pilot/SPEC-shell.md` (spec-sync merge, two hunks: 5.5 error log and 10 "No error log yet").**
  Took spec-sync's text: it is the later, ruling-numbered wording (rulings 3, 4, 6, 10).
- **`pilot/shell-test-pins.md` (one row).** Took spec-sync's (only "S1 rebuild 1" in the cell differs).
- **`pilot/wording-shell.tsv` (whole file).** Spec-sync added two columns (`title_case`, `changed`) to
  every row, so every row conflicted. Took spec-sync's file and re-added the 14 rows this side added
  (nine `screen.misfits.reasons.*` and `screen.notices.feed/machine/paused/reader/renamed`), with
  `title_case` = their words. `tracker/api.py` needed no conflict resolution: S8a's engine keys are
  what is there.
- **`tests/test_api.py` (S1 merge).** Auto-merged.

Expected when S6b merges `claude/shell-s5-sheet` (checked with `git merge-tree`): conflicts in
`docs/repo-map.json`/`.md` (regenerate), `pilot/SPEC-shell.md`, `pilot/wording-shell.tsv` (S5's added
rows: re-add them, and drop the ones this file now carries), `pilot/harness/interact.mjs`,
`tests/test_shell.py` and `tests/test_single_source.py`.

## What this session changed (one commit per step)

1. **Engine words.** `screen.misfits.reasons.not_a_year` = "Bad Year" (ruling 18a; the registry test now
   requires every code to have words). `screen.notices.pick_request` = "Pick a Request First" and
   `screen.notices.name_requests` = "Name Each Custom Request" (**proposed for Jason**, marked so in the
   table and the code). `editor.advanced` = "Advanced". `screen.close` = "Close" (S5 review F9);
   `screen.icons.dismiss` stays. `editor.routing` and `routing_all` are **kept**: `app.js` on this branch
   still reads them (S5 stops reading them, per its handoff; S6b can drop them then). Table rows added.
2. **Ruling 21.** `firm.returns[].paused`: true for every return of a household whose active returns span
   two open years (`households.open_years`, the test behind `runner.TWO_OPEN_YEARS`), computed from the
   registry walk `firm` already makes: no extra disk read. Test plus a mutation check (`> 1` to `> 2`
   fails it).
3. **Window join.** `show_in_explorer` added to `api.MENU`, `DEFAULT_MENU_WORDS` and the `file`, `moved`
   and `received` popups in `app/main.js` (the four templates are now exactly S5's `JOIN_POPUPS`);
   `request` unchanged. A new test pins the four templates (mutation-checked); S2's two popup tests
   updated. The reveal path (`open(path, "reveal")`, `openChecked`, the reveal-only kind) was already
   in from S8a; `preload.js` needed no change.
4. **SPEC text.** 5.2 and 11.3 tables gain Show in File Explorer; 5.7 names the reveal-only kind
   (`filed_copy`, `moved_copy`, `shown_copy`), `shown_key` and the final key names; 9.2 lists
   `returns[].paused`, `files[].open_key` and the top-level `paths`; 9.3 mentions `firm`'s keys; 11.4 gets
   rows for `misfits.reasons`, `close`, the two proposed notices and `editor.advanced`.
5. **Runbook.** One note (ruling 22): the fallback log's place, that uninstalling leaves it, that it can
   hold client names, delete the folder by hand; the normal `tracker-errors.log` is named beside it.
   `test_single_source` passes.
6. **`pilot/DECISIONS.md`.** P85-P107: rulings 1-22 in order with 18a after 18, decision text as written
   in `shell-rulings.md`, "applies as" and status from the ledger.
7. **Tour.** Step titles and lines in Title Case (`Needs Review`, `One Clients Folder`, ...); "Drop files
   here" keeps the inbox folder's own name. A test pins it (mutation-checked).
8. **Handoff and Windows prompt.** `pilot/HANDOFF.md` has an index and what is left;
   `pilot/wintest/PROMPT-shell.md` is the Windows check.

## Gate

Each test file its own process, Python 3.11 then 3.13: `test_shell`, `test_shell_menu`, `test_api`,
`test_registry`, `test_pilot_ui`, `test_tour`, `test_pilot`, `test_single_source`, `test_layers`,
`test_repo_map`, `test_row_columns`, `test_tripwire`, `test_errors` all pass on both. `python -m ruff check .`
clean; `tools/repo_map.py check` current. New tests were mutation-checked.

## Left for S6b

1. Merge `claude/shell-s5-sheet` last (it carries S4). Resolve as above; keep each side's reviewed
   behaviour. Re-run the harness against the live engine and delete the vocabulary mirror
   (`HARNESS_LIVE_VOCAB=1`).
2. Drop `editor.routing` / `routing_all` from the API and their tests once S5's `app.js` no longer reads
   them.
3. `app/renderer/index.html` still has `<h3>Needs review</h3>` (an S3/S5 file; Title Case, ruling 10).
4. `pilot/harness/stub.js` and `interact.mjs` still spell "Needs review" and other lower-case words in the
   stub vocabulary.
5. `tests/test_shell_menu.py` says "the renderer part is joined by S6": the two halves now live in two
   files; S6b may fold or leave.
6. Two words wait for Jason (marked PROPOSED): `pick_request` and `name_requests`.
7. The Windows check: `pilot/wintest/PROMPT-shell.md`; the firm summary speed (6.7 s in the sandbox for
   750 returns, budget 3 s) is the number to watch.
