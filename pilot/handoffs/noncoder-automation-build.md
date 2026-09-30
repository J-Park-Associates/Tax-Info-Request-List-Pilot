# Handoff: the plain-English library keeps itself current (P116)

**Date:** 2026-09-30
**Spec:** `pilot/SPEC-noncoder.md`. **Decision:** P116 in `pilot/DECISIONS.md`.

## What was built

- `tools/noncoder_pages.py`: `check`, `todo`, `stamp [PAGE ...]`, `place NOTE`, `organize [--dry-run]`, `hook`. Standard library only; hashes each original as Git commits it (`tools.repo_map.git_text_auto_eol_lf`).
- Section 9 of the spec (Jason's amendment): `organize` moves and renames pages (handoff pages by their note's name, program pages by first topic, overviews to Start Here), retires a page whose originals are all gone to `7 - History/Retired Pages` with a Retired line, renumbers stage folders, never overwrites, removes the empty folders it leaves, and re-keys `pages.json` for moved pages. `stamp` keeps the version a page replaces in `7 - History/Earlier Versions` from Git's `HEAD`; `pages.json` is schema 2 (`{"page": <hash>, "originals": {...}}` per page). History is exempt from the page rules and listed on the start page. The Stop hook runs `organize`, then `check`; `todo` lists what `organize --dry-run` would do first.
- `docs/For NonCoders/pages.json` (generated fingerprints) and `docs/For NonCoders/README.md` (now generated from the pages' Tags lines, plus the footer line). `stamp` reproduced the previous start page except that the Kind table now lists Overview first (the spec's vocabulary order) and the footer was added.
- `tests/test_noncoder_pages.py`: 62 tests, most on a miniature library in `tmp_path`.
- `docs/noncoder-style.md`: the writers' rules (rule 7 dropped), a Tags section, and "Keeping the library current".
- `.claude/settings.json`: the Stop hook, merged beside the untouched `permissions`.
- `CLAUDE.md` (guard file added to "Test minimally"; a paragraph before "The routing tools"), `tests/test_layers.py` (allowed spelling), `docs/repo-map.curated.json` (two nodes), `pilot/DECISIONS.md` (P116), `docs/maintenance-guide.md` (one paragraph in Part 5).
- The first `organize` run on the committed library renamed the two Stage 6 pages to `S6a - 01 Build, Part 1` and `S6b - 01 Build, Part 2` (they were `S6 - 01` and `S6 - 02`); nothing cites the old names. It now prints nothing on the committed tree.
- The Code map page no longer names `docs/repo-map.json` and `docs/repo-map.md` as originals: the map hashes `pages.json`, so a page that hashed the map could never be current. `docs/noncoder-style.md` says never to name them.
- Because `CLAUDE.md`, `pilot/DECISIONS.md` and the curated map are originals of pages, their three pages were checked; the first two got one sentence each and all three were re-stamped.

## Checked

- `check` exits 0 on the tree. The hook pipe test: `{}` exits 0; after appending a blank line to `shell-S1.md` it exits 2 with the work order on stderr; after `git checkout` it exits 0 again. The hook runs in well under a second.
- `ruff`, the map's `check`, and the tests `test_noncoder_pages`, `test_layers`, `test_single_source`, `test_repo_map`, `test_tripwire` all pass.

## Where the spec was read loosely

- The spec says six headings for both layouts; `docs/noncoder-style.md` gives six for each, so the check uses the style file's headings.
- "Existing tracked file" is checked as an existing file: a Git call would break the no-subprocess budget and the tests' temporary libraries.
- `place` for a stage letter with no pages yet (for example `S6c`) starts at 01 under its own prefix; the existing Stage 6 pages use the prefix `S6`.
- Section 9.1 says the current library already satisfies rules 2-4. It did not quite: the two Stage 6 names above, and the Final Checks, Rulings and Other Work names are the older hand-chosen ones. So the name rule keeps a name that has the right shape (`N Title`, a dated title, any name in Rulings, the label of a stage page) and recomputes only the stage prefix and number; the folder is always exact.
- Program-page folder rule and "file name contains" rule are implemented as written; `organize` is not run by `check`, so a misplaced page is fixed by the hook and pinned by the dry-run test rather than reported by `check`.
- `stamp` exits 1 and prints the work order when anything is still wrong after it runs.

## Rebuild 1

Fixes to the review's findings, and nothing more:

1. The Stop hook command is now a shell line that exits 0 when the script is missing and prefers the checkout's `.venv` Python (a missing script made python exit 2 and could trap a session). The exact-command test and SPEC section 6 match.
2. `organize` retires a page only when none of its originals is in the working tree and none is in Git's `HEAD` (never when Git is unavailable), so a rename is no longer taken for a removal. An original missing but still in `HEAD` is a `check` finding. When the hook's `organize` moves anything, the hook exits 2 (unless `stop_hook_active`) telling the session to stage the moves and run `repo_map.py update`.
3. A new stage with no folder is a `check` finding (asking a person to create or name the folder) instead of an error; the hook reports it.
4. A failure part way through `organize` rolls back every rename already made and raises; a leftover `*.organize-*` file is a `check` finding.
5. Wording: the tool docstring and the code-map notes say the hook runs `organize` (moves pages, adds the Retired line) and never edits page prose; the style file counts four commands; deviation 1 says six headings.
6. New tests through `main()` (hook on stdin JSON, `check` exit 1, `organize --dry-run`); the sorted-findings test now compares two libraries built in different orders.
7. `main()` sets stdout and stderr to UTF-8 (errors replaced) so a Windows console cannot crash a report.

## Left for Jason

Nothing waits on a decision. Any future note or changed original makes the hook and the test ask for its page.

## Review 2 and the lead's fix

The second Opus review passed findings 1, 3, 5, 6 and 7 of review 1 and
found two defects left by the rebuild, plus one minor point. Under the
process rule that a finding surviving one rebuild is fixed by the lead,
the lead fixed them directly:

1. **Rollback could overwrite a page.** Undoing a failed organize renamed
   each page straight back, which on Linux silently overwrites a page that
   had already moved into that name (two pages that swapped names). Now
   `_roll_back` works in two phases, never renames over an existing file,
   and names any page it could not put back and where it now is.
2. **A note renamed before its first commit retired its page.** "Not in
   HEAD" was read as "removed". Now a page is retired only when Git shows
   each original was committed once and removed since (`git log`); anything
   else stays a check finding for the agent.
3. **Hook:** the move message now stages only `docs/For NonCoders`, and a
   session that already tried once gets a dry run (nothing moved behind its
   back).

Four tests added (swap rollback, a rollback that cannot put a page back,
the uncommitted-rename case, the hook's dry run when already active).
