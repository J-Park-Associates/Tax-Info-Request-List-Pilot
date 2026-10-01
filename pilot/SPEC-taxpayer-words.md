# "Client" becomes "Taxpayer" on screen - SPEC (P196)

Stacked on the firm-columns branch (P194, P195; tip `61901ba`), branch
`claude/taxpayer-words`. Jason's words (P196, 2026-09-30): "Lets change
client to "Taxpayer" across the entire app"; then: the folders keep their
names; the emails: screens only; the Clients page: "Households".

## 0. What changes, in plain English

Every word the app's window shows staff that said "Client" now says
"Taxpayer" where it means the person, and "Household" where it means the
household the app lists - the page Jason named **Households**, its menu, its
links and its search box. The folders on disk, the reminder letters, the
firm's standing rules and the pilot terms keep their words. No code name,
stored value or record field changes.

## 1. Rulings and their reasons

| # | Ruling | Reason |
|---|---|---|
| R1 | Where "client" means **the person** who owes the documents, the screen says **Taxpayer**: Waiting on Taxpayer(s), Ask the Taxpayer, Taxpayer (Greeting Name), Taxpayer Confirmed Final Version, No Taxpayer Name Found, Sorts What Your Taxpayers Send, the editor's Taxpayer field. | Jason's ruling, word for word (P196). |
| R2 | Where "client" means **a household** - the page that lists households, its menu item, its footer noun and empty line, its name column, the household link's tooltip, the menu that acts on the open household, the search box (which finds households and returns) and the grey Sort tooltip on a firm page ("open one first") - the screen says **Household**. Owner question Q3; built as recommended. | Jason named the page "Households", not "Taxpayers": a row there is a household (Okafor Family), not a person. The menu, link and search that act on that row say the same word, so one thing has one name. |
| R3 | A label that **names a folder on disk** keeps "Client(s)": Change Clients Folder…, Open Clients Folder, Open Client Folder, Choose Your Clients Folder, Settings' Clients Folder, the tour's One Clients Folder / Choose One Clients Folder. Owner question Q4; built as recommended. | The folders keep their names (P196): the tree is `Clients`, and the firm's own root is often named so (`G:\Shared drives\Clients`). The button and File Explorer then say the same word. |
| R4 | The firm's **standing rules** and the **pilot terms** keep "client". Owner question Q1; built as recommended. | They speak of the firm's real clients and their documents, not of a screen; the rules are one text held equal across the README, roadmap, CLAUDE.md and the map (`tests/test_single_source.py`), and changing the terms' words would ask every tester to accept them again. |
| R5 | The side panel's **Client Types** becomes **Taxpayer Types**. Owner question Q2; built as recommended. | Individuals, Businesses, Trusts & Estates and Nonprofits are kinds of taxpayer; every one files its own return. |
| R6 | The **reminder drafts** keep their words, letter and staff footer alike; every drafted line that says "client" is listed in section 5 for Jason, one by one (Q5). | Jason: "Screens only". The letter itself never says "client". |
| R7 | **No code identifier, key, stored value, record field, CSS class or test name changes.** The vocabulary keys stay `clients`, `client_name`, `navigate_client`, `client_types`; the stored override reason stays "Client confirmed this is the final version" (P78: only its label changes); the record's field stays `client` with its label "Client" in the files the record writes (the README, the workbook). | P196: "Code names are not renamed." A key rename would touch every test and the wire for no word anyone sees. |
| R8 | Words that no longer fit get **shorter words, not a wider box** (P180 Q9). The search box's placeholder drops "Search" (the magnifier and its tooltip, Find a Household, say it). | "Search Households and Returns" measures 203 px and "Search Files, Households and Returns" 236 px against the box's 198 px of text room; the old Needs Review placeholder (205 px) was already cut by 7 px, and this fixes it. |
| R9 | Files the app writes but does not show in its window - the Firm Report page's "Client" column (`runner.py`), the index workbook's "Client's Subfolder" column and the record's "Client" field (`records.py`), the CLI's "Client inbox:" (`scaffold.py`), the error log's sentences - are **not in this change**. | They are not the app's screen; each is a file a person or a client may read elsewhere, and two of them are the engine's (no engine tests rerun for a word). Listed for a later decision if Jason wants them (section 8). |

## 2. Every change, old words -> new words

Line numbers are on the base `61901ba` (each edit is one line, so they hold).

### 2.1 The vocabulary (`tracker/api.py`)

