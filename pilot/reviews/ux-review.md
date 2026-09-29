# User-experience review - Pilot 0.1 - 2026-09-29

Two independent reviewers (Opus, built nothing), each on half of the tester's life with the product: **U1a** the first hour, from the installer to the first filed document, as a partner at a small firm (findings U-1 upward); **U1b** the working week - every morning, draft day, the client's side, and getting help - as staff (U-101 upward). Both drove the real application (real `app/main.js`, real engine, real page) in headless Chromium on synthetic data and looked at the screenshots; what could not be seen on Linux was read from code and is labelled so. The orchestrating session merged the halves without changing a finding and verified every blocking finding and three others per half.

**Findings:** 3 blocking (U-1, U-2, U-101), 35 should-fix (U-3, U-4, U-5, U-6, U-7, U-8, U-9, U-10, U-11, U-12, U-13, U-14, U-15, U-102, U-103, U-104, U-105, U-106, U-107, U-108, U-109, U-110, U-111, U-112, U-113, U-114, U-115, U-116, U-117, U-118, U-119, U-120, U-121, U-122, U-123), 15 nit (U-16, U-17, U-18, U-19, U-20, U-21, U-22, U-23, U-24, U-124, U-125, U-126, U-127, U-128, U-129).

**Labels.** *blocking*: fix before 0.1 reaches an outside firm - it could show a client's document to the wrong party, alter an original, run code from a dropped file, send anything, lose the record, stop a tester finishing Tester Guide sections 3-6, or make the way to report a problem carry client data. *should-fix*: the next build round. *nit*: minor. Items that are by design are answered in the table near the end, with the decision that covers them. Every finding cites `path:line`, says how it was established (**Evidence**), what it means for a firm or who hits it and when, a **Fix** concrete enough to specify, and whether it reopens a logged **Decision**. Nothing here was fixed by the reviewers; fixes are separate jobs.

## Scope and method

### U1a - the first hour

Read: briefs 00 and 02, `ux-counts.md`, the harness README, the Tester Guide, SPEC §7, §8, §10, §13, DECISIONS, `pilot/installer/setup.iss`, the renderer, `app/main.js` and the engine lines cited.

Ran: the harness (real `app/main.js`, engine and page, headless Chromium) on r1, blanked to a new install (`settings.json` `{}`, store and data home removed). I pointed it at `/tmp/u1a-own`, a copy of a firm's folders as Guide §2 describes (`Smith, John 2025`, `Acme LLC`, `Doe, Jane 2024`, a loose `.docx`), made the first household in the wizard, dropped the suite's synthetic pile into its inbox as the hand step, and ran Sort & Scan. Scripts: `$S/u1a/run1-5.js`, numbers in `run*.json`, screenshots in `$S/reviews/shots-u1a/run1-5`, each one cited here looked at. r1 reset and `/tmp/u1a-own` removed afterwards.

Seen in the browser: stages b (also a second launch), c, d (all 11 steps), e, f, g, h (recorded openPath), i, j (`openAttempts()`), k (six window sizes) and l.

Read from code or inferred for Windows: stage a, what "Quit." does, Task Scheduler, Explorer, and the packaged window (tested at 1384x861).

Linux differences, not reported: no Task Scheduler; `scan 0001.pdf` parks as "a scan needs OCR", which a Windows tester never sees; fallback fonts.

Correction to the flow map: a 1040 offers 26 rows, 5 ticked (seen). 41 is the ticked total across all six forms (`FORM_TEMPLATES`: 107 rows, 74 distinct documents, so "about 74 document kinds" is true).

### U1b - the working week

Read the briefs, `ux-counts.md`, the harness README, Tester Guide §§4-10, workflow.md "Roles" and "Six things", runbook §§2-5 headings, SPEC 12.6 and P5/P12/P21/P26. Drove the real app (harness, headless Chromium, 1400x900 and 1100x700) on root **r4** (awkward pile) and on my own clean root **r4b** (`/tmp/r4b`, built with `build_roots.py`) for a return with something outstanding. Screenshots are in `reviews/shots-u1b/` (numbers restart per launch, so each is named by its full file name).

- **Seen in the browser:** the pass, Needs Review (list and deck), File it, Not requested, Unfile, Put it back (one working copy moved with `mv` to act out a drag), Unlearn, Paste rows, the lock notice (a child process held `locking.acquire_lock`, then was killed), Clear lock, sharing and the Inbox link, Mark as shared, the hand-over dialog (second return added with API `create`, row changed by a shell `dismiss`), Schedule Off/On, Repair, the reminder card, toggle, Copy (clipboard read back), Approve, Open the draft file.
- **Rendered in memory:** the practice status page (`write_status_page` with the writer replaced) and the Status Report (`view.render_page`), each shown with `page.setContent`; the plain-text draft (`write_draft` captured); the client README (`scaffold._readme_text`).
- **Read from code:** rollover, uninstall, stale locks from another computer, Mark X missing, rename, the error log.
- **Deny list:** no document, record, log, page or draft file was opened. `ls` for names only. My writes to the roots were engine calls (pass, create, dismiss, the lock) and the one `mv` inside `Prepared`.
- **Linux (labelled, not reported):** no Task Scheduler ("This computer has no Task Scheduler…"), so the schedule never runs here; no OCR (`scan 0001.pdf` parks); `openPath` is recorded, not performed; `.msg` worked here.

## Findings

### Blocking

#### U-1 **blocking** `app/renderer/style.css:58-66` - `.main` never scrolls. Its `.card` children (`app/renderer/style.css:140-146`, `overflow: hidden`, so their automatic minimum height is 0) shrink instead, so after the first scan the Needs review list, the filed list, the request table and the household card are cut to slivers at every window size.
- **Evidence:** seen in the browser. `run2/23-after-pass-1400x900.png`: the Needs review card shows 40 px of 2120, Filed 3 of 47, requests 16 of 779 and household 10 of 433 (`run2.json` squeeze1400). `run2/25-after-pass-1100x700.png`: every card is 2 px. `run3/01-list-1920x1017.png`, maximised on a 1080p screen: one review item of eight, no request rows, and the Filed card is an invisible line. Laptop sizes are the same or worse, "One at a time" does not help (87 of 417 px at 1920x1017), and the wheel scrolls nothing (`run3.json`, `afterWheelResults`); only Tab drags hidden rows into view. The footer (`app/renderer/index.html:345`) is not a card, so it never shrinks and takes 269 of 838 px at 1400x900 and 362 of 638 px at 1100x700. `run2/24-after-pass-1400x900-expanded.png` shows what should be visible, not what the user sees. The original repository's `app/renderer/style.css` has the same rule.
- **Who hits it and when:** every tester at the first scan, Guide §6 step 4. They cannot read Needs Review or see a filed document, and may believe only one document is waiting.
- **Fix:** let `.main` scroll: `.main > * { flex-shrink: 0 }` (or `min-height: auto` on the cards). Keep the request table's own `max-height` scroll. Add a harness check at 1100x700 and 1400x900 that every visible card's height equals its content height and that `.main` scrolls. Consider folding the rules footer.
- **Decision:** reopens P10 (edits an existing renderer file), or the fix lands in the original repository and is merged in as `upstream` (P17).

