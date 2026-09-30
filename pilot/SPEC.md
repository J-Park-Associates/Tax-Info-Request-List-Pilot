# Pilot edition 0.1 - SPEC

> Note (2026-09-29): this SPEC built the first edition. The shipped version
> label is now 0.2 (`pilot-content.js`), and `style.css` also carries a
> `forced-colors` block for Windows contrast themes (P50). Everything else
> below still describes what was built.

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
  (P7, P18) and the schedule setting in section 12 (P21). No change to
  `app/main.js`, `app/preload.js` or `app/renderer/style.css` (P10), and none
  to `app/renderer/app.js` except the Schedule dialog of section 12 (P21);
  `app/package.json` changes only in the two name lines of section 3a.
- No sample sandbox, feedback button, usage collection or expiry (P5).
- No network call of any kind, no new IPC channel (P10).
- The tour **only points**. It never clicks a button, never runs a pass, never
  calls `window.tracker`, never opens a file or folder.
- The schedule setting (section 12) is the one engine feature the pilot
  builds itself (P21); it is Build C, not part of the tour or installer.

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

- **Where acceptance lives (P46, superseding P9).** The durable record is
  the tracker's own: `pilot-record.json` in the data folder, per Windows
  account, read and written by the API command `pilot-record` over the
  existing `tracker-cmd` channel (`{}` reads it; `{"terms": "<version>"}`
  and `{"tour_seen": true}` record; the reply is `{terms, tour_seen}`). The
  window's `localStorage` (`pilot.terms.accepted`, `pilot.tour.seen`) is only
  its cache. Every `localStorage` access is in `try/catch`, and both live in
  one place, `PilotRecord` at the top of `pilot.js`, the one name `tour.js`
  uses from it.
- The shell runs a command only after the page's first call (`list`) has
  named the commands, so `PilotRecord` waits until `vocab.commands` lists
  `pilot-record` (it looks every 200 ms, for up to 2 minutes) before it asks.
  A reply with an error is sent to `window.tracker.logError` and counts as
  no answer.
- **Cache says this version is accepted:** no terms. In the background the
  record is read, and if it lacks this version it is written (a 0.1 tester
  accepted before the record existed).
- **Cache says nothing** (empty, blocked, or storage that could not be
  opened): the terms show at once (fail safe), and the record is asked.
  If it holds this version's acceptance, the overlay is removed without a
  word, the cache is refilled, and the tour is **not** started. If it cannot
  answer or holds another version, the terms stay. A storage failure never
  shows the terms again without the record having been asked.
- Overlay `z-index: 60` (the app's modals use 40), covers the whole window,
  dims it, and swallows clicks. **Escape does nothing** and clicking outside does
  nothing: a `keydown` listener on `document` in the capture phase stops
  Escape and keeps Tab focus inside the card while the terms are open.
- Focus goes to the checkbox when shown.
- **Accept**: record the acceptance (`PilotRecord.acceptTerms`: the cache
  and `pilot-record` with `{"terms": String(terms.version)}`), remove the
  overlay, then start the tour unless the cache (or the record, once read)
  says it was seen.
- **Quit**: `window.close()`.

**Exposes** nothing but what `tour.js` needs, `PilotRecord.tourSeen()`.
`tour.js` defines `PilotTour`; `pilot.js` only calls `PilotTour.start()` (it
is loaded after, so resolve it at click/accept time, not load time).

**The shell's part (P46).** `main.js` keeps the single-instance lock, and it
writes the page's storage to disk as the window closes
(`session.flushStorageData()` on the window's `close`). Electron lets go of
the single-instance lock as it starts quitting, before it closes that
storage. A restart made in that gap gets a window whose storage cannot be
opened, and that is why the durable record, not the cache, is the answer.

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
- Close or Finish -> `stop()`, and calls `PilotRecord.tourSeen()` (the cache
  and `pilot-record` with `{"tour_seen": true}`, P46). `tour.js` itself
  never touches `window.tracker` or `localStorage`.
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

## 8. Tour copy (approved by Jason, 2026-09-28, P22)

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
   • Nothing guessed, nothing sent     • Schedule on/off and run time: the Schedule button
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
| 11 | overview | What to expect | Replay this tour any time with the Tour button. | Runs offline on your own Windows PC • No AI reads client documents • Originals never altered • Nothing guessed, nothing sent | Windows only • About 74 document kinds, 6 return types • Scans slow without the optional graphics pack • Schedule on/off and run time: the Schedule button • Installer unsigned: Windows shows a warning • Problems or ideas: {email} |

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
        "fallback": "New household is at the top of the window."
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
        "fallback": "Inbox opens once a household is chosen at the top left."
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
        "fallback": "Scan works once a household is chosen at the top left."
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
        "fallback": "Status opens once a household is chosen at the top left."
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
          "Schedule on/off and run time: the Schedule button",
          "Installer unsigned: Windows shows a warning",
          "Problems or ideas: {email}"
        ],
        "fallback": ""
      }
    ]
  }
