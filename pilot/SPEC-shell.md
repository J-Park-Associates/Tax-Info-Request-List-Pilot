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
| `app/renderer/tooltip.js` **new** | The custom tooltip (PLAN-ui section 5, words capped by P63). |
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
scripts `app.js`, `tooltip.js`, `pages.js`, `sheet.js`, `shell.js`,
`pilot-content.js`, `pilot.js`, `tour.js`. The new scripts are classic
scripts, as `app.js` is: they share its globals and add their own, each
named for what it does. No module loader, no bundler, no package.

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
| E21 | (new) side panel sections | Kept | `#side-sections` | Overview, Needs review, Reminders, Clients |
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
| E65 | Put back / Keep here / Send to review / Mark missing (moved) | Put back and Keep here kept; Send to review removed | sheet; right-click | "Put back", "Keep here" |
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
| E80 | `#filed-card` rows, Unfile, Mark missing | Received rows; actions by right-click | return page | "Unfile", "Mark missing" |
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
  above zero (Needs review: files waiting; Reminders: drafts ready). Hover
  `--bg-nav-hover`, pressed `--bg-pressed`. **Selected:** `--bg-selected`
  fill, weight 600, and a 3 × 16px `--accent` pill at the row's left inside
  edge, centred (Fluent's selection indicator, not a border).
  `aria-current="page"` on the selected one.
- Household, year and return pages select **Clients** (they live under it).
- Foot: `#last-sort` in caption `--text-caption`, 16px from the panel's
  sides, 16px from the badge. States in section 8.3.

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

### 3.6 Rows and groups (one row style, every page; P71, P76)

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
| Ctrl+1 … Ctrl+4 | Overview, Needs review, Reminders, Clients |
| Ctrl+F | focus `#find` |
| F5 | Refresh |
| F9 | Sort now (when enabled) |
| Ctrl+N | New household… |
| Ctrl+E | Edit request list… (a return open) |
| Alt | the menu bar (Windows) |
| F6 | cycle focus: side panel › path row › page › side panel |
| Esc | close the sheet, the search list, a tooltip, in that order |
| Enter, Shift+F10 | a row's step, a row's right-click menu |

The accelerators are the menu's (section 5), so they work from anywhere and
show in the menus. F6, Esc and the listbox keys are the page's: the one
`keydown` listener stays in `app.js` (a test holds the renderer to one) and
hands them to `shellKey(e)` in `shell.js` before its own Escape handling.

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
| **File** | New household… (`new_household`) | Ctrl+N | a clients folder is set |
| | Change clients folder… (`change_root`) | | always |
| | Open clients folder (`open_root`) | | a clients folder is set |
| | — | | |
| | Exit (role `quit`, label `exit`) | Alt+F4 (Windows' own) | always |
| **Edit** | role `editMenu` (Undo, Redo, Cut, Copy, Paste, Select all), label `edit` | Windows' own | always |
| **Client** | Edit household… (`edit_household`) | | a household, year or return is open and not locked |
| | Add a return… (`add_return`) | | same |
| | Roll forward… (`roll_forward`) | | same, and the household has a year to roll |
| | Mark as shared (`mark_shared`) | | same, and it is not shared |
| | — | | |
| | Edit request list… (`edit_list`) | Ctrl+E | a return is open and not locked |
| | Draft reminder… (`draft_reminder`) | | a return is open |
| | — | | |
| | Open client folder (`open_client_folder`) | | a household, year or return is open |
| | Open inbox (`open_inbox`) | | same |
| | Open working folder (`open_working`) | | a return is open |
| **View** | Overview (`overview`) | Ctrl+1 | a clients folder is set |
| | Needs review (`needs_review`) | Ctrl+2 | same |
| | Reminders (`reminders`) | Ctrl+3 | same |
| | Clients (`clients`) | Ctrl+4 | same |
| | — | | |
| | Find (`find`) | Ctrl+F | same |
| | Refresh (`refresh`) | F5 | always |
| **Tools** | Sort now (`sort_now`) | F9 | a household, year or return is open, no sort runs, not locked |
| | Stop sorting (`stop_sorting`) | | a sort runs |
| | — | | |
| | Schedule… (`schedule`) | | a clients folder is set |
| | Repair schedule (`repair_schedule`) | | same |
| | Firm report (`firm_report`) | | the API reported `paths.status` |
| | — | | |
| | Clear stuck lock (`clear_lock`) | | the open return's lock is stale |
| **Help** | Take the tour (`tour`) | | always |
| | Safeguards (`safeguards`) | | always |
| | Terms (`terms`) | | always |
| | Open error log (`error_log`) | | always (section 5.5) |
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
| `household` | a household row; the household segment; the household H1 | the Client menu's household items: Edit household…, Add a return…, Roll forward…, Mark as shared, —, Open client folder, Open inbox |
| `return` | a return row; the return segment; the return H1 | Edit request list…, Draft reminder…, —, Open working folder, Open client folder, Open inbox |
| `file` | a parked or set-aside file row | Check… (`check`), Not requested (`not_requested`), Another return… (`another_return`) |
| `moved` | a moved-by-hand row | Check…, Put back (`put_back`), Keep here (`keep_here`) |
| `request` | a Needs you or Waiting request row | Edit request… (`edit_request`) |
| `received` | a Received row | Unfile (`unfile`), Mark missing (`mark_missing`) |

The page sends the enable list with each popup, by the rules of 5.1 (a
locked return greys the writing items).

### 5.3 The page tells the menu what applies

On every route change, state change and lock change, `shell.js` sends
`{enable: [ids]}`: the ids whose rule in 5.1 holds now. `main.js` sets
`enabled` on the menu items whose ids it knows and ignores anything else.
It never adds, removes or renames an item for the page.

### 5.4 The one channel: `menu` (preload)

`preload.js` gains exactly this, beside what it has:

```js
menu: {
  // A menu item was chosen: {id, token}. token is the page's own, echoed.
  onCommand: (listener) => ipcRenderer.on("menu", (_e, m) => listener(m)),
  // What applies now: {enable: [ids]}; or pop a right-click menu:
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

- **Open error log:** `main.js` opens the error log the API named
  (`vocab.shell.error_log`) with `shell.openPath` when it is a regular file
  and no symbolic link (the same test `openPath` makes); otherwise it sends
  `{id: "error_log", missing: true}` and the page shows the toast
  "No error log yet".
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

## 6. Pages, one per level, and their states

Every page is drawn by `pages.js` into `#page` from data it is handed; it
calls nothing itself. Words are `vocab.screen.*` (section 11.3) unless named.
**Firm pages** (Overview, Needs review, Reminders, Clients) have no H1: the
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

### 6.1 Overview (the landing page)

```
 [bar] Overview                                        [find    ] [sort]
 ───────────────────────────────────────────────────────────────────────
   12              31                 148
   Need a person   Waiting on clients Complete

   Work waiting  43
   1040 - John & Jane Smith     Smith Family      3 need you    Mar 3   Open ›
   1120-S - Rivera Design LLC   Rivera Design     1 need you    Mar 5
   1040 - Ana Lopez             Lopez Household   2 waiting   Due Apr 15
```

- **Figures:** three numbers in the figure role, `--text`, 48px apart, each
  with its caption under it. They count **returns**, and each active return
  is in exactly one: **Need a person** (anything in its Needs you group),
  else **Waiting on clients** (anything in Waiting on client), else
  **Complete**. They add up to the active returns this year. Not links.
- **Work waiting** (H2, count): one row per return in the first two
  buckets. Name: the return. Detail: its household. Status: "{n} need you"
  (`--st-attention`) or "{n} waiting" (`--st-waiting`). Date: the oldest file
  waiting ("Mar 3") for the first bucket, the due date ("Due Apr 15") for
  the second, or empty. Step: **Open**. Order: need-you returns by their
  oldest waiting file, oldest first; then waiting returns by due date,
  soonest first, then by name.
- **Empty:** in place of the H2 and rows, "Nothing is waiting" (body) and
  under it "Next sort {time}" (caption) when the schedule has a next run.
- **Right-click** on a row: the `return` menu.

### 6.2 Needs review (firm)

- One group per return with files waiting: H2 is the return's name, its
  caption the household and the count. Groups ordered by their oldest file.
- Rows: name = the file's own name; detail = the request it most likely is
  (the first suggestion's name), else empty; status = the reason's short
  label (11.4), `--st-attention`; date = received; step **Check** → the
  sheet (7.1), which loads that return's `state`. Right-click: `file`.
- The sheet's next arrow walks every file on this page, group by group.
- **Empty:** "Nothing needs review" and "Next sort {time}".
- The side count is the number of files.

### 6.3 Reminders (firm)

- One list, no H2 (the page is one thing). Rows: one per return whose draft
  for this week is ready and not yet approved. Name: the return. Detail:
  household. Status: the stage's short name (`--st-waiting`), or
  "Held" (`--st-attention`) when files or rows hold it. Date: drafted.
  Step **Draft reminder** → the sheet (7.2). Right-click: `return`.
- **Empty:** "No drafts ready".
- The side count is the number of rows.

### 6.4 Clients

- A two-option switch at the keyline, 24px under the path row: **Work
  waiting** (the default each time the page opens) and **All**. The
  selected option has P52's selected look.
- Rows: one per household, by name. Name: the household. Detail: "{n}
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
  return. Name: the return. Detail: "Inactive" or "Rolled forward" when the
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

   Needs you  3
   scan0012.pdf        W-2                Could not tell       Mar 3   Check ›
   IMG_2231.jpg        1099-INT           Fits two requests    Mar 4
   1098 - Chase                           Could not use        Mar 2

   Waiting on client  2                                    Draft reminder ›
   1099-B - Schwab     Dec 2025           Outstanding
   K-1 - Park LP       1 of 2             Partly in

   Received  9
   W-2 - Acme Corp     acme-w2.pdf        Received             Mar 1

 ▸ Set aside  4
```

- H1: the return's name. Caption: "Due {date}" when the record has one.
- **Needs you** (`group == "needs_you"`), in this order: files parked for a
  person, oldest first; then files moved by hand; then request rows whose
  side is Us or Decide, in list order. Files the router set into buckets
  ("Emails and zips", "Not documents") sit under those two words as caption
  sub-headings, weight 600, inside the group.
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
  name, or "{n} files". Status "Received" or "Accepted" (`--st-done`). Date:
  received. No step; right-click: `received` (Unfile, Mark missing).
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
one action. The list, with words from section 11: sort failed (Retry),
counts not available (Retry), in use on {host}, stuck lock from {host},
setup needs attention, install folder name too long, drive not signed in
and the other machine warnings, {n} folders skipped (Show), names
shortened to fit, two years open, folder renamed (Accept), and the
shell's own failures. The dismiss icon ends each.

### 8.5 Tooltip (`tooltip.js`)

PLAN-ui section 5, with P63 and P65: any element with `data-tip` gets it,
after 500ms of hover or at once on keyboard focus; Esc and pointer-out hide
it; one `#tip` element, `role="tooltip"`, tied by `aria-describedby`; kept
inside the window; at most 320px wide; caption type on `--bg-raised` with
`--shadow-overlay` and a 1px `--border`. Its text is always vocabulary or a
user's name, never typed in the renderer, never over five words (names
excepted). Placed with `element.style.setProperty` (allowed by the CSP, as
the tour does). Every `title=` in the renderer goes; `setTip(el, text)`
replaces them.

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
     "counts": {"needs_you": n, "waiting": n, "received": n, "set_aside": n},
     "files": n,                  # of needs_you, the files (parked + moved)
     "oldest": "YYYY-MM-DD"|null, # the oldest file waiting for a person
     "due": "YYYY-MM-DD"|null,    # the record's due date
     "draft": {"ready": bool, "stage": n, "held": n, "drafted": "YYYY-MM-DD"|null},
     "problem": str               # a short sentence, or ""
  }],
  "files": [{"return": str, "name": str, "code": str, "received": "YYYY-MM-DD",
             "suggestion": str}],
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
- A return whose record cannot be read is one row with `problem` set and
  zero counts; it never fails the reply (decision 189's rule). A root that
  cannot be walked is `PRACTICE_NOT_WALKED`, as `list` says it.
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

### 11.1 The rules

Five words or fewer for every label, heading, notice, error, tooltip,
dialog line and toast; placeholders count as one word; `&` access keys are
not counted. No path of any kind. Sentence case; no full stop on labels,
headings, buttons or tooltips. Say return, sort, request list, client
folder, inbox; never manifest, engagement, pass, record, scan or a request
code. Two exceptions (P63): the pilot terms and the reminder letter. User
data (names, file names) is content and is not counted.

### 11.2 Today's strings over five words

**Approved by Jason (P84).** All 212, today and proposed, one row each, in [`wording-shell.tsv`](wording-shell.tsv)
(columns: source, key, today, verdict, proposed, words, where, note).
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
- **No error log yet:** when the tracker fails before it has a data folder
  (first start only), there is nowhere to keep its details, and they are no
  longer printed on screen; the notice says "Tracker failed; no error log".

### 11.3 New words: the menu (`vocab.menu`, `api.MENU`)

| Key | Words | | Key | Words |
|---|---|---|---|---|
| `file` | &File | | `view` | &View |
| `new_household` | New household… | | `overview` | Overview |
| `change_root` | Change clients folder… | | `needs_review` | Needs review |
| `open_root` | Open clients folder | | `reminders` | Reminders |
| `exit` | Exit | | `clients` | Clients |
| `edit` | &Edit | | `find` | Find |
| `client` | &Client | | `refresh` | Refresh |
| `edit_household` | Edit household… | | `tools` | &Tools |
| `add_return` | Add a return… | | `sort_now` | Sort now |
| `roll_forward` | Roll forward… | | `stop_sorting` | Stop sorting |
| `mark_shared` | Mark as shared | | `schedule` | Schedule… |
| `edit_list` | Edit request list… | | `repair_schedule` | Repair schedule |
| `draft_reminder` | Draft reminder… | | `firm_report` | Firm report |
| `open_client_folder` | Open client folder | | `clear_lock` | Clear stuck lock |
| `open_inbox` | Open inbox | | `help` | &Help |
| `open_working` | Open working folder | | `tour` | Take the tour |
| `check` | Check… | | `safeguards` | Safeguards |
| `not_requested` | Not requested | | `terms` | Terms |
| `another_return` | Another return… | | `error_log` | Open error log |
| `put_back` | Put back | | `about` | About |
| `keep_here` | Keep here | | `unfile` | Unfile |
| `edit_request` | Edit request… | | `mark_missing` | Mark missing |

### 11.4 New words: the screen (`vocab.screen`)

Where an existing key does the same job, the existing key is reworded
(11.2) and reused, not duplicated; these are the words with no key today.

| Key | Words | Where |
|---|---|---|
| `sections.overview` / `needs_review` / `reminders` / `clients` | Overview / Needs review / Reminders / Clients | side panel, path |
| `side_label` | Sections | the side panel's name for screen readers |
| `path_label` | Path | the path's name for screen readers |
| `find` | Find a client | search name and tooltip |
| `find_none` | No match | search list |
| `sort.now` / `sort.stop` / `sort.firm` / `sort.locked` / `sort.stopping` | Sort now / Stop sorting / Open a client to sort / In use elsewhere / Stopping | sort icon tooltip and name |
| `last_sort.today` / `other_day` / `failed` / `never` / `running` | Sorted {time} / Sorted {date} / Sort failed / Not sorted yet / Sorting {n} of {total} | side panel foot |
| `last_sort.done` | Sorted | done icon tooltip |
| `figures.need` / `waiting` / `complete` | Need a person / Waiting on clients / Complete | Overview |
| `work` | Work waiting | Overview H2 |
| `empty.overview` / `next_sort` | Nothing is waiting / Next sort {time} | Overview empty |
| `empty.needs_review` | Nothing needs review | Needs review empty |
| `empty.reminders` | No drafts ready | Reminders empty |
| `empty.clients` | No clients yet | Clients empty |
| `empty.work` | No work waiting | Clients, Work waiting empty |
| `empty.returns` | No returns yet | household empty |
| `empty.received` | Nothing received yet | Received group |
| `filters.work` / `filters.all` | Work waiting / All | Clients switch |
| `counts.need` / `waiting` / `complete` | {n} need you / {n} waiting / Complete | row status |
| `counts.returns` / `one_return` / `files` | {n} returns / 1 return / {n} files | row detail |
| `due` | Due {date} | row date, return caption |
| `partly` | {n} of {total} | row detail |
| `groups.needs_you` / `waiting` / `received` / `set_aside` | Needs you / Waiting on client / Received / Set aside | return page |
| `steps.check` / `open` / `draft` / `edit` | Check / Open / Draft reminder / Edit | row step |
| `moved` | Moved by hand | row status |
| `held` | Held | Reminders row status |
| `inactive` / `rolled` | Inactive / Rolled forward | household row detail |
| `contact` | Contact {name} | household caption |
| `shared` / `not_shared` | Shared / Not shared | household caption, done icon |
| `icons.dismiss` / `open` / `next` / `more` | Dismiss / Open / Next / More | icon tooltips |
| `sheet.reminder` | Reminder | sheet title |
| `sheet.drafted` | Drafted {date}, stage {n} | sheet caption |
| `loading` | Loading | screen readers only |
| `setup.title` / `choose` / `start` / `missing` | Choose your clients folder / Choose folder… / Start / Folder not found | setup page |
| `notices.firm_failed` | Counts not available | notice |
| `notices.skipped` / `show` | {n} folders skipped / Show | notice |
| `notices.no_log` | No error log yet | toast |
| `notices.drive` | Drive not signed in | notice (the machine warning's short line) |
| `misfits.title` | Folders skipped | dialog |
| `safeguards.title` | Safeguards | dialog |
| `about.edition` | Pilot {version} | About dialog, badge |
| `retry` | Retry | notice action |
| `copied` / `saved` | Copied / Saved | toast |
| `schedule.move_warning` | Only if {host} is retired | Repair schedule confirm |

### 11.5 Short reasons (`reasons.py`, one per code, `vocab.reasons`)

A `short` beside each code's sentence; the row shows it, the sentence stays
where it is used today (the index, the letter, the log).

| Code | Short | | Code | Short |
|---|---|---|---|---|
| `unmatched` | Could not tell | | `name-absent` | No client name found |
| `ambiguous` | Fits two requests | | `name-other` | Names another return |
| `contested` | Claimed by two requests | | `named-across` | Names another household |
| `between-returns` | Fits two returns | | `unnamed-across` | No name on it |
| `ocr-only` | Read from scan only | | `name-points-at` | Name hints a request |
| `no-request-accepts` | File type not asked | | `shows-form-number` | Shows a form number |
| `several-forms-unsorted` | Several forms, unsorted | | `issuer-not-named` | Issuer not named |
| `no-room` | No room for name | | `no-people` | Return has no people |
| `could-not-file` | Could not file | | `answer-not-counted` | Statement not counted |
| `put-back-refused` | Could not put back | | `opened-not-across` | Came in email or zip |
| `unfiled` | Unfiled by a person | | `container-damaged` | Email or zip damaged |
| `not-requested` | Not requested | | `container-empty` | Nothing attached |
| `assigned` | Filed by a person | | `container-limit` | Email or zip too big |
| `matched` | Filed | | `container-locked` | Email or zip locked |
| `several-forms` | Filed as several forms | | `password` | Password protected |
| `filed-whole` | Filed whole | | `google-stub` | Google shortcut only |
| `file-moved` | Moved by hand | | `extension` | File type not allowed |
| `copy-missing` | Copy missing | | `not-a-document` | Not a document |
| `copy-changed` | Copy was changed | | `too-small` | File almost empty |
| `copy-and-original-gone` | Copy and original gone | | `too-large` | Too large to read |
| `interrupted-move` | Step interrupted | | `no-pages` | PDF has no pages |
| `interrupted-move-lost` | Move interrupted | | `unreadable-pdf` | PDF will not open |
| `pending-sync` | Syncing | | `unreadable-image` | Photo will not open |
| `vanished` | File disappeared | | `heic-reader` | HEIC photo, no reader |
| `no-keyword` | Expected words missing | | `uncheckable-type` | Cannot check this type |
| `wrong-document` | Looks like wrong document | | `extraction-failed` | Text could not be read |
| `wrong-period` | Wrong period | | `no-text-layer` | Scan not readable |
| `reader-unavailable` | Reader did not start | | `no-text-after-ocr` | No readable text |
| `reading-crashed` | Reader stopped | | `ocr-failed` | Scan reading failed |
| `reading-stopped` | Reading timed out | | `unreadable` | Nothing readable |

A test requires one short label for every code in `BY_CODE` and
`PLAIN_CODES`, each five words or fewer.

### 11.6 Stages and safeguards

- Reminder stages gain a `short` each: "Heads up", "Checking in",
  "Deadline near", "Final notice". The letter's subject keeps its full name.
- `tracker/__init__.py` gains `SAFEGUARDS`, four short lines beside
  `STANDING_RULES` (which keeps its full wording): "No AI reads documents",
  "Originals never changed", "Nothing is guessed", "Nothing is ever sent"
  (P64). `vocab.rules` carries both; Help › Safeguards shows the short ones.

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
| One clients folder | `setup-card` | `page` (the setup page) |
| Household and request list | `btn-new-household` | `side-sections` (Clients) |
| Drop files here | `btn-inbox` | `crumbs` |
| Sort | `btn-scan` | `sort` |
| Originals, untouched | `moved-card` | `page` |
| Organized working copies | `filed-card` | `page` |
| Needs review | `review-card` | `side-sections` |
| Status page | `btn-status`, `eng-select` | `side-sections` (Overview) |
| Drafted reminder | `reminder-card` | `side-sections` (Reminders) |

- **Tour lines:** one line per step, five words or fewer
  ([`wording-shell.tsv`](wording-shell.tsv), `tour.steps[n].does`); the
  strength, limit and fallback lines and the stage chips go. The test that
  capped tour lines at 30 words (`tests/test_pilot.py`) caps them at five.

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
[`shell-test-pins.md`](shell-test-pins.md): 162 tests, of which 114 hold
unchanged, 34 change, 1 goes and 13 were open; this section settles the 13.
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
- `test_one_keydown_listener_owns_the_keyboard`: exactly one
  `addEventListener("keydown"` across all renderer files (it stays in
  `app.js` and hands the shell's keys to `shellKey(e)` in `shell.js`).
- `test_the_harness_is_never_loaded_by_the_app`.

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
| `…test_the_app_opens_one_window`, `_ELECTRON_STUB`, `_SHELL_HARNESS` | the stub gains `Menu.buildFromTemplate`, `setApplicationMenu`, `nativeTheme` |
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
1100 × 700 and 1400 × 900: Overview, Overview empty, Needs review,
Reminders, Clients (work waiting, all), household, household with no
returns, year, return, return with nothing received, the check sheet, the
reminder sheet, setup, loading, sort running, sort failed, locked, a
tooltip by mouse and by keyboard, contrast theme (`forced-colors`
emulated). It is never loaded by the app, and pytest does not run it.

## 15. Questions for Jason (before the build)

All answered (2026-09-29): **Q1 yes** (P79), **Q2 grey it for 0.2** (P80),
**Q3 leave it out** (P81), **Q4 option A**, the detail the record has
(P83), **Q5 wording approved** (P84), **Q6 confirmed** (P82). The build may
start.

| # | Question | Recommendation |
|---|---|---|
| Q1 | May the build add the read-only `firm` command and the three small fields of section 9 (files under `tracker/` beyond wording)? | **Yes.** Without it the Overview, Needs review, Reminders and Clients pages have no counts. Nothing is written; no filing or status logic changes. |
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
| **S5 Sheet and dialogs** | `sheet.js` (7), the right-click wiring, the roll, safeguards, about and folders-skipped dialogs, the dialogs' help lines cut | S4 | `app/renderer/sheet.js`, `app.js` (dialogs), `index.html` (dialogs), their tests |
| **S6 Join** | the renderer on the real API instead of the stub; vocabulary keys that do not meet; the whole set of affected tests; the Windows check prompt | S1-S5 | as found |

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
budget of 9.2); a tooltip by mouse and by Tab; Remote Desktop at 1100 × 700.
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
- No network call, no new package, the CSP unchanged, nothing that reads a
  client document.

## 18. Out of scope

- Anything that files, routes, reads or validates a document; the
  schedule; the installer; the reminder letter's words.
- A firm-wide Sort now (P80), a shipped Tester Guide (P81).
- Porting the shell to the main tracker (a later job in that repository).
- Charts, a dashboard, tabs, a second button row, glass or blur (the
  brief's anti-goals).
