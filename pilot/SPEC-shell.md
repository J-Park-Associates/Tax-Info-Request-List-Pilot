# Pilot 0.2 - the app shell - SPEC

Status: **for Jason's approval** (2026-09-29). Nothing is built. Written by
the SPEC session (opus, high effort) from the confirmed brief
[`BRIEF-shell.md`](BRIEF-shell.md), the audit [`AUDIT-shell.md`](AUDIT-shell.md),
[`../PRODUCT.md`](../PRODUCT.md), decisions P50-P66 and the parts of
[`PLAN-ui.md`](PLAN-ui.md) (sections 5-8) and [`SPEC-ui.md`](SPEC-ui.md)
(tokens and buttons) that still stand. New decision rows: P67-P78
([`DECISIONS.md`](DECISIONS.md)). The clickable mock-up (made-up names only)
is a private artifact; its link is in [`HANDOFF.md`](HANDOFF.md) and its
source is [`mockup-shell.html`](mockup-shell.html) (open it in a browser).

> **Amended by rulings 1-13 (2026-09-29).** Jason's rulings on the build
> (`pilot/handoffs/shell-rulings.md`, rows 1-13; later rows win over
> earlier) and the proposals the finished builds made (S1, S2, S3, S4, S7)
> are folded in below. Where this SPEC's older text and a ruling
> disagreed, the ruling won. Sections changed:
>
> - **1** - the vendored Floating UI files and the load order (ruling 5);
>   the fallback error log and the agent deny list (ruling 4).
> - **3.9** (new) - links: file names open File Explorer, household and
>   return names navigate, return links carry their year, no path is ever
>   shown (rulings 8, 9, 11, 12, 13).
> - **4.3** - the menu bar stays hidden until Alt (ruling 3); the tour's
>   and the terms' own keydown listeners (ruling 1).
> - **5.1, 5.2** - item words in Title Case (ruling 10).
> - **5.5** - Open Error Log opens the fallback log; the fallback log
>   (ruling 4); the failure's on-screen text (ruling 6).
> - **5.7** (new) - `open-path`'s reveal option and the openable keys of
>   working copies (rulings 8, 12).
> - **6** - the pages draw the three link kinds and "{Return Name} ({Year})";
>   the diagrams follow Title Case and "Could Not Sort" (rulings 8-13).
> - **8.5** - the tooltip: Floating UI placement, 300 ms hover, focus on
>   every control but the search box, hidden when its control scrolls out
>   of view (rulings 2, 5, 7).
> - **9.2, 9.3** - `year` on the `firm` rows, `files[]`' fields, "Could Not
>   Be Read" (ruling 13; S1).
> - **11.1-11.6** - Title Case, the rule and every word table (ruling 10);
>   "Could Not Sort" (ruling 8); the no-error-log line (rulings 4, 6); the
>   three link tooltips (rulings 11, 12).
> - **12** - tour step titles in Title Case, "Needs Review" (rulings 8, 10).
> - **14.1, 14.2** - the accepted keydown exception (ruling 1); the tooltip,
>   fallback-log and Title Case tests.
> - **16** - S7 and S8a in the build table; the Windows check's added steps.
> - **19** (new) - open for Jason.
> - **Rulings 15-29 (2026-09-29 and 30), added by the fix pass:**
>   **3.5, 8.4** - the failed-sort notice has no button and clears with the
>   record (rulings 20, 28); **3.6, 6.4** - a return's or household's row
>   wraps (rulings 21, 27); **3.9, 6.7** - an email or zip is plain text
>   (ruling 24), several files under one request each get their own row
>   (ruling 17); **5.2** - Unfile and Mark Missing open a small confirm box
>   (ruling 16); **6.2, 9.2** - firm Needs Review names are links
>   (ruling 15); **6.4, 9.2** - the paused marker (ruling 21); **6.7, 8.4** -
>   a failed sort says "Sort Failed: {reason}" (rulings 25, 29);
>   **11.4** - the Folders Skipped reasons (rulings 18, 18a) and the
>   approved notice words (rulings 14, 23).
>
> The decision rows for these rulings are S6's to number and log; this SPEC
> names rulings by their row in `shell-rulings.md`.

Two things needed Jason before any build (section 15). Both are settled:
the engine part is approved (P79) and the wording is approved (P84).

1. **The wording table** (section 11 and [`wording-shell.tsv`](wording-shell.tsv)),
   as P66 requires.
2. **The engine part** (section 9): one new read-only API command, `firm`,
   that gives the Overview its counts. The firm view cannot be drawn
   without it, and PRODUCT.md says a change that reaches `tracker/` needs
   its own SPEC and Jason's yes. Section 9 is that SPEC.

## 0. What changes, in plain English

Today the app is one long page: ten buttons in a navy bar, a return picker,
then up to nine stacked cards and four safety cards at the bottom. After this
work:

- A **side panel** on the left lists four firm sections - Overview, Needs
  review, Reminders, Clients - with a count beside the two that hold work.
  Its foot says when the last sort ran.
- The top of the page is a **path**, like File Explorer's address bar:
  Clients › Smith Family › 2025 › 1040 - John & Jane Smith. Every part is
  clickable. At its right end sit a **search box** and the **sort icon**,
  the only button always on screen.
- Each level has **one page**. A return's page is one list in four groups:
  Needs you, Waiting on client, Received, and Set aside (folded shut).
- A row's one next step (**Check**, **Draft reminder**, **Open**, **Edit**)
  shows when the mouse is over the row or the keyboard is on it. Checking a
  file or drafting a reminder opens a **side sheet** from the right.
- Everything else moves to a real **menu bar** (File, Edit, Client, View,
  Tools, Help) and to the **right-click menu**, which is the same menu.
- Every word on screen is **five words or fewer** and no path is ever shown.
- The app follows Windows' **light or dark** setting.

The filing engine does not change. No document is read differently, no
status is computed differently, and nothing is sent.

## 1. Where it lives (P67)

This work edits the pilot's copy of the original's renderer files, as
PLAN-ui's "pilot now, port to the main tracker later" allowed. README rule 1
(small, named differences) is set aside for the files and lines this SPEC
names, and for no others.

