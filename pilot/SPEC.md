# Pilot edition 0.1 - SPEC

Status: **draft for Jason's approval** (2026-09-28). Wording in sections 7 and 8
is proposed copy; builders use it exactly as approved.

Read first: [`README.md`](README.md) (branch rules), [`DECISIONS.md`](DECISIONS.md)
(P1-P15). Decisions referenced below as P-numbers.

## 1. What this is

A Windows installer for **Tax Document Tracker - Pilot**, given to a first batch
of other CPA firms to run on their own clients' files. It is the current product
from `main`, unchanged in how it sorts, plus three pilot additions:

1. a **"Pilot edition 0.1" badge** in the header;
2. a **terms screen**, shown once, that the tester must accept before using it;
3. a **guided tour** over the real screen that shows each part of the flow and
   says, for each, what it does, why it is safe, and what its current limit is.
   The tour is the marketing piece (P6).

And, outside the app: an **installer** (`setup.iss` + a build script) and a
**Tester Guide**.

### Non-goals (do not build)

- No change under `tracker/` (P7). No change to `app/main.js`, `app/preload.js`,
  `app/renderer/app.js`, `app/renderer/style.css` or `app/package.json` (P10).
- No sample sandbox, feedback button, usage collection or expiry (P5).
- No network call of any kind, no new IPC channel (P10).
- The tour **only points**. It never clicks a button, never runs a pass, never
  calls `window.tracker`, never opens a file or folder.
- The schedule on/off setting is **not** built here; it is built on `main`
  (P14, section 12).

## 2. Constraints every pilot file obeys

These come from tests that already run over the app; breaking one fails the gate.

| Constraint | Enforced by |
|---|---|
| CSP `script-src 'self'; style-src 'self'`: scripts and styles only as files; no inline `<script>` body, no `on...=` attributes, no `style=` attributes in HTML | `index.html` CSP; `tests/test_single_source.py` |
| No `fetch(`, `XMLHttpRequest`, `WebSocket`, `EventSource`, `sendBeacon`, `window.open(`, `openExternal`, `import(`, `loadURL`, non-string `require(` - **not even in comments** | `tests/test_layers.py::test_the_app_has_no_network_call` (scans every `app/**/*.js`) |
| No new IPC channel; `main.js` and `preload.js` channel lists stay as they are | `tests/test_single_source.py` |
| The product name literal ("Tax Document Tracker") never typed in renderer files; read `vocab.product` at run time if needed | `tests/test_single_source.py` (and P11 for new files) |
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
  "contact": {"email": "jasonpark@jparkassociates.com"},
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
- `terms`: `title` (string), `paragraphs` (array of strings, shown in order),
  `checkbox` (string), `accept` (button label), `quit` (button label).
- `tour.steps[]`: each step has
  - `id` - unique, lowercase, `a-z0-9-`;
  - `anchors` - array of element ids (no `#`), tried in order; the first one
    that is visible is highlighted; may be empty (a centred step);
  - `title`, `does`, `strength`, `limit` - non-empty strings;
  - `fallback` - string shown when no anchor is visible (non-empty whenever
    `anchors` is non-empty; `""` when `anchors` is empty).
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
    div.pilot-terms-body                   one <p> per terms.paragraphs[i]
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
    div.pilot-tour-count          "Step 3 of 11"
    h2#pilot-tour-title           step.title
    section: h3 "What it does"     p step.does
    section: h3 "Why it's safe"    p step.strength
    section: h3 "Current limit"    p step.limit
    p.pilot-tour-fallback          step.fallback (only when no anchor is visible)
    div.pilot-tour-actions: button Back | button Next ("Finish" on the last) | button Close
