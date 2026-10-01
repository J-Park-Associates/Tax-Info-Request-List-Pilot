# Taxpayer words (P196) - builder's hand-back

Branch `claude/taxpayer-words`, stacked on `61901ba` (firm-columns tip).
SPEC: `pilot/SPEC-taxpayer-words.md`. Not pushed; no pull request.
No new decision rows: the sub-rulings live in the SPEC (R1-R9) and its owner
questions; P196's status line says so.

## Changes (file:line after the build)

| Where | Old -> New |
|---|---|
| `tracker/api.py:940` `ASK_THE_CLIENT` | Ask the Client -> Ask the Taxpayer |
| `tracker/api.py:1207` `OVERRIDE_LABELS[0]` | Client Confirmed Final Version -> Taxpayer Confirmed Final Version (label only) |
| `tracker/api.py:1216` new `EDITOR_LABELS`; `:2000` editor field label | Client -> Taxpayer (the record keeps "Client") |
| `tracker/api.py:1229, 1243` `MENU.client`, `MENU.clients` | &Client -> H&ousehold; Clients -> Households |
| `tracker/api.py:1281` sections, `:1290` navigate_client, `:1293` find | Households; Navigate to Household; Find a Household |
| `tracker/api.py:1297-1298` placeholders | Households and Returns; Files, Households and Returns |
| `tracker/api.py:1302` sort.firm, `:1316` figures.waiting | Open a Household to Sort; Waiting on Taxpayers |
| `tracker/api.py:1350` nouns, `:1360` side.types | Households; Taxpayer Types |
| `tracker/api.py:1405` client_name, `:1414` empty, `:1436` groups.waiting | Household Name; No Households Yet; Waiting on Taxpayer |
| `tracker/reasons.py:827` name-absent | No Client Name Found -> No Taxpayer Name Found |
| `app/main.js:487, 501` | H&ousehold; Households (held equal to `api.MENU`) |
| `app/renderer/index.html:390` | Taxpayer (Greeting Name) |
| `app/renderer/pilot-content.js:83` | Sorts What Your Taxpayers Send |
| `README.md:115, 125, 516`; `docs/runbook.md:297-298, 410, 1155, 1219, 1227, 1230` | the Household menu, the Households page, "open a household first" |
| `pilot/wording-shell.tsv` | 9 rows updated, 13 added (each notes P196) |
| `pilot/harness/interact.mjs:54, 135, 168, 483, 492, 587, 654, 731` | expected words |
| `tests/test_api.py` | new `test_no_word_the_window_draws_says_client_but_a_folders_own_name`, `test_the_editor_says_taxpayer_where_the_record_keeps_client`; `:9143` pin |
| `tests/test_shell.py` | vocabulary mirrors and pins (979-991, 1684-1686, 1887, 3087, 3124-3127, 3180, 3594-3595) |
| docs | `pilot/HANDOFF.md` top, `SPEC-shell.md` 11 and `SPEC-lists.md` 15 pointers, `DECISIONS.md` P196 status, curated map notes (shell.js, pages.js) |

**Parallel builder's places:** `tracker/api.py` lines changed are only those
above (all between 614 and 2010; none in 3543-3561). `docs/runbook.md` lines
changed: 297, 298, 410, 1155, 1219, 1227, 1230 (none in 36-50).
`settings.py`, `make_samples.py`, `run_checks.ps1` untouched.

## What stays, and why (SPEC section 3)

Folders and path pieces (`Clients`, `Drop files here`; folder buttons keep
"Client", R3); the reminder drafts (R6); every code name, key, JSON field,
CSS class, route level, test name and the stored override reason (R7); the
standing rules and the pilot terms (R4); sentences that reach only the error
log or command line; the Firm Report, workbook and README files (R9, left
for later).

## Owner questions (all open; each built as recommended)

Q1 rules and terms keep "client" (A). Q2 Taxpayer Types (A). Q3 "Household"
where a household is meant - menu, link tooltip, search, Sort tooltip,
Household Name column (A). Q4 folder buttons keep "Client(s)" (A). Q5 the
draft's staff-footer lines keep "client" (A each; listed one by one in the
SPEC with file:line).

## Dead code

None added; the one new name (`EDITOR_LABELS`) has its caller. Comments by
the changed words brought up to date. `python -m ruff check .`: "All checks
passed!"

## Tests (each file its own process, in parallel)

| File | Python 3.11.15 (private venv, scratchpad, hash-checked locks) | Python 3.14.3 (`C:\Python314`) |
|---|---|---|
| `tests/test_api.py` | 440 passed | 440 passed |
| `tests/test_shell.py` | 158 passed | 158 passed |
| `tests/test_shell_menu.py` | 30 passed, 3 skipped | 30 passed, 3 skipped |
| `tests/test_reasons.py` | 58 passed | 58 passed |
| `tests/test_tour.py` | 9 passed | 9 passed |
| `tests/test_pilot.py` | 24 passed | 24 passed |
| `tests/test_single_source.py` | 179 passed | 179 passed |
| `tests/test_layers.py` | 29 passed | 29 passed |
| `tests/test_repo_map.py` | 80 passed (rerun) | 80 passed (rerun) |

`test_repo_map` first failed on both: the SPEC was edited after the map was
refreshed (the map hashes every file). Refreshed, rerun alone: passed.
`test_tripwire` and `test_errors` not run: no test's file access and no
error wording changed. `python tools/repo_map.py check`: "Map is current
(405 nodes)". `node --check` on `interact.mjs`, `main.js`, `pilot-content.js`: ok.

## The 1100 px proof

GDI+ in the Windows font (Segoe UI Variable Text; Semibold for headers and
labels), as the firm-columns build measured:

- Search box: 198 px of text room (240 - 32 left - 8 right - 2 border).
  "Search Households and Returns" 203 px and "Search Files, Households and
  Returns" 236 px did not fit, so R8 shortens them: "Households and Returns"
  159 px, "Files, Households and Returns" 192 px. (The old Needs Review
  placeholder, 205 px, was already cut by 7 px; now it fits.)
- Households' name header "Household Name" 100 px + 28 = 128 px in a column
  of at least 160 px. Side heading "Taxpayer Types" 87 px in 208 px. Side
  item "Households" 81 px. Footer "Showing 1-25 of 300 Households" 179 px.
- "Waiting on Taxpayers" 137 px in a figure a third of the page; "Waiting on
  Taxpayer" 157 px as a group heading. "No Taxpayer Name Found" 143 px, under
  Needs Review's longest reason "Looks Like Wrong Document" 159 px.
- New return: "Taxpayer (Greeting Name)" 145 px in its 179 px grid column
  (640 px dialog). "Taxpayer Confirmed Final Version" 210 px, under the
  drop-down's longest option (281 px). Tour line 205 px.
- No width, token or layout changed: the firm-columns sum (832 <= 843 px)
  stands.

## Not done

- The rendered check (`interact.mjs`, Playwright): not installed on this PC;
  the harness's words are updated and syntax-checked. The Windows check should
  run it, or look at Households and Needs Review at 1100 x 700 (the search
  placeholder is the tightest fit: 192 of 198 px).
- R9's files (Firm Report column, workbook column, README field label, CLI
  line), if Jason wants them - the engine's, with their own tests.