#### U-2 **blocking** `app/renderer/index.html:143-179` - On a new install the setup card is squeezed by the same rule, and its only button, "Use this folder" (`app/renderer/index.html:176`), is clipped out of sight at the default window size.
- **Evidence:** seen in the browser, `run2/01-fresh-1400x900.png`. The card shows 264 of 366 px, the button sits at 525-565 below the card's bottom edge at 517, and a hit test at its centre does not reach it (`run2.json` geom1400). The same happens at 1384x861, the Electron content area, and at 1536x790, a maximised laptop at 125% scaling (`run5.json`). At 1100x700 even the folder box is hidden (`run2/03-fresh-1100x700.png`). Only a maximised window at 100% scaling shows the button. Pressing Enter in the folder box saves (`app/renderer/app.js:3931`), but nothing on screen or in the Guide says so.
- **Who hits it and when:** first launch, Guide §4 step 3: after Browse… fills the box there is nothing to click, and the tester stops.
- **Fix:** the U-1 fix. Also move "Use this folder" next to the folder box so it is the first thing after Browse….
- **Decision:** as U-1.

#### U-101 **blocking** `tracker/api.py:388-389` - The only diagnostic the app points to, `tracker-errors.log`, names client folders and files, and nothing tells a tester not to send it.
- **Evidence:** read from code. FAILED says "the details are in tracker-errors.log beside the tracker's database". `tracker/settings.py:197-202` says the log "can name a client's folder". Its warnings carry household names and file names (`tracker/scaffold.py:600-605`, `tracker/view.py:776`). Guide §10 (`pilot/Tester Guide.md:80-82`) forbids client *documents* and asks for screenshots with names covered, but never mentions the log. Every screen shows client names (select, review rows, letter).
- **Who hits it and when:** asking for help, the first time a tester sees a FAILED notice. Attaching "the details" is the natural reply to that sentence.
- **Fix:** Guide §10: "Do not send tracker-errors.log or any file from the data folder; copy the notice's first line (it names the error class and code only)". Also make FAILED say "tell J Park the words in brackets". Optionally (reopens P5) add a "Copy problem report" button. It would copy the version, class, code, command and time, and no names.
- **Decision:** reopens P5 (the button only; the Guide change needs none).

### Should-fix

#### U-3 **should-fix** `app/renderer/pilot-content.js:148-158` - Tour step 6, "Originals, untouched", says it "lists the originals moved from the inbox" and that its card "appears after a scan moves something". The card it points at is "Moved by hand" (`tracker/api.py:723-725`): working copies a person moved. It never appears after a scan.
- **Evidence:** seen in the browser. `run1/09-tour-step-06.png` shows the promise. After the first pass the moved card is still hidden (`run2.json` afterPass.movedHidden). The app has no list of moved originals anywhere.
- **Who hits it and when:** first scan, looking for the promised originals list (Guide §6 step 4 makes the same promise).
- **Fix:** rewrite step 6 to say the originals are in the client's year folder, reached with Open Client Folder, and point it at `btn-client-folder`. Drop "can be undone" or say it is per document (Unfile).
- **Decision:** reopens P22.

#### U-4 **should-fix** `app/renderer/pilot-content.js:184-194` - Tour step 9 says the button "opens the status page: every requested document, received or missing, with validation notes". It points at Open Status, which opens the practice page (`tracker/runner.py:2262-2272`): Engagements, Waiting for a person, Problems, Folders left alone, and no rows per request. The page the step describes is "Open Status Report".
- **Evidence:** seen in the browser (`run1/12-tour-step-09.png`), and the page's contents read from the generator's code.
- **Who hits it and when:** first scan, Guide §6 step 4: the tester opens the practice summary and finds no list of their documents.
- **Fix:** point step 9 at `btn-view` with its label's words, or name both buttons in the step. Make the Guide say "Open Status Report".
- **Decision:** reopens P22.

#### U-5 **should-fix** `app/renderer/app.js:3842-3866` - Before the first household, five toolbar buttons do nothing when pressed (Open Inbox, Open Client Folder, Open Status Report, Open Status, Edit Request List). Sort & Scan answers "Pick an engagement first (--engagement <folder>)" (`tracker/api.py:1050`), a command-line flag. The tour points at three of these buttons, and the fallbacks written for exactly this state can never show (counts §3, 5 of 9).
- **Evidence:** seen in the browser. `run2.json` noRoot: no notice, banner or dialog for four of the buttons, and `openAttempts()` is empty for Inbox and Status before a root. The notice: `run1/16-scan-with-no-root.png`, still there after the folder is set (`run1/18`).
- **Who hits it and when:** first launch, pressing what the tour just showed; silence or a code, against decision 193.
- **Fix:** grey these buttons with a tooltip until a return is selected, and word the no-return refusal for a person ("Create a household first: New household"). Show the tour fallback when no return is selected, not only when the button is hidden.
- **Decision:** reopens P24.

#### U-6 **should-fix** `app/renderer/app.js:3865-3866` - Before the first pass, Open Status and Open Status Report are refused by main.js, and the page throws the answer away. The refusal is also the wrong sentence: "That is no longer the folder or file the tracker reported" (`app/main.js:93`, `tracker/api.py:1151`), for a file that has never existed.
- **Evidence:** seen in the browser. `run2.json` openBefore shows both refused, and `afterOpenBefore` shows no new notice (`run2/21-after-open-status-before-pass.png`). After the pass both open (`openAfter`, reply "").
- **Who hits it and when:** first household, checking Status before the first scan; nothing happens.
- **Fix:** show a non-empty open reply as a notice. Give main.js a "not made yet: it appears after the first Sort & Scan" sentence when the lstat finds nothing.
- **Decision:** none.