```

The three section headings are fixed words in `tour.js` (they are UI labels,
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

## 7. Terms text (draft for approval)

```json
"terms": {
  "version": 1,
  "title": "Before you start: this is a pilot",
  "paragraphs": [
    "This is a pilot edition of Tax Document Tracker, given to a small group of firms to try before general release. It works, but it is still being finished. Expect rough edges, and please tell us about them.",
    "Keep your own backups. Before you point this program at a clients folder, make sure that folder is backed up. For your first tries, we suggest a copy of a few real client folders rather than your live ones.",
    "How it treats your files. Files a client drops in are moved, byte for byte and under their own names, into that client's folder for the year. They are never edited, renamed or compressed. All sorting and renaming happens on copies, and every move is recorded.",
    "No AI reads your documents. Every sorting decision comes from fixed, written rules. A document the rules cannot place with certainty goes to Needs Review for a person to decide.",
    "Nothing is sent. The program drafts reminder emails for you to read and send yourself. It has no email sending of its own, and it does not send your data anywhere: it runs entirely on this computer and needs no internet connection.",
    "No warranty. The pilot is provided as is, without warranty of any kind. You remain responsible for your clients' records and for checking what the program files.",
    "Questions or problems: email {email}. Please do not send client documents; describe what happened, or send a screenshot with client names covered."
  ],
  "checkbox": "I have read this and will keep my own backups.",
  "accept": "I agree - continue",
  "quit": "Quit"
}
```

## 8. Tour copy (draft for approval)

Eleven steps, in this order.

```json
"tour": {"steps": [
  {
    "id": "welcome",
    "anchors": [],
    "title": "Welcome to the pilot",
    "does": "This tour walks through one full season's flow: a client drops documents in one folder, the program sorts and renames them, and you see what arrived, what is missing, and what needs a person.",
    "strength": "Everything you are about to see runs on this computer, with fixed rules you can read. No AI reads a client document, and nothing is ever sent.",
    "limit": "This is a pilot. It covers individual, business, trust and exempt-organization returns (1040, 1120, 1120-S, 1065, 1041, 990), about 74 kinds of document in all.",
    "fallback": ""
  },
  {
    "id": "clients-folder",
    "anchors": ["setup-card", "eng-select"],
    "title": "One clients folder",
    "does": "You choose one clients folder. Inside it, each household gets a folder you share with the client, holding a single inbox called 'Drop files here', and a private working folder that only your firm sees.",
    "strength": "The client only ever sees their own shared folder. Your working copies, notes and records stay in the private tree.",
    "limit": "Use a folder your firm already backs up and syncs (for example a shared drive). One computer should run the automatic schedule for a given clients folder.",
    "fallback": "You have already chosen a clients folder. The switcher at the top left moves between returns."
  },
  {
    "id": "new-household",
    "anchors": ["btn-new-household"],
    "title": "A household and its request list",
    "does": "Create a household, pick the return type, and tick the documents you expect (W-2s, 1099s, K-1s, a prior-year return, and so on). That list is the request list the client works from.",
    "strength": "Documents are matched against your own request list, so a file lands under the item you asked for, in the order you asked for it.",
    "limit": "Requests are chosen from the built-in list for each return type, plus custom lines you add. A document type the program does not know yet will go to Needs Review rather than be guessed.",
    "fallback": ""
  },
  {
    "id": "drop-files",
    "anchors": ["btn-inbox"],
    "title": "The client drops files here",
    "does": "Inbox opens the household's 'Drop files here' folder. The client (or you) drops everything in: PDFs, scans, phone photos, spreadsheets, even zipped folders and forwarded emails.",
    "strength": "The client never has to name or sort anything. One folder, all year.",
    "limit": "Phone photos and poor scans are read with on-device text recognition, which is slower on an ordinary processor and can miss faint text. Those files go to Needs Review rather than being guessed.",
    "fallback": ""
  },
  {
    "id": "scan",
    "anchors": ["btn-scan"],
    "title": "Scan sorts what arrived",
    "does": "Scan runs one pass for this household now: it reads each new file, matches it to a request, moves the original out of the inbox, and makes a neatly named working copy.",
    "strength": "A file is filed only when exactly one request accepts it. Anything ambiguous is set aside for a person - misfiling a tax document is worse than not filing it.",
    "limit": "A pass takes longer on a first scan with many image files. The same pass also runs by itself on a schedule on the computer chosen to run it.",
    "fallback": ""
  },
  {
    "id": "originals",
    "anchors": ["moved-card"],
    "title": "Originals, moved and untouched",
    "does": "This card lists the originals the last pass moved out of 'Drop files here' into the client's folder for the year, with a way to put any of them back.",
    "strength": "Originals are moved byte for byte under their own names and never altered. Every move is recorded, so any of them can be undone.",
    "limit": "Moving a file is final for the client's inbox: the client sees it leave 'Drop files here' once it has been taken in.",
    "fallback": "This card appears after a scan has moved something out of the inbox."
  },
  {
    "id": "working-copies",
    "anchors": ["filed-card"],
    "title": "Organized working copies",
    "does": "Each accepted document is copied into the return's Prepared folder with an organized name taken from your request list - for example 'A01 - W-2 - TY2025.pdf' - ready for preparation.",
    "strength": "Names follow your request list, so every return's folder reads the same way, and the working copies can be checked or re-made at any time from the originals.",
    "limit": "Names follow the built-in pattern; custom naming schemes are not offered in the pilot.",
    "fallback": "This list appears after the first document has been filed."
  },
  {
    "id": "needs-review",
    "anchors": ["review-card"],
    "title": "Needs Review: a person decides",
    "does": "Anything the rules could not place with certainty - an unknown form, a document two requests both accept, an unreadable scan - waits here with the likely matches, for you to file with one click or dismiss.",
    "strength": "Nothing is guessed. The program shows you why it stopped and never files a doubtful document on its own.",
    "limit": "Expect more items here in the first weeks, especially from firms whose clients send unusual layouts. Every item you file teaches you what the program recognizes; it does not change the rules by itself.",
    "fallback": "This card appears when a pass has set a document aside for a person."
  },
  {
    "id": "status",
    "anchors": ["btn-status"],
    "title": "Status: what is in, what is missing",
    "does": "Status opens the household's status page: every requested document, whether it has arrived, and any validation notes (for example a document for the wrong year or the wrong person).",
    "strength": "One page answers 'what are we still waiting for?' without opening a single folder.",
    "limit": "The status page is a file on this computer; it is not a client portal and is not shared automatically.",
    "fallback": ""
  },
  {
    "id": "reminder",
    "anchors": ["reminder-card"],
    "title": "A drafted reminder - never sent",
    "does": "Once a week the program drafts a reminder email listing what is still missing, in plain words the client can act on. You read it, copy it, and send it yourself.",
    "strength": "Nothing is ever sent. There is no email sending in the program at all, so no client is ever contacted without you.",
    "limit": "You send reminders from your own email program; the pilot does not connect to Outlook or Gmail.",
    "fallback": "This card appears when a reminder has been drafted for this household."
  },
  {
    "id": "wrap-up",
    "anchors": [],
    "title": "What to expect from the pilot",
    "does": "That is the whole flow: one inbox for the client, sorted originals, organized working copies, a Needs Review queue, a status page and drafted reminders. Replay this tour any time with the Tour button.",
    "strength": "Runs offline on your own Windows PC. No AI reads client documents, originals are never altered, nothing is guessed and nothing is sent.",
    "limit": "Windows only. About 74 document kinds across 6 return types. Scans read slowly without the optional graphics-card pack. One computer should run the automatic schedule, which can be turned on or off in the app's settings. The installer is not yet signed, so Windows shows a warning when you install. Please send problems and ideas to {email}.",
    "fallback": ""
  }
]}
```

**Schedule wording** (P14). The wrap-up `limit` names the on/off setting. Until
the pilot has merged the `main` commit that adds that setting, the sentence
"which can be turned on or off in the app's settings" is replaced by
"(an on/off setting is coming in the release build)", and the pilot is **not
released** (section 12).

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
- `.pilot-tour-card`: `position: fixed;` white, 380px wide (max 92vw),
  8px radius, shadow; the three `h3` headings 12px uppercase grey; the
  "Current limit" section has a light amber left border so limits read as
  honest caveats, not small print.

## 10. The installer

### `pilot/installer/setup.iss` (Inno Setup 6)

Inno Setup is used because the Python standard library cannot build a Windows
installer; it is free and needs no admin rights to run the result (P4).

- `#define AppVersion` comes from the command line (`/DAppVersion=...`); the
  script refuses to compile without it (`#ifndef AppVersion` -> `#error`).
