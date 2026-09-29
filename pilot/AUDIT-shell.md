# Audit: every element of today's screen, kept only if it earns its place

Status: **for Jason's review** (2026-09-29). Companion to
[`BRIEF-shell.md`](BRIEF-shell.md); input to the SPEC. Decision rows P63-P64.
Source: a full inventory of `index.html`, `app.js`, `pilot.js`, `tour.js` and
`pilot-content.js`, and a word count of all 687 strings the app shows
([`wording-inventory.tsv`](wording-inventory.tsv) lists the 212 over five words).

## The rules applied (Jason, 2026-09-29)

1. **Keep it only if the task breaks without it.** Otherwise cut it, or move it
   one level back: the right-click menu, the menu bar, or Help.
2. **No text over five words** on screen: labels, headings, notices, errors,
   tooltips, dialog text. Two exceptions are proposed below (the pilot terms and
   the client's reminder letter), both Jason's to confirm.
3. **An icon that explains itself carries no words**: no label, no tooltip, no
   message. It keeps an invisible name for screen readers only.
4. **No paths in the UI.** Never a drive, folder path, settings path or working
   copy name. Places are named by role ("client folder", "inbox") and opened in
   File Explorer from a menu, never printed.
5. **No duplicates.** Where two controls do one job, one goes.
6. **No success message where the result is visible.** A row that moves to
   Received needs no banner. A one-word toast only when the effect is off
   screen ("Copied", "Saved").
7. **No detail on screen that belongs in the error log.** Exit codes, host
   names of lock files, stderr, file names of logs: Help > Open error log.

## Before and after, in numbers

| | Today | After |
|---|---|---|
| Buttons always on screen | 12 (10 in the top bar, Tour, Stop) | **1** (the sort icon) |
| Separate cards stacked on the page | 9 | **0** (one grouped list) |
| Text blocks always visible under the list | 4 safety cards, ~150 words | **0** (Help > Safeguards) |
| Strings over five words | 212 of 687 | **0**, outside the two exceptions |
| Places a path is printed | 9 | **0** |
| Controls or headings doing the same job | 20 flagged | **0** (Schedule and Repair stay two menu items: different jobs) |
| Icons on screen | 13 | **7**: search, sort (stop while sorting), close ×, open ›, next, done ✓, more ⋯ |

## 1. Window, side panel, top row

| Element today | Verdict | After (≤5 words) |
|---|---|---|
| Window title | Keep (Windows' own title bar) | "Tax Document Tracker" |
| Logo image | Keep, side panel top, 24px | (image only) |
| Product name beside the logo, divider | **Cut**: the window title already names it | - |
| Pilot badge "Pilot edition 0.2" | Keep, as a caption at the side panel's foot | "Pilot 0.2" |
| Tour button | **Menu**: Help | "Take the tour" |
| Return drop-down `#eng-select` | **Cut**: the breadcrumb and the pages replace it | - |
| Form chip ("1040") | **Cut**: the return's name starts with its form | - |
| "Status report: current/behind" chip | **Cut**: the report moves to a menu | - |
| New household (+ icon) | **Menu**: File, Ctrl+N; plus the Clients page's empty state | "New household…" |
| Open Inbox (tray icon) | **Menu**: Client; right-click | "Open inbox" |
| Open Client Folder (folder icon) | **Menu**: Client; right-click | "Open client folder" |
| Edit Request List (grid icon) | **Menu**: Client, Ctrl+E; right-click on a return | "Edit request list…" |
| Schedule (calendar icon) | **Menu**: Tools | "Schedule…" |
| Repair the schedule (clock icon) | **Menu**: Tools, beside Schedule | "Repair schedule" |
| Open Status Report (this return) | **Cut**: the return's page shows the same, live | - |
| Open Status (whole practice) | **Menu**: Tools, for printing only; Overview replaces it on screen | "Firm report" |
| Sort & Scan (primary, refresh icon) | **Icon**, beside the search bar; F9 | (sort icon) |
| Stop (while sorting) | **Merge** into the sort icon, which turns into a stop icon | (stop icon) |
| Progress "Smith Family (3 of 40)", "Sorting scan0012.pdf" | Keep as the side panel's last line; file name cut | "Sorting 3 of 40" |
| Side panel section icons | **None**: the four words carry it | Overview, Needs review, Reminders, Clients |
| Search bar | Keep; the magnifier is the only label | (magnifier) |

## 2. Notices and messages

| Element today | Verdict | After (≤5 words) |
|---|---|---|
| After-install banner with its findings list | Keep **only on failure**, one line; the list goes to the error log | "Setup needs attention" |
| Failure notices | Keep, one area, one line each | e.g. "Sort failed" |
| Notice buttons Retry / Look again / Dismiss | **Merge** Look again into Retry; Dismiss becomes × | "Retry", × |
| Result banner after every action | **Cut** (rule 6); toast only when off screen | "Copied", "Saved" |
| "Clients folder set to {root} (written to {settings path})…" | **Cut** (rule 4 and 6) | - |
| Reader warning "Move the app to a shorter folder, for example C:\JPA Tracker…" | Keep as a notice, path cut | "Install folder name too long" |
| Last-pass banner | **Move** to the side panel's foot | "Sorted 6:00 AM" ✓ / "Sort failed" |
| Machine warnings | One-line notice; details to the error log | e.g. "Drive not signed in" |
| Lock notice (time, host, file, "buttons are greyed…") | One line; the greyed-buttons sentence cut (greyed shows it) | "In use on OFFICE-PC" |
| Clear lock button | **Menu**: Tools, enabled only when stale | "Clear stuck lock" |
| Toasts "Pick the request this document belongs to first." etc. | Shorten | "Pick a request first" |
| "Folders the tracker leaves alone" fold, with paths | One notice with a count; the list shows folder names and a two-word reason | "3 folders skipped" |
| "Returns short of room under this root" | One notice; the row shows it too | "Names shortened to fit" |

## 3. First run (setup)

| Element today | Verdict | After (≤5 words) |
|---|---|---|
| "Where do you keep your clients?" + summary sentence | Heading kept, sentence cut | "Choose your clients folder" |
| Path box with "e.g. G:\Shared drives\Clients" | **Cut** (rule 4): Browse fills it; the page shows the folder's name only | (folder name) |
| Browse… / Use this folder | **Merge**: one button picks, a second starts | "Choose folder…", "Start" |
| Firm name / phone + their help lines | Labels kept, help cut | "Firm name", "Firm phone" |
| Setup note (root problems, "{root} is not a folder any more…") | One line, no path | "Folder not found" |

## 4. Household page (was the household card)

| Element today | Verdict | After (≤5 words) |
|---|---|---|
| "Household" label + name | Name is the page heading; label cut (the breadcrumb says it) | (household name) |
| Shared with / Contact / Inbox link, each with a help tooltip | **Move** to Edit household; the page shows one caption | "Contact: John Smith" |
| Shared state line + "Mark as shared" | One caption; the action goes to the menus | "Shared" ✓ / "Not shared" |
| Sharing checklist with full folder paths | **Cut** (rule 4); the Tester Guide carries the steps | - |
| Two-open-years warning | Notice | "Two years open" |
| Folder renamed + "Accept the folder's name" | Notice with one action | "Folder renamed" · "Accept" |
| Returns as buttons + reminder line each | Rows: return name, then a count badge | (name) (count) |
| "{n} documents waiting for a person across this household" | **Cut**: the count badges say it | - |
| Roll forward fold (intro, template, ticks, notes) | **Menu**: Client, once a year; a dialog | "Roll forward to 2026…" |
| Feeds lines ("This drop folder also feeds…") | **Move** to Edit household | - |
| Edit household / Add a return / Mark as shared buttons | **Menu**: Client; right-click | as named |

## 5. Return page (was the requests, reminder, moved, review and filed cards)

One list in groups: **Needs you**, **Waiting on client**, **Received**, and
**Set aside** folded shut. The group heading carries its count.

| Element today | Verdict | After (≤5 words) |
|---|---|---|
| "Document Requests" heading, summary line | **Cut**: the return's name heads the page; group counts replace the summary | - |
| Table column headings (ID, Document, Files, Status, Received, Notes) | **Cut**: each row reads without them | - |
| ID column (A01) | **Cut**: an internal code | - |
| Per-row rule tooltip ("Types… Must contain…") | **Cut**: it lives in the request list editor | - |
| Period | Shown only when it differs from the return's year | e.g. "Dec 2025" |
| Files "1 / 2" | Shown only when partly in | "1 of 2" |
| Status chip + Client/Us/Decide word + sentence | **Merge**: the group says who; the row keeps one status word in its colour; no dot, no sentence | e.g. "Wrong year", "Syncing" |
| Override reason tooltip, notes tooltip | **Cut** from the list; the editor holds them | - |
| Reminder card (status, held list, 4 stages, hint, edited, subject, preview, 3 buttons) | **Move** behind the Waiting group's row action; opens a side sheet | "Draft reminder ›" |
| Reminder stage names ("3 Response Requested; Deadline Approaching") | Shortened in the app; the letter's subject keeps the full name | "Heads up", "Checking in", "Deadline near", "Final notice" |
| Stage hint, "edited by hand - approve it…" | Hint cut; edited state one caption | "Edited by hand" |
| Copy for Outlook / Approve / Open the draft file | Keep Copy and Approve; Open the draft file **cut** (the sheet shows it) | "Copy", "Approve" |
| Moved-by-hand card with "{home} -> {now}" paths | Rows in Needs you, status word only | "Moved by hand" |
| Put it back / Keep it here / Send to review / Mark missing | Put back and Keep here stay in the sheet; Send to review **cut** (same as Unfile) | "Put back", "Keep here" |
| Needs review card: heading, summary, mode toggle | Rows in Needs you; summary cut; the one-at-a-time deck **cut** (the sheet's next arrow does it) | - |
| Buckets with long descriptions (emails and zips, not documents) | Headings only | "Emails and zips", "Not documents" |
| "came from the client's subfolder '{folder}'" | **Cut** (rule 4) | - |
| Row: file name + reason | File name (a name, not a path) and a short reason | e.g. "Fits two requests" |
| Open review copy (twice: list and deck) | One icon in the sheet (›); no label | (open icon) |
| Request picker, "Belongs to…", Suggested / Other requests | Keep; suggestion pre-selected | "Suggested", "Other" |
| File it / Accept the suggestion | **Merge** into one | "File it" |
| Not requested | Keep | "Not requested" |
| File under another return (twice) / File it under {label} | One item in the sheet's overflow | "Another return…" |
| Reasons list (why each suggestion) | One line per suggestion | e.g. "Name and year match" |
| Issuer box (K-1 only) with 30-word help | Label and button only | "Issuer name", "Add issuer" |
| Keyword box, teach spelling, dismiss note | **Fold** under one "More" in the sheet; help cut | "Keyword", "Spelling", "Reason" |
| Skip for now | The sheet's next arrow | (next icon) |
| Filed card: "{id} - {copy names}", Unfile, Mark missing | Rows in Received (document, from, date); actions by right-click | "Unfile", "Mark missing" |

## 6. Safety text

| Element today | Verdict | After (≤5 words) |
|---|---|---|
| Four safeguard cards under the list, ~150 words, two naming folders | **Cut** from the page; **Help > Safeguards** shows four short lines | "No AI reads documents", "Originals never changed", "Nothing is guessed", "Nothing is ever sent" |
| Start-up safety line (PLAN-ui section 6) | **Cut**: the terms say it once, Help keeps it | - |

## 7. Dialogs

| Dialog | Kept | Cut |
|---|---|---|
| Unsaved changes bar | "Unsaved changes", "Keep editing", "Discard" | the long sentence |
| Edit household | Contact, Shared with, Inbox link, Also feeds; Cancel, Save; feed warning "Its members can drop here" | every help line |
| File under another return | Title "Another return", Return, Request, Cancel, File it | - |
| Schedule | "Run automatically" switch, "First run", "How often", caption "Next: 6:00 PM", Cancel, Save | the loading sentence (outline rows instead), "Scan works either way…" |
| New household, step 1 | One heading "New household", Household, Contact, Shared with, Inbox link, warning "Shared members see documents", one Cancel, Continue | the second heading, the intro, every help line, two of three Cancels |
| Step 2 | Title "Return type"; cards show form and who ("1040 · Individual") | the blurb per card, the step note |
| Step 3 | Title "1040 requests", one "Back", Return name, Client, Tax year, Due date, People, the request ticks, "Add a request", "Create return" | the form chip, the duplicate warning, the year note, the 31-word "Ask the client" note, request IDs and rule summaries, the custom rows' extension and keyword columns (they live in the editor) |
| Request list editor | One heading, Client, Inbox link, Due date, Filing deadline, Reminders, Active; the table's Document, Count, Asked, Override, Reason, Short name; one **Advanced** switch for routing, learned keywords, paste and rename; Cancel, Save | the second heading, read-only fields (form, household, year, return, rolled from: the breadcrumb shows them), every column help tooltip, the per-row routing toggles (the one switch replaces them), the paste and rename hints, "left in the old folder…" |

## 8. Pilot layer

| Element today | Verdict | After (≤5 words) |
|---|---|---|
| Terms screen (seven sections) | **Exception proposed**: an agreement must be read whole; shown once | Jason's P20 text |
| Tour: 11 steps x (does, strength, limit, fallback), stage chips, "Step n of N" | One line per step; stage chips **cut** (the count shows progress) | e.g. "Clients drop files here" |
| Tour headings "What it does / Why it's safe / Current limit" | **Cut** | - |
| Tour step that mentions "Prepared" and 'A01 - W-2 - TY2025.pdf' | Reworded without folder or file names | "Copies get tidy names" |

## 9. Where every path went (rule 4)

| Today | After |
|---|---|
| Setup path box and its example path | Folder name only, after Choose folder… |
| "Clients folder set to…" banner with the settings path | Cut |
| Sharing checklist (card and create banner) | Cut; Tester Guide |
| Reader warning naming C:\JPA Tracker | "Install folder name too long" |
| Folders-left-alone list | Folder names, not paths |
| Moved-by-hand "{home} -> {now}" | "Moved by hand" |
| "came from the client's subfolder" | Cut |
| Editor "left in the old folder…: {left}" | Cut; error log |
| API refusals and after-install lines naming a {file} or {location} | Short sentence on screen; the path to the error log |

## 10. Two proposed exceptions and one open question

1. **Pilot terms** stay as written: an agreement cannot be five words.
2. **The reminder letter** stays as written: it is the client's email, shown as
   a preview.
3. **The sort icon's tooltip.** A sort icon is not self-explanatory to a new
   user. Proposed: a two-word tooltip ("Sort now") on this one icon, and none
   anywhere else.

## Consequences for the build (for the SPEC)

- The words are the API's (`tracker/api.py` `_vocab()` and the constants it
  reads), so the rewrite is a Python change and `tests/test_single_source.py`
  follows it. That reaches `tracker/`, which the brief left untouched: it needs
  the engine SPEC rule's sign-off (wording only, no behaviour).
- A new test: every vocab string is five words or fewer, has no path pattern
  (a drive letter, a backslash, `/`-joined folders), except the listed
  exceptions.
- `STANDING_RULES` keep their full wording in the code and docs; the app shows
  the four short lines, a change to the single-source test (P64).
