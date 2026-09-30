# Lane 4 hand-back: column headers, ordering, widths (Pilot 0.3)

Written 2026-09-30 00:18 PDT by the lane 4 builder, branch `claude/column-order`
(worktree `C:\Users\User\pl\order`, from `main` at 877c7a2). Not pushed, no pull
request, no rebase. Not self-reviewed: a separate reviewer is next.

## What was built

SPEC: `pilot/SPEC-lists.md` (new). Pointer added in `pilot/SPEC-shell.md` 3.6.

1. **Column headers on the four firm lists** (P135): Overview's Work Waiting,
   Needs Review (one header row above all its return groups), Reminders, Clients
   (both tabs share one order). Each header is a real button in a
   `role="columnheader"` cell of a one-row `role="table"`; a Tab stop; Enter and
   Space press it.
2. **Ordering** (P135): first press orders by the column, second reverses, third
   returns to today's order. Arrow (the drawn chevron, turned) plus `aria-sort`.
   Names as shown (numbers numerically, return names form first); Status and
   Stage by urgency (unreadable/paused, need a person, waiting, complete; larger
   count first; Held then later stage on Reminders); dates by the ISO date;
   Clients' Returns by number; blanks always last; ties keep the usual order.
   Needs Review orders files inside each return and returns follow their first
   file. Renderer only; no engine change. Kept while the app is open (P139).
3. **Widths** (P137): drag a header's right-edge grip; double-click fits the
   widest entry; Ctrl+Shift+Right/Left on a focused header steps 16px and says
   "{Column} Width {n}" in a new polite live region `#page-say`. Least/most per
   column; the name column takes what is left; past the window the page area
   scrolls sideways (header and rows together). Kept in this PC's localStorage
   (`tracker.columns`); **View › Reset Column Widths** (`reset_columns`) forgets
   them (P139). Needs Review's usual widths move 40px from Suggestion to Reason
   (160/200; same sum, 1100px still fits) for lane 2's finding that three reason
   words are cut at 160px. **Not measured on Windows** (see Q9).
4. **Needs Review levels** (P136): the household beside a return heading is a
   12px regular grey (`--text-secondary`) underlined link, blue on hover; a
   file's own name is a regular-weight link on every page (`row-file`). Before:
   heading, household and file all bold-ish blue links. After: 16/600 blue
   heading, 12/400 grey household, 14/400 blue file. Contrast pairs in SPEC 5.

## Words (P138; all Title Case, five words or fewer)

`vocab.screen.columns`: Return, Client, Status, Date, File, Suggestion, Reason,
Received, Stage, Drafted, Returns, "Order by {column}" (tooltip), "{column}
Width {n}" (screen reader). `vocab.menu.reset_columns`: "Reset Column Widths".
"Order", never "Sort". Rows added to `pilot/wording-shell.tsv`.

## Decisions written in `pilot/DECISIONS.md`

P135, P136, P137, P138, P139 (appended after P114). P142-P144 and P146-P148,
P150-P151 were **not** used.

## Open for Jason (SPEC-lists section "Open for Jason"; recommendation built)

Q1 tooltip word (A "Order by"); Q2 lists with headers (A the four firm lists);
Q3 order memory (A while the app is open); Q4 width memory (A this PC, with
Reset); Q5 household colour (A grey); Q6 heading band (A none); Q7 return-name
order (A as shown, form first); Q8 return-page sections look (A bar + icon +
row edge; specified, NOT built, see below); Q9 a reason still cut at 200px
(A shorter words, lane 2).

## NOT built: added scope that needs Jason's own confirmation

The permission classifier refused three actions in this session as possible
instruction poisoning: writing decision rows that included the linked-households
scope, reading `tracker/store.py` for that scope, and a SPEC edit adding the
return-page sections question. I reverted my half-made engine edits
(`tracker/records.py`, `tracker/store.py`; nothing of them remains) and did not
build the scopes that arrived as mid-task relayed messages beyond the two above
(Needs Review levels, widths), which went through. Not built, for the
orchestrator to confirm with Jason directly and hand to a fresh session:
- P141-P144 linked households (record field, store schema 20, `list`/`firm`
  fields, Edit Household, icon and panel). **No `firm` or `list` field was
  added**: lane 1 should not expect `household_links` or `links`.
- Return-page sections in their status colours (SPEC-lists section 6 is written;
  Q8; no code).
- P145 Overview redesign, P149 Needs Review cards, P152 pagination, P153/P154
  side panel and Under Construction items, P155 new app name in new text.
Also left as found: SPEC-lists has two sections numbered 7 (the renumbering
edit was the refused one).

## Lines changed in shared files (for the landing)

- `app/renderer/shell.js`: +104 `"aria-sort",` in `H_ATTRIBUTES`; +727
  `ids.push("reset_columns");` in `shellEnabled`; +827 `reset_columns: () =>
  pagesResetWidths(),` in `MENU_ANSWERS`; +908 in `shellKey`, after the listbox
  line: a key on `.col-head` goes to `pagesColumnKey`. The Escape block is untouched.
- `app/renderer/index.html`: +51-52 `#page-say` live region (and its comment)
  after `#notices`.
- `app/renderer/shell.css`: +468-552 (row-file, household link, header row,
  grips, measuring) after `.is-plain`; +809-814 in the forced-colours block.
- `tracker/api.py`: +1214-1215 `MENU["reset_columns"]`; +1284-1302
  `SCREEN["columns"]`. The `firm` command is untouched.
- Also `app/main.js` +494 and 537 (View menu item), `app/renderer/pages.js`
  (the lane's own work), `tests/test_shell.py`, `docs/repo-map.*`,
  `pilot/wording-shell.tsv`, `pilot/SPEC-shell.md` 3.6 (3 lines).

## Tests (SPEC's own, both interpreters)

`.venv` = Python 3.14, `.venv311` = Python 3.11.15. Same result on both.
- `tests/test_shell.py`: 121 passed, 2 failed - the two known harness-stub
  tests (WinError 206), pre-existing. 11 new tests, all pass.
- `tests/test_shell_menu.py`: 30 passed, 2 skipped, 1 failed - the known
  WinError 1314 symlink test, pre-existing.
- `tests/test_layers.py` 29 passed; `tests/test_single_source.py` 172 passed,
  but pytest exits 1 on a decision-185 tripwire in
  `test_the_app_opens_one_window`: `main.js` starts the checkout's own
  `.venv\Scripts\python.exe` (lines 26-36), which exists only because this
  worktree holds the venv the brief asked for; the same test is clean on a
  checkout of 877c7a2 without a `.venv`. Environmental, not this change.
- `tests/test_repo_map.py` 80 passed; `tests/test_vocab_report.py` 28 passed;
  `tests/test_tripwire.py` 19 passed; `tests/test_errors.py` 83 passed.
- `tests/test_api.py`: see the commit message / final reply (run last).
- `python -m ruff check .`: all checks passed. `python tools/repo_map.py
  check`: current. `python tools/vocab_report.py check`: current.
- Dead code: none in the changed files (every new function and constant is
  used; ruff clean).

Not checked here: the rendered look (no harness shots were run) and the
Windows font widths; both belong to the Windows check.