- `#define SourceDir` from the command line: the packaged folder
  `build-portable\dist\Tax Document Tracker-win32-x64`.
- `[Setup]`:
  - `AppName=Tax Document Tracker - Pilot` (a plain hyphen in files; the
    en-dash only in display text is optional),
  - `AppVersion={#AppVersion}`, `AppPublisher=J Park & Associates, CPA`,
  - a fixed `AppId` GUID (generate once; never change it - it is how
    upgrades find the old install),
  - `PrivilegesRequired=lowest`,
  - `DefaultDirName={localappdata}\Programs\Tax Document Tracker Pilot`,
  - `DefaultGroupName=Tax Document Tracker - Pilot`,
  - `OutputDir=..\..\build-portable\installer`,
  - `OutputBaseFilename=Tax-Document-Tracker-Pilot-Setup-{#AppVersion}`,
  - `UninstallDisplayName=Tax Document Tracker - Pilot {#AppVersion}`,
  - `ArchitecturesAllowed=x64compatible`, `ArchitecturesInstallIn64BitMode=x64compatible`,
  - `WizardStyle=modern`, `DisableProgramGroupPage=yes`.
- `[Files]`: `Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion`.
- `[Icons]`: Start-menu `Tax Document Tracker - Pilot` -> `{app}\Tax Document Tracker.exe`;
  optional desktop icon under a `[Tasks]` checkbox, unticked by default.
