# Pilot edition 0.1 - SPEC

Status: **draft for Jason's approval** (2026-09-28). Wording in sections 7 and 8
is proposed copy; builders use it exactly as approved.

Read first: [`README.md`](README.md) (branch rules), [`DECISIONS.md`](DECISIONS.md)
(P1-P19). Decisions referenced below as P-numbers.

**Where this lives (P17).** This SPEC belongs to the separate repository
`J-Park-Associates/Tax-Info-Request-List-Pilot`. Its `main` is the pilot. The
original repository `J-Park-Associates/Tax-Info-Request-List` is added as the
remote `upstream`; "`upstream/main`" below means the original product.

## 1. What this is

A Windows installer for **Tax Document Tracker Pilot**, given to a first batch
of other CPA firms to run on their own clients' files. It is the current product
from `upstream/main`, unchanged in how it sorts, under its own names on the PC
(section 3a), plus three pilot additions:

1. a **"Pilot edition 0.1" badge** in the header;
2. a **terms screen**, shown once, that the tester must accept before using it;
3. a **guided tour** over the real screen that shows each part of the flow and
   says, for each, what it does, why it is safe, and what its current limit is.
   The tour is the marketing piece (P6).

And, outside the app: an **installer** (`setup.iss` + a build script) and a
**Tester Guide**.

### Non-goals (do not build)

- No change under `tracker/` except the one data-folder line in section 3a
  (P7, P18). No change to `app/main.js`, `app/preload.js`,
  `app/renderer/app.js` or `app/renderer/style.css` (P10); `app/package.json`
  changes only in the two name lines of section 3a.
- No sample sandbox, feedback button, usage collection or expiry (P5).
- No network call of any kind, no new IPC channel (P10).
- The tour **only points**. It never clicks a button, never runs a pass, never
  calls `window.tracker`, never opens a file or folder.
- The schedule setting is **not** built here; it is built in the original
  repository
  (P14, section 12).

## 2. Constraints every pilot file obeys

These come from tests that already run over the app; breaking one fails the gate.

| Constraint | Enforced by |
|---|---|
| CSP `script-src 'self'; style-src 'self'`: scripts and styles only as files; no inline `<script>` body, no `on...=` attributes, no `style=` attributes in HTML | `index.html` CSP; `tests/test_single_source.py` |
| No `fetch(`, `XMLHttpRequest`, `WebSocket`, `EventSource`, `sendBeacon`, `window.open(`, `openExternal`, `import(`, `loadURL`, non-string `require(` - **not even in comments** | `tests/test_layers.py::test_the_app_has_no_network_call` (scans every `app/**/*.js`) |
| No new IPC channel; `main.js` and `preload.js` channel lists stay as they are | `tests/test_single_source.py` |
| The product name literal (`productName`, "Tax Document Tracker Pilot" after section 3a) never typed in renderer files; read `vocab.product` at run time if needed | `tests/test_single_source.py` (and P11 for new files) |
| Existing lines of `index.html` are not moved, reflowed or reformatted; only the four lines in section 3 are added | many exact-text assertions in `tests/test_api.py`, `tests/test_single_source.py` |
| No `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval(`, `new Function`, `startsWith(` in pilot JS | pilot tests (section 11), matching the rules `app.js` is held to |
| DOM built only with `document.createElement`, `textContent`, `classList`, `setAttribute` for `aria-*`/`role`/`type`/`disabled`, and `element.style.setProperty` for spotlight/card position only | pilot tests |
| No use of the product's removed former names in any tracked file (the pattern is in the removed-name test) | `tests/test_single_source.py` (removed-name scan) |

Scripts are classic (not modules), so `vocab` and `$` from `app.js` are visible
to later scripts. Pilot files may **read** `vocab.product` but must not call any
`app.js` function or change any `app.js` variable.

## 3. `app/renderer/index.html` - the only edit to an existing file

Add exactly these lines, nothing else:

- after line 11 (`<link rel="stylesheet" href="style.css" />`):
  `  <link rel="stylesheet" href="pilot-style.css" />`
- after line 628 (`<script src="app.js"></script>`), in this order:
  ```
    <script src="pilot-content.js"></script>
    <script src="pilot.js"></script>
    <script src="tour.js"></script>
  ```

## 3a. The pilot's own names on the PC (P18, P19)

So the pilot can never touch the real product's program, data or schedule -
even on the same Windows account - every name the PC sees is different.
These are the only edits to existing files besides section 3:

| File | Line | From | To |
|---|---|---|---|
| `app/package.json` | `name` | `tax-document-tracker` | `tax-document-tracker-pilot` |
| `app/package.json` | `productName` | `Tax Document Tracker` | `Tax Document Tracker Pilot` |
| `pyproject.toml` | `name` | `tax-document-tracker` | `tax-document-tracker-pilot` |
| `tracker/settings.py` | `DATA_HOME_NAME` | `"tax-document-tracker"` | `"tax-document-tracker-pilot"` |
| `README.md` | first line | `# Tax Document Tracker (...)` | `# Tax Document Tracker Pilot (...)` |
| `docs/ROADMAP.md` | first line | `# Tax Document Tracker — ...` | `# Tax Document Tracker Pilot — ...` |

What follows from them, with no further edit:

- program `Tax Document Tracker Pilot.exe`, packaged folder
  `build-portable\dist\Tax Document Tracker Pilot-win32-x64` (`Build App.bat`
  reads the name from `package.json`);
- data folder `%LOCALAPPDATA%\tax-document-tracker-pilot`;
- scheduled task `Tax Document Tracker Pilot` (`scheduling.TASK_NAME` is
  `product_name()`);
- window title from `vocab.product`.

`app/package-lock.json` keeps its old `name` field: `npm ci` does not compare
it, and leaving it avoids a conflict with every upstream lock update.

**The AI-tooling deny list keeps both data folders blocked (P19).**
`.claude/settings.json`'s deny list names the data folder so an agent's file
tools never open client data, and
`tests/test_single_source.py::test_the_agent_deny_list_names_the_data_home_and_every_file_that_names_a_client`
requires it to equal the list built from `DATA_HOME_NAME`. After the rename
that list would name only the pilot's folder, and the real product's folder
would drop out of the deny list on any computer working in this repository -
a weaker wall around client data. So:

- `.claude/settings.json` lists the entries for **both** folder names (the
  pilot's and `tax-document-tracker`);
- the test changes from "equals the constants' list" to "equals the constants'
  list plus the same entries for the original folder name
  `tax-document-tracker`", named in the test as `UPSTREAM_DATA_HOME_NAME`,
  so neither folder can drop out.

Every other test that reads these names reads them from `package.json` or the
constant and follows on its own; the build session runs the whole
name-sensitive set to prove it: `test_single_source`, `test_settings`,
`test_build`, `test_scheduling`, `test_after_install`, `test_api`,
`test_layers`, `test_repo_map`.

## 4. `app/renderer/pilot-content.js` - the one file Jason edits for wording

Exact shape (the markers and the JSON-only body are required; tests read the
body with Python's `json.loads`, the build reads it with `node -p`):

```js
// Pilot edition wording: the only file to edit for the badge, terms and tour text.
// Between the two marker lines is plain JSON (double quotes, no trailing commas,
// no comments), so the tests and the installer build can read it.
const PILOT =
// PILOT-CONTENT-BEGIN
{
  "edition": {"label": "Pilot edition", "version": "0.1"},
  "contact": {"email": "admin@jparkassociates.com"},
  "terms":   { ... section 7 ... },
  "tour":    {"steps": [ ... section 8 ... ]}
}
// PILOT-CONTENT-END
;
if (typeof module !== "undefined") { module.exports = PILOT; }
```

Field rules:

- `edition.version`: `^\d+\.\d+(\.\d+)?$`. The installer's version and file
  name come from it (P13). Bump it for every build sent to testers.
- `terms.version`: integer >= 1. Raising it makes every tester see and accept
  the terms again.
- `terms`: `title` (string), `sections` (array of `{heading, bullets[]}`,
  shown in order), `checkbox` (string), `accept` (button label), `quit`
  (button label).
- `tour.stages`: the six stage names, in order, for the progress strip.
- `tour.steps[]`: each step has
  - `id` - unique, lowercase, `a-z0-9-`;
  - `anchors` - array of element ids (no `#`), tried in order; the first one
    that is visible is highlighted; may be empty (a centred step);
  - `stage` - one of `tour.stages`, or `""` for the first and last steps
    (they show the whole strip as an overview);
  - `title` - non-empty string;
  - `does`, `strength`, `limit` - a non-empty string, or a non-empty list of
    non-empty strings shown as bullets;
  - `fallback` - string shown when no anchor is visible (non-empty whenever
    `anchors` is non-empty; `""` when `anchors` is empty).
- Every sentence or bullet is at most 30 words - the copy stays scannable.
- The literal `{email}` inside any string is replaced with `contact.email` at
  display time; no other substitution exists.

## 5. `app/renderer/pilot.js` - badge, Tour button, terms screen

Runs once at script load (the DOM is already parsed; no `DOMContentLoaded`).

**Badge.** Create `<span id="pilot-badge" class="pilot-badge">` with text
`"{edition.label} {edition.version}"` ("Pilot edition 0.1") and append it as the
last child of the header's `.brand` element. If `.brand` is missing, append it to
`document.body` inside a fixed-position corner (class `pilot-badge-float`) - the
badge must always show.

**Tour button.** Create `<button type="button" id="btn-tour" class="btn">Tour</button>`
and insert it immediately before `#btn-inbox`. If `#btn-inbox` is missing, append
it to `.toolbar`; if that is missing, to the badge. Click -> `PilotTour.start()`.

**Terms screen.** Built as its own overlay, not a member of `app.js`'s `DIALOGS`:

```
div#pilot-terms.pilot-terms-overlay        (role="dialog", aria-modal="true",
  div.pilot-terms-card                       aria-labelledby="pilot-terms-title")
    h2#pilot-terms-title                   terms.title
    div.pilot-terms-body                   per section: div.pilot-terms-section > h3 heading + ul > li per bullet
    label.pilot-terms-check  <input type=checkbox id="pilot-terms-agree"> terms.checkbox
    div.pilot-terms-actions
      button#pilot-terms-quit.btn          terms.quit
      button#pilot-terms-accept.btn.btn-primary (disabled until the box is ticked) terms.accept
```

- Shown when `localStorage["pilot.terms.accepted"]` is not the string of
  `terms.version`. Every `localStorage` access is in `try/catch`; if storage
  throws or is empty, the terms show (fail safe, P9).
- Overlay `z-index: 60` (the app's modals use 40), covers the whole window,
  dims it, and swallows clicks. **Escape does nothing** and clicking outside does
  nothing: a `keydown` listener on `document` in the capture phase stops
  Escape and keeps Tab focus inside the card while the terms are open.
- Focus goes to the checkbox when shown.
- **Accept**: write `pilot.terms.accepted` = `String(terms.version)`, remove the
  overlay, then if `localStorage["pilot.tour.seen"]` is not `"1"`, start the
  tour.
- **Quit**: `window.close()`.

**Exposes** nothing but what `tour.js` needs: `tour.js` defines `PilotTour`;
`pilot.js` only calls `PilotTour.start()` (it is loaded after, so resolve it at
click/accept time, not load time).

## 6. `app/renderer/tour.js` - the guided tour

Defines one global, `const PilotTour = { start, stop }`.

**Parts** (created on `start`, removed on `stop`):

```
div#pilot-tour.pilot-tour-layer                     z-index 55, full window,
  div.pilot-tour-spot                               the highlight box (hidden on centred steps)
  div.pilot-tour-card (role="dialog", aria-live="polite", aria-labelledby="pilot-tour-title")
    ol.pilot-tour-stages          one li.pilot-tour-stage per tour.stages; .is-current on
                                  the step's stage, .is-done on the ones before it
    div.pilot-tour-count          "Step 3 of 11"
    h2#pilot-tour-title           step.title
    section: h3 "What it does"                     p, or ul when step.does is a list
    section.pilot-tour-ok: h3 "Why it's safe"      p or ul (green ✓ marker)
    section.pilot-tour-warn: h3 "Current limit"    p or ul (amber ! marker)
      - when both strength and limit are lists (the wrap-up), the two sections
        sit side by side inside div.pilot-tour-compare
    p.pilot-tour-fallback          step.fallback (only when no anchor is visible)
    div.pilot-tour-actions: button Back | button Next ("Finish" on the last) | button Close
```

The three section headings and the ✓ / ! markers are fixed in `tour.js` /
`pilot-style.css` (they are UI labels,
not copy Jason edits).

**Behaviour.**

- `start()` shows step 1; if a tour is already open it restarts at step 1.
- For each step, the anchor is the first id in `anchors` whose element exists
  and has `getClientRects().length > 0`. With an anchor: the spot is sized to
  the element's `getBoundingClientRect()` plus 6px, the element is scrolled
  into view (`scrollIntoView({block: "center"})`), and the card sits below the
  spot, or above it when there is no room below, kept inside the window.
  Without one: no spot, the card is centred, and the `fallback` line shows.
- The layer dims the page with the spot cut out (a large `box-shadow` on the
  spot), and **blocks clicks on the app** while the tour is open - the tour
  only points (section 1).
- Re-place on `resize` and on `scroll` (capture phase), and re-check the
  current step's anchor every 500 ms while open (a card may appear because a
  scheduled pass finished); clear the timer and listeners on `stop()`.
- Keys while open: Escape = Close, Right arrow = Next, Left arrow = Back.
  (The terms screen, when open, takes precedence: the tour never starts while
  `#pilot-terms` exists.)
- Back is disabled on step 1. Next on the last step reads "Finish".
- Close or Finish -> `stop()`, and writes `localStorage["pilot.tour.seen"] = "1"`
  (in `try/catch`).
- `{email}` in any string is replaced with `PILOT.contact.email`.
- Text only via `textContent`. No `window.tracker`, no click simulation, no
  `.click()`, no `dispatchEvent`.

## 7. Terms text (approved by Jason, 2026-09-28, P20)

Jason's wording, set as short headed sections of bullets so a tester can scan
it in about 30 seconds. Builders copy it exactly.

How it reads on screen:

```
 Before you start: this is a Pilot
 ┃ This is a Pilot
 ┃  • A test edition of Tax Document Tracker, built by J Park & Associates.
 ┃  • It works, but it is still being finished. Expect rough edges.
 ┃  • Please tell us what you find.
 ┃ Keep your own backups
 ┃  • ...
 [ ] I have read this and will keep my own backups.
                                   [ Quit. ]  [ I agree. Continue. ]
```

```json
  "terms": {
    "version": 1,
    "title": "Before you start: this is a Pilot",
    "sections": [
      {
        "heading": "This is a Pilot",
        "bullets": [
          "A test edition of Tax Document Tracker, built by J Park & Associates.",
          "It works, but it is still being finished. Expect rough edges.",
          "Please tell us what you find."
        ]
      },
      {
        "heading": "Keep your own backups",
        "bullets": [
          "Back up a Client’s folder before you point this program at it.",
          "For your first tries, use a copy of a few client folders, not your live ones."
        ]
      },
      {
        "heading": "How it treats your files",
        "bullets": [
          "Files a client drops in are moved, byte for byte and under their own names, into that client's folder for the year.",
          "They are never edited, renamed or compressed.",
          "Sorting and renaming happen only on copies. Every move is recorded."
        ]
      },
      {
        "heading": "No AI reads your documents",
        "bullets": [
          "Fixed, written rules make every sorting decision.",
          "Anything uncertain goes to Needs Review for a person to decide."
        ]
      },
      {
        "heading": "Nothing is sent",
        "bullets": [
          "The program drafts reminder emails. You read and send them yourself.",
          "No email sending, no data sent anywhere: it runs on this computer and needs no internet connection."
        ]
      },
      {
        "heading": "No warranty",
        "bullets": [
          "The Pilot is provided as is, without warranty of any kind.",
          "You remain responsible for your clients' records and for checking what the program files."
        ]
      },
      {
        "heading": "Questions or problems",
        "bullets": [
          "Email {email}.",
          "Please do not send client documents. Describe what happened, or send a screenshot with client names covered."
        ]
      }
    ],
    "checkbox": "I have read this and will keep my own backups.",
    "accept": "I agree. Continue.",
    "quit": "Quit."
  }
```

## 8. Tour copy (draft for approval, bulleted and visual)

Every step is one screen of short lines. Three visuals carry the flow:

1. **Progress strip** across the top of the card - the six stages of a
   season, current one filled amber, earlier ones ticked:

   ```
   ✓ Set up ─ ✓ Drop in ─ ● Sort ─ ○ Check ─ ○ Track ─ ○ Remind
   ```

   Welcome and Wrap-up show the whole strip unhighlighted, as an overview.
2. **Callout markers** - "Why it's safe" with a green ✓, "Current limit" with
   an amber !, drawn by CSS.
3. **Wrap-up comparison** - two columns side by side, Strengths ✓ and Current
   limits !, stacked on a narrow window:

   ```
   ✓ Strengths                         ! Current limits
   • Runs offline on your Windows PC   • Windows only
   • No AI reads client documents      • About 74 document kinds, 6 return types
   • Originals never altered           • Scans slow without the graphics pack
   • Nothing guessed, nothing sent     • Schedule on/off and run time in Settings
                                       • Installer unsigned: Windows warns
                                       • Problems or ideas: {email}
   ```

At a glance:

| # | Stage | Title | What it does | ✓ Why it's safe | ! Current limit |
|---|---|---|---|---|---|
| 1 | overview | Welcome to the Pilot | A client drops documents in one folder. • The program sorts and renames them. • You see what arrived, what's missing, and what needs you. | Runs on this computer with fixed rules. No AI reads documents. Nothing is sent. | 6 return types (1040, 1120, 1120-S, 1065, 1041, 990), about 74 document kinds. |
| 2 | Set up | One clients folder | Choose one clients folder. Each household gets a shared inbox and a private working folder. | Clients see only their own shared folder. Your working files stay private. | Use a folder your firm backs up. One computer runs the automatic schedule. |
| 3 | Set up | Household and request list | Create a household, pick the return type, tick the documents you expect. | Files are matched to your own request list, in your order. | Unknown document types go to Needs Review, never guessed. |
| 4 | Drop in | Drop files here | Inbox opens 'Drop files here'. PDFs, scans, photos, spreadsheets, zips and emails all go in. | The client never names or sorts anything. | Photos and faint scans read slowly and may go to Needs Review. |
| 5 | Sort | Scan | Reads each new file, matches it to a request, moves the original, makes a named copy. | Filed only when exactly one request fits. Doubt goes to a person. | First scans with many images take longer. The schedule also runs it automatically. |
| 6 | Sort | Originals, untouched | Lists the originals moved from the inbox into the client's year folder. | Moved byte for byte, never altered. Every move is recorded and can be undone. | Moved files leave the client's inbox. |
| 7 | Sort | Organized working copies | Accepted documents are copied into Prepared with organized names, e.g. 'A01 - W-2 - TY2025.pdf'. | Every return's folder reads the same way. Copies can be re-made from the originals. | Fixed naming pattern; custom schemes aren't offered yet. |
| 8 | Check | Needs Review | Unknown, ambiguous or unreadable files wait here with likely matches. File with one click, or dismiss. | Nothing is guessed. You see why it stopped. | Expect more items in the first weeks. The rules don't change on their own. |
| 9 | Track | Status page | Opens the status page: every requested document, received or missing, with validation notes. | One page answers 'what are we still waiting for?' | A file on this computer, not a client portal. |
| 10 | Remind | Drafted reminder | Weekly, drafts a reminder listing what's missing. You copy and send it. | Nothing is ever sent. No client is contacted without you. | Send from your own email; no Outlook or Gmail link. |
| 11 | overview | What to expect | Replay this tour any time with the Tour button. | Runs offline on your own Windows PC • No AI reads client documents • Originals never altered • Nothing guessed, nothing sent | Windows only • About 74 document kinds, 6 return types • Scans slow without the optional graphics pack • Schedule on/off and run time in Settings • Installer unsigned: Windows shows a warning • Problems or ideas: {email} |

The content, exactly:

```json
  "tour": {
    "stages": [
      "Set up",
      "Drop in",
      "Sort",
      "Check",
      "Track",
      "Remind"
    ],
    "steps": [
      {
        "id": "welcome",
        "stage": "",
        "anchors": [],
        "title": "Welcome to the Pilot",
        "does": [
          "A client drops documents in one folder.",
          "The program sorts and renames them.",
          "You see what arrived, what's missing, and what needs you."
        ],
        "strength": "Runs on this computer with fixed rules. No AI reads documents. Nothing is sent.",
        "limit": "6 return types (1040, 1120, 1120-S, 1065, 1041, 990), about 74 document kinds.",
        "fallback": ""
      },
      {
        "id": "clients-folder",
        "stage": "Set up",
        "anchors": [
          "setup-card",
          "eng-select"
        ],
        "title": "One clients folder",
        "does": "Choose one clients folder. Each household gets a shared inbox and a private working folder.",
        "strength": "Clients see only their own shared folder. Your working files stay private.",
        "limit": "Use a folder your firm backs up. One computer runs the automatic schedule.",
        "fallback": "Clients folder already chosen. Switch returns from the list at top left."
      },
      {
        "id": "new-household",
        "stage": "Set up",
        "anchors": [
          "btn-new-household"
        ],
        "title": "Household and request list",
        "does": "Create a household, pick the return type, tick the documents you expect.",
        "strength": "Files are matched to your own request list, in your order.",
        "limit": "Unknown document types go to Needs Review, never guessed.",
        "fallback": ""
      },
      {
        "id": "drop-files",
        "stage": "Drop in",
        "anchors": [
          "btn-inbox"
        ],
        "title": "Drop files here",
        "does": "Inbox opens 'Drop files here'. PDFs, scans, photos, spreadsheets, zips and emails all go in.",
        "strength": "The client never names or sorts anything.",
        "limit": "Photos and faint scans read slowly and may go to Needs Review.",
        "fallback": ""
      },
      {
        "id": "scan",
        "stage": "Sort",
        "anchors": [
          "btn-scan"
        ],
        "title": "Scan",
        "does": "Reads each new file, matches it to a request, moves the original, makes a named copy.",
        "strength": "Filed only when exactly one request fits. Doubt goes to a person.",
        "limit": "First scans with many images take longer. The schedule also runs it automatically.",
        "fallback": ""
      },
      {
        "id": "originals",
        "stage": "Sort",
        "anchors": [
          "moved-card"
        ],
        "title": "Originals, untouched",
        "does": "Lists the originals moved from the inbox into the client's year folder.",
        "strength": "Moved byte for byte, never altered. Every move is recorded and can be undone.",
        "limit": "Moved files leave the client's inbox.",
        "fallback": "Appears after a scan moves something."
      },
      {
        "id": "working-copies",
        "stage": "Sort",
        "anchors": [
          "filed-card"
        ],
        "title": "Organized working copies",
        "does": "Accepted documents are copied into Prepared with organized names, e.g. 'A01 - W-2 - TY2025.pdf'.",
        "strength": "Every return's folder reads the same way. Copies can be re-made from the originals.",
        "limit": "Fixed naming pattern; custom schemes aren't offered yet.",
        "fallback": "Appears after the first document is filed."
      },
      {
        "id": "needs-review",
        "stage": "Check",
        "anchors": [
          "review-card"
        ],
        "title": "Needs Review",
        "does": "Unknown, ambiguous or unreadable files wait here with likely matches. File with one click, or dismiss.",
        "strength": "Nothing is guessed. You see why it stopped.",
        "limit": "Expect more items in the first weeks. The rules don't change on their own.",
        "fallback": "Appears when a pass sets a document aside."
      },
      {
        "id": "status",
        "stage": "Track",
        "anchors": [
          "btn-status"
        ],
        "title": "Status page",
        "does": "Opens the status page: every requested document, received or missing, with validation notes.",
        "strength": "One page answers 'what are we still waiting for?'",
        "limit": "A file on this computer, not a client portal.",
        "fallback": ""
      },
      {
        "id": "reminder",
        "stage": "Remind",
        "anchors": [
          "reminder-card"
        ],
        "title": "Drafted reminder",
        "does": "Weekly, drafts a reminder listing what's missing. You copy and send it.",
        "strength": "Nothing is ever sent. No client is contacted without you.",
        "limit": "Send from your own email; no Outlook or Gmail link.",
        "fallback": "Appears when a reminder is drafted."
      },
      {
        "id": "wrap-up",
        "stage": "",
        "anchors": [],
        "title": "What to expect",
        "does": "Replay this tour any time with the Tour button.",
        "strength": [
          "Runs offline on your own Windows PC",
          "No AI reads client documents",
          "Originals never altered",
          "Nothing guessed, nothing sent"
        ],
        "limit": [
          "Windows only",
          "About 74 document kinds, 6 return types",
          "Scans slow without the optional graphics pack",
          "Schedule on/off and run time in Settings",
          "Installer unsigned: Windows shows a warning",
          "Problems or ideas: {email}"
        ],
        "fallback": ""
      }
    ]
  }
```

**Schedule wording** (P14). Until the pilot has merged the `upstream/main`
commit that adds the schedule setting, the wrap-up limit
"Schedule on/off and run time in Settings" reads
"Schedule on/off and run time: coming in the release build", and the pilot is
**not released** (section 12).

## 9. `app/renderer/pilot-style.css`

All pilot styles, classes and the pilot ids only; no rule may target an
existing app id or class other than `.brand` (for the badge's spacing).

- `.pilot-badge`: small pill, amber background (`#f59e0b`), dark text
  (`#1f2937`), 11px bold uppercase, 2px 8px padding, 10px left margin,
  vertically centred in the dark header.
- `.pilot-badge-float`: the same, `position: fixed; top: 8px; right: 8px; z-index: 70`.
- `.pilot-terms-overlay`: `position: fixed; inset: 0; z-index: 60;` dim
  `rgba(15,23,42,.6)`; card centred, max-width 640px, max-height 85vh, body
  scrolls.
- `.pilot-tour-layer`: `position: fixed; inset: 0; z-index: 55;` transparent
  (the spot's shadow does the dimming); on centred steps the layer itself dims.
- `.pilot-tour-spot`: `position: fixed; border-radius: 8px;
  box-shadow: 0 0 0 9999px rgba(15,23,42,.55); outline: 3px solid #f59e0b;
  transition: all .2s;`
- `.pilot-tour-card`: `position: fixed;` white, 400px wide (max 92vw),
  8px radius, shadow; the three `h3` headings 12px uppercase grey; body text
  14px, bullets with 4px spacing.
- `.pilot-tour-stages`: a single row of small pills (11px) joined by thin
  lines; `.pilot-tour-stage.is-current` amber fill, dark text;
  `.is-done` grey text with a ✓ before it (CSS `::before`); others outlined.
- `.pilot-tour-ok h3::before` a green (`#16a34a`) ✓; `.pilot-tour-warn`
  a light amber left border and `h3::before` an amber (`#d97706`) !, so limits
  read as honest caveats, not small print.
- `.pilot-tour-compare`: two equal columns with a 16px gap; the card widens
  to 600px (max 92vw) on that step; below 520px window width the columns
  stack.
- `.pilot-terms-section`: 3px amber left rule, 10px left padding, 12px
  between sections; `h3` 14px bold; bullets 14px.

## 10. The installer

### `pilot/installer/setup.iss` (Inno Setup 6)

Inno Setup is used because the Python standard library cannot build a Windows
installer; it is free and needs no admin rights to run the result (P4).

- `#define AppVersion` comes from the command line (`/DAppVersion=...`); the
  script refuses to compile without it (`#ifndef AppVersion` -> `#error`).
- `#define SourceDir` from the command line: the packaged folder
  `build-portable\dist\Tax Document Tracker Pilot-win32-x64`.
- `[Setup]`:
  - `AppName=Tax Document Tracker Pilot`,
  - `AppVersion={#AppVersion}`, `AppPublisher=J Park & Associates, CPA`,
  - a fixed `AppId` GUID (generate once; never change it - it is how
    upgrades find the old install),
  - `PrivilegesRequired=lowest`,
  - `DefaultDirName={localappdata}\Programs\Tax Document Tracker Pilot`,
  - `DefaultGroupName=Tax Document Tracker Pilot`,
  - `OutputDir=..\..\build-portable\installer`,
  - `OutputBaseFilename=Tax-Document-Tracker-Pilot-Setup-{#AppVersion}`,
  - `UninstallDisplayName=Tax Document Tracker Pilot {#AppVersion}`,
  - `ArchitecturesAllowed=x64compatible`, `ArchitecturesInstallIn64BitMode=x64compatible`,
  - `WizardStyle=modern`, `DisableProgramGroupPage=yes`.
- `[Files]`: `Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion`.
- `[Icons]`: Start-menu `Tax Document Tracker Pilot` -> `{app}\Tax Document Tracker Pilot.exe`;
  optional desktop icon under a `[Tasks]` checkbox, unticked by default.
- `[Run]`: offer "Launch Tax Document Tracker Pilot" at the end
  (`postinstall nowait skipifsilent`).
- `[UninstallRun]`: `Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN ""Tax Document Tracker Pilot"" /F"; Flags: runhidden; RunOnceId: "RemoveSchedule"`.
  The task name is `tracker.scheduling.TASK_NAME`, which is `product_name()`,
  i.e. `productName` = "Tax Document Tracker Pilot" (section 3a); the test in section 11 checks the
  two agree. A missing task is fine (schtasks fails quietly, the uninstall goes on).
- **No `[UninstallDelete]` section.** Uninstall removes only the files it
  installed. It never touches the clients root, the data folder
  `%LOCALAPPDATA%\tax-document-tracker-pilot`, or `settings.json` (written beside the
  exe after install, so not an installed file and left in place) (P12).

### `pilot/Build Pilot Installer.bat`

Follows the E-10 rules of the root `.bat` files even though `tests/test_build.py`
does not scan `pilot/`: the first command is
`set NoDefaultCurrentDirectoryInExePath=1`, and every Windows tool is called by
full path (`%SystemRoot%\System32\...`).

Steps, stopping with a clear message and non-zero exit on any failure:

1. `cd /d "%~dp0.."` (the repository root).
2. **Refuse a dirty tree:** if `git status --porcelain` prints anything, print
   "Commit or discard your changes first: the installer must be built from
   exactly what is committed." and exit 1 (P13).
3. Read the version:
   `node -p "require('./app/renderer/pilot-content.js').edition.version"` into
   `VER`; exit if empty.
4. `set TRACKER_BUILD_NONINTERACTIVE=1` and `call "Build App.bat"`; exit if it
   failed or `build-portable\dist\Tax Document Tracker Pilot-win32-x64\Tax Document Tracker Pilot.exe`
   is missing.
5. Find `ISCC.exe` in `%ProgramFiles(x86)%\Inno Setup 6\`,
   `%ProgramFiles%\Inno Setup 6\`, `%LOCALAPPDATA%\Programs\Inno Setup 6\`.
   If none: print "Inno Setup 6 is not installed. Install it from
   jrsoftware.org (free), then run this again." and exit 1.
6. Run `ISCC.exe /DAppVersion=%VER% /DSourceDir="<full path to the packaged folder>" pilot\installer\setup.iss`.
7. Print the installer's full path and its SHA-256
   (`%SystemRoot%\System32\certutil.exe -hashfile <file> SHA256`), and a
   reminder: "Tag this commit pilot-%VER% (never v...)".
8. Pause unless `TRACKER_BUILD_NONINTERACTIVE` was set by the caller.

## 11. Tests (Python, reading files as text)

Name each test as the claim it makes. Run under Python 3.11 and the office's.

**`tests/test_pilot.py`** (owns `app/renderer/pilot.js`)

- `test_the_pilot_content_is_json_between_its_markers` - body between
  `// PILOT-CONTENT-BEGIN` and `// PILOT-CONTENT-END` parses with `json.loads`.
- `test_the_edition_version_is_a_plain_version_number`.
- `test_the_terms_have_every_field_and_a_positive_version`.
- `test_every_terms_section_has_a_heading_and_bullets`.
- `test_the_contact_is_the_firms_admin_address` - `contact.email` is
  `admin@jparkassociates.com`.
- `test_every_line_of_copy_is_short` - every terms bullet and tour sentence or
  bullet is at most 30 words.
- `test_the_page_loads_the_pilot_after_the_app` - `index.html` has
  `pilot-style.css` after `style.css`, and `pilot-content.js`, `pilot.js`,
  `tour.js` in that order after `app.js`.
- `test_the_pilot_files_build_the_page_only_with_text` - none of `innerHTML`,
  `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval(`, `new Function`,
  `startsWith(` in `pilot-content.js`, `pilot.js`, `tour.js`.
- `test_the_pilot_never_types_the_product_name` - `productName` from
  `app/package.json` does not appear in the three pilot JS files or
  `pilot-style.css`.
- `test_the_terms_cannot_be_escaped` - `pilot.js` handles `keydown` in the
  capture phase and never adds the terms to `DIALOGS`.
- `test_the_pilot_style_targets_only_its_own_names` - every selector in
  `pilot-style.css` starts with `.pilot-`, `#pilot-`, `#btn-tour` or `.brand`.

**`tests/test_tour.py`** (owns `app/renderer/tour.js`)

- `test_every_tour_anchor_is_an_element_the_page_has` - each id in every
  `anchors` list occurs as `id="<id>"` in `index.html`.
- `test_every_step_has_its_three_callouts` - `title` non-empty; `does`,
  `strength`, `limit` each a non-empty string or a non-empty list of
  non-empty strings.
- `test_every_step_sits_on_the_strip` - each `stage` is in `tour.stages`;
  only the first and last steps have `""`; stages never go backwards.
- `test_a_step_that_points_says_what_to_expect_when_it_cannot` - non-empty
  `fallback` whenever `anchors` is non-empty.
- `test_step_ids_are_unique_and_the_tour_opens_and_closes_centred` - unique
  ids; first and last steps have no anchors.
- `test_the_tour_only_points` - `tour.js` contains none of `window.tracker`,
  `.click(`, `dispatchEvent`.
- `test_the_tour_text_carries_no_placeholder_but_the_email` - the only `{...}`
  token in any string is `{email}`.

**`tests/test_pilot_installer.py`** (no owned module)

- `test_the_installer_installs_for_one_user_without_admin` - `PrivilegesRequired=lowest`.
- `test_uninstalling_removes_the_schedule_it_ran` - `[UninstallRun]` deletes a
  task whose name equals `tracker.scheduling.TASK_NAME` evaluated with the
  package's `productName` (import `tracker.scheduling`; compare to
  `app/package.json` `productName`).
- `test_uninstalling_never_deletes_client_or_tracker_data` - no
  `[UninstallDelete]` section; no `{localappdata}\tax-document-tracker-pilot` (nor the original `tax-document-tracker`),
  `settings.json` or `Delete` of anything outside `{app}`.
- `test_the_installer_needs_a_version_to_compile` - `#ifndef AppVersion` and `#error`.
- `test_the_pilot_build_refuses_what_is_not_committed` - the `.bat` runs
  `git status --porcelain` and exits on output.
- `test_the_pilot_build_follows_the_root_scripts_rules` - first command sets
  `NoDefaultCurrentDirectoryInExePath=1`; it calls `Build App.bat`; it reads
  the version from `pilot-content.js`; it never mentions a `v` tag except in the
  "never v" warning.

Plus the standing affected tests: `tests/test_layers.py` (the network scan now
covers the new JS), `tests/test_single_source.py`, `tests/test_repo_map.py`.

## 12. Dependency on the original repository: the schedule setting - on/off and run time (P14, P16)

Jason asked for the scheduled job to be a setting testers can turn on or off in
the app, and whose run time they can set (P16). The app re-registers the
schedule by itself (decision 209's after-install step runs at launch, at Setup,
and when the clients root is saved), so both the switch and the chosen time
must live in the engine and be respected there: today that step re-registers
with the defaults (`scheduling.DEFAULT_START` = 07:00, repeating every
`DEFAULT_REPEAT_MINUTES` = 120 minutes), which would silently undo a time a
person chose. It is
therefore a feature of the original repository with its own SPEC and decision
number, built, reviewed and merged on its `main` like any other.

Brief for that session in the original repository (it writes its own SPEC; this is input, not the SPEC):

- A per-computer setting, "Run the schedule on this computer", on or off, shown
  where the app shows its settings.
- **Off** removes this computer's task and is remembered, so the after-install
  step at launch, at Setup and on saving the clients root does not register it
  again; the first screen says plainly that the schedule is off.
- **On** registers it through the existing after-install path (the same outcome
  and sentences as **Repair the schedule**).
- **Run time.** In the same setting: the time of day the schedule first runs
  (`HH:MM`, default 07:00) and how often it repeats after that (default every
  120 minutes, with "once a day" as a choice). The API's `install-schedule`
  already takes `start` and `every`; what is new is that the chosen values are
  **saved per computer and used by every re-registration** (launch, Setup,
  saving the clients root, **Repair the schedule**), never reset to the
  defaults. Changing the time re-registers the task at once and the setting
  shows the next run.
- A time that is not a valid `HH:MM`, or an interval outside what Task
  Scheduler accepts, is refused with a sentence saying why; nothing is saved.
- The weekly reminder draft day is unchanged by the run time.
- The designation file (which computer runs the schedule) is unchanged by the
  switch or the time.
- Nothing is ever sent; Scan still works with the schedule off.

Pilot side: the pilot takes it at its next merge from `upstream/main`. Until then the
wrap-up copy uses the "coming in the release build" sentence (section 8), and
**pilot 0.1 is not released** until that merge is in and the wrap-up sentence
is swapped back. The Tester Guide names the setting only once it exists.

## 13. `pilot/Tester Guide.md`

Plain English, for a CPA, not a programmer. Sections:

1. **What this is** - two sentences, the standing rules in plain words, and
   "this is a pilot".
2. **Before you start** - Windows 10 or 11; keep backups; try it first on a
   copy of a few client folders.
3. **Install** - run `Tax-Document-Tracker-Pilot-Setup-<version>.exe`; Windows
   SmartScreen says "Windows protected your PC" because the installer is not
   yet signed: click **More info**, then **Run anyway**. No admin rights needed.
4. **First launch** - read and accept the terms; the tour starts; choose a
   clients folder.
5. **Your first household** - New household, pick the return type, tick the
   documents you expect.
6. **Try it** - open Inbox, drop in a mix (a W-2, a 1099, a phone photo, a
   document it will not know), press Scan, then look at the moved originals,
   the Prepared folder, Needs Review, Status, and (after the weekly draft day)
   the reminder.
7. **The schedule** - what it does, which computer runs it, and the setting
   to turn it on or off and choose when it runs (added once it exists on
   the original repository, section 12).
8. **What it will not do yet** - the limits from the wrap-up step.
9. **Uninstall** - Windows Settings -> Apps -> Tax Document Tracker Pilot.
   It removes the program and its scheduled task. It leaves your clients
   folder, your settings and the program's data folder
   (`%LOCALAPPDATA%\tax-document-tracker-pilot`) where they are.
10. **Problems and ideas** - email admin@jparkassociates.com; never attach
    client documents; describe or screenshot with names covered.

## 14. Safety note for testing at J Park (P15, revised by P18)

After section 3a the pilot has its own program, data folder and scheduled task,
so it cannot touch the real product's data or schedule, and a separate Windows
account is no longer required. Still point it at a **copy** of client folders,
never the live clients root, and never let the pilot and the real product run
schedules over the same clients folder.

## 15. Build split and done criteria

- **Build A (sonnet):** `pilot/installer/setup.iss`, `pilot/Build Pilot Installer.bat`,
  `pilot/Tester Guide.md`, `tests/test_pilot_installer.py`.
- **Build B (sonnet):** `app/renderer/pilot-content.js` (sections 4, 7, 8 as
  approved), `pilot.js`, `tour.js`, `pilot-style.css`, the four `index.html`
  lines, `tests/test_pilot.py`, `tests/test_tour.py`.
- Each build works on its own branch of this repository (`build-a`,
  `build-b`), cut from `main`, and is merged back into `main` with a merge
  commit; each runs `python tools/repo_map.py update` after its merge, the
  second one again.
- **Build A** also makes the section 3a renames and the P19 deny-list change,
  first, as its own commit, and runs the name-sensitive tests listed there.
- Build A's `.bat` reads `pilot-content.js`, which Build B writes; Build A's
  test fixture may use a temporary copy in the section 4 shape.

Done when, on this repository's `main`:

- the gate passes: dead code removed, `ruff check .`, `repo_map.py check`, the
  affected tests (section 11 plus `test_layers`, `test_single_source`,
  `test_repo_map`) under both interpreters;
- `git diff upstream/main...main -- tracker/ app/main.js app/preload.js app/renderer/app.js app/renderer/style.css app/package.json`
  shows only the section 3a lines;
- run from source on a scratch root (`tests/samples.py::build_scratch_root`,
  local only): the terms show once and cannot be escaped; the tour starts after
  accepting; every step either highlights its element or shows its fallback;
  the badge and Tour button show; Scan still works;
- the opus review (a session that built nothing) has no open findings.