```

**Schedule wording** (P21). The wrap-up limit names the Schedule button that
Build C adds (section 12). If Build C has not merged when Build B does, Build B
still uses this wording; the pilot is not released until Build C is in.

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
- **`[InstallDelete]`: the old program code only** (P115, narrowing P12). An
  upgrade first removes `{app}\resources\app` and
  `{app}\resources\tracker-api\_internal` (the name is `config.apiName`),
  which `[Files]` then replaces whole, so no file the new version dropped is
  left behind. Never the folders above them: the graphics card pack
  (`gpu-runtime`) sits beside `tracker-api.exe` and `settings.json` beside the
  app's executable. `CloseApplications=force` and `RestartApplications=no`:
  a running app or pass is closed, not merely asked, since a locked old file
  left after the deletion would stop the copy half way; nothing restarts. An
  upgrade aborted half way is repaired by running the installer again.

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
   If none: print "Inno Setup 6.3 or later is not installed. Install it from
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
- `test_an_upgrade_clears_only_the_old_program_code` - `[InstallDelete]` is
  exactly the two code folders (P115).
- `test_the_upgrades_deletion_is_one_section_only` - one `[InstallDelete]`
  heading, so no second one can hide a data path (P115).
- `test_an_upgrade_closes_the_running_app_and_restarts_nothing` -
  `CloseApplications=force`, `RestartApplications=no` (P115).
- `test_the_installer_needs_a_version_to_compile` - `#ifndef AppVersion` and `#error`.
- `test_the_pilot_build_refuses_what_is_not_committed` - the `.bat` runs
  `git status --porcelain` and exits on output.
- `test_the_pilot_build_follows_the_root_scripts_rules` - first command sets
  `NoDefaultCurrentDirectoryInExePath=1`; it calls `Build App.bat`; it reads
  the version from `pilot-content.js`; it never mentions a `v` tag except in the
  "never v" warning.

Plus the standing affected tests: `tests/test_layers.py` (the network scan now
covers the new JS), `tests/test_single_source.py`, `tests/test_repo_map.py`.

## 12. The schedule setting: on/off, start time, how often (P16, P21)

Jason asked for the scheduled job to be a setting testers turn on or off, and
whose run time they choose (P16), built in the pilot only (P21). This is
**Build C**.

### 12.1 Why the engine must change

- The schedule is registered from five places: the app's launch
  (`api._cmd_after_install` -> `after_install.launch()`), `Setup.bat`
  (`--reason setup`), saving the clients root (`api._cmd_set_root`),
  **Repair the schedule** (`api._cmd_install_schedule`) and **Move schedule
  here** (`api._cmd_move_schedule_here`). All but Repair use the fixed
  defaults `scheduling.DEFAULT_START` (07:00) and
  `DEFAULT_REPEAT_MINUTES` (120), and Repair's page always sends `{}`. A chosen
  time would be overwritten by the next of any of them.
- `after_install.launch()` compares only the program and the designation, so a
  changed choice would never be re-registered at launch.
- The start time is checked only by `scheduling`'s own command line; a bad
  value from the API reaches the task file unchecked. A `ValueError` from a
  bad interval is not caught in `_schedule`.
- `every = 0` already makes a once-a-day task (no `<Repetition>` block), but
  `SCHEDULE_CLAIMED` / `SCHEDULE_REGISTERED` would say "every 0 minutes".
- The morning last-pass line (`runner.LAST_PASS_AMBER_HOURS = 4`,
  `LAST_PASS_OLD`) assumes the 2-hour default.
- There is no settings screen once the clients root is set.

### 12.2 Where the choice lives