| Line | Key | Old | New | Rule |
|---|---|---|---|---|
| 939 | `ASK_THE_CLIENT` (`vocab.ask_the_client`) | Ask the Client | Ask the Taxpayer | R1 |
| 1206 | `OVERRIDE_LABELS[0]` | Client Confirmed Final Version | Taxpayer Confirmed Final Version | R1 (label only; R7) |
| 1223 | `MENU.client` | &Client | H&ousehold | R2 (Alt+O: H is Help's) |
| 1237 | `MENU.clients` | Clients | Households | R2 |
| 1275 | `screen.sections.clients` | Clients | Households | P196 |
| 1284 | `screen.navigate_client` | Navigate to Client | Navigate to Household | R2 |
| 1287 | `screen.find` | Find a Client | Find a Household | R2 |
| 1291 | `screen.find_placeholder` | Search Clients and Returns | Households and Returns | R2, R8 |
| 1292 | `screen.find_placeholder_files` | Search Files, Clients and Returns | Files, Households and Returns | R2, R8 |
| 1296 | `screen.sort.firm` | Open a Client to Sort | Open a Household to Sort | R2 |
| 1310 | `screen.figures.waiting` | Waiting on Clients | Waiting on Taxpayers | R1 |
| 1344 | `screen.paging.nouns.clients` | Clients | Households | P196 |
| 1354 | `screen.side.types` | Client Types | Taxpayer Types | R5 (Q2) |
| 1397 | `screen.columns.client_name` | Client Name | Household Name | R2 |
| 1406 | `screen.empty.clients` | No Clients Yet | No Households Yet | P196 |
| 1428 | `screen.groups.waiting` | Waiting on Client | Waiting on Taxpayer | R1 |
| 1992 | `editor.engagement_fields[client].label` | Client | Taxpayer | R1: a new `EDITOR_LABELS` beside it overrides the record's label for the editor only (R7) |

### 2.2 The engine's one drawn word (`tracker/reasons.py`)

| Line | Key | Old | New |
|---|---|---|---|
| 827 | `SHORT_REASONS["name-absent"]` | No Client Name Found | No Taxpayer Name Found |

### 2.3 The renderer and the window

| File:line | Old | New |
|---|---|---|
| `app/main.js:487` (menu default, held equal to `api.MENU`) | &Client | H&ousehold |
| `app/main.js:501` | Clients | Households |
| `app/renderer/index.html:390` (new return, field label) | Client (Greeting Name) | Taxpayer (Greeting Name) |
| `app/renderer/pilot-content.js:83` (tour, step 1) | Sorts What Your Clients Send | Sorts What Your Taxpayers Send |

No word is typed in `pages.js`, `shell.js`, `app.js` or `sheet.js`: they draw
the vocabulary. Their code names (`pagesClients`, `pagesClientType`,
`shellHasClient`, the `clients` level) stay (R7).

## 3. What stays, and why

- **(b) Folders, files and path pieces:** the `Clients` tree and
  `layout.CLIENTS_TREE`, `Drop files here`, `client_household_dir`, every
  path and the folder labels of R3. The misfit reasons (Unowned Folder,
  Look-Alike Folder) never said "client".
- **(c) The reminder drafts:** every line, section 5 (R6).
- **(d) Code:** every identifier, vocabulary key, JSON field (`client`,
  `client_folder`, `clients_root`), CSS class (`clients-bar`), route level
  (`clients`), test name, and the stored override reason (R7).
- **(e) The standing rules** (`STANDING_RULES` in `tracker/__init__.py` and
  its copies) and **the pilot terms** (`pilot-content.js` `terms`): R4, Q1.
- **Sentences that reach only the error log or the command line** (the
  long `reasons.py` sentences, "Clients folder problem: ...", "Tell the app
  where your clients live first ...", the sharing lines, the cut help
  lines): not drawn (SPEC-shell 11.1); R9.

## 4. Files, functions and owning tests

| File | Change | Owning tests |
|---|---|---|
| `tracker/api.py` | 2.1; new `EDITOR_LABELS` | `tests/test_api.py` (pins `navigate_client`; Title Case of every drawn word) |
| `tracker/reasons.py` | 2.2 | `tests/test_reasons.py` |
| `app/main.js` | 2.3 | `tests/test_shell_menu.py` (main.js's menu equals `api.MENU`) |
| `app/renderer/index.html`, `pilot-content.js` | 2.3 | `tests/test_shell.py`, `tests/test_tour.py`, `tests/test_pilot.py` |
| `tests/test_shell.py` | its vocabulary mirrors and the pinned placeholders and link words say the new words | itself |
| `pilot/harness/interact.mjs` | its expected words (Households, the tour line, Waiting on Taxpayer, Navigate to Household, Find a Household) | not run on this PC (Playwright absent, as for firm-columns) |
| docs (section 7) | the lines that quote the screen | `tests/test_single_source.py` |

Guards: `tests/test_layers.py`, `tests/test_single_source.py`,
`tests/test_repo_map.py`; `tests/test_tripwire.py` only if a test's file
access changes (it does not); `tests/test_errors.py` only if error wording
changes (it does not).

## 5. Owner questions (each answerable by a letter; the recommendation is built)

- **Q1. The standing rules and the pilot terms say "client" ("No generative
  AI ever reads a client financial document"; "Back up a Client's folder").
  Change them?** A) keep "client" there - they speak of the firm's real
  clients and their documents, the rules are one text kept equal in five
  places, and new terms words would ask every tester to accept again
  (**recommended, built**); B) say "taxpayer" in both (the terms' version
  goes up, so each tester accepts again); C) the rules keep, the terms change.