#### U-7 **should-fix** `tracker/api.py:551` - New household opens before a clients folder is set. The tester fills three screens, and Create then refuses with "Tell the app where your clients live first (Settings, or `python -m tracker.settings <folder>`)". There is no Settings in the app, and the fallback is a Python command.
- **Evidence:** seen in the browser, `run2/11-noroot-create-refused.png`. Closing raises the unsaved-changes bar (`run2/12-noroot-unsaved-bar.png`), so the typing is lost or kept in a dialog that cannot succeed.
- **Who hits it and when:** first launch, for a tester who takes Guide §5 ("Press New household") before §4 step 3 is visibly done, which U-2 makes likely.
- **Fix:** grey New household until a root is set, or refuse when the dialog opens with "Choose your clients folder first (the card above)". Drop the command from the sentence the app shows.
- **Decision:** none.

#### U-8 **should-fix** `tracker/settings.py:83-87` - Saving the clients folder turns the schedule on by itself: `schedule_enabled` defaults to true, and a new computer claims the folder (`tracker/scheduling.py:744-745`). The one sentence that says so is replaced about 0.2 s later.
- **Evidence:** seen in the browser for the replacement. The banner log shows the save banner with its schedule sentence at 267 ms, overwritten by "No households under … yet" at 493 ms (`run1.json` bannerLog). The Windows sentence ("This computer (…) now runs the schedule for this clients folder: every day from 07:00, every 120 minutes", `tracker/scheduling.py:558-559`) is Windows-only, inferred.
- **Who hits it and when:** first launch. From then on test inboxes are emptied every two hours and reminders drafted on Saturdays, though the tester pressed nothing. Guide §7 (lines 52-62) reads as opt-in, and the wrap-up does not say it is already on.
- **Fix:** have the empty-root banner keep the schedule sentence (append, do not replace; `app/renderer/app.js:2276-2282`). Say in Guide §7, and in tour step 2's limit, that the schedule is on from the moment the folder is chosen, and how to turn it off. Or ship the pilot with the default off.
- **Decision:** reopens P21 if the default changes; none for the wording.

#### U-9 **should-fix** `tracker/layout.py:77-79` - When the app is pointed at a copy of the firm's own client folders, as the Guide and terms direct, it leaves every one of them alone. It then creates `Clients` and `J Park & Associates` inside that folder, so the tester's private working tree carries another firm's name.
- **Evidence:** seen in the browser. `run1/19-misfits-open.png`: all three folders read "is not one of the two trees the tracker reads (Clients and J Park & Associates); left alone", behind a collapsed line. `run2.json` ownAfterCreate: `Clients` and `J Park & Associates` sit beside the tester's folders. Terms (`app/renderer/pilot-content.js:29`) and Guide lines 20 and 32 say to point it at client folders.
- **Who hits it and when:** first launch, Guide §4 step 3: no clients appear, and the tester's working files land in a folder named after the pilot's author (tour step 2: "Your working files stay private").
- **Fix:** tell testers in Guide §2 and §4, and in the setup card's note, to choose a new empty folder, because the program builds its own two folders and never reads existing client folders. Name the private tree from the firm name typed at setup, or with a neutral name.
- **Decision:** reopens P7 for the engine name. None for the wording.

#### U-10 **should-fix** `pilot/README.md:38-47` - The app works only with Google Drive syncing a Shared Drive ("OneDrive is not supported"), but no text a tester sees says so.
- **Evidence:** read from code. I searched `pilot/Tester Guide.md`, `app/renderer/pilot-content.js` (terms and tour) and `app/renderer/index.html`: none mentions Drive or OneDrive. The only hints are the folder box placeholder ("e.g. G:\Shared drives\Clients") and, after the household is created, the checklist's "The tracker cannot see Drive's sharing" (seen, `run2/18-created-1400x900.png`).
- **Who hits it and when:** first launch: many Windows 11 PCs keep Desktop and Documents in OneDrive, so a copy made there is unsupported, untold.
- **Fix:** one line in Guide §2 and in the terms' files section: Google Drive for desktop with a Shared Drive, or a local folder for the test; not OneDrive.
- **Decision:** none.

#### U-11 **should-fix** `app/renderer/index.html:511` - The wizard's first step asks for the "Inbox link" before the inbox exists. After Create, the sharing checklist arrives in a green success banner. "Mark as shared" then refuses with the fragment "paste the inbox's link into the household first" (`tracker/api.py:682`), which does not name Edit household.
- **Evidence:** seen in the browser. `run2/13-wizard-1-household.png`, `18-created-1400x900.png` (a seven-line to-do in success green, with Drive grants the app cannot see), `20-mark-shared-no-link.png`. Guide §5 (lines 34-38) mentions neither the household step nor the sharing.
- **Who hits it and when:** first household: with no client to share with, the tester cannot tell whether the checklist blocks the test.
- **Fix:** drop Inbox link from the first step or mark it "after Create". Show the checklist as a warning-coloured to-do. Word the refusal "Paste the inbox's share link under Edit household first." Add to Guide §5: "For the test, you can skip the sharing steps."
- **Decision:** none.

#### U-12 **should-fix** `app/renderer/pilot-style.css:44-64` - The terms body scrolls inside the card with no cue. The last section, the only place in the app that says "Please do not send client documents", is below the fold, and the tester can tick and accept without seeing it. The tour's wrap-up then gives the email address without the warning (`app/renderer/pilot-content.js:208-228`).
- **Evidence:** seen in the browser. `run1/01-first-paint.png`: "Questions or problems" is cut, with 716 px of content in 599 at 1400x900. `run1/03-terms-1100x700.png`: 716 in 429, and three of the seven sections are hidden. `run1/14-tour-step-11.png` shows the bare email line.
- **Who hits it and when:** first launch, and when asking for help; only Guide §10 still carries the warning.
- **Fix:** show a fade or "scroll for more" cue, or keep Accept disabled until the body has been scrolled to the end. Add "never attach client documents" to the wrap-up's email line.
- **Decision:** reopens P22 for the wrap-up line.

#### U-13 **should-fix** `tracker/api.py:2574` - The engine reports the return's `Prepared` folder as openable, but no button opens it. Guide §6 step 4 ("The Prepared folder") and tour step 7 send the tester there, and Open Client Folder opens the client tree, not the private tree Prepared sits in.
- **Evidence:** read from code. I searched `app/renderer/app.js` for `paths.prepared`: no match. Seen: the filed card is the only place in the app that names a working copy, and it is a 3 px strip (U-1).
- **Who hits it and when:** first scan. The tester must find `<clients folder>\J Park & Associates\<household>\<year>\<return>\Prepared` in Explorer by themselves.
- **Fix:** add "Open Prepared folder" beside Open Client Folder (the path is already in the openable map, `tracker/api.py:1148`), or have the Guide give the path.
- **Decision:** reopens P10.