| File | Change |
|---|---|
| `app/main.js` | Menu bar and right-click menus built from the API's words (section 5); the `menu` channel; first-paint colour follows light/dark; opens the error log. `Menu.setApplicationMenu(null)` goes (P58). |
| `app/preload.js` | One channel, `menu`, both directions (section 5.4). Nothing else crosses. |
| `app/renderer/index.html` | New skeleton (section 3.1). Removed: the top bar, the return picker, every card, every banner, the assurances footer. Kept: the dialogs, with their help lines cut. Added: the side sheet, the tooltip, three small dialogs (Roll forward, Safeguards, About) and the folders-skipped dialog. |
| `app/renderer/app.js` | Keeps the API call, vocabulary, notices, dialogs, editor, wizard, schedule and every action. Loses the card renderers, the review deck and the return picker (section 13, the function table). |
| `app/renderer/shell.js` **new** | Side panel, path, search, sort icon, routing, keyboard map, the menu channel, right-click requests. |
| `app/renderer/pages.js` **new** | The pages (section 6), the row and group components, their states. |
| `app/renderer/sheet.js` **new** | The side sheet: Check a file, Draft reminder. |
| `app/renderer/tooltip.js` **new** | The custom tooltip (PLAN-ui section 5, words capped by P63): its timing, focus, Esc and `role=tooltip` logic; placement by Floating UI (8.5). |
| `app/renderer/vendor/floating-ui/` **new** (ruling 5) | `@floating-ui/dom` 1.8.0 and `@floating-ui/core` 1.8.0 (which has `@floating-ui/utils` 0.2.12 compiled in), MIT, vendored **unedited** as two UMD files, `floating-ui.core.umd.min.js` and `floating-ui.dom.umd.min.js`, with the three licence files and a README naming the versions, the registry integrity and every file's SHA-256. A test pins each file's SHA-256 (decision 191's habit). No CDN, no runtime `npm` install, `app/package.json` untouched. Tippy.js is not used (built on Popper.js, about 2 MB, last released 2021). |
| `.claude/settings.json` (ruling 4) | The agent deny list gains the fallback error log (5.5): `Read` and `Edit` of `…/AppData/Local/Tax Document Tracker Pilot/error.log` and `error.log.*`, and the same under `~/.config/` off Windows; pinned by `test_the_agent_deny_list_names_the_data_home_and_every_file_that_names_a_client`. |
| `app/renderer/shell.css` **new** | Layout and components of the new markup. Tokens only: no colour, size or step written outside `pilot-ui.css`'s `:root` blocks. |
| `app/renderer/pilot-ui.css` | Tokens gain dark values and purpose names (section 10); grid steps become 4/8/16/24/32/48; rules for removed elements are deleted. |
| `app/renderer/style.css` | **Not edited.** Its rules for removed elements simply match nothing. Its literal colours that still apply are overridden in `pilot-ui.css`'s dark block (section 10.4). |
| `app/renderer/pilot.js`, `tour.js`, `pilot-content.js` | Badge moves to the side panel's foot; the Tour button goes (Help menu); tour anchors follow the new ids; tour lines are five words (section 12). |
| `app/renderer/pilot-style.css` | Badge styles for its new place; nothing else. |
| `tracker/api.py`, `tracker/reasons.py`, `tracker/reminder.py`, `tracker/__init__.py`, `tracker/manifest.py` (wording only, P66) | Words rewritten per the approved table; new vocabulary blocks `menu` and `screen`; a short label per reason code; four short safeguard lines. |
| `tracker/api.py` (section 9, **needs Jason's yes**) | The `firm` read command; `group` on each item of `state`; `paths` on `list`. |
| `pilot/harness/` **new** | The stubbed page for screenshots in the cloud's Chromium (section 14.4). Never loaded by the app. |

Load order in `index.html` (all `'self'`, CSP unchanged):
styles `style.css`, `pilot-ui.css`, `shell.css`, `pilot-style.css`;
scripts `vendor/floating-ui/floating-ui.core.umd.min.js`,
`vendor/floating-ui/floating-ui.dom.umd.min.js`, `app.js`, `tooltip.js`,
`pages.js`, `sheet.js`, `shell.js`, `pilot-content.js`, `pilot.js`,
`tour.js`. The two vendor files sit directly above `app.js` (core, then
dom), so nothing parser-blocking lies between `app.js` and `shell.js`; they
depend on nothing and still load before `tooltip.js`, which reaches them
only through the one global `FloatingUIDOM`. Every `<script src>` is a file
of the app (no scheme, no `//`). The new scripts are classic
scripts, as `app.js` is: they share its globals and add their own, each
named for what it does. No module loader, no bundler, no package beyond
the vendored files.

## 2. Every element of today's screen, and where it goes

Verdict words: **Kept** (on screen, reworded to five words), **Tooltip**
(one hover away), **Client menu** (menu bar Client and the right-click menu),
**Menu bar** (another menu), **Sheet** (the side sheet), **Dialog**,
**Notice** (the one notice area), **Page** (a page of section 6),
**Removed**. The words are the audit's; section 11 is the full table.

### 2.1 Window, top bar, side panel

| # | Today (id) | Verdict | New home | On screen |
|---|---|---|---|---|
| E1 | Window title | Kept | Windows' title bar | product name |
| E2 | `header.topbar` navy bar | Removed | - | - |
| E3 | Logo `img.brand-logo` | Kept | `#side-brand`, a navy band at the side panel's top | (image) |
| E4 | `#brand-product`, `.brand-divider` | Removed (the title bar names it) | - | - |
| E5 | Pilot badge `#pilot-badge` | Kept | side panel foot, caption | "Pilot 0.2" |
| E6 | Tour button (pilot.js) | Menu bar | Help › Take the tour | - |
| E7 | Return picker `#eng-select` | Removed (the path and pages replace it) | - | - |
| E8 | Form chip `#eng-form` | Removed (the return's name starts with its form) | - | - |
| E9 | View-state chip `#view-state` | Removed (the report is in a menu) | - | - |
| E10 | `#btn-new-household` | Menu bar | File › New household… (Ctrl+N); also the Clients page's empty state | - |
| E11 | `#btn-inbox` | Client menu | Client › Open inbox | - |
| E12 | `#btn-client-folder` | Client menu | Client › Open client folder | - |
| E13 | `#btn-repair-schedule` | Menu bar | Tools › Repair schedule | - |
| E14 | `#btn-edit` | Client menu | Client › Edit request list… (Ctrl+E) | - |
| E15 | `#btn-schedule` | Menu bar | Tools › Schedule… | - |
| E16 | `#btn-view` (this return's page) | Removed (the return's page shows it live) | - | - |
| E17 | `#btn-status` (firm page) | Menu bar | Tools › Firm report | - |
| E18 | `#btn-scan` Sort & Scan | Kept, as an icon | `#sort` at the path row's right end; F9 | tooltip "Sort now" |
| E19 | `#btn-stop-pass` | Merged into E18 | `#sort` shows a stop icon while sorting | tooltip "Stop sorting" |
| E20 | `#pass-progress` | Kept, one line | `#last-sort` at the side panel foot | "Sorting 3 of 40" |
| E21 | (new) side panel sections | Kept | `#side-sections` | Overview, Needs Review, Reminders, Clients |
| E22 | (new) search | Kept | `#find` in the path row; Ctrl+F | tooltip "Find a client" |

### 2.2 Notices and messages

| # | Today (id) | Verdict | New home | On screen |
|---|---|---|---|---|
| E23 | `#after-install` banner and its list | Notice, only on failure; the list to the error log | `#notices` | "Setup needs attention" |
| E24 | `#notices` failure notices | Kept | `#notices` at the top of the page area | e.g. "Sort failed" |
| E25 | Notice buttons Retry / Look again / Dismiss | Look again merged into Retry; Dismiss becomes the close icon | notice | "Retry", close icon |
| E26 | `#banner` result banner | Removed (P63 rule 6); toast only when the effect is off screen | `#toast` | "Copied", "Saved" |
| E27 | "Clients folder set to…" | Removed | - | - |
| E28 | `#reader-warning` | Notice, no path | `#notices` | "Install folder name too long" |
| E29 | `#last-pass` banner | Kept, moved | `#last-sort` | "Sorted 6:00 AM" / "Sort failed" |
| E30 | `#machine-warnings` | Notice, one line each; details to the error log | `#notices` | e.g. "Drive not signed in" |
| E31 | `#lock-notice` with time, host, file | Notice, one line | `#notices` | "In use on {host}" |
| E32 | `#btn-unlock` Clear lock | Menu bar | Tools › Clear stuck lock (enabled only when stale) | - |
| E33 | Toasts (long) | Kept, shortened | `#toast` | e.g. "Pick a request first" |
| E34 | `#misfits-card` fold with paths | Notice with a count; **Show** opens a dialog of folder names | `#notices`, `#misfits-modal` | "3 folders skipped" |
| E35 | `#room-card` | Notice; the rows say it too | `#notices` | "Names shortened to fit" |

### 2.3 First run

| # | Today (id) | Verdict | New home | On screen |
|---|---|---|---|---|
| E36 | `#setup-card` heading and summary | Page; sentence cut | the setup page in `#page` | "Choose your clients folder" |
| E37 | `#root-input` path box, example path | Removed from view; a hidden input keeps the value | setup page | the folder's name only |
| E38 | `#btn-browse`, `#btn-save-root` | Merged: one picks, one starts | setup page | "Choose folder…", "Start" |
| E39 | Firm name, phone and help lines | Labels kept, help cut | setup page | "Firm name", "Firm phone" |
| E40 | `#setup-note` | One line, no path | setup page | "Folder not found" |

### 2.4 Household (was `#household-card`)

| # | Today (id) | Verdict | New home | On screen |
|---|---|---|---|---|
| E41 | `#household-heading` label | Removed (the path says it) | - | - |
| E42 | `#household-name` | Kept | Household page H1 | (name) |
| E43 | Members / contact / link, each with help | Edit household dialog; one caption on the page | household page caption | "Contact John Smith" |
| E44 | `#household-shared` + Mark as shared | Caption; action to Client menu | caption; Client › Mark as shared | "Shared" / "Not shared" |
| E45 | `#household-checklist` with paths | Removed (the Tester Guide carries it) | - | - |
| E46 | `#household-two-years` | Notice | `#notices` | "Two years open" |
| E47 | `#household-paused` + Accept | Notice with one action | `#notices` | "Folder renamed" · "Accept" |
| E48 | `#household-returns` buttons | Page rows | household page | (return name) and its count |
| E49 | `#household-queue` sentence | Removed (the counts say it) | - | - |
| E50 | `#household-roll` fold | Client menu › Roll forward…, a dialog | `#roll-modal` | "Roll forward" |
| E51 | `#household-feeds`, `#household-fed-by`, `#household-feeds-unresolved` | Edit household dialog | `#household-modal` | - |
| E52 | `#btn-edit-household`, `#btn-add-return`, `#btn-mark-shared` | Client menu | Client › … | - |

### 2.5 Return (was the requests, reminder, moved, review and filed cards)

| # | Today (id) | Verdict | New home | On screen |
|---|---|---|---|---|
| E53 | Requests heading, `#summary` | Removed (the H1 and group counts replace them) | - | - |
| E54 | Table header row, ID column | Removed | - | - |
| E55 | Per-row rule tooltip | Removed (the editor holds rules) | - | - |
| E56 | Period | Kept only when it differs from the return's year | row detail | e.g. "Dec 2025" |
| E57 | Files "1 / 2" | Kept only when partly in | row detail | "1 of 2" |
| E58 | Status chip + side word + sentence (`chip()`, `sideLine()`) | Merged: the group says who; the row keeps one status word in its colour | row status | e.g. "Could not use" |
| E59 | Override reason and notes tooltips | Removed (the editor holds them) | - | - |
| E60 | `#reminder-card` | Sheet, from the Waiting group | `#sheet` (reminder) | "Draft reminder" |
| E61 | Reminder stage names | Short names in the app; the letter keeps its own | sheet | "Heads up", "Checking in", "Deadline near", "Final notice" |
| E62 | `#reminder-hint`; `#reminder-edited` | Hint removed; edited is one caption | sheet | "Edited by hand" |
| E63 | `#btn-copy`, `#btn-approve`, `#btn-open-draft` | Copy and Approve kept; Open the draft file removed | sheet | "Copy", "Approve" |
| E64 | `#moved-card` rows with paths | Needs you rows | return page | "Moved by hand" |
| E65 | Put back / Keep here / Send to review / Mark Missing (moved) | Put back and Keep here kept; Send to review removed | sheet; right-click | "Put back", "Keep here" |
| E66 | `#review-card` heading, summary, `#review-mode` | Removed; rows in Needs you | - | - |
| E67 | `#review-deck` (one at a time) | Removed (the sheet's next arrow does it) | - | - |
| E68 | Bucket headings with descriptions | Group sub-headings only | return page | "Emails and zips", "Not documents" |
| E69 | "came from the client's subfolder…" | Removed | - | - |
| E70 | Review row: file name + reason | Kept, short | Needs you row | e.g. "Fits two requests" |
| E71 | Open review copy (twice) | One icon | sheet | open icon, tooltip "Open" |
| E72 | Request picker, Suggested / Other | Kept, suggestion pre-selected | sheet | "Suggested", "Other" |
| E73 | File it / Accept the suggestion | Merged | sheet | "File it" |
| E74 | Not requested | Kept | sheet; right-click | "Not requested" |
| E75 | File under another return / File it under {label} | One item in the sheet's More menu | sheet | "Another return…" |
| E76 | Reasons list | One line per suggestion | sheet | e.g. "Name and year match" |
| E77 | Issuer box (K-1) | Label and button only | sheet | "Issuer name", "Add issuer" |
| E78 | Keyword box, teach spelling, dismiss note | Folded under **More** in the sheet | sheet | "Keyword", "Spelling", "Reason" |
| E79 | Skip for now | The sheet's next arrow | sheet | next icon, tooltip "Next" |
| E80 | `#filed-card` rows, Unfile, Mark Missing | Received rows; actions by right-click | return page | "Unfile", "Mark Missing" |
| E81 | `#dismissed-card` (files set aside) | Set aside group | return page | "Not requested" |
| E82 | `#rows-set-aside-group` | Set aside group | return page | "Set aside" |

### 2.6 Safety text

| # | Today (id) | Verdict | New home | On screen |
|---|---|---|---|---|
| E83 | `#assurances` four cards | Dialog | Help › Safeguards, `#safeguards-modal` | four short lines (P64) |

### 2.7 Dialogs (kept; help lines cut per the audit, section 7)

| # | Dialog | Kept | Cut |
|---|---|---|---|
| E84 | Unsaved changes bar | "Unsaved changes", "Keep editing", "Discard" | the long sentence |
| E85 | `#household-modal` | Contact, Shared with, Inbox link, Also feeds; Cancel, Save; warning "Its members can drop here" | every help line |
| E86 | `#handover-modal` | Title "Another return", Return, Request, Cancel, File it | - |
| E87 | `#schedule-modal` | "Run automatically", "First run", "How often", caption "Next: 6:00 PM", Cancel, Save | the loading sentence (outline rows instead), "Scan works either way…" |
| E88 | `#modal` step 1 | "New household", Household, Contact, Shared with, Inbox link, warning "Shared members see documents", Cancel, Continue | second heading, intro, help lines, two of three Cancels |
| E89 | `#modal` step 2 | "Return type"; cards "1040 · Individual" | the blurb per card, the step note |
| E90 | `#modal` step 3 | "1040 requests", Back, Return name, Client, Tax year, Due date, People, ticks, "Add a request", "Create return" | form chip, duplicate warning, year note, the 31-word note, request IDs, rule summaries, custom rows' extension and keyword columns |
| E91 | `#editor` | Heading, Client, Inbox link, Due date, Filing deadline, Reminders, Active; Document, Count, Asked, Override, Reason, Short name; one **Advanced** switch; Cancel, Save | second heading, read-only fields, column help, per-row routing toggles, paste and rename hints, "left in the old folder…" |
| E92 | (new) `#roll-modal` | Title "Roll forward to {year}", the ticks, Cancel, "Roll forward" | intro, template note |
| E93 | (new) `#safeguards-modal` | Title "Safeguards", four lines, Close | - |
| E94 | (new) `#about-modal` | product name, "Pilot 0.2", Close | - |
| E95 | (new) `#misfits-modal` | Title "Folders skipped", one row per folder: name and two-word reason, Close | paths |

### 2.8 Pilot layer

| # | Today | Verdict | On screen |
|---|---|---|---|
| E96 | Terms screen | Exception (P63): shown once, whole | Jason's P20 text |
| E97 | Tour cards (does, strength, limit, fallback, stage chips) | One line per step; the rest removed | e.g. "Clients drop files here" |

## 3. The shell

### 3.1 Skeleton (`index.html` body)

```
body
├─ div#shell                         grid: [side 240px][main 1fr]
│  ├─ nav#side                       aria-label = screen.side_label
│  │  ├─ div#side-brand              navy band, 48px, logo 32px tall
│  │  ├─ ul#side-sections            four li > button[data-section]
│  │  │                              each: span.side-name, span.side-count
│  │  └─ div#side-foot
│  │     ├─ p#last-sort              role=status, aria-live=polite
│  │     └─ (pilot.js puts #pilot-badge here)
│  └─ div#main                       grid rows: [bar 48px][notices auto][page 1fr]
│     ├─ header#bar
│     │  ├─ nav#crumbs               aria-label = screen.path_label; ol of segments
│     │  ├─ div#find-wrap            input#find (role=combobox) + ul#find-list (role=listbox)
│     │  └─ button#sort              icon only; aria-label + data-tip from the API
│     ├─ div#notices                 role=alert, aria-live=polite (kept id)
│     └─ main#page                   tabindex=-1; pages.js draws here; scrolls
├─ aside#sheet                       role=dialog, aria-modal, hidden; see 7
├─ div#sheet-scrim
├─ div#tip                           role=tooltip, one element reused
├─ div#toast                         kept
├─ svg (display none) with <symbol> icons: search, sort, stop, dismiss,
│  chevron, next, done, more        (section 3.8)
└─ the dialogs (kept ids) and #roll-modal, #safeguards-modal,
   #about-modal, #misfits-modal
```

The window's minimum is 1100 × 700 (unchanged); the main area is then 860
wide. Nothing scrolls sideways at the minimum.

### 3.2 One left keyline

Every text on a page starts at the same x: 32px inside `#main`. The path,
the H1, group headings, row names and notices all align to it. Rows are full
width (their hover fill runs edge to edge) with `padding-inline: var(--sp-8)`.
Numbers are right-aligned in their column, with tabular figures.

### 3.3 Side panel

- 240px wide, `--bg-nav`, a 1px `--border` hairline on its right edge.
- `#side-brand`: 48px tall, `--brand` (navy in both themes), the logo 32px
  tall, `padding-inline: var(--sp-4)`. It is the one navy surface.
- Sections: 40px rows, 16px from the panel's edges (`margin-inline:
  var(--sp-2)`, `padding-inline: var(--sp-2)`), `--radius-control`. The name
  in body; the count right-aligned in caption, tabular, and shown only when
  above zero (Needs Review: files waiting; Reminders: drafts ready). Hover
  `--bg-nav-hover`, pressed `--bg-pressed`. **Selected:** `--bg-selected`
  fill, weight 600, and a 3 × 16px `--accent` pill at the row's left inside
  edge, centred (Fluent's selection indicator, not a border).
  `aria-current="page"` on the selected one.
- Household, year and return pages select **Clients** (they live under it).
- Foot: `#last-sort` in caption `--text-caption`, 16px from the panel's
  sides, 16px from the badge. States in section 8.3.
- Pilot 0.3 raises the panel (icons, badges, Client Types, Under
  Construction items, Settings, the brand band's words):
  `pilot/SPEC-lists.md` section 15 (P153, P154, P179).

### 3.4 Path row (`#bar`)

- 48px tall, `--bg-page`, a 1px `--border` hairline under it.
- `#crumbs` is an `ol`: segments are buttons in body `--link`, separated by
  the chevron icon (12px, `--text-caption`, `aria-hidden`). The last segment
  is the current level: `--text`, weight 600, not a button,
  `aria-current="page"`. **Clients** and the year never shrink. The
  household segment (at most 240px) and the current one (at most 400px)
  shrink first, each to no less than 96px, cut with "…", and carry their
  full name as the tooltip only when cut.
- Paths: firm sections show one segment (the section's name). Clients ›
  household › year › return below Clients. The year always shows (P61).
- `#find`: 240px wide, 32px tall, `--radius-control`, a 1px `--border-strong`
  edge with `--border-input` bottom edge, the search icon inside at the
  left (16px), no placeholder text; its name is `aria-label` and its
  tooltip "Find a client". Section 8.2 is its behaviour.
- `#sort`: a 32 × 32 subtle icon button, 8px after `#find`, 32px from the
  window's right edge (the keyline mirrored). Section 8.1.

### 3.5 Notice area (`#notices`)

Between the path row and the page, full width, `padding: var(--sp-2)
var(--sp-8)`. Each notice is one 40px line, `--radius-control`: its fill
and ink say the kind (err, warn, info tokens) and its words say what
happened, so the kind is never colour alone. At most one action button
(small, secondary) and the dismiss icon (tooltip "Dismiss") at its right.
Failures and warnings stay until dismissed or fixed (decision 193
unchanged). Notices never push the path row away: the page area scrolls,
the bar and notices do not.

**The failed-sort notice (rulings 20, 28).** While the record of the last
scheduled sort says it failed, every page shows one notice, "Sort Failed"
(the vocabulary's word), with **no button and no action**. It clears when
the next scheduled overnight sort succeeds. The app's own Sort names one
household and never writes that record, so nothing on a page could clear
the notice, and nothing on a firm page may send a sort with no return
chosen (ruling 28 supersedes ruling 26's greyed Retry). The side panel's
last-sort line says the same. The notice is left as it is while a sort
runs.

### 3.6 Rows and groups (one row style, every page; P71, P76)

Column headers, ordering and column widths on the four firm lists, and the
Needs Review heading, household and file levels: `pilot/SPEC-lists.md`
(Pilot 0.3, P135-P139).

A **row** is 40px tall (`min-height: 40px`, `align-items: center`), a 1px
`--border` hairline under it (not under the last row of a group). Columns,
left to right:

| Column | Width | Type | Content |
|---|---|---|---|
| name | flex, min 240px | H3: body 14/20, weight 600, `--text` | the document, file, return or household name; "…" and tooltip when cut |
| detail | 200px | body, `--text-secondary` | period, "1 of 2", the household, or the file's own name |
| status | 160px | body, weight 600, its status token | one status word or count, e.g. "Could not use", "3 need you" |
| end | 144px, right-aligned | the date in caption, `--text-caption`, tabular; the step in body, `--link`, weight 600, no wrap | at rest the date ("Mar 3", "Due Apr 15"); on hover or focus the row's next step and a chevron in the same place |

The date and the step share the end column so the row fits the narrowest
window: at 1100px the main area is 860 wide, and name (240) + 200 + 160 +
144 + three 16px gaps + the 32px keylines on both sides is 856. The date
stays in the row's accessible name while the step shows. A row with no
step keeps its date on hover.

**A row may wrap (rulings 21, 27).** A return's row, a household's row and
any row with a marker let the name and status wrap instead of ending
in "…", so "{Return Name} ({Year})" always shows its year at the 1100px
minimum and "Two Years Open; Sorting Paused" is always whole. A row grows
only for a long name: one line stays 40px (the minimum), two lines are 48px
and three 68px (a 20px line and 4px above and below, on the 4px grid, plus
the 1px rule). A file's name keeps its "…" and tooltip. The link's tooltip
stays "Navigate to Return" or "Navigate to Client".

Hover `--bg-hover`; pressed `--bg-pressed`; the focused row gets the focus
ring inset (`outline-offset: -2px`). An empty column keeps its width, so the
columns line up down a page.

A **group** is an H2 (16/24, 600, `--text`) with its count in caption beside
it, `margin-top: var(--sp-8)` (the first: `var(--sp-6)`), `margin-bottom:
var(--sp-2)`, then its rows. No box, no fill, no rule under the heading:
space and weight divide the groups. A group with no rows shows one caption
line in place of rows (section 6's empty words) or is left out, as each page
says.

**Keyboard and screen readers:** each group's rows are one
`role="listbox"`, named by its heading (`aria-labelledby`), holding
`role="option"` rows; the listbox is one Tab stop and moves focus with
`aria-activedescendant`. Up/Down, Home/End, PageUp/PageDown move;
**Enter** runs the row's next step; **Shift+F10** or the menu key opens its
right-click menu. The visible step text is `aria-hidden` (the option's
accessible name is its columns read in order, and the step is announced
by `aria-description` = the step's words). Clicking anywhere on a row
selects it; clicking its step runs the step; double-click runs the step.

### 3.7 Type roles (five, P62)

| Role | Size / line | Weight | Font | Used for |
|---|---|---|---|---|
| H1 | 20 / 28 | 600 | display | page heading |
| H2 | 16 / 24 | 600 | display | group heading, sheet title, dialog title |
| H3 | 14 / 20 | 600 | text | row name, section name when selected |
| body | 14 / 20 | 400 | text | everything else |
| caption | 12 / 16 | 400 | text | counts, dates, the last-sort line, badge |
| figure | 28 / 36 | 600 | display | the Overview's three numbers only |

Line heights are written unitless as `calc(20 / 14)` etc., so each lands
exactly on the 4px grid (P72). Build E's 16/22 subtitle becomes 16/24.
Dialog titles, which Build E set at 20/28, become H2 (16/24): one step under
the page's H1, so a dialog never out-shouts the page behind it.

### 3.8 Icons

Seven drawn icons (the audit's count), inline SVG `<symbol>`s in
`index.html`, 16px on a 16 viewBox, 1.5px stroke, round caps,
`currentColor`: **search, sort, stop, dismiss, open (chevron), next, done,
more**. The chevron also serves as the path separator and the row step's
trailing mark (decorative there, `aria-hidden`). No emoji or text glyph
stands in for an icon ("›" in the audit's words is drawn, not typed).
Every icon that is a control has an `aria-label` and a tooltip of five
words or fewer (P65); none has a visible label beside it.

### 3.9 Links (rulings 8, 9, 11, 12, 13)

Three kinds of name are live links, drawn in `--link` wherever a page
shows them. A link shows the **name only, never a path** (P63).

| Name | Does | Tooltip (`vocab.screen`) |
|---|---|---|
| A **file name** (a parked, moved-by-hand, set-aside or filed file's own name, in a row's name or detail column) | Shows **that exact working copy** in File Explorer, the file selected in its folder (5.7) | "Show in File Explorer" |
| A **household name** (a row's name or detail, a group's caption) | Navigates to that household's page in the app; no engine call | "Navigate to Client" |
| A **return name** (a row's name, a Needs Review group heading) | Navigates to that return's page in the app; no engine call | "Navigate to Return" |

- **The only link that opens File Explorer is a file name** (ruling 12). No
  household or return row carries an open key for a link; "Opens File
  Explorer" applies to files only. Opening the client folder, the inbox or
  the working folder stays in the Client menu (5.1).
- **A return link carries its tax year:** wherever a return name is drawn
  as a link (the Overview's Work Waiting, the household and year pages,
  Reminders, the Needs Review group headings) it reads
  **"{Return Name} ({Year})"**, e.g. "1120-S - Rivera Design LLC (2025)",
  so two years of one return can be told apart (ruling 13). The year is the
  return's own, from the API's row (`year`, 9.2), never typed or worked out
  by the renderer. The path row and the page's H1 are unchanged: the path
  already carries the year.
- A link that cannot act (the copy is gone or changed) says the shell's
  "Not Opened; It Has Changed" as a notice, as the open icon does (7.1).
- `pages.js` builds the three kinds (S5); the keys a file link opens by
  are the API's (5.7, S8a).

## 4. Behaviour of the shell

### 4.1 Routing

`shell.js` holds one route: `{level, section, household, year, ret}` where
`level` is one of `overview`, `needs-review`, `reminders`, `clients`,
`household`, `year`, `return`, `setup`. `go(route)` draws the path, selects
the side section, sends the menu's enable list (5.3), and asks `pages.js`
to draw. No history, no back button: the path and the side panel are the
way around (P75). The app opens on Overview; at first run on `setup`.
The last route is not remembered across launches.

### 4.2 Data

- `list` at start (as today, `BOOTSTRAP_COMMAND`): households, returns,
  vocabulary, last pass, warnings, and (section 9) `paths`.
- `firm` (section 9) after `list`, and again after a sort ends, after F5,
  and after any write that changes a count (file, unfile, not requested,
  put back, keep here, mark missing, approve, edit). While it runs the firm
  pages show their loading state; a failure is one notice with Retry and
  the pages show what they last had.
- `state` for one return when its page opens or its sheet opens, as today
  (`showReturn`). A household page needs no `state`: it draws from `list`
  and `firm`.
- **F5 / View › Refresh** asks `list`, then `firm`, then `state` of the
  open return. It never reloads the page.

### 4.3 Keyboard map

| Keys | Does |
|---|---|
| Ctrl+1 … Ctrl+4 | Overview, Needs Review, Reminders, Clients |
| Ctrl+F | focus `#find` |
| F5 | Refresh |
| F9 | Sort now (when enabled) |
| Ctrl+N | New household… |
| Ctrl+E | Edit request list… (a return open) |
| Alt | the menu bar (Windows). The bar stays **hidden until Alt** (`autoHideMenuBar: true`; ruling 3) |
| F6 | cycle focus: side panel › path row › page › side panel |
| Esc | close the sheet, the search list, a tooltip, in that order |
| Enter, Shift+F10 | a row's step, a row's right-click menu |

The accelerators are the menu's (section 5), so they work from anywhere and
show in the menus. F6, Esc and the listbox keys are the page's: the one
`keydown` listener stays in `app.js` (a test holds the renderer to one) and
hands them to `shellKey(e)` in `shell.js` before its own Escape handling.

**Accepted exception (ruling 1):** the terms screen (`pilot.js`) and the
tour (`tour.js`) keep their own capturing `keydown` listeners, as built.
They take over the keyboard on purpose and act only while they are open.
The new files (`shell.js`, `pages.js`, `sheet.js`, `tooltip.js`) add none.

Because Electron delivers a menu accelerator (Ctrl+1 to 4, Ctrl+F, Ctrl+N,
Ctrl+E, F5, F9) to the menu first, and it then reaches the page as `{id}`
on the `menu` channel, the page acts on the `{id}` only, never also on the
raw key, or it would act twice (S2's note; the Windows check confirms it).

## 5. Menu bar, right-click menus and the one channel (P58, P68, P69)

### 5.1 The template (`main.js`)

Built by `buildMenu(words)` from `vocab.menu` (section 11.2) and set with
`Menu.setApplicationMenu`. `main.js` holds default words **word for word**
the API's `MENU` constant, the pattern it already uses for `vocab.shell`
(decision 193), so the menu is there from the first frame and a test keeps
the two equal. When a `list` reply carries `vocab.menu`, `learn()` keeps it
and the menu is rebuilt only if a word differs.

| Menu | Item (id) | Accelerator | Enabled when |
|---|---|---|---|
| **File** | New Household… (`new_household`) | Ctrl+N | a clients folder is set |
| | Change Clients Folder… (`change_root`) | | always |
| | Open Clients Folder (`open_root`) | | a clients folder is set |
| | — | | |
| | Exit (role `quit`, label `exit`) | Alt+F4 (Windows' own) | always |
| **Edit** | role `editMenu` (Undo, Redo, Cut, Copy, Paste, Select all), label `edit` | Windows' own | always |
| **Client** | Edit Household… (`edit_household`) | | a household, year or return is open and not locked |
| | Add a Return… (`add_return`) | | same |
| | Roll Forward… (`roll_forward`) | | same, and the household has a year to roll |
| | Mark as Shared (`mark_shared`) | | same, and it is not shared |
| | — | | |
| | Edit Request List… (`edit_list`) | Ctrl+E | a return is open and not locked |
| | Draft Reminder… (`draft_reminder`) | | a return is open |
| | — | | |
| | Open Client Folder (`open_client_folder`) | | a household, year or return is open |
| | Open Inbox (`open_inbox`) | | same |
| | Open Working Folder (`open_working`) | | a return is open |
| **View** | Overview (`overview`) | Ctrl+1 | a clients folder is set |
| | Needs Review (`needs_review`) | Ctrl+2 | same |
| | Reminders (`reminders`) | Ctrl+3 | same |
| | Clients (`clients`) | Ctrl+4 | same |
| | — | | |
| | Find (`find`) | Ctrl+F | same |
| | Refresh (`refresh`) | F5 | always |
| | Show Under Construction (`show_under_construction`), a checked item | | always (P197) |
| **Tools** | Sort Now (`sort_now`) | F9 | a household, year or return is open, no sort runs, not locked |
| | Stop Sorting (`stop_sorting`) | | a sort runs |
| | — | | |
| | Schedule… (`schedule`) | | a clients folder is set |
| | Repair Schedule (`repair_schedule`) | | same |
| | Firm Report (`firm_report`) | | the API reported `paths.status` |
| | — | | |
| | Clear Stuck Lock (`clear_lock`) | | the open return's lock is stale |
| **Help** | Take the Tour (`tour`) | | always |
| | Safeguards (`safeguards`) | | always |
| | Terms (`terms`) | | always |
| | Open Error Log (`error_log`) | | always (section 5.5) |
| | — | | |
| | About (`about`) | | always |

Top-level labels carry their Windows access key (`&File`, `&Edit`,
`&Client`, `&View`, `&Tools`, `&Help`) in the API's words; the five-word
test strips the `&`. There is no Reload, Force reload, Zoom, Toggle full
screen or Developer tools item, and no accelerator for them: F5 is Refresh
(the page re-reads), Ctrl+R and Ctrl+Shift+I do nothing. So the council's
E-7 reason for hiding Electron's default menu still holds (P58), and
`devTools: !app.isPackaged` stays.

**Tester guide** is not in Help: the app has no copy of it (it is emailed
with the installer, `RELEASE.md`), so the item would open nothing; Jason
left it out of 0.2 (P81).

### 5.2 Right-click menus (native, P68)

A right-click (or Shift+F10 / the menu key) on a target asks `main.js` to
pop a **native** menu at the pointer (or under the focused row). Native, so
there is one menu style in the app - the menu bar's - with Windows'
keyboard, screen reader and dark support for free.

| Template (`popup`) | Target | Items (ids, words from `vocab.menu`) |
|---|---|---|
| `household` | a household row; the household segment; the household H1 | the Client menu's household items: Edit Household…, Add a Return…, Roll Forward…, Mark as Shared, —, Open Client Folder, Open Inbox |
| `return` | a return row; the return segment; the return H1 | Edit Request List…, Draft Reminder…, —, Open Working Folder, Open Client Folder, Open Inbox |
| `file` | a parked or set-aside file row | Check… (`check`), Not Requested (`not_requested`), Another Return… (`another_return`), Show in File Explorer (`show_in_explorer`) |
| `moved` | a moved-by-hand row | Check…, Put Back (`put_back`), Keep Here (`keep_here`), Show in File Explorer |
| `request` | a Needs you or Waiting request row | Edit Request… (`edit_request`) |
| `received` | a Received row | Unfile (`unfile`), Mark Missing (`mark_missing`), Show in File Explorer |

The page sends the enable list with each popup, by the rules of 5.1 (a
locked return greys the writing items).

**Unfile and Mark Missing ask first (ruling 16).** Choosing **Unfile** opens
a small confirm box with one field, "Reason (Optional)", and a confirm
button; the reason is sent as the write's `note` and kept in the record as
the old list kept it, and one press is one write. **Mark Missing** does the
same when the wording table has a note word for it. Cancel writes nothing.

### 5.3 The page tells the menu what applies

On every route change, state change and lock change, `shell.js` sends
`{enable: [ids], checked: [ids]}`: the ids whose rule in 5.1 holds now, and
the checkable ids that are on (P197; `main.js` keeps only `CHECKABLE` ids, and
a message without `checked` leaves the tick). `main.js` sets `enabled` on the
menu items whose ids it knows and ignores anything else.
It never adds, removes or renames an item for the page.

### 5.4 The one channel: `menu` (preload)

`preload.js` gains exactly this, beside what it has:

```js
menu: {
  // A menu item was chosen: {id, token}. token is the page's own, echoed.
  onCommand: (listener) => ipcRenderer.on("menu", (_e, m) => listener(m)),
  // What applies now: {enable: [ids], checked: [ids ticked]}; or pop a right-click menu:
  // {popup, enable: [ids], token, x, y}.
  send: (message) => ipcRenderer.send("menu", message),
},
```

`main.js`, `ipcMain.on("menu", …)`, treats every message as untrusted:

- `enable` must be an array of strings; ids not in the template are dropped.
- `popup` must be one of the six template names; anything else is ignored.
- `token` must be a string of at most 64 characters; it is never used by
  `main.js`, only sent back with the chosen id. The page's token is a row
  key it made itself - never a path.
- `x`, `y` are numbers inside the window, else the menu opens at the
  pointer.
- A click on any item sends `{id, token}` on `menu` to the window that
  asked (or, for the menu bar, to the one window), except `exit` (role) and
  `error_log` (5.5).

No command reaches the tracker through this channel: the page answers a
menu id exactly as it answers a click, through `window.tracker.call`, with
every existing check in place.

### 5.5 Handled in `main.js` alone

- **Open Error Log:** `main.js` opens the error log the API named
  (`vocab.shell.error_log`) with `shell.openPath` when it is a regular file
  and no symbolic link (the same `lstat` test `openPath` makes, shared as
  `openChecked`); when the API named none, it opens the shell's **fallback
  log** (below) if that exists, through the same test. Otherwise it sends
  `{id: "error_log", missing: true}` and the page shows the toast
  "No Error Log Yet".
- **The fallback error log (ruling 4).** When a tracker command fails and
  the API has named no error log (no data folder yet, first start only),
  the failure is still **saved**: `keepInLog()` appends its details (a
  heading with the time, then stderr, at most 64 KB an entry) to
  `%LOCALAPPDATA%\Tax Document Tracker Pilot\error.log` on Windows
  (`process.env.LOCALAPPDATA`, else `os.homedir()\AppData\Local`; the
  folder is named from `productName`); off Windows (tests, development
  runs) `app.getPath('userData')`. A local folder that does not roam:
  never the roaming `%APPDATA%`, never the data home
  (`tax-document-tracker-pilot`) or the upstream one
  (`tax-document-tracker`), and neither of those is created. A renderer
  error (`log-error`) and a shell serialisation error go the same way when
  no log is named. Past **256 KB** the file becomes `error.log.1` (one copy,
  replacing an older one), so it never holds much more than 512 KB; if the
  rotation cannot be done, the old log is dropped and writing goes on. A
  link or a folder at `error.log` is left alone, and every write is caught:
  a write that fails never throws and never changes the reply. The raw
  stderr can name clients, so it stays in that file on this PC: never on
  screen, never in a reply, never sent. Its path is in the agent deny list
  (`.claude/settings.json`, section 1), pinned by test.
- **A failure's on-screen text (ruling 6):** the failure's own approved
  sentence, a blank line, then "Tracker Failed" (`shell.no_log`, in
  ruling 10's casing). Not reduced to the two words for this pilot.
- **Menu bar:** it stays hidden until Alt (`autoHideMenuBar`; ruling 3).
- **Exit:** role `quit`.

### 5.6 Light and dark at first paint (P59, P73)

`pageBackground()` reads `pilot-ui.css` (not `style.css`) for
`--window-light:` and `--window-dark:`, and returns the one for
`nativeTheme.shouldUseDarkColors`, or `undefined` when
`nativeTheme.shouldUseHighContrastColors` (a contrast theme paints its
own). `nativeTheme.on("updated")` sets the window's background colour
again, so a switch while the app is open does not flash the old colour
behind a resize. `nativeTheme.themeSource` stays `"system"`. The page
follows the setting through `prefers-color-scheme`; nothing in the
renderer asks.

### 5.7 Showing a file in File Explorer (`open-path` with reveal; rulings 8, 12)

- **The option.** `window.tracker.open(path, how)` gains a second argument:
  `open(path)` opens as today; `open(path, "reveal")` shows the item in
  File Explorer with the file selected in its folder
  (`shell.showItemInFolder`). The preload passes `how` on the existing
  `open-path` channel; no new channel.
- **Same guard.** Reveal goes through the same allow-list and the same
  `lstat` test as opening: the path must be one the API reported
  (`openable`), of the kind the API named, and no symbolic link; anything
  else is refused with "Not Opened; It Has Changed" or the not-reported
  sentence, and nothing is shown. Reveal applies to a **file** only.
- **Openable keys for working copies.** The API reports each working copy
  a file link may show under `state.paths`, by a key, never on a field the
  page draws: a parked file's review copy (the existing `review_copy`
  key), each working copy of a filed document (one per request it was
  filed under, in `filed_names`' order) and where a moved-by-hand copy is
  now. Index rows carry the keys of their copies and a moved row its key,
  so the page asks by key and the path never reaches a drawn element.
  `PATH_KINDS` names each key's kind: `review_copy` is `file` (it opens in
  the default program and is revealed); `filed_copy`, `moved_copy` and
  `shown_copy` are **reveal-only** (kind `reveal`): `open-path` shows them
  in File Explorer with `"reveal"` and refuses a plain open, because none
  of them carries the Protected View mark. A parked or set-aside row's
  `shown_key` is the key of the copy it *shows* (its `review_copy` key
  where that copy opens, else a `shown_copy` key; "" for a program, which
  has no copy), beside `open_key`, the copy it *opens*. Only paths the
  record already holds; nothing is read from disk to find them. **Household and
  return rows carry no open key for a link** (ruling 12): only file names
  open File Explorer.
- The key names and fields are S8a's, final (its review 3 found nothing):
  `review_copy <row>`, `shown_copy <row>`, `filed_copy <row> <n>` and
  `moved_copy <row>`; `open_keys` on index rows, `open_key` and `shown_key`
  on parked rows, `open_key` on moved rows.

## 6. Pages, one per level, and their states

Every page is drawn by `pages.js` into `#page` from data it is handed; it
calls nothing itself. Words are `vocab.screen.*` (section 11.3) unless named.
**Firm pages** (Overview, Needs Review, Reminders, Clients) have no H1: the
path's one segment and the selected section name them, and a heading would
say it a third time (P75). **Household, year and return pages** open with
an H1, the level's full name (the path may have cut it).

Common states, used by every page below:

- **Loading:** the page's frame at once (H1 from `list` where there is
  one), then six outline rows per group it will draw: 40px rows holding two
  static bars in `--bg-hover` at the name and status columns. No spinner,
  no shimmer (Remote Desktop, and motion that says nothing). `#page` has
  `aria-busy="true"` and a visually hidden "Loading".
- **Failed read:** the notice for it (4.2), and the page keeps what it last
  drew; with nothing drawn yet, it draws only its frame.
- **Locked return:** the lock notice; writing menu items greyed (5.1); the
  sheet's writing buttons drawn disabled.
- **Long names:** a household name up to 60 characters and a return name up
  to 80 end in "…" at their column's width, with the full name as the row's
  tooltip. An H1 is never cut: it wraps, to two lines at most (the widest
  name, 80 characters at 20px, needs two at the 860px minimum). User data (names, file names) is content, not copy: the
  five-word rule does not count it, and a test feeds names at those lengths.
- **Links (3.9):** every file, household and return name a page draws is
  a link of its kind; a return drawn as a link reads "{Return Name}
  ({Year})". The words in the diagrams below are in Title Case (11.1).

### 6.1 Overview (the landing page)

```
 [bar] Overview                                        [find    ] [sort]
 ───────────────────────────────────────────────────────────────────────
   12              31                 148
   Need a Person   Waiting on Clients Complete

   Work Waiting  43
   1040 - John & Jane Smith (2025)     Smith Family     3 Need You    Mar 3   Open ›
   1120-S - Rivera Design LLC (2025)   Rivera Design    1 Need You    Mar 5
   1040 - Ana Lopez (2025)             Lopez Household  2 Waiting   Due Apr 15
```

- **Figures:** three numbers in the figure role, `--text`, 48px apart, each
  with its caption under it. They count **returns**, and each active return
  is in exactly one: **Need a person** (anything in its Needs you group),
  else **Waiting on clients** (anything in Waiting on client), else
  **Complete**. They add up to the active returns this year. Not links.
- **Work waiting** (H2, count): one row per return in the first two
  buckets. Name: the return, a link reading "{Return Name} ({Year})"
  (3.9). Detail: its household, a link. Status: "{n} need you"
  (`--st-attention`) or "{n} waiting" (`--st-waiting`). Date: the oldest file
  waiting ("Mar 3") for the first bucket, the due date ("Due Apr 15") for
  the second, or empty. Step: **Open**. Order: need-you returns by their
  oldest waiting file, oldest first; then waiting returns by due date,
  soonest first, then by name.
- **Empty:** in place of the H2 and rows, "Nothing is waiting" (body) and
  under it "Next sort {time}" (caption) when the schedule has a next run.
- **Right-click** on a row: the `return` menu.

### 6.2 Needs Review (firm)

- One group per return with files waiting: H2 is the return's name, a
  link reading "{Return Name} ({Year})" (3.9), its caption the household
  (a link) and the count. Groups ordered by their oldest file.
- Rows: name = the file's own name (a link to its review copy in File
  Explorer, 3.9); detail = the request it most likely is
  (the first suggestion's name), else empty; status = the reason's short
  label (11.4), `--st-attention`; date = received; step **Check** → the
  sheet (7.1), which loads that return's `state`. Right-click: `file`.
- The sheet's next arrow walks every file on this page, group by group.
- **Empty:** "Nothing Needs Review" and "Next sort {time}".
- The side count is the number of files.

### 6.3 Reminders (firm)

- One list, no H2 (the page is one thing). Rows: one per return whose draft
  for this week is ready and not yet approved. Name: the return, a link
  reading "{Return Name} ({Year})". Detail: household, a link. Status: the stage's short name (`--st-waiting`), or
  "Held" (`--st-attention`) when files or rows hold it. Date: drafted.
  Step **Draft reminder** → the sheet (7.2). Right-click: `return`.
- **Empty:** "No drafts ready".
- The side count is the number of rows.

### 6.4 Clients

- A two-option switch at the keyline, 24px under the path row: **Work
  waiting** (the default each time the page opens) and **All**. The
  selected option has P52's selected look.
- Rows: one per household, by name. Name: the household, a link
  ("Navigate to Client", 3.9). Detail: "{n}
  returns" (this year's, "1 return" for one). Status: "{n} need you",
  "{n} waiting" or "Complete", summed over its returns. Date: empty. Step
  **Open** → the household page. Right-click: `household`.
- 500 households draw in one pass (one `DocumentFragment`); no paging, no
  virtual list. Search (8.2) is the fast way to one household.
- **Empty (no households):** "No clients yet" and one secondary button
  **New household…** - the one button a page may carry, because an empty
  firm has nothing else to act on.
- **Empty (switch on Work waiting, none waiting):** "No work waiting".

### 6.5 Household

- H1: the household's name. Under it one caption line of what applies,
  joined by " · ": "Contact {name}", "Shared" or "Not shared".
- One group per tax year, newest first: H2 is the year. Rows: one per
  return. Name: the return, a link reading "{Return Name} ({Year})" (3.9).
  Detail: "Inactive" or "Rolled forward" when the
  list says so, else empty. Status: as on Clients. Step **Open**.
  Right-click: `return`.
- Household notices while any of its pages is open: two years open,
  folder renamed (with **Accept**), feeds that do not resolve.
- **Empty (no returns):** "No returns yet" and one secondary button **Add a
  return…**.
- Right-click on the H1 or its path segment: `household`.

### 6.6 Year

- H1: the year. Rows: that year's returns, as on the household page. A year
  exists only when it holds a return, so there is no empty state.

### 6.7 Return

```
 [bar] Clients › Smith Family › 2025 › 1040 - John & Jane Smith  [find] [sort]
 ───────────────────────────────────────────────────────────────────────────
   1040 - John & Jane Smith
   Due Apr 15

   Needs You  3
   scan0012.pdf        W-2                Could Not Sort       Mar 3   Check ›
   IMG_2231.jpg        1099-INT           Fits Two Requests    Mar 4
   1098 - Chase                           Could Not Use        Mar 2

   Waiting on Client  2                                    Draft Reminder ›
   1099-B - Schwab     Dec 2025           Outstanding
   K-1 - Park LP       1 of 2             Partly In

   Received  9
   W-2 - Acme Corp     acme-w2.pdf        Received             Mar 1

 ▸ Set Aside  4
```

(The file names `scan0012.pdf`, `IMG_2231.jpg` and `acme-w2.pdf` are links
that show their working copy in File Explorer, 3.9.)

- H1: the return's name. Caption: "Due {date}" when the record has one.
- **Needs you** (`group == "needs_you"`), in this order: files parked for a
  person, oldest first; then files moved by hand; then request rows whose
  side is Us or Decide, in list order. Files the router set into buckets
  ("Emails and zips", "Not documents") sit under those two words as caption
  sub-headings, weight 600, inside the group.
  - Every file name below is a link to its working copy (3.9, 5.7), except
    an email or a zip, which is plain text with no key (ruling 24).
  - Parked file: name = file name; detail = first suggestion or empty;
    status = short reason; date = received; step **Check** (7.1).
  - Moved by hand: name = file name; detail = its request; status "Moved by
    hand"; step **Check** (7.1, moved).
  - Request row: name = its short name or document; detail = period (when
    it differs from the return's year) or "1 of 2"; status = its label
    (e.g. "Could not use"); date = received, if any; step **Edit** → the
    request list editor, scrolled to that row with its first cell focused.
- **Waiting on client** (`group == "waiting"`): request rows. Status = its
  label ("Outstanding", "Partly in", "Not yet checked"). Step **Draft
  reminder** (7.2), the same as the group heading's, which shows it on hover
  or focus of the heading.
- **Received** (`group == "received"`): request rows. Detail: the file's own
  name (a link to that filed working copy, 3.9) when one file answers it, or
  "{n} files". When several files answer one request, **each file gets its
  own row** under the request (set in, not counted), with its own file link
  and right-click (Show in File Explorer, Unfile) (ruling 17). Status "Received" or "Accepted" (`--st-done`). Date:
  received. No step; right-click: `received` (Unfile, Mark Missing).
- **Set aside** (`group == "set_aside"`): a `details` element, shut each
  time the page opens; its summary is the H2 with its count. Rows: not
  asked ("Not asked"), not applicable ("Not applicable {year}"), and files a
  person set aside ("Not requested", step **Check**).
- A group with no rows is left out, except **Received**, which shows
  "Nothing received yet" (a return with nothing received yet is a state
  the brief asks for).
- Right-click on the H1 or its path segment: `return`.

### 6.8 Setup (first run, and File › Change clients folder…)

- Side panel sections, `#find` and `#sort` drawn disabled, with no counts;
  the path row empty.
- H1 "Choose your clients folder". Then **Choose folder…** (secondary);
  after a pick, the folder's own name beside it (body) - never its path; a
  hidden input keeps the path for `saveRoot()`.
- "Firm name" and "Firm phone": labels above 32px inputs, 320px wide.
- **Start** (primary), enabled once a folder is chosen. A problem is one
  notice: "Folder not found".
- From the File menu the page also has **Cancel** (subtle) back to the last
  route, and the side panel stays enabled.

## 7. The side sheet (`#sheet`, P74)

A drawer from the right, 400px wide, the window's full height, over a scrim
(`--scrim`; a click on it is Esc). It is modal: it joins the dialog stack
(`DIALOGS`, `openDialog`, `trapTab` in `app.js`), focus goes to its title,
Tab stays inside, and closing returns focus to the row that opened it.
It slides in over 150ms (`transform`), and appears at once when Windows
asks for less motion.

- **Header**, 48px (it lines up with the path row): H2 title, cut with "…";
  at the right, icon buttons: **open** (Check only; tooltip "Open"), **more**
  (Check only; a disclosure, `aria-expanded`; tooltip "More"), **next**
  (tooltip "Next"), **dismiss** (tooltip "Dismiss").
- **Body** scrolls; `padding: var(--sp-6)`.
- **Footer**, 64px, a hairline above: the secondary action, then the
  primary at the right (P52's dialog order).

### 7.1 Check a file

Drawn by `reviewRow()` / `movedRow()` for one row (they already build every
part; `sheet.js` places one row's nodes in the body and restyles them).

- Status line: the short reason (`--st-attention`) and received (caption).
- **Belongs to** picker, pre-set to the best suggestion: a 32px select, full
  width, option groups "Suggested" and "Other". Under it one caption line
  per suggestion's reason (e.g. "Name and year match").
- K-1 only: "Issuer name" input and **Add issuer**.
- **More** (the header's more icon opens it): Keyword, Spelling, Reason
  fields and **Another return…** (subtle), which opens `#handover-modal`.
- Footer: **Not requested** (secondary), **File it** (primary).
  Moved by hand: **Keep here** (secondary), **Put back** (primary).
- After a write that succeeds the row leaves the list (visible, so no
  message) and the sheet shows the next file; after the last it closes.
- **Next** moves on without writing (was Skip for now). Its order: this
  return's Needs you files from a return page; every file of the Needs
  review page from there.
- The open icon opens the review copy (`openCopy()`); a copy that is gone
  says the shell's "Not opened; it has changed" as a notice.

### 7.2 Draft reminder

Drawn by `drawReminder()` into the sheet (its element ids move into the
sheet unchanged, so `loadReminder()`, `copyReminder()` and
`approveReminder()` keep working).

- Title "Reminder". Caption: drafted date and stage, e.g. "Drafted Mar 1,
  stage 2".
- Held: a warn line "Held: {n} need a decision" or "Held: {n} files not
  sorted", and the held rows' names under it.
- The four stages as a segmented control ("Heads up", "Checking in",
  "Deadline near", "Final notice"), the chosen one in the selected look.
- "Edited by hand" (caption) when it is.
- Subject (body, 600), then the letter preview. The letter keeps its own
  fonts and inks and stays on white paper in dark mode, with a hairline
  edge (P53, SPEC-ui 7.4): it is the email the client receives.
- Footer: **Approve** (secondary), **Copy** (primary). Copy's toast:
  "Copied" (the effect is off screen).
- **Next** (Reminders page only): the next return with a draft.

## 8. Controls and their states

### 8.1 The sort icon (`#sort`, P60, P70)

| State | Icon | Colour | Tooltip and name | Does |
|---|---|---|---|---|
| Ready (a household, year or return open) | sort | `--link` | "Sort now" | runs the pass for the open household (`runScan()`) |
| Firm page | sort, disabled | `--text-disabled` | "Open a client to sort" | nothing (P80) |
| Return locked elsewhere | sort, disabled | `--text-disabled` | "In use elsewhere" | nothing |
| Sorting | stop | `--danger` | "Stop sorting" | `stopPass()` |
| Stopping | stop, disabled | `--text-disabled` | "Stopping" | nothing |

`aria-keyshortcuts="F9"` while ready. The one Stop is this icon: the side
panel's foot shows progress only (P70, the audit over the brief's section 3).

### 8.2 Search (`#find`)

A combobox (`aria-expanded`, `aria-controls="find-list"`,
`aria-activedescendant`). Typing filters the households and returns of the
`list` reply by name, case- and accent-insensitive, from the first letter;
no call to the API. The list shows up to eight options, households first:
the name (H3) and a caption (a return shows its household and year).
Down/Up move, Enter opens the chosen one (or the first), Esc clears and
closes, a click outside closes. No match: one disabled option "No match".

### 8.3 The last-sort line (`#last-sort`)

| State | Words | Colour | Mark |
|---|---|---|---|
| Sorted today | "Sorted {time}" (e.g. "Sorted 6:00 AM") | `--text-caption` | done icon, tooltip "Sorted" |
| Sorted another day | "Sorted {date}" (e.g. "Sorted Mar 3") | `--text-caption` | done icon |
| Last sort failed | "Sort failed" | `--st-error` | none (the notice has the rest) |
| Never | "Not sorted yet" | `--text-caption` | none |
| Sorting | "Sorting {n} of {total}" | `--text-caption` | a 4px bar under the words, `--accent` on `--border`, `role="progressbar"` with its values |
| Stopping | "Stopping" | `--text-caption` | the bar, still |

The file being read is never named (P63).

### 8.4 Notices

One line each, the kind by fill and ink (err, warn, info tokens), at most
one action. The list, with words from section 11: sort failed (no button,
3.5; ruling 28),
counts not available (Retry), in use on {host}, stuck lock from {host},
setup needs attention, install folder name too long, drive not signed in
and the other machine warnings, {n} folders skipped (Show), names
shortened to fit, two years open, folder renamed (Accept), and the
shell's own failures. The dismiss icon ends each.

**A failed sort on the return's own banner (rulings 25, 29)** says "Sort
Failed: {reason}", five words at most in all, Title Case, from the
vocabulary (`vocab.scan.reasons`, keyed by the pass's own failure `code`),
never a path: Another PC Sorting (a lock held elsewhere), Two Years Open
(a paused household), Folder Not Found (the client folder or the return's
folder is gone) and, for any other kind, Unexpected Error. The long detail
stays in the error log. A command killed at the 30-minute cap says what it
was: "Sort Stopped: Ran Too Long" for a sort, "Change Stopped: Ran Too Long"
and "It May Be Partly Done." for a write, "Stopped: Ran Too Long" for a read
(final review A, finding 5).

### 8.5 Tooltip (`tooltip.js`)

PLAN-ui section 5, with P63 and P65, and rulings 2, 5 and 7:

- **When it shows.** Any element with `data-tip` gets it after **300 ms**
  of hover (ruling 7; `TIP_DELAY_MS`), on every control. On **keyboard
  focus** it shows at once on **every control except the search box**
  (`#find`), which shows none on focus so the tip never covers its list
  (ruling 2, option b); hover still shows the search icon's tip ("Find a
  Client", the icon lets the pointer through to the box). Esc and
  pointer-out hide it.
- **What it is.** One `#tip` element, `role="tooltip"`, tied by
  `aria-describedby`; at most 320px wide; caption type on `--bg-raised`
  with `--shadow-overlay` and a 1px `--border`. Its text is always
  vocabulary or a user's name, never typed in the renderer, never over
  five words (names excepted).
- **Where it goes (ruling 5).** Placement is Floating UI's
  (`FloatingUIDOM.computePosition`, strategy `fixed`, from the vendored
  files of section 1): below its element, 4px off it (`offset(4)`),
  flipped above when there is no room (`flip`), shifted to stay 8px inside
  the window (`shift` with 8px padding). `tooltip.js` keeps its own timing,
  focus, Esc and `role=tooltip` logic and uses the library for placement
  only, through the one global `FloatingUIDOM`; no `import`, no `require`,
  no edge arithmetic of its own. The result is set with
  `element.style.setProperty` (allowed by the CSP, as the tour does): no
  `style` attribute, no `innerHTML`.
- **Scrolling.** While it shows, the tip is placed again when the window
  is resized or anything scrolls, so it follows its element. When its
  element is **scrolled out of view** the tip is hidden (Floating UI's
  `hide()`, `referenceHidden`), and it does **not** come back when the
  element scrolls back into view: it returns only on the next hover or
  focus.
- Every `title=` in the renderer goes; `setTip(el, text)` replaces them.

### 8.6 Motion

150ms `--ease` for hover, press, the sheet and a notice's fade; menus are
Windows'. No motion when a page changes. `prefers-reduced-motion: reduce`
sets every duration to 0.

### 8.7 Browser surfaces

Themed from the tokens, both themes: `::selection` (`--bg-selected`,
`--text`), `caret-color: var(--text)`, `scrollbar-color: var(--scroll-thumb)
transparent` on `#page`, the sheet body and the dialogs,
`font-variant-numeric: tabular-nums` on every count, date and figure,
`accent-color: var(--accent)` for checkboxes and radios.

## 9. The engine part (read only; needs Jason's yes)

The firm view needs, for every return, how many things sit in each group
and whether its reminder draft is ready. Today only the scheduled pass's
firm page (`runner.status_report()`) reads that, into an HTML file. This
section adds one read-only command and three small payload fields. No
filing, status, reminder or scheduling behaviour changes; nothing is
written; no lock is taken.

### 9.1 One grouping rule, in Python

A new function `api.item_group(item, placed)` returns one of `needs_you`,
`waiting`, `received`, `set_aside`, by the first line that holds:

| Row | Group |
|---|---|
| override Not applicable | `set_aside` |
| not asked and nothing in | `set_aside` |
| side Client (`reminder.sides()`) | `waiting` |
| side Us or Decide | `needs_you` |
| status Received, or override Accepted | `received` |
| any other row (asked, nothing usable in, no side: Not yet checked) | `waiting` |

Files: parked for a person and moved by hand are `needs_you`; set aside by
a person (Not requested) are `set_aside`. `state` gains `group` on each
item and each file row, from this function; `firm` counts with it. So a
count on the Overview and the group on the return's page cannot disagree
(a test pins it on the sample).

### 9.2 `firm`

No arguments. Reply:

```
{
  "returns": [{
     "path": str, "household": str,
     "year": n,                   # the return's tax year (ruling 13)
     "counts": {"needs_you": n, "waiting": n, "received": n, "set_aside": n},
     "files": n,                  # of needs_you, the files (parked + moved)
     "oldest": "YYYY-MM-DD"|null, # the oldest file waiting for a person
     "due": "YYYY-MM-DD"|null,    # the record's due date
     "draft": {"ready": bool, "stage": n, "held": n, "drafted": "YYYY-MM-DD"|null},
     "problem": str,              # a short sentence, or ""
     "paused": bool               # its household has two open years (ruling 21)
  }],
  "files": [{"return": str, "year": n, "name": str, "handle": str, "code": str,
             "received": "YYYY-MM-DD", "suggestion": str,
             "open_key": str}],   # the key of the file's copy in `paths`, or "" (ruling 15)
  "paths": {key: path},           # each key's path, reveal only (ruling 15)
  "totals": {"need": n, "waiting": n, "complete": n, "files": n, "drafts": n},
  "next_sort": "HH:MM"|null
}
```

- Walk: `discover_engagements(root)`, as `list` does. Inactive and skipped
  returns (`runner.why_skipped`) are left out of `returns` and `totals`.
- Per return, the readers the practice page and `state` already use, with
  `follow=False` as `status_report()` does: `load_manifest`,
  `summarize`, `reminder.triage` and `reminder.sides`, the index for its
  parked and moved files (`runner._parked_files`' reading), the
  engagement's info for `due`, and the reminder's draft-week reader for
  `draft` (the one `_reminder_payload` uses; the letter is not composed).
- A `returns[]` row carries no return name: the page joins it to `list`
  by `path`. `year` is the return's own tax year from its record (else its
  folder's year), so a return link can read "{Return Name} ({Year})"
  without the renderer working it out (ruling 13). A `files[]` entry's
  `return` is its return's `path`; it carries that return's `year`, the
  file's `handle` (the key its return's `state` knows it by), and
  `suggestion`, the first suggestion's request label or "". Files moved by
  hand are listed too (code `file-moved`, no suggestion), so `files[]`,
  `returns[].files` and `totals.files` agree, and `oldest` comes from that
  one list.
- `paused` (ruling 21) is true on every `returns[]` entry of a household
  whose active returns span two open years (`households.open_years`, the
  test behind `runner.TWO_OPEN_YEARS` and `household.two_open_years`),
  computed from the walk the reply already makes: no further disk read.
  The page marks the return with the notice's words.
- `files[].open_key` and the top-level `paths` are ruling 15's: a file's
  name is a link that shows its copy in File Explorer. A key is the state's
  (`shown_copy <row>` for a parked or set-aside file, `moved_copy <row>` for
  one moved by hand); two returns may spell one key for different paths, so
  the later is suffixed ` #2`, ` #3`, and `paths` answers each spelling.
- A return counts under **Need a person** when its `needs_you` count or its
  `files` is above zero, or it has a `problem`; never as Complete.
- `draft.ready`: drafted this draft-week and not yet approved (an approval
  the letter was edited after does not count); `held`: the holding rows
  plus the unsorted inbox files; a hold does not unmake ready (6.3).
- A return whose record cannot be read is one row with `problem` set and
  zero counts; it never fails the reply (decision 189's rule). Its
  `problem` is "Could Not Be Read" (`api.FIRM_UNREADABLE`; the words need
  Jason's approval, section 19) and the detail goes to the error log. A
  root that cannot be walked is `PRACTICE_NOT_WALKED`, as `list` says it.
- These fields are S1's (rebuilds 1 and 3); `year` on both lists and
  `handle` on `files[]` came in S1 rebuild 3, not yet reviewed at this sync.
- `next_sort`: the schedule's next run as `scheduling` reports it to the
  Schedule dialog, or null.
- Budget: 750 returns under 3 seconds on the office PC (measured in the
  Windows check, section 16). No reading of any document.
- `firm` is added to `COMMANDS`, not to `WRITING_COMMANDS`; `main.js`
  learns it through `vocab.commands` like every other.

### 9.3 Two small payload fields

- `list` gains `paths: {"clients_root": root, "status": root/status.html}`,
  and `PATH_KINDS` gains `"clients_root": "folder"`, so File › Open clients
  folder and Tools › Firm report open only what the API reported (decision
  188's rule in `main.js` is unchanged).
- `list`'s `last_pass` gains `{"ok": bool, "when": iso}` beside its line,
  so the last-sort line can say "Sorted {time}" or "Sort failed" without
  parsing the runner's sentence.
- `paths` rides on `list` only, not on the writes that carry the list.
- (Rulings 8 and 12, S8a.) `state.paths` also reports each working copy a
  file link may show, by key, with `PATH_KINDS` naming each key's kind;
  index rows and moved rows carry their copies' keys, and a parked row its
  `shown_key` (5.7). Household and return rows carry none. `firm` reports
  the same for its files (`files[].open_key`, `paths`; 9.2).

### 9.4 Tests for the engine part (`tests/test_api.py`)

- `test_firm_counts_match_the_return_pages_groups`: on the sample, each
  return's counts equal the `group` tally of its `state`.
- `test_firm_is_read_only`: the root's files, the store and the record are
  byte-identical after `firm`; no lock file appears.
- `test_firm_says_an_unreadable_record_as_its_own_row`.
- `test_firm_leaves_out_inactive_returns`.
- `test_item_group_follows_its_table`: one row per line of 9.1.
- `test_list_reports_the_clients_root_and_the_firm_report_as_openable`.

## 10. Tokens, light and dark (P72, P73)

### 10.1 Where they are written

In `pilot-ui.css`, and nowhere else: one `:root` block (light), then
`@media (prefers-color-scheme: dark) { :root { … } }` holding the **same
names** with dark values. `--bg-page` is `var(--window-light)` in the first
and `var(--window-dark)` in the second; `main.js` reads those two literals
(5.6). Names say what a colour is for, never its hue, except the kept
aliases below. Outside the two blocks, no stylesheet of the pilot's writes
a hex, `rgb(`, font size, weight or line height (Build E's rule, now for
`shell.css` too).

| Token | Light | Dark | For |
|---|---|---|---|
| `--bg-page` | `#ffffff` | `#1b1e24` | page and window |
| `--bg-nav` | `#f3f5f8` | `#15171c` | side panel |
| `--bg-raised` | `#ffffff` | `#23272f` | sheet, dialogs, tooltip, toast |
| `--bg-hover` | `#f1f5f9` | `#252a32` | row and button hover |
| `--bg-nav-hover` | `#e7ecf2` | `#1f232a` | section hover |
| `--bg-pressed` | `#e2e8f0` | `#2d333c` | pressed |
| `--bg-selected` | `#e3eaf4` | `#26303f` | selected section, selected option, text selection |
| `--text` | `#0f172a` | `#e8ecf2` | headings, row names, body |
| `--text-secondary` | `#434f63` | `#b9c3cf` | row detail column |
| `--text-caption` | `#566579` | `#9aa6b4` | captions, counts, dates |
| `--text-disabled` | `#94a3b8` | `#5f6b7a` | disabled (exempt, WCAG 1.4.3) |
| `--accent` | `#14335c` | `#a8c4ee` | primary fill, selection pill, progress |
| `--accent-hover` | `#0e2544` | `#c3d6f4` | primary hover |
| `--on-accent` | `#ffffff` | `#0e1a2e` | text on the accent |
| `--link` | `#14335c` | `#a8c4ee` | path segments, row steps, subtle buttons |
| `--focus` | `#2563eb` | `#7fb0ff` | focus ring |
| `--border` | `#e2e8f0` | `#2e343d` | hairlines |
| `--border-strong` | `#cbd5e1` | `#434b57` | control edges |
| `--border-input` | `#7d8ea5` | `#7a8697` | input bottom edge |
| `--st-attention` | `#8a3a0c` | `#f2b872` | status: needs you, held |
| `--st-waiting` | `#1e3a8a` | `#a3bff0` | status: waiting on client, stage |
| `--st-done` | `#05603f` | `#7dd8b0` | status: received, accepted |
| `--st-error` | `#991b1b` | `#ffa29b` | status: failed |
| `--danger` | `#b42318` | `#ff9189` | danger text (Stop, Unfile, Discard) |
| `--err-bg` | `#fef2f2` | `#3a1d20` | error notice fill |
| `--err-border` | `#fecaca` | `#6e2f33` | error notice edge |
| `--err-fg` | `#991b1b` | `#ffb8b3` | error notice ink |
| `--warn-bg` | `#fffbeb` | `#35290f` | warning notice fill |
| `--warn-border` | `#fde68a` | `#6b5420` | warning notice edge |
| `--warn-fg` | `#7c3a0a` | `#f6d08a` | warning notice ink |
| `--info-bg` | `#eff6ff` | `#1a2940` | info notice fill |
| `--info-border` | `#bfdbfe` | `#34507a` | info notice edge |
| `--info-fg` | `#1e3a8a` | `#bcd3f7` | info notice ink |
| `--badge-bg` | `#fcd34d` | `#fcd34d` | pilot badge fill |
| `--badge-fg` | `#0e2544` | `#0e2544` | pilot badge ink |
| `--brand` | `#14335c` | `#14335c` | the side panel's brand band (the logo's ground) |
| `--window-light` | `#ffffff` | `#ffffff` | first paint, light (main.js reads it) |
| `--window-dark` | `#1b1e24` | `#1b1e24` | first paint, dark (main.js reads it) |
| `--scrim` | `rgba(15, 23, 42, 0.32)` | `rgba(0, 0, 0, 0.56)` | behind the sheet and dialogs |
| `--scroll-thumb` | `#8593a6` | `#737f8e` | scrollbar thumb |
| `--shadow-overlay` | `0 8px 32px rgba(15, 23, 42, 0.24), 0 2px 8px rgba(15, 23, 42, 0.12)` | `0 8px 32px rgba(0, 0, 0, 0.48), 0 2px 8px rgba(0, 0, 0, 0.32)` | sheet, tooltip, toast, dialogs |

Kept names, so every rule already written picks up the right value in both
themes (they become aliases in both blocks):

| Old name | Becomes |
|---|---|
| `--bg` | `var(--bg-page)` |
| `--card` | `var(--bg-raised)` |
| `--muted` | `var(--text-secondary)` |
| `--subtle` | `var(--text-caption)` |
| `--navy` | `var(--accent)` |
| `--navy-deep` | `var(--accent-hover)` |
| `--blue`, `--blue-dark` | `var(--focus)` |
| `--surface-hover` | `var(--bg-hover)` |
| `--surface-pressed` | `var(--bg-pressed)` |
| `--surface-selected` | `var(--bg-selected)` |
| `--surface-sunken`, `--surface-disabled` | `var(--bg-nav)` |
| `--ok-bg` / `--ok-border` / `--ok-fg` | light `#ecfdf5` / `#a7f3d0` / `#065f46`; dark `#10291f` / `#1f5a43` / `#9be3c3` (7.29 and 10.43:1) |
| `--amber`, `--amber-deep`, `--amber-soft` | unchanged in both (the tour's spot ring) |

The primary button's text becomes `var(--on-accent)` (in dark the accent is
light, so white text on it would fail).

### 10.2 Contrast, computed before writing

WCAG 2 ratios of every pair the shell draws, both themes (the script that
computed them becomes the test in 14.1). Text pairs that the brief asks to
be AAA are held to 7:1; captions and states to 4.5:1; marks that are not
text (focus ring, input edge, selection pill) to 3:1. All pass.

| Text or mark | On | Needs | Light | Dark | Used for |
|---|---|---|---|---|---|
| `--text` | `--bg-page` | 7:1 | 17.85 | 14.08 | H1-H3, row names, body |
| `--text` | `--bg-nav` | 7:1 | 16.35 | 15.12 | side panel section names |
| `--text` | `--bg-hover` | 7:1 | 16.3 | 12.17 | row name on hover |
| `--text` | `--bg-nav-hover` | 7:1 | 15.03 | 13.3 | section name on hover |
| `--text` | `--bg-selected` | 7:1 | 14.74 | 11.23 | selected section |
| `--text` | `--bg-raised` | 7:1 | 17.85 | 12.63 | sheet, menus, dialogs, tooltip |
| `--text` | `--bg-pressed` | 7:1 | 14.48 | 10.73 | pressed row or button |
| `--text-secondary` | `--bg-page` | 7:1 | 8.28 | 9.36 | second column, body secondary |
| `--text-secondary` | `--bg-hover` | 7:1 | 7.56 | 8.08 | second column on hover |
| `--text-secondary` | `--bg-raised` | 7:1 | 8.28 | 8.39 | secondary in the sheet |
| `--text-caption` | `--bg-page` | 4.5:1 | 5.94 | 6.75 | captions, dates, counts |
| `--text-caption` | `--bg-nav` | 4.5:1 | 5.44 | 7.25 | last-sort line, section counts |
| `--text-caption` | `--bg-hover` | 4.5:1 | 5.43 | 5.83 | date on a hovered row |
| `--text-caption` | `--bg-selected` | 4.5:1 | 4.91 | 5.38 | count on the selected section |
| `--text-caption` | `--bg-raised` | 4.5:1 | 5.94 | 6.05 | captions in the sheet and menus |
| `--link` | `--bg-page` | 7:1 | 12.67 | 9.38 | breadcrumb segments, row actions |
| `--link` | `--bg-hover` | 7:1 | 11.56 | 8.1 | row action on a hovered row |
| `--on-accent` | `--accent` | 7:1 | 12.67 | 9.78 | primary button text |
| `--on-accent` | `--accent-hover` | 7:1 | 15.36 | 11.81 | primary button hover |
| `--st-attention` | `--bg-page` | 7:1 | 7.8 | 9.44 | status: needs you |
| `--st-attention` | `--bg-hover` | 4.5:1 | 7.12 | 8.16 | status on hover |
| `--st-waiting` | `--bg-page` | 7:1 | 10.36 | 8.96 | status: waiting on client |
| `--st-waiting` | `--bg-hover` | 4.5:1 | 9.45 | 7.74 | status on hover |
| `--st-done` | `--bg-page` | 7:1 | 7.63 | 9.8 | status: received |
| `--st-done` | `--bg-hover` | 4.5:1 | 6.97 | 8.46 | status on hover |
| `--st-error` | `--bg-page` | 7:1 | 8.31 | 8.66 | status: failed |
| `--st-error` | `--bg-nav` | 4.5:1 | 7.61 | 9.3 | last-sort line when it failed |
| `--danger` | `--bg-raised` | 4.5:1 | 6.57 | 6.89 | danger menu item and button |
| `--danger` | `--bg-hover` | 4.5:1 | 6.0 | 6.64 | danger item hovered |
| `--err-fg` | `--err-bg` | 7:1 | 7.6 | 9.27 | error notice |
| `--warn-fg` | `--warn-bg` | 7:1 | 8.21 | 9.7 | warning notice |
| `--info-fg` | `--info-bg` | 7:1 | 9.52 | 9.62 | info notice |
| `--badge-fg` | `--badge-bg` | 7:1 | 10.66 | 10.66 | pilot badge |
| `--focus` | `--bg-page` | 3:1 | 5.17 | 7.6 | focus ring (non-text, 1.4.11) |
| `--focus` | `--bg-nav` | 3:1 | 4.73 | 8.16 | focus ring on the side panel |
| `--focus` | `--bg-raised` | 3:1 | 5.17 | 6.81 | focus ring in the sheet |
| `--border-input` | `--bg-page` | 3:1 | 3.34 | 4.52 | input edge (1.4.11) |
| `--border-input` | `--bg-raised` | 3:1 | 3.34 | 4.05 | input edge in dialogs |
| `--accent` | `--bg-page` | 3:1 | 12.67 | 9.38 | selection indicator bar (1.4.11) |
| `--accent` | `--bg-selected` | 3:1 | 10.46 | 7.48 | indicator on its selected fill |
| `--scroll-thumb` | `--bg-page` | 3:1 | 3.12 | 4.10 | scrollbar thumb |
| `--ok-fg` | `--ok-bg` | 7:1 | 7.29 | 10.43 | the editor's saved line |

Disabled text is exempt (WCAG 1.4.3) and is paired with the `disabled`
attribute and no hover change (P52). The logo is exempt (a logotype) and
sits on `--brand` in both themes, the ground it was drawn for; the band is
11.6:1 against the light side panel and, in dark, is set apart by its
hairline (the navy band on a near-black panel is a deliberate block of
brand colour, not a text pair).

### 10.3 Space and size (P72)

- **Spacing** (padding, margin, gap): `--sp-1` 4, `--sp-2` 8, `--sp-4` 16,
  `--sp-6` 24, `--sp-8` 32, `--sp-12` 48. Build E's `--sp-half` (2),
  `--sp-3` (12) and `--sp-5` (20) are deleted; every use moves to the
  nearer step that keeps the component's size on the grid (a 32px button
  keeps `padding: 0 var(--sp-4)`; a 24px one `0 var(--sp-2)`).
- **Sizes** are multiples of 4: row 40, control 32 and 24, path row and sheet
  header 48, sheet footer 64, side panel 240, sheet 400, search 240, icon 16,
  selection pill 3 × 16 (the one 3px value, Fluent's), hairline 1.
- **Corners:** `--radius-control` 4 (controls, section rows, notices),
  `--radius` 8 (dialogs, toast, tooltip), `--radius-pill` goes with the
  chips.

### 10.4 Contrast themes and the original's literal colours

- `shell.css` ends with its own `forced-colors: active` block (each
  stylesheet ends with one, as the tests already require of the others),
  covering the new parts: side sections and rows draw `CanvasText` on
  `Canvas`; the selected section and the focused row use `Highlight` /
  `HighlightText`; the selection pill, the focus ring, hairlines, the
  sheet's edge and notices use `CanvasText`; icons are `currentColor`;
  disabled is `GrayText`. The brand band gives way to `Canvas` with a
  `CanvasText` edge.
- `style.css` writes some colours as literals in its rules (not through
  its tokens). Those rules still in use (dialogs, inputs, the editor, the
  wizard) are overridden in `pilot-ui.css`'s dark block, selector for
  selector. The build lists them from the file (a rule with a literal
  colour whose selector still matches markup that exists after this work)
  and `test_every_literal_colour_still_in_use_has_a_dark_value` (14.1)
  keeps the list honest.

## 11. Wording (P63, P66)

Since P196 the screen says Taxpayer for the person and Household for the
listed household where this section says client; a button naming a folder
on disk keeps "client folder". See `SPEC-taxpayer-words.md`.

### 11.1 The rules

Five words or fewer for every label, heading, notice, error, tooltip,
dialog line and toast; placeholders count as one word; `&` access keys are
not counted. No path of any kind. No full stop on labels, headings,
buttons or tooltips. Say return, sort, request list, client folder, inbox;
never manifest, engagement, pass, record, scan or a request code. Two
exceptions (P63): the pilot terms and the reminder letter. User data
(names, file names) is content and is not counted.

**Title Case throughout (ruling 10, 2026-09-29; replaces "sentence case",
and P53's sentence-case table headers).** Every drawn phrase (at most five
words) is Title Case:

- Capitalise every word except **a, an, the, and, but, or, nor, for, of,
  on, in, to, by, at, as, up, vs** when they are neither the first nor the
  last word.
- Capitalise each part of a hyphenated word ("Last-Year", "Set-Aside"),
  and the word after a colon or semicolon ("Held: {n} Need a Decision",
  "Not Opened; It Has Changed").
- Leave untouched: placeholders (`{n}`, `{host}`), numbers, ALL-CAPS tokens
  ("AI", "PDF", "HEIC"), file names and record data (names the record
  holds, stored override reasons).
- **Exceptions, unchanged:** the pilot terms; the client reminder letter
  and its subject; the error log's contents; prose in the docs.

Examples: "Needs Review", "Could Not Sort", "Fits Two Requests", "Moved by
Hand", "Open a Client to Sort", "Sort Stopped: Ran Too Long". Sections
11.3-11.6 and the `title_case` column of
[`wording-shell.tsv`](wording-shell.tsv) give every exact spelling. Words
quoted elsewhere in this SPEC in sentence case (sections 0-8, written
before ruling 10) are the same words and are drawn in the spelling of
11.3-11.6; where the two differ, 11.3-11.6 wins. S8a applies the rule to
the engine's words (with a test), S5 and S6 to the renderer's and the
tour's literals.

### 11.2 Today's strings over five words

**Approved by Jason (P84).** All 212, today and proposed, one row each, in [`wording-shell.tsv`](wording-shell.tsv)
(columns: source, key, today, verdict, proposed, words, where, note,
title_case, changed). `title_case` is the proposed words in ruling 10's
casing, the spelling the app draws (empty for a cut row; the terms
unchanged). `changed` says what ruling 10 or a later ruling did to the
row: `case` (casing only), `word (rulings …)` (the words changed),
`no`, or `-` (cut).
Verdicts: **reword** 67, **cut** 113 (not shown in the app any more),
**error-log** 10 (the detail goes to the error log; a short line stays),
**merge** 5 (says the same as another row), **exception** 17 (the terms).

- "Cut" removes the words from the screen, not always from the code: a
  constant another reader uses keeps its words there. The status report
  page (`tracker/view.py`) still reads the status labels' sentences, and the
  reminder letter reads its own; the build removes a key from `_vocab()`
  only when no page of the app reads it.
- **Override reasons** (`override_reasons[0..2]`) are values the record
  stores. Their words in the record do not change (that would change
  behaviour, outside P66); the editor's list shows the short label for each
  stored value (P77).
- **A risky act keeps its warning:** moving the schedule to this computer
  gains "Only if {host} is retired" (`schedule.move_warning`), and the
  editor's Active field keeps "No: sorting skips this return".
- **No error log yet (rulings 4 and 6):** when the tracker fails before it
  has a data folder (first start only), the API names no error log; the
  details are no longer printed on screen, they are saved in the shell's
  fallback log (`error.log` in `%LOCALAPPDATA%\Tax Document Tracker Pilot`,
  a local folder that does not roam, never the data home; capped at 256 KB
  with one `.1` copy; 5.5), and the notice is the failure's own sentence, a
  blank line, then "Tracker Failed" (`shell.no_log`).

### 11.3 New words: the menu (`vocab.menu`, `api.MENU`)

| Key | Words | | Key | Words |
|---|---|---|---|---|
| `file` | &File | | `view` | &View |
| `new_household` | New Household… | | `overview` | Overview |
| `change_root` | Change Clients Folder… | | `needs_review` | Needs Review |
| `open_root` | Open Clients Folder | | `reminders` | Reminders |
| `exit` | Exit | | `clients` | Clients |
| `edit` | &Edit | | `find` | Find |
| `client` | &Client | | `refresh` | Refresh |
| `edit_household` | Edit Household… | | `tools` | &Tools |
| `add_return` | Add a Return… | | `sort_now` | Sort Now |
| `roll_forward` | Roll Forward… | | `stop_sorting` | Stop Sorting |
| `mark_shared` | Mark as Shared | | `schedule` | Schedule… |
| `edit_list` | Edit Request List… | | `repair_schedule` | Repair Schedule |
| `draft_reminder` | Draft Reminder… | | `firm_report` | Firm Report |
| `open_client_folder` | Open Client Folder | | `clear_lock` | Clear Stuck Lock |
| `open_inbox` | Open Inbox | | `help` | &Help |
| `open_working` | Open Working Folder | | `tour` | Take the Tour |
| `check` | Check… | | `safeguards` | Safeguards |
| `not_requested` | Not Requested | | `terms` | Terms |
| `another_return` | Another Return… | | `error_log` | Open Error Log |
| `put_back` | Put Back | | `about` | About |
| `keep_here` | Keep Here | | `unfile` | Unfile |
| `edit_request` | Edit Request… | | `mark_missing` | Mark Missing |
| `show_in_explorer` | Show in File Explorer | | `show_under_construction` | Show &Under Construction (P197, a checked item) |

### 11.4 New words: the screen (`vocab.screen`)

Where an existing key does the same job, the existing key is reworded
(11.2) and reused, not duplicated; these are the words with no key today.

| Key | Words | Where |
|---|---|---|
| `sections.overview` / `needs_review` / `reminders` / `clients` | Overview / Needs Review / Reminders / Clients | side panel, path |
| `side_label` | Sections | the side panel's name for screen readers |
| `path_label` | Path | the path's name for screen readers |
| `find` | Find a Client | search name and tooltip |
| `find_none` | No Match | search list |
| `sort.now` / `sort.stop` / `sort.firm` / `sort.locked` / `sort.stopping` | Sort Now / Stop Sorting / Open a Client to Sort / In Use Elsewhere / Stopping | sort icon tooltip and name |
| `last_sort.today` / `other_day` / `failed` / `never` / `running` | Sorted {time} / Sorted {date} / Sort Failed / Not Sorted Yet / Sorting {n} of {total} | side panel foot |
| `last_sort.done` | Sorted | done icon tooltip |
| `figures.need` / `waiting` / `complete` | Need a Person / Waiting on Clients / Complete | Overview |
| `work` | Work Waiting | Overview H2 |
| `empty.overview` / `next_sort` | Nothing Is Waiting / Next Sort {time} | Overview empty |
| `empty.needs_review` | Nothing Needs Review | Needs Review empty |
| `empty.reminders` | No Drafts Ready | Reminders empty |
| `empty.clients` | No Clients Yet | Clients empty |
| `empty.work` | No Work Waiting | Clients, Work waiting empty |
| `empty.returns` | No Returns Yet | household empty |
| `empty.received` | Nothing Received Yet | Received group |
| `filters.work` / `filters.all` | Work Waiting / All | Clients switch |
| `counts.need` / `waiting` / `complete` | {n} Need You / {n} Waiting / Complete | row status |
| `counts.returns` / `one_return` / `files` | {n} Returns / 1 Return / {n} Files | row detail |
| `due` | Due {date} | row date, return caption |
| `partly` | {n} of {total} | row detail |
| `groups.needs_you` / `waiting` / `received` / `set_aside` | Needs You / Waiting on Client / Received / Set Aside | return page |
| `steps.check` / `open` / `draft` / `edit` | Check / Open / Draft Reminder / Edit | row step |
| `moved` | Moved by Hand | row status |
| `held` | Held | Reminders row status |
| `inactive` / `rolled` | Inactive / Rolled Forward | household row detail |
| `contact` | Contact {name} | household caption |
| `shared` / `not_shared` | Shared / Not Shared | household caption, done icon |
| `icons.dismiss` / `open` / `next` / `more` | Dismiss / Open / Next / More | icon tooltips |
| `sheet.reminder` | Reminder | sheet title |
| `sheet.drafted` | Drafted {date}, Stage {n} | sheet caption |
| `loading` | Loading | screen readers only |
| `setup.title` / `choose` / `start` / `missing` | Choose Your Clients Folder / Choose Folder… / Start / Folder Not Found | setup page |
| `notices.firm_failed` | Counts Not Available | notice |
| `notices.skipped` / `show` | {n} Folders Skipped / Show | notice |
| `notices.no_log` | No Error Log Yet | toast |
| `notices.drive` | Drive Not Signed In | notice (the machine warning's short line) |
| `misfits.title` | Folders Skipped | dialog |
| `misfits.reasons.<code>` | two words per misfit code (ruling 18); `not_a_year` is Bad Year (ruling 18a) | dialog, beside the folder name |
| `close` | Close | the one word for closing a sheet or a dialog (S5 review F9); `icons.dismiss` stays for the notice icon |
| `notices.pick_request` / `name_requests` | Pick a Request First / Name Each Custom Request (proposed for Jason) | the request-list editor, beside a disabled action |
| `editor.advanced` (`vocab.editor`) | Advanced | the editor's one switch for routing columns |
| `safeguards.title` | Safeguards | dialog |
| `about.edition` | Pilot {version} | About dialog, badge |
| `retry` | Retry | notice action |
| `copied` / `saved` | Copied / Saved | toast |
| `schedule.move_warning` | Only If {host} Is Retired | Repair schedule confirm |
| `show_in_explorer` (ruling 12) | Show in File Explorer | tooltip of every file name that is a link (3.9) |
| `navigate_client` (ruling 11) | Navigate to Client | tooltip of every household name that is a link |
| `navigate_return` (ruling 12) | Navigate to Return | tooltip of every return name that is a link |
| `FIRM_UNREADABLE` (`firm`'s `problem`, S1) | Could Not Be Read | Overview row of a return whose record cannot be read; **awaiting Jason's approval** (section 19) |

The three link keys' words are Jason's (rulings 11 and 12); the key names
are S8a's work in progress and are final with its review.

### 11.5 Short reasons (`reasons.py`, one per code, `vocab.reasons`)

A `short` beside each code's sentence; the row shows it, the sentence stays
where it is used today (the index, the letter, the log). A label shortened into
a tag has its longer words in `reasons.REASON_TIPS` (`vocab.reason_tips`), shown
as its tooltip every time (P116).

| Code | Short | | Code | Short |
|---|---|---|---|---|
| `unmatched` | Could Not Sort | | `name-absent` | No Client Name Found |
| `ambiguous` | Fits Two Requests | | `name-other` | Names Another Return |
| `contested` | Claimed by Two Requests | | `named-across` | Names Another Household |
| `between-returns` | Fits Two Returns | | `unnamed-across` | No Name on It |
| `ocr-only` | Read From Scan Only | | `name-points-at` | Name Hints a Request |
| `no-request-accepts` | File Type Not Asked | | `shows-form-number` | Shows a Form Number |
| `several-forms-unsorted` | Several Forms, Unsorted | | `issuer-not-named` | Issuer Not Named |
| `no-room` | No Room for Name | | `no-people` | Return Has No People |
| `could-not-file` | Could Not File | | `answer-not-counted` | Statement Not Counted |
| `put-back-refused` | Could Not Put Back | | `opened-not-across` | Email or Zip (P116; tooltip "Came in Email or Zip") |
| `unfiled` | Unfiled by a Person | | `container-damaged` | Email or Zip Damaged |
| `not-requested` | Not Requested | | `container-empty` | Nothing Attached |
| `assigned` | Filed by a Person | | `container-limit` | Email or Zip Too Big |
| `matched` | Filed | | `container-locked` | Email or Zip Locked |
| `several-forms` | Filed as Several Forms | | `password` | Password Protected |
| `filed-whole` | Filed Whole | | `google-stub` | Google Shortcut Only |
| `file-moved` | Moved by Hand | | `extension` | File Type Not Allowed |
| `copy-missing` | Copy Missing | | `not-a-document` | Not a Document |
| `copy-changed` | Copy Was Changed | | `too-small` | File Almost Empty |
| `copy-and-original-gone` | Copy and Original Gone | | `too-large` | Too Large to Read |
| `interrupted-move` | Step Interrupted | | `no-pages` | PDF Has No Pages |
| `interrupted-move-lost` | Move Interrupted | | `unreadable-pdf` | PDF Will Not Open |
| `pending-sync` | Syncing | | `unreadable-image` | Photo Will Not Open |
| `vanished` | File Disappeared | | `heic-reader` | HEIC Photo, No Reader |
| `no-keyword` | Expected Words Missing | | `uncheckable-type` | Cannot Check This Type |
| `wrong-document` | Looks Like Wrong Document | | `extraction-failed` | Text Could Not Be Read |
| `wrong-period` | Wrong Period | | `no-text-layer` | Scan Not Readable |
| `reader-unavailable` | Reader Did Not Start | | `no-text-after-ocr` | No Readable Text |
| `reading-crashed` | Reader Stopped | | `ocr-failed` | Scan Reading Failed |
| `reading-stopped` | Reading Timed Out | | `unreadable` | Nothing Readable |

`unmatched` was "Could not tell"; it is "Could Not Sort" (ruling 8(c),
spelled per ruling 10: Jason typed "Could not Sort", and ruling 10 wins).

A test requires one short label for every code in `BY_CODE` and
`PLAIN_CODES`, each five words or fewer.

### 11.6 Stages and safeguards

- Reminder stages gain a `short` each: "Heads Up", "Checking In",
  "Deadline Near", "Final Notice". The letter's subject keeps its full name
  and its own casing (ruling 10's exception).
- `tracker/__init__.py` gains `SAFEGUARDS`, four short lines beside
  `STANDING_RULES` (which keeps its full wording): "No AI Reads Documents",
  "Originals Never Changed", "Nothing Is Guessed", "Nothing Is Ever Sent"
  (P64, in ruling 10's casing). `vocab.rules` carries both; Help ›
  Safeguards shows the short ones.

## 12. The pilot layer

- **Badge:** `pilot.js` puts `#pilot-badge` in `#side-foot`, caption,
  "Pilot 0.2" (`about.edition`), `--badge-bg` / `--badge-fg`, 24px tall,
  `--radius-control`. Its float fallback stays for a missing panel.
- **Tour button:** removed from the page; Help › Take the tour starts the
  tour (`menu` id `tour`).
- **Terms:** shown once as today (P20, exception). Help › Terms shows the
  same card read-only: its Accept and Quit become one **Close**.
- **Tour anchors** (`pilot-content.js`) move to the new ids:

| Step | Today | New anchor |
|---|---|---|
| One Clients Folder | `setup-card` | `page` (the setup page) |
| Household and Request List | `btn-new-household` | `side-sections` (Clients) |
| Drop Files Here | `btn-inbox` | `crumbs` |
| Sort | `btn-scan` | `sort` |
| Originals, Untouched | `moved-card` | `page` |
| Organized Working Copies | `filed-card` | `page` |
| Needs Review | `review-card` | `side-sections` |
| Status Page | `btn-status`, `eng-select` | `side-sections` (Overview) |
| Drafted Reminder | `reminder-card` | `side-sections` (Reminders) |

The step titles are drawn, so they are in Title Case (ruling 10); the
Needs Review step's title is "Needs Review" (ruling 8(b)). S6 changes them
in `pilot-content.js`.

- **Tour lines:** one line per step, five words or fewer
  ([`wording-shell.tsv`](wording-shell.tsv), `tour.steps[n].does`); the
  strength, limit and fallback lines and the stage chips go. The test that
  capped tour lines at 30 words (`tests/test_pilot.py`) caps them at five.
  The lines are drawn in the spelling of the table's `title_case` column
  (e.g. "Unsure Files Wait for You"); the terms keep their own wording.

## 13. `app.js`: what stays, what goes

| Kept as is | Kept, changed | Moved or removed |
|---|---|---|
| `el`, `fill`, `call`, `withEng`, `isSetAside`, `overrideLabel`, `toast`, the notice machinery (`notice`, `drawNotice`, `failed`, `failureSentence`, `warningNotices`, `dismissNotice`), the dialog stack (`DIALOGS`, `openDialog`, `closeDialog`, `requestClose`, `keepEditing`, `trapTab`, snapshots), every write (`fileRow`, `assignParked`, `addIssuerAndFile`, `fileWhereItWaits`, `handOver`, `dismissParked`, `unfileDocument`, `withdrawAnswer`, `restoreMoved`, `keepMoved`, `markShared`, `acceptFolderName`, `clearLock`, `copyReminder`, `approveReminder`, `saveHousehold`, `saveSchedule`, `repairSchedule`, `createEngagement`, `saveEditor`), the pass (`runScan`, `stopPass`, `onPassMessage`, `passEnded`, `scanDone`) | `applyVocabulary` (only ids that still exist; the menu's words are `main.js`'s); `reviewRow`, `movedRow` (build one row for the sheet, with More folding Keyword, Spelling, Reason); `drawReminder` (short stage names, no hint, no Open the draft file); `drawProgress` (to `#last-sort`); `showLock`, `applyLock` (a notice; the menu's enable list instead of `LOCKED_BUTTONS`); `openEditor` (takes a row to focus; help lines cut); `openNewHousehold` and the wizard steps, `openHouseholdEditor`, `openSchedule` (help lines cut); `bootstrap`, `loadEngagements`, `adoptList`, `showReturn` (hand data to `shell.js` and `pages.js` instead of drawing cards); `saveRoot` (the setup page; the hidden input); `renderAfterInstall`, `renderShortOfRoom`, `renderMisfits` (notices; misfits into `#misfits-modal`); `rollFromCard` and `renderRollFold` (into `#roll-modal`) | removed: `chip`, `sideLine`, `setAsideHeading`, `requestTableRow`, `ruleTooltip`, `render`, `renderEngagements`, `renderHousehold`'s card drawing, `returnReminderLine`, `renderSharing`'s checklist, `banner`, the deck (`REVIEW_MODE_*`, `storedReviewMode`, `setReviewMode`, `applyReviewMode`, `deckOrder`, `renderDeck`, `deckCard`, `acceptCard`, `openCardInList`, `skipCard`, `cameFrom`), `renderUnfileList`'s card, `SCAN_LABEL` (the sort icon's words are the API's); moved to `pages.js`: the grouping of `state` into rows (by `group`); to `sheet.js`: placing one row in the sheet and the next order |

Every `title=` and `.title =` in the renderer becomes `setTip()`. The guards
that hold for `app.js` today (no `innerHTML`, no `insertAdjacentHTML`, no
`outerHTML`, no `document.write`, no `eval`, no inline style attribute, no
network call) hold for each new file, and the tests say so by name.

## 14. Tests

The survey of every test that reads the renderer or shell files is
[`shell-test-pins.md`](shell-test-pins.md): 162 tests, of which 113 hold
unchanged, 35 change (one more since rulings 4 and 6), 1 goes and 13 were
open; this section settles the 13.
Test names state the claim, as the repository's convention asks.

### 14.1 New: `tests/test_shell.py`

Static (read the files):

- `test_every_colour_pair_meets_its_contrast_in_both_themes`: parses both
  `:root` blocks of `pilot-ui.css` and checks the table of 10.2 (the table
  is the test's data).
- `test_every_light_token_has_a_dark_value_and_no_other`.
- `test_the_window_colours_main_reads_are_the_pages`: `--window-light` /
  `--window-dark` exist, `--bg-page` resolves to them, and `main.js` reads
  those two names from `pilot-ui.css`.
- `test_every_space_is_a_step_of_the_grid`: in `shell.css` and
  `pilot-ui.css`, padding, margin and gap are `0`, `auto`, a
  `var(--sp-1|2|4|6|8|12)` or `calc()` of them; the retired steps are gone.
- `test_every_size_is_a_multiple_of_four`: every `--size-*` token; the
  selection pill (3) and the hairline (1) by name.
- `test_every_line_height_lands_on_the_grid`: each type role's size times
  its line height is a multiple of 4.
- `test_the_shells_stylesheet_follows_the_structure_passes_rules`: the
  `test_pilot_ui.py` rules applied to `shell.css` too (no hex or `rgb(`
  outside the token blocks, no literal font size, weight or line height,
  no `url(`, `@import`, `@font-face`, blur or backdrop, `!important` only
  under reduced motion, every non-`none` `display` under `:not(.hidden)`,
  and it ends with its own `forced-colors` block).
- `test_every_literal_colour_still_in_use_has_a_dark_value` (10.4).
- `test_every_screen_word_is_five_words_or_fewer`: walks `_vocab()`; the
  keys that are not screen words (patterns, identifiers, command names,
  path kinds, the letter's own text) are an explicit list in the test.
- `test_no_screen_word_names_a_path`: no drive letter, no backslash, no
  `word/word`, no `.log`, `.db`, `.jsonl`, and none of the placeholders
  `{root}`, `{path}`, `{location}`, `{file}`, `{home}`, `{now}`, `{left}`,
  `{log}`.
- `test_every_short_reason_is_there_and_short` (11.5).
- `test_every_icon_has_a_name_and_a_tooltip`: each icon-only button in
  `index.html` carries `data-tip-key` naming a vocabulary key of five
  words or fewer; `shell.js` sets both `aria-label` and the tooltip from it.
- `test_the_renderer_has_no_title_attribute`: no `title=`, no `title:` in
  `el()` attributes, no `.title =` in any renderer file.
- `test_the_menu_has_no_reload_zoom_or_developer_tools`: no such role and
  no `CmdOrCtrl+R`, `CmdOrCtrl+Shift+I`, `F12` or zoom accelerator.
- `test_the_menus_default_words_are_the_apis_word_for_word`.
- `test_every_menu_id_is_answered_by_the_page_and_every_answer_is_in_the_menu`.
- `test_the_preload_exposes_one_menu_channel`.
- `test_every_accelerator_is_named_once`.
- `test_the_new_renderer_files_keep_the_renderers_guards`: `shell.js`,
  `pages.js`, `sheet.js`, `tooltip.js`: no `innerHTML`,
  `insertAdjacentHTML`, `outerHTML`, `document.write`, `eval`,
  `new Function`, `fetch`, `XMLHttpRequest`, `WebSocket`, `window.open`,
  `openExternal`, `startsWith(`, inline style attribute or `on*=`.
- `test_the_new_renderer_files_type_no_words_of_their_own`: no string
  literal of two or more words.
- `test_one_keydown_listener_owns_the_keyboard`: the page's one
  `document.addEventListener("keydown"` is in `app.js`, which hands the
  shell's keys to `shellKey(e)` in `shell.js` before its dialog handling,
  and the new files (`shell.js`, `pages.js`, `sheet.js`, `tooltip.js`) add
  none. **Accepted exception (ruling 1):** the capturing listeners of
  `pilot.js` (the terms) and `tour.js` stay, as built; they act only while
  the terms or the tour are open (`test_pilot`'s
  `test_the_terms_cannot_be_escaped` pins the terms' one).
- `test_the_harness_is_never_loaded_by_the_app`.
- **Joined (S6b):** `test_the_harness_stub_speaks_the_apis_vocabulary`,
  `test_the_harness_stub_replies_have_the_shape_of_the_engines`,
  `test_every_link_key_the_engine_sends_names_a_real_file_main_js_would_reveal`,
  `test_the_three_info_dialogs_close_with_the_apis_close_word` and
  `test_every_word_index_html_types_is_in_title_case`.
- **Tooltips (rulings 2, 5, 7):**
  `test_the_vendored_floating_ui_is_the_pinned_bytes_and_nothing_else`
  (the SHA-256 of every vendored file, no extra file, the README names the
  versions and hashes);
  `test_the_loading_order_is_the_specs_and_the_csp_is_unchanged` (every
  `<script src>`, however quoted and in any case, is a file of the app, no
  scheme and no `//`; core, then dom, above `app.js`, before `tooltip.js`;
  the CSP is `script-src 'self'`);
  `test_the_tooltip_reaches_floating_ui_only_through_its_one_global`
  (only `FloatingUIDOM`, `computePosition`/`offset`/`flip`/`shift`/`hide`,
  no `import`/`require`, no edge arithmetic, no colour or size literal,
  placement only through `style.setProperty`);
  `test_a_tip_goes_when_its_element_is_scrolled_out_of_view`;
  `test_the_hover_delay_is_300_ms_and_keyboard_focus_waits_for_nothing`;
  `test_the_search_box_alone_shows_no_tooltip_on_keyboard_focus` (both
  halves of ruling 2: focus shows the tip on every other control; the
  search box shows none).
- **Title Case (ruling 10):** a test walks the screen words of `_vocab()`
  (the menu, the screen block, the short reasons, the stage shorts, the
  safeguards, the reworded keys) and requires each in the casing of 11.1,
  with the exceptions' keys (terms, the letter and its subject) listed in
  the test. Its name is S8a's.
- **Links (rulings 8-13):** the page draws a file name as a link that asks
  `open(key, "reveal")`, a household or return name as a link that
  navigates with no engine call, each with its tooltip, and a return link
  reads "{Return Name} ({Year})" from the row's `year`; no link's text or
  tooltip holds a path. The names are S5's; `main.js`'s reveal (same
  allow-list and `lstat`, file only) is S8a's.

Run in node against the file's own functions, as the existing
`_run_renderer` tests do:

- `test_a_return_page_draws_its_groups_in_order_and_leaves_out_empty_ones_but_received`.
- `test_the_overview_puts_each_return_in_one_bucket`.
- `test_a_row_carries_one_step_and_its_status_word_and_no_sentence`.
- `test_long_names_are_cut_and_carry_their_full_name_as_the_tooltip`
  (60 and 80 characters).
- `test_search_finds_a_household_by_any_part_of_its_name_without_calling_the_api`.
- `test_the_menu_channel_drops_what_it_does_not_know` (`main.js`'s handler
  on a stub: unknown ids, a bad popup, a long token, a token echoed).
- `test_the_sort_icon_is_stop_while_a_sort_runs_and_grey_on_a_firm_page`.

The engine part's tests are in 9.4.

### 14.2 Tests that change on purpose

| Test | Change |
|---|---|
| `test_single_source::test_the_shell_and_the_preload_agree_on_every_ipc_channel`, `…sends_on_only_the_channels_the_preload_listens_to` | the `menu` channel, both ways |
| `…test_the_packaged_app_has_no_menu_and_the_source_app_runs_its_private_python` | becomes: the app's menu is the template of 5.1 in both builds (the Python half stays) |
| `…test_the_app_opens_one_window`, `_ELECTRON_STUB`, `_SHELL_HARNESS` | the stub gains `Menu.buildFromTemplate`, `setApplicationMenu`, `nativeTheme`, `ipcMain.on`, `app.getPath`; the harnesses force `process.platform` (`linux` by default) so the fallback log's place does not depend on the host |
| `…test_with_no_error_log_the_shell_says_stderr_in_the_reply_and_writes_no_file` (rulings 4, 6) | becomes `…test_with_no_error_log_named_the_failure_is_saved_in_the_fallback_log_and_the_reply_says_two_words`; joined by `…test_with_an_error_log_named_the_failure_goes_there_and_not_to_the_fallback_or_the_screen`, `…test_the_fallback_log_is_capped_and_a_write_that_fails_never_throws` (the cap, a link, a folder, a stuck `.1`) and `…test_on_windows_the_fallback_log_is_local_and_never_the_roaming_or_data_folder` |
| `…test_the_agent_deny_list_names_the_data_home_and_every_file_that_names_a_client` (ruling 4) | also expects the fallback log's `Read`/`Edit` rules, spelled from `package.json`'s `productName` |
| `…test_the_standing_rules_are_worded_once_and_quoted_everywhere` | the page half: `#safeguards-modal` holds one line per `SAFEGUARDS` entry (P64); the docs half unchanged |
| `…test_the_scan_button_label_is_typed_once`, `…test_documents_name_buttons_by_their_labels` | the label is `vocab.menu.sort_now`, typed nowhere in the renderer; docs name the menu items |
| `…test_accept_and_file_it_are_one_call_site`, `…test_the_issuer_action_has_one_call_site`, `…test_every_review_action_the_renderer_sends_carries_the_rows_seq` | recounted without the deck (the sheet is one caller) |
| `…test_the_end_of_a_pass_gives_sort_and_scan_back_through_the_locks_mark`, `…test_a_switch_between_two_locked_returns…` | the lock gives back the menu's enable list and `#sort`, not `LOCKED_BUTTONS` |
| `…test_every_draw_after_an_await_goes_through_renderFor`, `…test_switching_returns_is_one_state_call` | the picker's handler is gone; the path, rows and search reach `showReturn` |
| `…test_the_reminder_card_is_never_hidden_on_an_error`, `…test_the_reminder_card_is_drawn_from_state` | the sheet, same functions |
| `…test_the_side_sentence_is_text_beside_the_chip_and_never_a_tooltip`, `…test_an_accepted_rows_side_word…` | the row shows no sentence as text or tooltip (P63); an Accepted row sits in Received with the label table's word; `_titles()` also collects `data-tip` |
| `…test_the_card_hands_the_roll_call_the_household_it_shows_and_no_other`, `…test_the_roll_fold_says_what_unticking_does…`, `…test_a_catalog_that_will_not_load…`, `…test_the_roll_folds_people_button…`, `…test_the_roll_banner_says_a_failed_retirement…` | the roll dialog (`rollFromDialog`); a banner becomes a notice |
| `…test_every_word_of_roll_forward_add_a_return_and_new_household_is_the_apis` | the keys the table cuts leave `ROLL_AND_ADD_KEYS` |
| `…test_every_word_a_scan_reply_is_said_in_is_the_apis` | a sort's success summary is gone (the rows show it); its problems are notices in the API's words |
| `…test_edit_request_list_says_so_when_the_state_is_still_another_returns` | a notice, not `banner()` |
| `…test_every_dialog_is_in_the_one_registry_and_closes_through_one_guard` | the set grows: the sheet and the four new dialogs |
| `…test_no_text_box_is_named_only_by_its_placeholder` | the setup page's inputs keep their labels; `#root-input` is hidden |
| `test_api::test_the_vocabulary_carries_every_word_the_review_card_shows`, `…gets_its_vocabulary_from_the_api`, `…carries_every_word_201_shows`, `…the_schedule_dialog_uses_only_the_apis_words`, `…the_schedule_is_repaired_from_the_toolbar…`, `…the_renderer_types_no_unlearn_word`, `…the_settings_carry_the_firm_phone…`, `…the_renderer_types_none_of_the_moved_cards_words`, `…the_moved_card_offers_mark_missing…`, `…the_apps_request_table_folds_not_asked_rows…`, `…the_first_screen_says_every_machine_warning…`, `…the_wizard_sends_every_catalog_row_and_the_tick_is_asked`, `…rule_two_names_the_inbox…` (page half) | the words of the approved table; the deck's keys go; the Repair item is in Tools; machine warnings are notices; the request rows are grouped by `group` |
| `test_pilot_ui::test_the_structure_pass_never_unhides_a_hidden_element` | `.mode-toggle` leaves `NEVER_HIDDEN` |
| `test_pilot_ui::test_cards_never_shrink_inside_the_scrolling_column` | the rule is `#page > *` (P55 still holds) |
| `test_pilot_ui`'s grid test | the steps are 4/8/16/24/32/48 |
| `test_tour::test_every_tour_anchor_is_an_element_the_page_has` | the anchors of section 12 |
| `test_pilot`'s tour-line cap | five words |
| `test_repo_map::test_every_function_a_curated_note_names_exists_in_the_tree` | the curated notes for `app.js` lose the removed functions' names, in the same commit |

### 14.3 Tests that go

`test_single_source::test_the_review_mode_key_is_a_key_and_not_a_word`:
the Cards/List deck and its stored key are removed.

### 14.4 The harness (`pilot/harness/`, first build)

`stub.js` defines `window.tracker` with made-up data only (the Smith Family,
Rivera Design LLC, Ana Lopez and 500 generated households with made-up
names) and the vocabulary of section 11 in its key shape, so the renderer
can be drawn before the engine part lands. `shoot.mjs` loads
`app/renderer/index.html` in the cloud's Playwright Chromium with the stub
injected (`addInitScript`) and saves every scenario in light and dark at
1100 × 700 and 1400 × 900: Overview, Overview empty, Needs Review,
Reminders, Clients (work waiting, all), household, household with no
returns, year, return, return with nothing received, the check sheet, the
reminder sheet, setup, loading, sort running, sort failed, locked, a
tooltip by mouse and by keyboard, contrast theme (`forced-colors`
emulated). It is never loaded by the app, and pytest does not run it.

**Joined (S6b).** The harness speaks the engine, not a copy of it: the
vocabulary is `tracker.api._vocab()` of the tree, dumped on every run (no
snapshot, no switch), and the stub's `list`, `firm` and `state` replies are
held to the real ones of a scratch clients tree by
`test_the_harness_stub_speaks_the_apis_vocabulary` and
`test_the_harness_stub_replies_have_the_shape_of_the_engines`
(`tests/test_shell.py`). The one code the stub sends that the vocabulary has
no word for (`unwritten_code`, a folder skipped) is deliberate: the page
draws the name alone.

## 15. Questions for Jason (before the build)

All answered (2026-09-29): **Q1 yes** (P79), **Q2 grey it for 0.2** (P80),
**Q3 leave it out** (P81), **Q4 option A**, the detail the record has
(P83), **Q5 wording approved** (P84), **Q6 confirmed** (P82). The build may
start.

| # | Question | Recommendation |
|---|---|---|
| Q1 | May the build add the read-only `firm` command and the three small fields of section 9 (files under `tracker/` beyond wording)? | **Yes.** Without it the Overview, Needs Review, Reminders and Clients pages have no counts. Nothing is written; no filing or status logic changes. |
| Q2 | On a firm page, no household is open, so Sort now has nothing to sort: grey the icon ("Open a client to sort"), or add a firm-wide Sort now (a new engine command that runs every household, as the schedule does)? | **Grey it in 0.2.** A firm-wide sort from the app is its own engine SPEC (locks across 500 households, a run of hours). |
| Q3 | Help › Tester guide: the app has no copy (it is emailed). Leave it out, or ship the guide inside the app? | **Leave it out** for 0.2. |
| Q4 | A row's second column: the brief says "from whom", but the record keeps no sender for a request. Show the detail the record has (period, "1 of 2", the file's own name, the likely request) instead? | **Yes**, the detail. |
| Q5 | Approve the wording: [`wording-shell.tsv`](wording-shell.tsv) (212 rows) and sections 11.3-11.6 (new words). | - |
| Q6 | Where the brief and the later audit disagree, this SPEC follows the audit: no dot beside a status word; no summary line under the return's name; one Stop (the icon), not a second in the side panel. Confirm. | **Confirm.** |

## 16. Build: sessions, order and what can run side by side

Each build is its own fresh session (sonnet), handing off through this SPEC,
[`HANDOFF.md`](HANDOFF.md) and its commits; each is reviewed by a separate
opus session (high effort) with numbered findings against this SPEC, then
rebuilt and reviewed again until a review has no findings (Jason's loop).
Commits end with `[skip ci]`; the tests run locally, never on GitHub.

| Session | Builds | Needs first | Files |
|---|---|---|---|
| **S1 Engine** (P78) | section 9 (after Q1), the vocabulary blocks `menu` and `screen`, short reasons, stage shorts, `SAFEGUARDS`, the wording rewrite (after Q5) and the docs that quote the changed words | Q1, Q5 | `tracker/api.py`, `reasons.py`, `reminder.py`, `__init__.py`, `manifest.py` (words), `README.md`, `docs/runbook.md`, `CLAUDE.md`, `docs/ROADMAP.md` where they quote words; `tests/test_api.py`, `test_single_source.py` (Python side), `test_reasons.py`, `test_reminder.py` |
| **S3 Renderer foundation** | tokens light and dark (10), `shell.css`, `tooltip.js`, the `index.html` skeleton (3.1), `shell.js` (4, 8.1-8.3, 5.3-5.4's page side), the setup page, notices' placement, the pilot layer (12), the harness (14.4) | the SPEC only (draws from the stub) | `app/renderer/*` (not `app.js`'s card code), `pilot/harness/`, `tests/test_shell.py` (renderer part), `test_pilot_ui.py`, `test_tour.py`, `test_pilot.py` |
| **S2 Shell process** | the menu template, `buildMenu`, the `menu` channel, 5.5, first paint (5.6), `preload.js` | S1 (`api.MENU`) | `app/main.js`, `app/preload.js`, `tests/test_shell.py` (menu part), `test_single_source.py` (shell pins) |
| **S4 Pages** | `pages.js` (6), the row and group components, removal of the card renderers from `app.js` (13) | S3 | `app/renderer/pages.js`, `app.js`, `index.html` (removals), tests of 14.2 that follow the cards |
| **S5 Sheet and dialogs** | `sheet.js` (7), the right-click wiring, the roll, safeguards, about and folders-skipped dialogs, the dialogs' help lines cut; the three link kinds and "{Return Name} ({Year})" in `pages.js` and the sheet (3.9); the renderer's literals in Title Case | S4, S8a's keys | `app/renderer/sheet.js`, `pages.js` (links), `app.js` (dialogs), `index.html` (dialogs), their tests |
| **S7 Tooltips** (rulings 2, 5, 7; branch `claude/shell-s7-tooltips`) | Floating UI vendored and placing the tip; focus on all but the search box; 300 ms hover; hidden when scrolled out of view (8.5) | S3 | `app/renderer/tooltip.js`, `vendor/floating-ui/`, `index.html` (two script lines), `tests/test_shell.py`, `pilot/harness/` |
| **S8a Links and words** (rulings 8-12, 10; branch `claude/shell-s8a-links`) | the openable keys of working copies and `open-path`'s reveal (5.7, 9.3); the three link tooltips; the engine's and `main.js`'s words in Title Case, with a test (11.1) | S2 | `tracker/api.py` and the modules whose words it reads, `app/main.js`, `app/preload.js`, their tests, the docs that quote the words |
| **S6 Join** | the renderer on the real API instead of the stub; vocabulary keys that do not meet; the whole set of affected tests; the tour titles and lines in Title Case (12); the Windows check prompt; the decision rows for rulings 1-13 | S1-S5, S7, S8a | as found |

**Side by side (parallel):** **S1 and S3** run at the same time: S1 is Python
and docs, S3 is renderer files drawn from the stub, and they meet only in
the vocabulary's key names, which section 11 fixes. **S2 and S4** run at the
same time after them: S2 is `main.js` and `preload.js`, S4 is `pages.js` and
`app.js`. S5 follows S4 (both edit `app.js` and `index.html`), and S6
follows all. S1 and S3 each start from this branch; S2 builds on S1's
branch and S4 on S3's; S5 on S4's; S6 merges S2's branch into S5's with a
merge commit. Side-by-side sessions write separate handoff files
(`pilot/handoffs/shell-<name>.md`) and only S6 edits `HANDOFF.md` and
`DECISIONS.md`, so no two sessions edit one file. The prompts for every
session, review and rebuild are in [`HANDOFF.md`](HANDOFF.md).

### The Windows check (after S6)

`pilot\wintest\run_checks.ps1 -Tests` with the files the stack touched:
`test_shell.py`, `test_api.py`, `test_single_source.py`, `test_pilot_ui.py`,
`test_tour.py`, `test_pilot.py`, `test_reasons.py`, `test_reminder.py`,
`test_layers.py`, `test_repo_map.py`, `test_tripwire.py`, `test_errors.py`
(the words of errors change). Hands-on, each because the change can reach
it: the menu bar by mouse and by Alt; every accelerator; right-click on a
row, the path and a heading, and Shift+F10; light and dark (Settings,
Personalisation, Colours) with the app open, and a contrast theme; the
first paint in dark (no white flash); Sort now and Stop on a real
household; the firm pages on the office's clients folder (the 3-second
budget of 9.2); a tooltip by mouse (after 300 ms) and by Tab (at once; none
on the search box), and a tip whose control scrolls away; a file name link
(File Explorer opens with that copy selected) and a household and a return
link (the app navigates; the return reads "{Return Name} ({Year})"); Help ›
Open Error Log before the first data folder exists (the fallback in
`%LOCALAPPDATA%\Tax Document Tracker Pilot`) and after; Remote Desktop at
1100 × 700.
Not repeated: the installer, the schedule's registration, filing itself -
this work does not reach them.

## 17. Checks every build passes before it pushes

- Dead code in the changed files deleted first (CLAUDE.md, decision 207).
- The affected tests only, each file its own process, under the floor
  interpreter and the office's; then `python -m ruff check .`;
  `python tools/repo_map.py update` and `check`, with the curated notes of
  every changed module rewritten in the same commit.
- The harness's screenshots of the scenarios the session changed, light
  and dark, both sizes, looked at before the handoff.
- `.claude/skills/impeccable/scripts/impeccable detect --json` over the
  changed UI files, once, its findings fixed or answered in the handoff.
- No network call, no new package (the vendored Floating UI files of
  ruling 5 are the one exception, pinned by hash), the CSP unchanged,
  nothing that reads a client document.

## 18. Out of scope

- Anything that files, routes, reads or validates a document; the
  schedule; the installer; the reminder letter's words.
- A firm-wide Sort now (P80), a shipped Tester Guide (P81).
- Porting the shell to the main tracker (a later job in that repository).
- Charts, a dashboard, tabs, a second button row, glass or blur (the
  brief's anti-goals).

## 19. Open for Jason (from the SPEC sync, 2026-09-29)

None blocks a build; each is recorded rather than guessed.

| # | Question | Why it is open |
|---|---|---|
| O1 | Approve "Could Not Be Read" (`api.FIRM_UNREADABLE`), the Overview's line for a return whose record cannot be read (9.2, 11.4). | S1 added it; it is not in the approved wording table. |
| O2 | A long name that is cut carries its full name as its tooltip (3.6, 6); a name that is a link carries "Show in File Explorer", "Navigate to Client" or "Navigate to Return" (3.9). One element has one tooltip: which wins when a link's name is cut? | Rulings 8-12 and the long-name rule meet on one element; neither says. |
| O3 | How a keyboard user acts on a name link inside a row: the row is one `option` of a listbox and Enter runs the row's step (3.6). | Not ruled; S5 to propose (for example, the link's action as a right-click item, or Enter on the name). |
| O4 | Does a right-click menu gain a "Show in File Explorer" item for a file row? | S8a's work in progress names the word for "the right-click item that does the same"; no ruling adds an item to 5.2. **Built without a ruling** (the final review found it in the menu). |
| O5 | `triage.places.footer` ("In the Page {page} Footer") is a fragment joined into the side sheet's reason line, not a phrase of its own: Title Case it as the rule reads, or leave it lower case inside the line? | Ruling 10 speaks of phrases; this one is spliced into another. The table shows the Title Case form, flagged. |
| O6 | Ruling 6 wrote "Tracker failed"; this SPEC draws it "Tracker Failed" (ruling 10). Confirm. | The rulings file says ruling 10 wins over the lower-case spellings of rows 8 and 13; row 6 is not named, but its words are drawn. |

Pending other jobs, not Jason: S8a's key names (5.7, 9.3, 11.4) and its
Title Case test's name are final with S8a's review; `year` and `handle` on
`firm`'s rows (9.2) with S1 rebuild 3's review.

Also open for Jason (the fix pass, 2026-09-30): "Bad Year" (ruling 18a) is a
working word he may change; firm speed on Windows over a streamed Drive is
unmeasured; the status word "Came in Email or Zip" is cut in the 160px status column in the cloud's font (it fits on Windows, 131px; a file row keeps its ellipsis; answered by P116: the tag
"Email or Zip", with those words as its tooltip, `pilot/SPEC-email-zip-tag.md`). The ruling
25 reason words were approved as ruling 29.
