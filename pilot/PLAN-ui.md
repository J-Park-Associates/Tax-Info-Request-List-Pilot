# Plan: a simpler app screen (sidebar + tabs, hover descriptors, plain English)

> **Partly replaced (P62, 2026-09-29):** the layout is now
> [`BRIEF-shell.md`](BRIEF-shell.md): firm sections in the side panel, an explorer
> breadcrumb, one grouped list per return, and no tabs, sidebar tree or ⋯ More
> button. The tooltip, plain English, start-up safety line and notice area
> below still stand.

Approved by Jason on 2026-09-29 in a planning session. This is the input to the
SPEC job (see [`HANDOFF.md`](HANDOFF.md), Next). Nothing here is built yet.

## Context

Jason finds the tracker's one screen crowded. Today it is one long page: a row of
**9 buttons**, up to **6 banners**, then stacked cards (household, requests,
reminder, moved-by-hand, needs review, filed) and **four always-on safety-rule
cards (~150 words)** at the bottom. Many rows carry full sentences, file paths,
lock host names and settings paths that a preparer does not need day to day.
Hover help today is only the plain Windows grey box (`title=`), which appears
slowly and never for keyboard users.

He wants the look of the file-manager screenshot: a folder tree on the left, one
clean table on the right, a few pill buttons in a blue top bar, and explanations
moved into hover descriptors. Decisions already made in this session:

| Question | Jason's answer |
|---|---|
| Layout | **Sidebar tree + tabs** |
| Row sentence (Client / Us / Decide) | **Move to hover and shorten it** — reverses decision 200's "never a tooltip" |
| All wording | **Every sentence in the app in easy, plain English** |
| Safety rules | **One-line badge shown at start-up, then it goes away** |
| Hover descriptor | **Custom tooltip** (no new packages) |
| Where to build | **Pilot now, port to the main tracker later** — supersedes P10 for this work |

This session only plans. Building follows the repo's loop: SPEC → build →
separate review, each in a fresh session handing off through files.

## The design

### Screen at a glance

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ▣ Tax Document Tracker  Pilot │ Park / 2025 / 1040 - John & Maria   🛡  [Sort & Scan] [Inbox] [Report] [⋯] │
├───────────────────┬──────────────────────────────────────────────────────────┤
│ 🔍 Find a client  │  Requests 3 │ Needs review 2 │ Reminder │ Filed 14        │
│ ▾ Park household  │  12 asked · 9 received · 3 outstanding                    │
│   ▾ 2025          │ ┌──────────────────────┬───────┬──────────────┬────────┐ │
│     1040 - John…  3│ │ Document             │ Files │ Status       │ Received│ │
│     1065 - Park…   │ │ W-2 – Acme Corp      │ 1 / 1 │ ● Received   │ Mar 3  │ │
│ ▸ Lee household  1│ │ 1099-B – Schwab      │ 0 / 1 │ ● Outstanding │  —     │ │
│ ▸ Kim household    │ │                      │       │   Client ⓘ   │        │ │
│                   │ └──────────────────────┴───────┴──────────────┴────────┘ │
│ + New household   │                                                          │
│ Last sort: 6:00 AM ✓                                                         │
└───────────────────┴──────────────────────────────────────────────────────────┘
```

### 1. Top bar (9 buttons → 3 + a menu)
- Kept in view: **Sort & Scan** (primary), **Open Inbox**, **Open Status Report**.
- **⋯ More** menu holds: New household, Open Client Folder, Edit Request List,
  Schedule, Repair the schedule, Open Status (whole practice). Menu order keeps
  `btn-edit` < `btn-schedule` < `btn-view` (pinned by `tests/test_api.py`).
- A breadcrumb (household / year / return) replaces the return drop-down and the
  form and "status report current/behind" chips; those two chips become tooltips
  on the breadcrumb.
- Pilot badge and Tour button stay where `pilot.js` injects them.

### 2. Left sidebar (the folder tree)
- The tree's top node, **All clients**, is the firm-wide list and the page the
  app opens on: the Status page shown inside the app (tester feedback 1 and 4
  in `HANDOFF.md`). The API's `list` command already returns every household.
- Households → tax year → returns, with a small number badge per return
  (outstanding + needs review). Search box filters the tree by name.
- Clicking a **household** shows its overview (shared with, contact, inbox link,
  sharing checklist, roll-forward) — today's household card, trimmed.
- Clicking a **return** shows its tabs. Uses the existing `showReturn(path)`
  (`app/renderer/app.js:2259`); the `#eng-select` drop-down is removed and
  its data (grouped by household) feeds the tree.