#### U-14 **should-fix** `pilot/Tester Guide.md:40-50` - The Guide names buttons the screen does not have: "Inbox" is "Open Inbox", "Scan" is "Sort & Scan" (`app/renderer/app.js:157`), and "Status" could be either "Open Status" or "Open Status Report". Counts §5: 8 of the Guide's 19 terms match no label exactly. After Open Inbox the app gives no next step and never notices that files have arrived.
- **Evidence:** seen in the browser (the toolbar in every screenshot; openPath recorded for `…/Clients/Smith Family/Drop files here`). Counts §5.
- **Who hits it and when:** first household and first scan, where the Guide is the only instruction.
- **Fix:** use the on-screen labels word for word in Guide §6 and §7. Add to §6 step 2: "Drag the files into that folder, then come back to the program and press Sort & Scan."
- **Decision:** none.

#### U-15 **should-fix** `pilot/installer/setup.iss:36` - Guide §3 covers only the SmartScreen "Run anyway" path, and nothing tells the tester how to start the program again.
- **Evidence:** Windows-only, inferred. Windows 11 Smart App Control (on for some new PCs) blocks unsigned programs with no "Run anyway"; the desktop icon is unticked, and the first launch comes from the installer.
- **Who hits it and when:** install, and the first time they reopen the program.
- **Fix:** add to Guide §3: "If Windows says Smart App Control blocked it, email us". Add to §4: "Next time, open it from the Start menu: Tax Document Tracker Pilot".
- **Decision:** none. P4 stands.

#### U-102 **should-fix** `app/renderer/app.js:926-927` - The picker starts on the top suggestion even when the reason says the evidence is wrong, so one click files another person's W-2 with a green banner.
- **Evidence:** seen. `Jane Doe W-2 2025.pdf` ("the page names none of this return's people") and `old W-2.pdf` ("possible wrong period") both start on A01. Clicking **File it** on Jane Doe's gave "Jane Doe W-2 2025.pdf filed as A01 - W-2 - TY2025 (4).pdf." in green (`02-a-filed-jane-banner.png`). There was no warning, because it was "the suggestion" (`app/renderer/app.js:1031-1036`).
- **Who hits it and when:** the morning queue. The primary blue button beside a pre-filled picker reads as "accept".
- **Fix:** when the shortlist carries a name-absent, other-return or wrong-period sentence, start the picker on "Belongs to…". Then say the filing in a warn banner ("filed although the page names none of this return's people").
- **Decision:** reopens decision 84 (the picker starts on the suggestion), for these reasons only.

#### U-103 **should-fix** `tracker/rollover.py:351-354` - A return made in the pilot season with the blank "Due date (optional)" gets 2026-04-10. Its first letter is Stage 4, "URGENT … final notice", naming two dates already past.
- **Evidence:** reproduced by running the engine. `create` with no `due` returned due 2026-04-10 and filing deadline 2026-04-15 (`tracker/api.py:3336`, `tracker/templates.py:769-800`). After a pass the card's letter read "URGENT - … final notice, 2 document(s) still needed … Our firm's deadline to receive everything is April 10, 2026 … late-filing penalties". The default year is last year (`tracker/templates.py:732-742`) and `stage_for` returns 4 for a past date (`tracker/reminder.py:792-813`). The wizard never shows the date it will use (`app/renderer/index.html:563-564`).
- **Who hits it and when:** first household (Sept-Dec 2026), then the first reminder every tester reads.
- **Fix:** have the wizard show the computed Due Date and Filing Deadline before Create. When the Due Date is already past, ask for one (or leave it blank, which gives stage 1).
- **Decision:** reopens decision 117 (default dates) for creation in a past season.