- **Q2. The side panel's "Client Types" (Individuals, Businesses, Trusts &
  Estates, Nonprofits).** A) **Taxpayer Types** (**recommended, built**);
  B) Household Types; C) Return Types; D) keep Client Types.
- **Q3. Where "client" meant a household - the menu that acts on the open
  household, the household link's tooltip, the search box, "Open a Client to
  Sort" - which word?** A) **Household**, the word of the page Jason named
  (**recommended, built**): menu **Household** (Alt+O), "Navigate to
  Household", "Find a Household", "Households and Returns", "Open a Household
  to Sort", the Households page's column "Household Name"; B) Taxpayer
  throughout (menu "T&axpayer", "Navigate to Taxpayer", "Find a Taxpayer",
  "Taxpayers and Returns", "Open a Taxpayer to Sort", "Taxpayer Name").
- **Q4. Buttons that name a folder on disk ("Open Client Folder", "Change
  Clients Folder…", "Choose Your Clients Folder").** A) keep "Client(s)", so
  the button says the folder's own name in File Explorer (**recommended,
  built**); B) "Taxpayer(s) Folder" on screen while the folder stays
  `Clients`.
- **Q5. Drafted reminder lines that say "client".** None is in the letter
  the client reads; all are in the **staff footer** below the cut line, which
  a person deletes before sending. Answer each A) keep (**recommended,
  built**) or B) say "taxpayer":
  - Q5.1 `reminder.SIDE_US.sentence`: "US - Waiting on us, not the client;
    the letter does not ask for it." (`tracker/reminder.py:292`)
  - Q5.2 `reminder.REVIEW_WARNING`: "{n} file(s) the client already sent are
    still in 00 - Needs Review." (`tracker/reminder.py:353`)
  - Q5.3 The firm-side reasons quoted under Q5.1's heading, each ending
    "- never the client" (`tracker/reasons.py:114, 309, 349, 363, 379, 393,
    408, 421, 436, 451, 462, 634, 672, 687`), and "ask the client ..." in the
    reasons at `:166, 196, 215, 647`.
  - The refusals "held - ... the client ..." (`tracker/reminder.py:302, 308,
    316, 320, 342`) are not in a draft: a held draft is not written, and
    they reach the run log and the command line only. Listed for
    completeness; kept.

## 6. What staff will notice

- The side panel's fourth page is **Households** (Ctrl+4), and its list's
  name column **Household Name**; its footer says "Showing 1-25 of 300
  Households"; empty, "No Households Yet". The path row starts at Households.
- The menu bar reads File, Edit, **Household**, View, Tools, Help; View ›
  **Households**.
- Overview's middle figure reads **Waiting on Taxpayers**; a return's blue
  group **Waiting on Taxpayer**.
- The search box reads **Households and Returns** (Needs Review: **Files,
  Households and Returns**), its tooltip **Find a Household**; a household
  name's tooltip **Navigate to Household**; the grey Sort icon on a firm
  page **Open a Household to Sort**.
- The side panel's heading **Taxpayer Types**.
- New return: **Taxpayer (Greeting Name)**; the request list's heading ends
  **Ask the Taxpayer**; the editor's field **Taxpayer**; its override reason
  **Taxpayer Confirmed Final Version** (records already saved keep their
  stored words and show the new label).
- Needs Review's reason **No Taxpayer Name Found**.
- The tour's first line **Sorts What Your Taxpayers Send**.
- Unchanged: the folder buttons, the Clients folder on disk, the letters, the
  terms and Help › Safeguards.

## 7. Docs made true in the same commit

- `README.md:115, 125, 516` - the Household menu; the four pages end
  Households.
- `docs/runbook.md:297-298, 410, 1155, 1219, 1227, 1230` - the Household
  menu; "marked on Households"; the four pages; "open a household first".
  (Not lines 36-50, the parallel builder's.)
- `pilot/wording-shell.tsv` - the rows of 2.1-2.3 (existing rows updated,
  rows the table lacked added, each noting P196).
- `pilot/HANDOFF.md` - the top status line.
- `pilot/SPEC-shell.md` 11.1 and `pilot/SPEC-lists.md` 15 - a one-line
  pointer here.
- `docs/repo-map.curated.json` - the shell.js and pages.js notes say
  Taxpayer Types and Households; then `python tools/repo_map.py update`.
- `pilot/DECISIONS.md` P196 - status.

## 8. Left for later (not built)

- R9's files (the Firm Report column, the workbook column, the record's
  field label in the README, the CLI line), if Jason wants "Taxpayer" there
  too. The Firm Report and the workbook are the engine's, and their tests
  would run.
- The rendered 1100 px check of the new words (`pilot/harness/interact.mjs`):
  Playwright is not on this PC; the Windows check runs it.

## 9. Fit at the 1100 px window

Measured in the Windows font with GDI+ (as the firm-columns build did); the
figures are in the hand-back. Every longer word fits its box at 1100 px; the
search placeholder is the one that did not, and R8 shortens it. No column
width, token or layout changes, so the firm-columns sum (832 px <= 843 px)
is unchanged.