- Footer: **+ New household** and a one-line "Last sort" status (today's
  `#last-pass` banner); details in its tooltip.

### 3. Tabs for one return (stacked cards → one at a time)
- **Requests (n outstanding)**, **Needs review (n)**, **Reminder**, **Filed (n)**,
  and **Moved by hand (n)** only when n > 0. The tab with work waiting shows a
  count; the app opens on Needs review when it has items, otherwise Requests.
- One summary line above the table (e.g. "12 asked · 9 received · 3 outstanding").

### 4. Requests table (6 columns → 4)
- **Document · Files · Status · Received.**
- ID moves into the Document tooltip; Notes becomes a small note icon with the
  note in its tooltip (shown only when a note exists).
- Status cell: coloured chip + the side word (**Client / Us / Decide**). The
  sentence moves into the side word's tooltip and is shortened (Jason's ruling;
  new decision row reverses decision 200's "never a tooltip").
- Zebra rows and the screenshot's light spacing. "Set aside (n)" fold stays below.

### 5. Hover descriptors (custom tooltip)
- New `app/renderer/tooltip.js` (~70 lines, plain JavaScript) plus a few CSS rules
  in `style.css`. Any element with `data-tip` gets it: shows after ~300 ms on
  hover and at once on keyboard focus, hides on Escape / mouse-out, `role="tooltip"`
  + `aria-describedby`, stays inside the window, max ~320 px wide.