#### U-104 **should-fix** `tracker/reminder.py:513-517` - The stage toggle rewrites the letter into statements that are false for the date: Stage 4, 16 days before the Due Date, says "We have now reached or passed our firm's cutoff".
- **Evidence:** seen on r4b, with the Due Date 2026-10-15 and today 2026-09-29 (`01-f-stage4-expanded.png`). Approve then recorded "approved 2026-09-29 at stage 4".
- **Who hits it and when:** draft day, a person nudging a slow client up a rung.
- **Fix:** give stages 3-4 wording that is true before the date ("our cutoff is October 15"). Or show a warn line when the pressed stage is above the date's.
- **Decision:** reopens decision 118 (the toggle's words only; who is asked is unchanged).

#### U-105 **should-fix** `app/renderer/app.js:637-652` - The card that Copy for Outlook copies from never shows the draft's warning "5 file(s) the client already sent are still in 00 - Needs Review. Identify them before sending".
- **Evidence:** rendered the file in memory. The footer is `tracker/reminder.py:353-354` and `2079-2082`. `state.reminder_card` has no such field, and the card text on r4b shows none. Decision 118 keeps staff lines off the clipboard, not off the screen.
- **Who hits it and when:** draft day. The card is the path the app promotes.
- **Fix:** show the needs-attention and Needs-Review lines on the card, under the letter and outside the copied text, with the count linking to the review card.
- **Decision:** none.

#### U-106 **should-fix** `tracker/reminder.py:268` - The letter's count and its list disagree after a request is added: "Of the 6 items we asked for, 4 are in" lists one item. The new row is not asked until the next pass.
- **Evidence:** seen on r4b after pasting E01 and saving (`01-f-reminder-card-expanded.png`). E01 had an empty status in `state`, and the save banner warned only that E01 "can never be filed automatically".
- **Who hits it and when:** draft day, right after editing the list.
- **Fix:** re-scan on a save that adds rows (unlearn already re-scans), or have the card say "E01 is not checked yet; press Sort & Scan before sending".
- **Decision:** none.

#### U-107 **should-fix** `tracker/scaffold.py:772` - The client README says "Questions? Contact John A. Smith." That is the client's own name, because the household Contact is the letters' greeting name.
- **Evidence:** rendered in memory for r4 and r4b. `CONTACT_HELP` (`tracker/api.py:577`) defines Contact as "the greeting name in every return's letter". The README reuses it as the firm's contact.
- **Who hits it and when:** the client, the first time they open their folder after the first pass.
- **Fix:** name the firm on the README (the settings' firm and phone), never the household contact.
- **Decision:** none.

#### U-108 **should-fix** `tracker/reminder.py:243-246` - The client-facing texts use the firm's internal labels. The subject is "Smith Family 2025 1040 - John A. Smith: 1 document(s) still needed", list lines read "A02 - … (TY2025)", and the README repeats identical "A01 - W-2 … Received 29 Sep 2026" lines, one per W-2.
- **Evidence:** seen (card, clipboard) and rendered (README, draft).
- **Who hits it and when:** the client, every letter and every README.
- **Fix:** give the letter and README a client wording: "your 2025 tax return", the document name without the identifier or TY code, and an issuer or person where the index knows it.
- **Decision:** none.

#### U-109 **should-fix** `app/renderer/app.js:960-961` - Every review row and every deck card shows a stray "0" when the household has one return.
- **Evidence:** seen (`04-a-after-pass-expanded.png`, `01-a-deck-expanded.png`). `fedReturns().length && el(...)` yields `0`, and `el()` appends it as text (`app/renderer/app.js:55-58`). The same happens at `app/renderer/app.js:1328-1329`. It disappeared once the household had a second return.
- **Who hits it and when:** first scan, every tester.
- **Fix:** `fedReturns().length > 0 && …` at both sites, plus a test that no review row has a bare numeric text node.
- **Decision:** none.

#### U-110 **should-fix** `app/renderer/app.js:1098` - The hand-over dialog names the document by its raw record path ("../../../../Clients/Smith Family/2025/old W-2.pdf"). After a refusal, retrying says "Pick the request this document belongs to first." with a request picked.
- **Evidence:** seen (`02-j-handover-dialog.png`, `04-j-handover-second-click-toast.png`). `ho-name` gets the handle. `finally { handingOver = null }` (`app/renderer/app.js:1139`) runs on failure too, while the dialog stays open, so the next click fails the `!handingOver` check. The refusal went to `#notices` behind the overlay, and the card was not redrawn, because `failed()` was called rather than `refused()`.
- **Who hits it and when:** the morning, a household that feeds another return.
- **Fix:** show `original_name`. Clear `handingOver` only on success or close. Say the refusal inside the dialog (an `#ho-error` like `#sc-error`) and redraw the card.
- **Decision:** none.

#### U-111 **should-fix** `app/renderer/app.js:1934-1954` - A refusal from inside a dialog lands behind the overlay, and the old error then sits above the success banner.
- **Evidence:** seen. An Inbox link without https left the dialog open and unchanged, and the notice was covered by the dialog (`04-j-refusal-behind-household-dialog.png`; `elementFromPoint` returned `hh-edit-title`). After fixing and saving, the red "not a web address" stayed above a green "Household: link" (`05-d-household-saved.png`). Same route for `loadHandOverRequests` (`app/renderer/app.js:1117`). Decision 193 says no reply goes quiet.
- **Who hits it and when:** first household (sharing step), the morning (hand-over).
- **Fix:** refusals inside a dialog go to the dialog's own error line (the pattern `saveSchedule` uses, `app/renderer/app.js:2467`). A success dismisses notices about the same field.
- **Decision:** none.

#### U-112 **should-fix** `app/renderer/app.js:1283-1288` - A parked member of a zip or email does not say which file it came from, so staff cannot find it or ask the client about it.
- **Evidence:** seen. `escape.txt` (from `documents.zip`, member `../../escape.txt`) and `inner.zip` (from `nested.zip`) show only their own names. The client's folder holds only the zips. `state.index[].container` carries the source, but `cameFrom` reads only `subfolder`. The Status Report says `../_Opened/documents/escape.txt`. The bare `helper.exe` became "Duplicate of setup.exe", and the two symlinks stayed in the inbox, named nowhere.
- **Who hits it and when:** the morning, any client who sends a zip or a forwarded email.
- **Fix:** add "inside documents.zip" (the container's own name) to the row, the deck card and the status pages. Say a Duplicate of a parked program in the Not-documents bucket.
- **Decision:** none.

#### U-113 **should-fix** `tracker/reasons.py:259-260` - Reason sentences are engine fragments, and the app links to no explanation.
- **Evidence:** seen. "looks like A01 (expected period not found (pattern: (?i)\b2025\b); possible wrong period)". "matched no request", with no next step. "a scan needs OCR". "…names none of this return's people; names none of this return's people" (doubled). History chains such as "unfiled by a person on …; was: assigned by a person …; was: …" on the status page. The explanations live in runbook §§4-5, which testers never get.
- **Who hits it and when:** the morning, every parked row.
- **Fix:** give each Reason a staff sentence that ends in an action ("ask the client which year this is", "file it by hand or mark Not requested"). Keep the pattern and code behind a "details" fold.
- **Decision:** none.

#### U-114 **should-fix** `app/renderer/app.js:3842-3869` - No button opens Prepared, 00 - Needs Review or the originals' year folder, although the API reports `prepared` and `originals` and `PATH_KINDS` allows them (`tracker/api.py:1146-1148`).
- **Evidence:** read from code (every `window.tracker.open` call). `state.paths` holds both. Guide §6 sends the tester to "The Prepared folder", which sits under the private tree "J Park & Associates" (`tracker/layout.py:79`), a name the Guide never gives.
- **Who hits it and when:** first scan (Guide §6.4).
- **Fix:** add "Open Prepared" and "Open Originals" beside Open Client Folder.
- **Decision:** none.

#### U-115 **should-fix** `app/renderer/app.js:3865-3866` - Open Status Report (and Open Status) before a return's first pass does nothing visible. What the shell refuses with is wrong.
- **Evidence:** seen. On the never-scanned return, main.js answered "That is no longer the folder or file the tracker reported; nothing was opened." (`tracker/api.py:1151`). The page discarded it: no notice, no banner.
- **Who hits it and when:** first household, before the first Sort & Scan.
- **Fix:** grey both buttons while `view.state` is "unknown" or no status page exists, with a title that says "written by the first Sort & Scan". Or say the reply in a notice.
- **Decision:** none.

#### U-116 **should-fix** `tracker/view.py:617-627` - As a morning page, the Status Report leads with machine facts, and its Status column is off-screen.
- **Evidence:** rendered (`e-status-report-top.png`). The Summary shows "Record SHA-256", two timestamps and row counts. Requests has 18 columns with Status 15th, past 1400 px, after the regex Date Pattern. The index has 17 columns including SHA-256. Headers sort by mouse only (`tracker/view.py:310-322`; `tabIndex -1`, no `aria-sort`).
- **Who hits it and when:** the morning, the lead opening one client.
- **Fix:** start with Document, Status, Received and Notes, plus the Needs Review count. Fold the routing columns and the machine summary. Make headers buttons with `aria-sort`.
- **Decision:** none.

#### U-117 **should-fix** `tracker/runner.py:2427` - The practice status page, which runbook §2 makes the first screen of the morning, does not say what is outstanding. It hides when the other returns last ran.
- **Evidence:** rendered (`e-status-page-top.png`). Returns get counts only ("Outstanding 0"). Every return the pass did not run reads "not this pass" (`tracker/runner.py:2274`), so after one household's Sort & Scan the rest of the practice shows no date. There is no legend for "Waiting for a person / Still syncing / Problem or skipped / Drafted / Candidates", no link to each Status Report, and the h1 is the product name.
- **Who hits it and when:** the morning, the partner's ten-second look.
- **Fix:** Last pass shows the record's last pass date, and "this pass" is marked beside it. Add a one-line legend, the outstanding request names (or a link to each Status Report) and the firm's name.
- **Decision:** none.

#### U-118 **should-fix** `app/renderer/app.js:2229-2233` - Nothing on screen refreshes by itself, and a restart forgets the return you were on.
- **Evidence:** seen and read. After Jane's return was added, the next launch opened on it (empty) instead of John's queue (`01-j-start-selected-return.png`). The only timer is the lock watch (`app/renderer/app.js:2059`), with no focus or visibility listener. Selection is not saved (`tracker/settings.py:65-80`).
- **Who hits it and when:** the morning. An app left open overnight shows last night's queue and banner.
- **Fix:** re-read `list` and `state` on window focus when the last pass is newer than what is drawn. Remember the selected return per machine (localStorage, as review-mode is).
- **Decision:** none.

#### U-119 **should-fix** `tracker/api.py:4720` - The Schedule dialog reads "First run at 07:00 AM · Every 2 hours · Next run: today at 01:00". The runs go on around the clock, the clock formats are mixed, and the Guide makes it sound opt-in.
- **Evidence:** seen (`01-g-schedule-dialog.png`; clock 00:25). `next_run` is correct for a day-long repeating series (`tracker/scheduling.py:502-527`). Repair's confirm says "Register the daily job … (on saturdays)" (`tracker/api.py:4701-4703`; lowercase, and "daily" against every 2 hours). Guide §7 says it "can run a scan for you", but setting the root claims and registers it on Windows (`tracker/scheduling.py:718-735`). Windows-only, inferred.
- **Who hits it and when:** install and first launch. Files leave "Drop files here" at 01:00 without anyone pressing anything.
- **Fix:** relabel as "Starts at / repeats every 2 hours, day and night". Show "1:00 AM" in the same 12-hour format as the input, and capitalise Saturday. In Guide §7, say it is on from the moment the clients folder is chosen.
- **Decision:** none.

#### U-120 **should-fix** `app/renderer/pilot-content.js:65` - Help is out of reach after the first launch. The email is plain text in the terms (shown once) and on tour step 11 only, there is no Help or About, and nothing opens the data folder or says what a report should include.
- **Evidence:** seen and read. `PATH_KINDS` has no log or data-home kind. The badge says "0.1", and `app/package.json` says 1.1.0.
- **Who hits it and when:** asking for help.
- **Fix:** add a Help line in the footer: the contact as a copyable (or mailto) link, the version, and "what to send" (U-101). Weigh P5: a button that composes a report with no names makes reports both safer and more useful. It is worth reopening and remains Jason's call.
- **Decision:** reopens P5.

#### U-121 **should-fix** `pilot/Tester Guide.md:40-62` - Seven Guide §§4-10 instructions do not match the app (see the table below).
- **Evidence:** seen, and `ux-counts.md` §5.
- **Who hits it and when:** first launch through the schedule.
- **Fix:** use the app's words in the Guide (or rename the buttons). Add where Prepared lives, that the letter shows any day, and that the schedule starts on.
- **Decision:** none.

| Guide | Guide says | App says |
|---|---|---|
| §4.3 | choose "the copy" of client folders | a copied firm tree is listed under "Folders the tracker leaves alone". Households must be made with **New household**, and the private tree is "J Park & Associates" for every firm |
| §6.1 | **Inbox** | **Open Inbox**, which opens "Drop files here" |
| §6.3, §7 | **Scan** | **Sort & Scan** (`app/renderer/app.js:157`) |
| §6.4 | **The moved originals** | no control. **Open Client Folder**, then the year folder |
| §6.4 | **The Prepared folder** | no control (U-114) |
| §6.4 | **Status**: "what is in and outstanding" | **Open Status** gives practice counts. What is in per request is **Open Status Report** |
| §6.4 | reminder "after the weekly draft day" | the card shows, copies and approves a letter any day (`01-f-reminder-card-expanded.png`) |

#### U-122 **should-fix** `tracker/filer.py:351` - Working copies of two people's W-2s are "A01 - W-2 - TY2025.pdf", "(2)" and "(3)". A preparer in Explorer cannot tell whose is whose without opening each.
- **Evidence:** `ls` of Prepared. The app's Filed list pairs original and copy names, but Explorer does not.
- **Who hits it and when:** the working week, preparing the return.
- **Fix:** add the confirmed person's name (and the issuer where it is known) to the short name, within decision 131's room rule.
- **Decision:** reopens decision 168.

#### U-123 **should-fix** `app/main.js:368-372` - Legibility: there is no zoom, controls are 11.5-13.5 px, states are shown by colour alone, and consequential help is hover-only.
- **Evidence:** seen and read. With the packaged menu removed, Ctrl+/- does nothing. `.btn-small` is 12.5 px and pilot text 11-12 px. `.banner.ok/.warn/.err` and `.refused` differ only by colour (`app/renderer/style.css:110-111`, `132-133`, `908`). The keyword box's consequence is a `title` only (`app/renderer/app.js:707`), as are rule details (`app/renderer/app.js:320`). The tour card is `role=dialog` without `aria-modal` (`app/renderer/tour.js:226-228`). There is no dark mode. The focus ring is visible (good).
- **Who hits it and when:** every day, and staff with reading glasses.
- **Fix:** keep zoom accelerators (a minimal menu or `before-input-event`). Add an icon or word to each banner state. Put the keyword help as visible text under the box.
- **Decision:** none.

### Nit

#### U-16 **nit** `app/renderer/index.html:43-97` - Until the first `list` reply, eight toolbar buttons show only an icon and there is no loading sign. Pressing the blank Sort & Scan in that window throws silently.
- **Evidence:** seen in the browser. `run3/07-second-launch-first-paint.png` (about 230 ms here). `run4.json`: `TypeError … reading 'pass_command'` at `app/renderer/app.js:2588`, and nothing on screen. On a PC with a cold Python start or a streamed Drive root the gap is longer (Windows-only, inferred).
- **Who hits it and when:** every launch, briefly.
- **Fix:** mark the toolbar busy until the vocabulary arrives, and ignore clicks until then.
- **Decision:** none.

#### U-17 **nit** `app/renderer/app.js:960-961` - Every Needs Review row shows a stray "0": `fedReturns().length && el(...)` yields 0, and `el()` prints it (`app/renderer/app.js:55-57`). The same code is in the card mode, `app/renderer/app.js:1328-1329`.
- **Evidence:** seen in the browser (`$S/u1a/crop-oldw2.png`, cut from `run2/24-…-expanded.png`: "Open" followed by "0").
- **Who hits it and when:** first scan, on every row.
- **Fix:** `fedReturns().length > 0 && …`, and a test that no review row has a bare number text node.
- **Decision:** none.

#### U-18 **nit** `tracker/reasons.py:260` - A reason shows the matcher's pattern: "expected period not found (pattern: (?i)\b2025\b); possible wrong period".
- **Evidence:** seen in the browser (same crop, on "W-2 Jane Smith 2024 - old.pdf").
- **Who hits it and when:** first scan, on any document from the wrong year.
- **Fix:** "does not show tax year 2025; it may be for another year".
- **Decision:** none.

#### U-19 **nit** `app/renderer/pilot-content.js:172-182` - Tour step 8 says "File with one click, or dismiss", but the button says "Not requested" (`tracker/api.py:690`).
- **Evidence:** seen in the browser (`run1/11-tour-step-08.png` against `run2/24-…-expanded.png`).
- **Who hits it and when:** first scan.
- **Fix:** "…, or mark it Not requested."
- **Decision:** reopens P22.

#### U-20 **nit** `app/renderer/tour.js:101-104` - The wrap-up's two columns are headed "Why it's safe" and "Current limit". The approved design (SPEC §8, visual 3) names them "Strengths" and "Current limits", and the left column lists strengths such as "Runs offline", not safety.
- **Evidence:** seen in the browser (`run1/14-tour-step-11.png`).
- **Who hits it and when:** first launch.
- **Fix:** for the wrap-up only, head the columns "Strengths" and "Current limits".
- **Decision:** none. It restores P20's design.

#### U-21 **nit** `app/renderer/app.js:2841-2848` - Request rows in the wizard show raw matching rules (`pdf · must contain "W-2, wage and tax statement, employee's social security number" · 2 files expected`) in a 250 px box nested inside the scrolling dialog. That box shows 4 rows at a time of 26.
- **Evidence:** seen in the browser (`run2/16-wizard-3-items-middle.png`).
- **Who hits it and when:** first household, Guide §5 step 3 ("Tick the documents you expect").
- **Fix:** show the document name and the expected count, and move the rules into a "details" fold.
- **Decision:** none.

#### U-22 **nit** `app/renderer/index.html:345` - The rules footer on every screen quotes the standing rules word for word, including "deterministic rules in the manifest", "There is no SMTP" and a 60-word "Nothing is guessed". The terms and the Guide say the same rules in plain words.
- **Evidence:** seen in the browser (every dashboard screenshot).
- **Who hits it and when:** first launch onward.
- **Fix:** show the Guide's plain four lines, the exact wording behind a fold (pinned by `tests/test_single_source.py`; owner's ruling).
- **Decision:** none.

#### U-23 **nit** `app/package.json:4` - The badge says "Pilot edition 0.1" (`app/renderer/pilot-content.js:9`), while the program's own file version is 1.1.0.
- **Evidence:** read from code. The exe's file properties show 1.1.0 (Windows-only, inferred).
- **Who hits it and when:** asking for help, when a tester quotes a version.
- **Fix:** stamp the packaged version from `app/renderer/pilot-content.js`, or show one version everywhere.
- **Decision:** reopens P13 ("the version has one home").

#### U-24 **nit** `app/renderer/app.js:2210-2212` - The amber line "No scheduled pass has run on this machine yet. If the schedule is installed here, one will run…" stays above everything, in warning colour, from before a folder is chosen until after a pass by hand. It says "if" about a schedule the app turned on (U-8).
- **Evidence:** seen in the browser (`run1/15`, `run2/23`).
- **Who hits it and when:** first launch and first scan.
- **Fix:** before any scheduled pass, show the next run time from the Schedule setting in neutral colour.
- **Decision:** none.


## Measurement: clicks to the first filed document (U1a)

From the app opening, with the tour closed: 2 for the terms, 1 to close the tour, 5 for the folder (Browse, pick the folder and Select Folder in the Windows dialog, maximise the window, Use this folder), 4 for the wizard (New household, Continue, Form 1040, Create return), 1 for Open Inbox, 1 to return to the app, 1 for Sort & Scan and 1 for Open Status Report. That is **16 clicks**, plus 3 typed fields (firm, household, contact) and 3 or more hand steps outside the app (open the folder with the test files, select them, drag them). Taking the whole tour makes it 26. Install adds about 7 more (inferred).

No filed row is visible in the app by mouse at any tested size (U-1): only Open Status Report (a browser page) or Tab reach one. What the screen left to memory: pressing Enter or maximising (not even the Guide says it), dragging files in and coming back, Scan = Sort & Scan, and where Prepared is.

#### U-124 **nit** `app/renderer/app.js:1436-1466` - Banners after corrections are terse or garbled. Examples: "setup.exe: Not Requested. not requested, by a person …", "Jane Doe W-2 2025.pdf: Needs Review." (not where it went, nor that A01 reverted), "Household: link", "approved 2026-09-29 at stage 4", "paste the inbox's link into the household first". The Filed list reads "A02 — A02 - 1099-INT-DIV - TY2025.csv". "The pass let go of this return; its buttons are back" is a warning-coloured notice (`app/renderer/app.js:2076`). The chip "Status report: behind/unknown" is unexplained (`app/renderer/app.js:384-388`).
- **Evidence:** seen (`06-b-unfile-banner.png`, `05-d-household-saved.png`).
- **Who hits it and when:** the morning.
- **Fix:** one sentence per result: what moved, where it is now, and what changed on the list. Put the lock release in the banner as ok, and give the chip a title ("regenerated by the next Sort & Scan").
- **Decision:** none.

#### U-125 **nit** `app/renderer/app.js:3968-3971` - Paste rows adds rows silently, below the fold, and the previous editor note stays.
- **Evidence:** seen (`04-b-editor-unsaved-bar.png`: the old "unlearned" note above a new Z99 row).
- **Who hits it and when:** editing a list.
- **Fix:** show "n row(s) added; nothing is saved until Save" in `#ed-note` and scroll to the first new row.
- **Decision:** none.

#### U-126 **nit** `tracker/api.py:452` - The pass banner counts only this pass. The second pass said "filed 0, 1 still syncing" while 13 still waited, and the household card that says so is crushed off-screen.
- **Evidence:** seen (`02-b-after-second-pass.png`).
- **Who hits it and when:** the morning.
- **Fix:** append "13 waiting for a person".
- **Decision:** none.

#### U-127 **nit** `tracker/reminder.py:1198` - The plain-text clipboard breaks one paragraph mid-sentence ("the shared\nfolder we set up", `tracker/reminder.py:259`) while the other paragraphs are unwrapped.
- **Evidence:** seen (clipboard read back).
- **Who hits it and when:** draft day, when pasting as plain text.
- **Fix:** do not wrap the text copied to the clipboard.
- **Decision:** none.

#### U-128 **nit** `pilot/Tester Guide.md:74-76` - Uninstall says the data folder stays, but not that it holds every client's record and a log naming them. It also does not say where settings.json stays (beside the program, `tracker/settings.py:177-190`), or that each client inbox keeps `_README.txt`.
- **Evidence:** read from code (`pilot/installer/setup.iss:48-54`).
- **Who hits it and when:** leaving the pilot.
- **Fix:** add two lines to Guide §9: what stays, and "delete %LOCALAPPDATA%\tax-document-tracker-pilot to remove the pilot's records".
- **Decision:** none (P12 stands).

#### U-129 **nit** `app/renderer/app.js:1685-1735` - Next year's roll is never offered in a Sept-Dec pilot. In January it appears unannounced, with no confirm, and retires last year's returns.
- **Evidence:** read from code (`tracker/api.py:2348-2359`).
- **Who hits it and when:** January, still in the pilot (P5: no expiry).
- **Fix:** add a Guide line, and a confirm naming what retires.
- **Decision:** none.

## By design: answers for testers

| Item | Why | Decision row |
|---|---|---|
| The terms cannot be closed with Escape or a click outside; "Quit." closes the program and the terms show again next time | a tester must see them; losing the stored answer shows them again, the safe direction | P5, P9, P20 |
| No feedback button; the email is plain text | pilot scope | P5 |
| The installer is unsigned; SmartScreen warns | a certificate can come later | P4 |
| "About 74 document kinds" while a 1040 shows 26 rows | 74 distinct documents across the 107 rows of six forms; true | proposed accepted |
| A 1040 ticks 5 of 26 rows; unticked rows still file what arrives | ticked means "asked and chased" | decision 142 |
| A spouse's W-2 goes to Needs Review when only the taxpayer is on People | nothing guessed; named requests need the person on the return | decision 128 |
| Folders outside the two trees are listed and never touched | positional discovery, no importer | decision 125 |
| Uninstall leaves the clients folder, the settings and the data folder | client data is never the installer's to delete | P12 |
| No undo for a whole pass. Undo is per document (Unfile, Put it back, File it from Not requested) | every move is recorded; a person decides each | proposed accepted (workflow.md "Six things") |
| Mark as shared cannot be unmarked, and the app cannot see Drive's grants | it records the firm's word; the link is required first | decision 126 |
| A live lock from another PC greys buttons until it ends or goes stale (2 h 05 min). Clear lock appears only when stale | a lock is not guessed dead; on this PC a dead process is stale at once (seen) | decisions 171, 193 |
| The deck cannot set a document aside | Not requested keeps its note box in the list | decision 114 |
| The card copies the body only; type the subject in Outlook | the subject goes in Outlook's box | decision 118 |
| Weekday session: the letter can be read, toggled, copied and approved. The Saturday draft file, "last drafted" and edited-draft protection are not seen. A partial upload holds the letter | draft day is Saturday | decision 115 |
| The practice page names every client | written into the firm's clients root, never a shared folder | proposed accepted (`tracker/runner.py:2437-2446`) |
| Uninstall leaves the clients folder, data folder and settings | client data is never the installer's to delete | P12 |
| No feedback button | Jason's choice (weighed in U-120) | P5 |
| A keyword taught by a filing survives Unfile; Unlearn is in the editor | a keyword is a rule about documents | workflow.md "Unfile" |

## Cross-references to the security review

- U-101 (the error notice sends a tester to a log that names clients) and S-1 in `security-review.md` are one finding seen from two sides. The fix is written once, under S-1; U-101 keeps the tester's-eye view and the screens involved.
- U1a's blocking findings U-1 and U-2 (the main column never scrolls) come from one stylesheet rule that the original repository carries unchanged since before the pilot was copied from it (`app/renderer/style.css:58-66` at the copy point a2d6af4 is identical), so the fix belongs in the original and is merged into the pilot.
- The review-copy Open button that does nothing is S-2 (the cause, in the API and shell) and is seen from the tester's side in U1b; both cite the same lines.

## Handed across the halves

- Review row density (keyword, note, spelling boxes and a picker on every row, `run2/24-…-expanded.png`); whether "File it" is one click.
- The first-pass reminder card is "held" (a decision and a file waiting); check on draft day.
- A joint 1040 gets only a Taxpayer on People; a Spouse prompt?
- No refresh after a scheduled pass; the last-pass line (U-24).
- The client-facing `_README.txt` that Create generates in the inbox (deny list; not rendered here).
- The Status page and Status Report, from their generators.

- The flex-column crush at 1400x900 and 1100x700: the household card, requests and reminder are cut to slivers, and the footer takes the screen (`03-a-after-pass.png`, `03-k-main-1100x700.png`).
- Tour wording and anchors (step 6 "can be undone", step 8 "dismiss", step 9 per-request claim).
- The wizard's required People step, which Guide §5 does not mention.

## Not reviewed

### U1a - the first hour

- A real Windows install, SmartScreen or Smart App Control, Explorer, Task Scheduler registration and the packaged window's DPI and fonts: no Windows here.
- What "Quit." does in Electron: read from code only.
- OCR (the photo and the scanned PDF) and `.msg`: no engines here.
- The awkward piles (r2, r4) and the draft day: outside the first hour.
- The contents of the Status page, the Status Report and the client README: deny list, and not rendered in memory for this review.
- A screen reader walkthrough: only focus and Tab behaviour were checked.

### U1b - the working week

- Windows itself: Task Scheduler, the packaged window, Explorer and Notepad opening, an Outlook paste of the HTML clipboard, the installer and uninstaller runs.
- OCR reading (the photo and the scan park here).
- A real Saturday pass writing `reminder-draft.txt` (rendered in memory instead).
- A stale lock from another host (only a dead process on this host was made).
- **Keep it here**, **Mark X missing** (it needs a consolidated statement or a copy that is gone), and rename run in the browser (read from code).
- The roll run live (`roll_year` is null in September).
- Screen-reader output.