`settings.json`, beside the program (`settings.settings_dir()`), which is per
computer and already holds the clients root, firm and phone. Three keys,
written only when a person saves the setting (so
`tests/test_settings.py`'s root-only file test still holds):

| Key | Type | Default when absent |
|---|---|---|
| `schedule_enabled` | `true` / `false` | `true` |
| `schedule_start` | `"HH:MM"`, 00:00-23:59 | `scheduling.DEFAULT_START` |
| `schedule_every` | minutes; `0` = once a day | `scheduling.DEFAULT_REPEAT_MINUTES` |

`settings.py` gains `schedule_preference()` -> `SchedulePreference(enabled,
start, every)` and `set_schedule(enabled, start, every)` (atomic
read-modify-write like the other setters). The preference is a small frozen
dataclass in `scheduling.py` so `after_install` and `api` share one type.

### 12.3 The allowed choices, checked in one place

- **How often:** once a day (`0`), or every 30, 60, 120 (default), 240 or 480
  minutes - `scheduling.EVERY_CHOICES = (0, 30, 60, 120, 240, 480)`.
- **Start:** `HH:MM`, two digits each, 00:00-23:59.
- `scheduling.check_start(value) -> str` and `scheduling.check_every(value) -> int`
  raise `ScheduleChoiceError(sentence)` naming the value and what is allowed.
  They are used by `set_schedule`, by `schedule_preference()` (a hand-edited
  bad value in `settings.json` is refused with a sentence naming the file and
  the key - never guessed, never silently reset), by `register_here` and by
  `scheduling`'s command line (which drops its own check).
- An unreadable preference at after-install time is a failure of the step,
  recorded and shown in the first-screen notice like `SETTINGS_UNREADABLE`;
  no task is registered from a guess.

### 12.4 Every registration path uses the saved choice

- `after_install.run(*, reason, start=None, every=None, checkout=None)`: when
  `start` / `every` are `None` it reads `schedule_preference()`. Every caller
  listed in 12.1 passes nothing, so all five paths use the saved choice.
  Repair's explicit `{start, every}` stays accepted for the command line, and
  is saved first when given (so Repair never registers something the setting
  does not show).
- **Off:** `_schedule` removes this computer's task (`scheduling.remove_task()`)
  and returns a new outcome `scheduling.OFF = "off"` with
  `SCHEDULE_OFF = "The schedule is off on this computer. Scan still works. Turn it on with the Schedule button."`
  It does **not** claim or change the designation: turning the schedule off
  on the designated computer leaves no computer running it, which the
  sentence says plainly; turning it on again registers it as before.
- **Launch:** the after-install record gains `preference`
  (`{"enabled", "start", "every"}`); `launch()` runs the step again when the
  saved preference differs from the recorded one, and stays a no-op (no
  `schtasks` call) when program, designation and preference are unchanged.
- **One run at a time (P47).** Every door is its own process and two can
  overlap (the launch step runs in the background and outlives its window).
  `run()` and `launch()` hold `after_install.LOCK_FILENAME` beside the record
  from before the choice is read until the record is written, so the run
  that acts last acts on the choice saved last. A run that cannot have the
  lock within `LOCK_WAIT_SECONDS` (10 minutes) changes nothing and records
  nothing; its one failure sentence is `STEP_BUSY`. A lock whose process has
  ended is taken over. Every task the step removes is noted on the local
  debug log with why.
- **Wording:** `SCHEDULE_CLAIMED` / `SCHEDULE_REGISTERED` gain once-a-day
  forms ("every day at {start}"), chosen by `every == 0`.
- **Last pass:** the amber threshold becomes two missed runs of the saved
  interval - `max(4, 2 * every / 60)` hours, or 48 hours for once a day - and
  `LAST_PASS_OLD` says the interval it assumed. With the schedule off the line
  says the schedule is off instead of turning amber.

### 12.5 API

- New command **`set-schedule`**, JSON on stdin `{enabled, start, every}`:
  check, save, run `after_install.run(reason=REASON_REPAIR)`, reply
  `{enabled, start, every, outcome, sentence, next_run, installed, after_install}`.
  `next_run` is a plain sentence ("Next run: today at 13:00" / "tomorrow at
  07:00" / "" when off), computed from the start, the interval and the local
  time. Added to `COMMANDS`, `WRITING_COMMANDS` and the module docstring's
  command list.
- `settings` also returns `schedule: {enabled, start, every}` and `next_run`.
- `install-schedule` defaults to the saved choice (12.4).
- `vocab.schedule` gains every word the dialog shows: `button`, `title`,
  `enabled_label`, `on`, `off`, `start_label`, `every_label`, the choice
  labels (`every_choices`: list of `{minutes, label}` - "Once a day",
  "Every 30 minutes", "Every hour", "Every 2 hours", "Every 4 hours",
  "Every 8 hours"), `note` ("Scan works either way. Nothing is ever sent."),
  `save`, `cancel`. The page types none of them
  (`tests/test_single_source.py` bans `DEFAULT_START` in `app.js`).

### 12.6 The Schedule dialog

- A **Schedule** button (`#btn-schedule`, label from `vocab.schedule.button`)
  inserted in `index.html` immediately **after** `#btn-edit` - outside the
  toolbar stretch `btn-client-folder`..`btn-edit` that
  `test_the_schedule_is_repaired_from_the_toolbar_in_the_apis_words` pins.
- A dialog `#schedule-modal` in the app's existing pattern
  (`modal-overlay hidden` > `modal`, registered in `app.js`'s `DIALOGS`, so
  Escape, focus trap and click-away behave like the other dialogs):

```
 Schedule on this computer
 Run the schedule    (●) On   ( ) Off
 First run at        [ 07:00 ]        <input type="time">
 How often           [ Every 2 hours ▾ ]
 Next run: today at 13:00
 Scan works either way. Nothing is ever sent.
                                   [ Cancel ]  [ Save ]
```

- Opens with the values from `settings`. Turning it Off greys the two fields.
- **Save** calls `set-schedule`; the reply's `sentence` shows in the usual
  banner (`#banner`), and the dialog closes. A refusal
  (`ScheduleChoiceError`) shows in the dialog and keeps it open.
- **Repair the schedule** keeps its button and flow, now re-registering the
  saved choice.

### 12.7 Runbook

`docs/runbook.md` changes where it assumes the fixed default: the schedule
paragraph (~608-626, now a per-computer saved setting and the Schedule
button), "every two hours" at ~125 and ~1530 ("on the saved schedule"), repair
at ~1164-1168, the last-pass amber rule at ~1210-1224, and the move step in
section 6 (~1950-1955).

### 12.8 Tests (Build C)

- `test_scheduling`: `check_start` / `check_every` accept every allowed value
  and refuse the rest with the sentence; once-a-day task file has no
  `<Repetition>`; once-a-day wording.
- `test_settings`: the preference round-trips; absent keys give the defaults;
  a bad saved value refuses naming file and key; saving the root alone still
  writes only the root.
- `test_after_install`: every path registers the saved choice; off removes
  the task and claims nothing; launch re-runs when the preference changed and
  stays a no-op (no `schtasks`) when nothing changed; an unreadable
  preference is a recorded failure.
- `test_api`: `set-schedule` round trip and refusal; Repair uses the saved
  choice; `settings` returns the schedule; `vocab.schedule` equality
  (~2492) and the command lists updated; the dialog uses only the API's
  words; the toolbar slice test still passes.
- `test_runner`: the amber threshold follows the interval and the off state.
- `test_single_source`: the runbook passages; the docstring command list.

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
7. **The schedule** - what it does, which computer runs it, and the
   **Schedule** button: turn it on or off, choose the first run time and how
   often (section 12).
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
  lines (Build E adds a fifth, the `pilot-ui.css` link, and the file itself:
  `SPEC-ui.md`), `tests/test_pilot.py`, `tests/test_tour.py`.
- **Build C (sonnet): the schedule setting** - section 12: `tracker/scheduling.py`,
  `settings.py`, `after_install.py`, `api.py`, `runner.py`, the Schedule
  button and dialog in `index.html` / `app.js`, `docs/runbook.md`, and the
  tests in 12.8. It runs **in parallel with A and B** (P23): B and C edit
  different spots of `index.html`, so the merge keeps both sides.
- Each build works on its own session branch cut from `main`, pushes it and
  opens a **draft pull request** to `main` (P23). After review and fixes, the
  integrate session merges them in the order **B, A, C**, each as a merge
  commit, running `python tools/repo_map.py update` and the gate after each.
  The prompts for every session are in [`PROMPTS.md`](PROMPTS.md).
- **Build A** also makes the section 3a renames and the P19 deny-list change,
  first, as its own commit, and runs the name-sensitive tests listed there.
- Build A's `.bat` reads `pilot-content.js`, which Build B writes; Build A's
  test fixture may use a temporary copy in the section 4 shape.

Done when, on this repository's `main`:

- the gate passes: dead code removed, `ruff check .`, `repo_map.py check`, the
  affected tests (section 11 plus `test_layers`, `test_single_source`,
  `test_repo_map`) under both interpreters;
- `git diff upstream/main...main -- tracker/ app/main.js app/preload.js app/renderer/app.js app/renderer/style.css app/package.json`
  shows only the section 3a lines and the section 12 schedule setting;
- run from source on a scratch root (`tests/samples.py::build_scratch_root`,
  local only): the terms show once and cannot be escaped; the tour starts after
  accepting; every step either highlights its element or shows its fallback;
  the badge and Tour button show; Scan still works; the Schedule dialog
  saves on/off, start and interval, and the choice survives a restart;
- the opus review (a session that built nothing) has no open findings.
