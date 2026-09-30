# Lane 4b hand-back: linked households, the raised lists, page buttons, side panel

Written 2026-09-30 by the lane 4b builder, branch `claude/column-order`
(worktree `C:\Users\User\pl\order`), on top of lane 4 (bf2d9ed, 11e2695).
New commits only; not pushed, no pull request, no rebase. Not self-reviewed:
a separate reviewer is next. SPEC: `pilot/SPEC-lists.md` sections 9-17
(section 7's files table has a lane 4b part; the duplicate 7 is now 8).

## Scope items

| # | Item | State |
|---|---|---|
| 1 | P141 linked households | **Built.** Record field `HouseholdInfo.related` (P170), both records written one lock at a time, store schema 20 in place, admission 3; Edit Household's Related Households list; violet link mark (`--st-linked`) on Overview, Needs Review, Reminders, Clients; panel with kinds; Escape/click outside closes and returns focus; Space on an active row opens it (P171). Owner question Q10 (kind words, A built). |
| 2 | Return-page sections (Q8) | **Built** (P176): bar, icon, tinted badge, row edge; headings stay text colour. |
| 3 | P145 Overview | **Built**: summary cards with icons, Work Waiting + count, tabs All / Need You (n) / Waiting (n) with aria-pressed, banding, pills with dot, form tag, placeholder. |
| 4 | P149 Needs Review | **Built**: reason cards (filters, All), "13 Files" beside the title, return cards (folder icon, household link + link mark, "1 Document", More Actions opening the return's own native menu), file icon, request tag with full title as tooltip, amber reason pills with an icon per reason family. Q12 (placeholder words, A built). |
| 5 | P152 page buttons | **Built** (P174): 50 per page after order/filters, Needs Review by whole groups, sticky header, page 1 on any change, forgotten on leaving. Q11 (50, A built). |
| 6 | P153/P154 side panel, Clients | **Built** (P175): icons, badges (Needs Review amber), five Under Construction items (aria-disabled, tooltip, toast only), Client Types (filter + removable filter tag), Settings = the existing Change Clients Folder page via `change_root`; Clients: Client Name / Returns / Status, Work Waiting count, pills, footer. Brand band changed on screen (P179, Q14): the logo's wordmark already reads the firm name, so the words are screen-reader only and "Tax Document Console" sits under the logo. |
| 7 | Keyboard status tooltip | **Built** (P178, `tooltip.js showTipNow`). |
| 8 | P140/P155 | No version or existing string renamed; new text says "Tax Document Console". |
| + | P180 (relayed mid-task) | Header tooltip is "Sort by {Column}" (`columns.sort_by`); Q1 decided C, Q2-Q7 and Q9 marked decided A in the SPEC; P138 row updated. |

Also found on screen (harness, 1100 x 700, light and dark) and fixed (P179): the
lists scrolled sideways beside Windows' 17px scrollbar; `--size-col-name` is now
224px. Measured on this PC (Segoe UI Variable via PIL): the longest reason pill
is 191px inside the 200px Reason column, so every reason shows whole (SPEC 16);
Q13 covers the Windows check. Not checked: Windows High Contrast on screen.

## Decisions taken

P170-P179 (in `pilot/DECISIONS.md` after P139). P141, P145, P149, P152-P155, P180
referenced, not re-taken. Owner questions open: Q10-Q14 (SPEC section 18).

## New reply fields (additive, for lane 1's firm cache)

- `firm.returns[].links`: `[{name, path, kind}]`, kind `feeds` / `fed_by` / `related`; `path` "" for a name no folder answers.
- `firm.returns[].form`: the recorded catalog id ("1040", "1120S", ...), "" when unknown.
- `firm.files[].suggestion_short`: the suggested request's short name.
- `list.households[].links` (as above); `list.households[].returns[].form`; `list.engagements[].form`.
- `state.household.related`: the household record's own related list.
- Store: `SCHEMA_VERSION` 20 (`engagements.household_related`, in place), `ADMISSION_VERSION` 3. If lane 1 also bumps the schema, the landing must renumber one of the two.

## Lines changed in shared files (new-file line numbers, vs 11e2695)

- `tracker/api.py`: 677-684 (RELATED_* words), 1271-1274, 1296-1357, 1359-1361, 1374-1376, 1400, 1428-1431, 1467-1469 (SCREEN words), 1781-1783 (household words), 2811-2813 (state `related`), 3604-3697 (list `links`/`form`, `_household_links`), 4068-4122 (`_related_from_spec`, `_mirror_related`), 4136-4141, 4163-4167 (`_cmd_edit_household`), 5604-5655 (firm row `form`, `suggestion_short`), 5712-5726 (`_cmd_firm` `links`).
- `tracker/records.py`: 1150-1155, 1165, 1172, 1189, 1218-1223, 1227-1239 (`related_from_json`), 2017-2021 (`household_problem`).
- `tracker/store.py`: 367-374, 388-391, 398, 416-418, 652, 1737-1738, 2085-2093.
- `app/renderer/shell.js`: 152-187 (`shellSideWords`), 320-349 (drawSide), 521-533 (drawCounts, drawFindWords), 539-570 (search), 614-618 (openFound), 941-945 (Escape), 988-1021 (wiring).
- `app/renderer/index.html`: 23-60 (side panel), 155-168 (icon symbols), 216-225 (Edit Household related).
- `app/renderer/shell.css`: 21, 38, 52-99 (side panel), 134-142, 149, 388, 395, 680-691 (figures), 816-1039 (raised lists block), 1096-1105 (forced colours).
- `app/renderer/pilot-ui.css`: 45 (`--size-col-name` 224px), 87-89 and 165-166 (new tokens).
- `app/main.js`: no change.
- Also `app/renderer/pages.js` (most of the lane's work), `tooltip.js` 96-105, `app.js` 1478-1481, 1517-1548, 1607, 3323, 3521-3527.

## Tests (SPEC's own, each file its own process)

RESULTS

## Checks

`python -m ruff check .`: all checks passed. `python tools/repo_map.py check`:
current. `python tools/vocab_report.py check`: current. Dead code: every new
Python and JS name is used; no commented-out code.

## Commits (on top of 11e2695)

COMMITS