- `[Run]`: offer "Launch Tax Document Tracker - Pilot" at the end
  (`postinstall nowait skipifsilent`).
- `[UninstallRun]`: `Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN ""Tax Document Tracker"" /F"; Flags: runhidden; RunOnceId: "RemoveSchedule"`.
  The task name is `tracker.scheduling.TASK_NAME`, which is `product_name()`,
  i.e. `productName` = "Tax Document Tracker"; the test in section 11 checks the
  two agree. A missing task is fine (schtasks fails quietly, the uninstall goes on).
- **No `[UninstallDelete]` section.** Uninstall removes only the files it
  installed. It never touches the clients root, the data folder
  `%LOCALAPPDATA%\tax-document-tracker`, or `settings.json` (written beside the
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
   failed or `build-portable\dist\Tax Document Tracker-win32-x64\Tax Document Tracker.exe`
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
- `test_the_contact_is_an_email_address`.
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
- `test_every_step_has_its_three_callouts` - `title`, `does`, `strength`,
  `limit` non-empty.
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
  `[UninstallDelete]` section; no `{localappdata}\tax-document-tracker`,
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

## 12. Dependency on `main`: the schedule on/off setting (P14)

Jason asked for the scheduled job to be a setting testers can turn on or off in
the app. The app re-registers the schedule by itself (decision 209's
after-install step runs at launch, at Setup, and when the clients root is
saved), so an off switch must live in the engine and be respected there. It is
therefore a `main`-lane feature with its own SPEC and decision number, built,
reviewed and merged on `main` like any other.

Brief for that `main` session (it writes its own SPEC; this is input, not the SPEC):

- A per-computer setting, "Run the schedule on this computer", on or off, shown
  where the app shows its settings.
- **Off** removes this computer's task and is remembered, so the after-install
  step at launch, at Setup and on saving the clients root does not register it
  again; the first screen says plainly that the schedule is off.
- **On** registers it through the existing after-install path (the same outcome
  and sentences as **Repair the schedule**).
- The designation file (which computer runs the schedule) is unchanged by the
  switch.
- Nothing is ever sent; Scan still works with the schedule off.

Pilot side: the pilot takes it at its next merge from `main`. Until then the
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
7. **The schedule** - what it does, which computer runs it, and the on/off
   setting (added once it exists on `main`, section 12).
8. **What it will not do yet** - the limits from the wrap-up step.
9. **Uninstall** - Windows Settings -> Apps -> Tax Document Tracker - Pilot.
   It removes the program and its scheduled task. It leaves your clients
   folder, your settings and the program's data folder
   (`%LOCALAPPDATA%\tax-document-tracker`) where they are.
10. **Problems and ideas** - email jasonpark@jparkassociates.com; never attach
    client documents; describe or screenshot with names covered.

## 14. Safety note for testing at J Park (P15)

The pilot shares the real product's data folder name
(`%LOCALAPPDATA%\tax-document-tracker`) and scheduled-task name. Install and test
it **only under a Windows account that does not run the firm's real schedule**,
and point it at a copy of client folders, never the live clients root.

## 15. Build split and done criteria

- **Build A (sonnet):** `pilot/installer/setup.iss`, `pilot/Build Pilot Installer.bat`,
  `pilot/Tester Guide.md`, `tests/test_pilot_installer.py`.
- **Build B (sonnet):** `app/renderer/pilot-content.js` (sections 4, 7, 8 as
  approved), `pilot.js`, `tour.js`, `pilot-style.css`, the four `index.html`
  lines, `tests/test_pilot.py`, `tests/test_tour.py`.
- Each build works in its own worktree on a branch cut from
  `pilot/first-edition` (`pilot/build-a`, `pilot/build-b`), is merged back with
  a merge commit, and runs `python tools/repo_map.py update` after the merge;
  the second merge re-runs it.
- Build A's `.bat` reads `pilot-content.js`, which Build B writes; Build A's
  test fixture may use a temporary copy in the section 4 shape.

Done when, on the merged branch:

- the gate passes: dead code removed, `ruff check .`, `repo_map.py check`, the
  affected tests (section 11 plus `test_layers`, `test_single_source`,
  `test_repo_map`) under both interpreters;
- `git diff origin/main...pilot/first-edition -- tracker/ app/main.js app/preload.js app/renderer/app.js app/renderer/style.css app/package.json`
  is empty;
- run from source on a scratch root (`tests/samples.py::build_scratch_root`,
  local only): the terms show once and cannot be escaped; the tour starts after
  accepting; every step either highlights its element or shows its fallback;
  the badge and Tour button show; Scan still works;
- the opus review (a session that built nothing) has no open findings.