- One helper `setTip(el, text)` replaces the ~27 `title` setters in `app.js`
  (all already fed from the API's `*_help` wording) and the 3 static `title=`
  in `index.html`.
- Moves into tooltips: file paths (misfits, moved-by-hand), the lock notice's
  computer name and start time, the settings-file path, the editor's routing
  rules summary, form blurbs in the new-return dialog, dialog help paragraphs
  (`.wiz-note` / `.rem-hint`) that are explanations rather than warnings.
- Stays visible (never hover-only): anything that warns before a risky act,
  errors, and the dirty-state "unsaved changes" bar.
- Positioning uses `element.style.setProperty` (allowed under the page's CSP, as
  the tour already does); no inline `style=`, no `innerHTML`.

### 6. Safety badge (four rule cards → start-up strip)
- At launch a slim strip shows "🛡 4 safeguards on" with the four headlines; it
  fades after ~8 seconds or at the first click, and collapses into a small shield
  icon in the top bar. Hovering or focusing the shield shows the four rules
  word for word. The four-block markup stays in `index.html` (pinned by
  `tests/test_single_source.py`), just inside the badge's pop-up.
- My choice, stated: the shield stays so the rules are always one hover away,
  rather than vanishing completely.

### 7. Banners
- One notice area at the top of the right pane. Success messages fade after
  ~6 seconds; failures and warnings stay until dismissed (decision 193 unchanged).
- Room-short, misfit folders and lock notice become one-line notices with
  details in tooltips.

### 8. Plain English everywhere
- Rules for every sentence on screen: ≤ 20 words, everyday words, active voice,
  one idea per sentence, no internal terms ("manifest", "engagement", "pass",
  "record", request codes like A01) — say "return", "sort", "request list".
- The words live in Python, not the screen code: `_vocab()` in `tracker/api.py`
  (~lines 1156-1590) and constants in `tracker/manifest.py` (`STATUS_LABELS`),
  `tracker/reminder.py` (`SIDES`), `tracker/view.py`, `tracker/records.py`,
  `tracker/__init__.py` (`STANDING_RULES`). Docs that quote them (README,
  CLAUDE.md, `docs/ROADMAP.md`, `docs/runbook.md` status table) change in the
  same commit; `tests/test_single_source.py` keeps them matched.
- The SPEC carries a **wording table** (every sentence: today → proposed) that
  Jason approves before anything is built, as with the terms (P20) and tour copy (P22).
- Not reworded: the client reminder letter body (decision 197; it is an email
  to clients, not screen text) unless Jason adds it.

### How this answers the 0.2 tester feedback (`HANDOFF.md`)
- 1, firm-wide client list: the sidebar tree and its **All clients** page.
- 2, too many buttons: the top bar's 3 buttons and the ⋯ More menu.
- 3, no tooltips: the custom tooltip on every control, words from the API.
- 4, Status inside the app as the landing page: **All clients**.
- 5, terms wording: one row of the wording table, Jason's text to approve.

### Other ideas for Jason to accept or drop in the SPEC review
- Sortable table columns (click a heading), like the screenshot's arrow.
- A "compact / comfortable" row-height switch.
- Dark mode (the app has none today; P31 deferred it).
- Collapse the request-list editor's routing columns under one "Advanced" switch
  (already partly folded per row by decision 201).

## How the work is split (each item is its own fresh session)

Parallel choice: **Build E3 (wording, Python files) runs alongside E1 → E2
(screen files)**, because they touch different files; E1 and E2 stay in order
because both rewrite `index.html`, `style.css` and `app.js`.

1. **SPEC** — opus, high effort. Writes `pilot/SPEC-ui.md` (new file, like
   `pilot/SPEC-glass.md`), decision rows **P51** (supersedes P10 and the "only
   four lines of index.html" rule of SPEC §2/§3 for this work; records "port to
   the main tracker later") and further P-rows for the tooltip reversal of
   decision 200, the safety badge and the plain-English rules. Includes the
   wording table and a clickable mock-up with **made-up names only**, shown to
   Jason in the cloud's Chromium with a stubbed tracker (Build B's method), as a
   private artifact. Jason approves layout and wording before any build.
2. **Build E1** — sonnet. `tooltip.js`, colour/spacing tokens in `style.css`,
   top bar + ⋯ More menu, safety badge, banner consolidation, technical details
   into tooltips.
3. **Build E2** — sonnet, after E1's review passes. Sidebar tree, tabs, 4-column
   requests table, row sentence into tooltip, tour anchor updates in
   `app/renderer/pilot-content.js` (`eng-select` and card anchors move).
4. **Build E3** — sonnet, in parallel. Plain-English wording in the Python
   constants and the docs that quote them, per the approved table; tour copy
   lines stay ≤ 30 words (`tests/test_pilot.py`).
5. **Review** after each build — opus, high effort, separate session; numbered
   findings against the SPEC; rebuild/review loop per Jason's rules.
6. **Windows check** — `pilot\wintest\run_checks.ps1 -Tests <named files>` plus
   hands-on: click through sidebar, every tab, every tooltip by mouse and by Tab
   key, the More menu, the start-up badge, a Sort & Scan.
7. **Port to the main tracker** — a later, separate job in that repository.

Each session ends by updating `pilot/HANDOFF.md` and `pilot/DECISIONS.md`.

## Critical files

- `app/renderer/index.html`, `app/renderer/app.js`, `app/renderer/style.css`
- new `app/renderer/tooltip.js` (loaded after `app.js`, before `pilot.js`)
- `app/renderer/pilot-content.js`, `tour.js` (anchors only)
- `tracker/api.py` (`_vocab()`), `tracker/manifest.py`, `tracker/reminder.py`,
  `tracker/view.py`, `tracker/records.py`, `tracker/__init__.py`
- `README.md`, `CLAUDE.md`, `docs/ROADMAP.md`, `docs/runbook.md`,
  `docs/repo-map.curated.json` (new tooltip module), `pilot/Tester Guide.md`
- Reused as is: `showReturn` / `select` / `renderFor` (app.js ~290-339, 2259),
  `openDialog` / `requestClose` / `DIALOGS` (app.js ~3700-3810), `applyVocabulary`
  (app.js 2107), `sideLine` (app.js 106), `requestTableRow` (app.js 319).

## Tests that will change on purpose

- `tests/test_single_source.py` ~3594-3608 (side sentence "never a tooltip") —
  inverted, citing the new P-row.
- `tests/test_tour.py` — anchors follow the new ids.
- `tests/test_api.py` — button-order and markup pins updated to the menu.
- New tests: every `data-tip` text comes from the API's words (renderer types
  none); tooltip shows on focus; no `title=` left in renderer files; the four
  safety-rule blocks still present.

## Verification

- Affected tests only, both Python versions (floor and office): `test_single_source`,
  `test_api`, `test_tour`, `test_pilot`, `test_row_columns`, `test_layers`,
  `test_repo_map`, `test_tripwire`, `test_errors`, plus the new tooltip tests;
  each file as its own process.
- `python -m ruff check .`, `python tools/repo_map.py update` then `check`.
- Screenshots in the cloud's Chromium with a stubbed tracker of: household
  overview, each tab, a tooltip open by mouse and by keyboard, the start-up
  badge before and after it fades, the More menu.
- The Windows check in step 6 before the pull request is marked ready.
- Nothing in this work reads a client document or adds any network call;
  `tests/test_layers.py::test_the_app_has_no_network_call` still passes.
