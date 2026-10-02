# Recommendations - Pilot 0.1 - 2026-09-29

Written by an independent synthesis writer (Opus; built nothing, wrote neither review) from the security (21 findings) and user-experience (53 findings) reviews, their counts and the browser harness.

## What the reviews say

The program has three parts: the **engine**, the Python part that sorts, files and writes pages and letters; the **window page** staff see and click; and the **shell**, the desktop program (built on Electron) that opens the window, starts the engine and opens files. The window reaches the engine through the **API**, its command door.

**What is strong, and must be protected.** Neither review could break the four standing rules: all 28 originals in the awkward pile moved byte for byte, a program in a zip was never written anywhere, nothing reaches the network, drafts stay drafts. Routing is deterministic; anything doubtful waits for a person. The window is sandboxed: no file or network access, built from data rather than pasted-in web code, six fixed functions to the rest. Attachments are unpacked in memory within limits; scans are read by a separate child program with a time limit. Every outside library is pinned by its fingerprint (a hash: a short code that changes if one byte of the file changes). Nothing below loosens any of this.

**The patterns behind the findings.**

1. **The pilot created a new border, and nothing was designed for it.** For a tester firm J Park is a third party, yet the app's failure notice sends the tester to a log that names clients.
2. **Words were written from the SPEC** (the specification each build follows), **not the running app.** 8 of the Tester Guide's 19 names match no label on screen; 5 of the tour's 9 fallback lines (shown when what a step points at is missing) can never show. Reviews checked builds against the SPEC, so a wrong SPEC passed.
3. **The tests read text; none looks at the screen.** A real browser showed both layout blockers at once. The first filed document takes 16 clicks (26 with the tour) and three hand steps, then no filed row is visible by mouse at any size tested.
4. **Replies have no fixed place on screen:** 17 ways of saying something; buttons stay silent, against decision 193.
5. **Checks that lived on GitHub Actions** (GitHub's paid test machines) **went dark** with Actions off.
6. **The engine speaks in its own terms,** to clients and to staff.
7. **The dangerous-file line is a hand-kept list applied in one place.**

## Recommendations

Each Decision offers rows for the pilot decision log, pilot/DECISIONS.md; Jason keeps one. A session is one SPEC, build and review round. Work placed in "the original" is built there and reaches the pilot by an **upstream merge** (pilot rule 3).

### R-1. One tester pack, written from the running app, that never asks for client data

**The problem.** The Tester Guide, terms and tour were written from the SPEC and never checked against the app. Worst: the failure notice points to the error log, which names clients' folders and files and can quote a document, while the Guide forbids only "client documents". A tester who emails it discloses taxpayer information to a third party through the pilot's own help path. The same gap names buttons that do not exist, says to choose a copy of client folders (ignored by the app), omits that only Google Drive works, and makes the self-starting schedule sound optional. Help sits on two screens shown once. Closes S-1 and U-101 (blocking); U-3, U-4, U-8, U-9, U-10, U-14, U-15, U-119, U-120, U-121; nits U-19, U-20, U-128, S-14.

**The rule.** Every name, step and promise a tester is given matches what the app shows, and nothing asks a tester to send anything that can hold client data. It becomes rule 6 of pilot/README.md.

**The test that enforces it.** tests/test_pilot.py: "every name the Guide and tour put in bold is a label on screen" and "no tester text asks for the log, a data-folder file or an uncovered screenshot"; the existing fallback test gains "and can be shown".

**The change.** Documents and the pilot's wording file (badge, terms and tour words). The Guide uses the screen's words and adds: choose a new empty folder; Google Drive with a Shared Drive or a local folder, never OneDrive; the schedule runs day and night once the folder is chosen, and how to stop it; Smart App Control; reopening from the Start menu; what stays after uninstalling. Guide, terms and last tour step: never send the log or data-folder files; quote the words in brackets. RELEASE.md: J Park never asks for a log. Tour steps 6, 8 and 9 and the wrap-up's headings corrected. In 0.2 the pilot's script adds a Help line (contact, version, what to send), as it adds the badge.

**How work changes.** J Park answers problem emails with "send the words in brackets". Reviews walk Guide sections 3-6 in the browser harness (a script driving the real app in an invisible browser, R-3), not the SPEC.

**The alternative rejected.** Rename the buttons to match the Guide. Their words come from the engine (decision 84), shared with the original; the Guide is the pilot's.

**Where it lands.** The pilot, as an addition under P7 and P10: every file it touches is the pilot's.

**Size.** Small: one session before 0.1, one in 0.2.

**Decision for Jason.**

| # | Date | Decision | Why |
|---|---|---|---|
| P-28a | 2026-09-29 | **Recommended.** Before 0.1, Guide, terms and tour rewritten from the running app and pinned to its labels by a test; J Park never asks for a log. In 0.2 the Help line adds "Copy problem report": version, error class and code, command, time; no names. Reopens P20, P22 and P5. | Closes both blockers now; a report without names beats a tester's guess. |
| P-28b | 2026-09-29 | As P-28a, but the Help line shows only contact, version and what to send. Reopens P20 and P22. | Keeps P5's "no feedback button". |
| P-28c | 2026-09-29 | Before 0.1 only the report wording; the rest in 0.2. Reopens P20. | Fastest; testers still meet wrong names in the first hour. |

### R-2. One file-type table, with the mark on by default

**The problem.** Decision 190 says programs, and files Windows runs or follows, are not documents: they wait unread, uncopied. The hand-kept list misses remote-desktop, console, web-page and drawing files: a zip from a hijacked client mailbox lands unmarked in the folder staff work from, one double-click from connecting this PC, which holds every client's folder, to a stranger's (S-101). The Protected View mark (Windows' tag for a file from the internet, so Office opens it read-only with macros, the small programs inside Office files, off) is applied only in Needs Review; macro workbooks in Prepared, the working-copies folder, and everything taken out of a zip go unmarked (S-102). Links in an inbox are named nowhere (S-104). Closes S-101 (blocking), S-102; nit S-104.

**The rule.** One table says, for every file type, whether the tracker parks it unread, copies it with the mark, or copies it plain; any type not on the short plain list is marked. It lives in tracker/validators.py.

**The test that enforces it.** tests/test_validators.py: "every type Outlook blocks outright is parked as a program"; tests/test_filer.py: "every copy written from a client's bytes carries the mark unless its type is plain".

**The change.** Engine. A list of known dangers becomes a default of caution: whatever is not shown to be plain is marked, on copies only, never originals. Inbox links are named in each sorting run's warnings and never entered.

**How work changes.** Staff see Office's read-only bar more often; "Enable editing" is one click. A new type is one row; the test says which column.

**The alternative rejected.** Add the missing types by hand: today's gap closes; the next waits for a review.

**Where it lands.** The original (an engine fix, pilot rule 1), merged in before 0.1.

**Size.** Small to medium: one session.

**Decision for Jason.**

| # | Date | Decision | Why |
|---|---|---|---|
| P-29a | 2026-09-29 | **Recommended.** One file-type table in the original: programs pinned to Outlook's blocked list plus the reviewers' types; every client copy not on the plain list marked; inbox links named. Merged before 0.1. Reopens decision 190. | Stops the next missing type, not only today's. |
| P-29b | 2026-09-29 | Add the reviewers' missing types; mark named macro types in Prepared and the opened-attachments folder. Reopens decision 190. | Smaller; the next gap waits for a review. |

### R-3. Screens that fit, proven in a real browser

**The problem.** The main column never scrolls; its cards shrink instead. After the first scan, Needs Review, the filed list, the requests and the household card are slivers at every size tested (U-1); on a new install the setup card's only button is out of sight at the default size (U-2). One rule in the stylesheet (the file that sets the window's layout), shared with the original, causes both. The terms card hides its last section, the only in-app "do not send client documents", with no scroll cue (U-12). A stray "0" sits on every review row (U-109); text is small, states are colour-only, there is no zoom (U-123). Closes U-1 and U-2 (blocking); U-12, U-109, U-123; nit U-17.

**The rule.** At the window sizes a firm uses, every screen shows or scrolls to all it holds, every button a step needs can be clicked, and no state is said by colour alone. It lives in app/renderer/style.css.

**The test that enforces it.** A new local screen check, tests/test_screens.py, driving the real page, shell and engine on invented clients: "at 1100x700, 1400x900 and 1920x1017 every visible card shows or scrolls to all its content, and every button a step needs can be clicked"; "no row prints a bare number". Without a browser it skips with a notice.

**The change.** The rule is fixed so the column scrolls; the terms card gets a scroll cue; banners get a word, not only a colour; zoom stays. The browser harness built for this review becomes a standing development tool. For it: it found both blockers and most of R-5's silent replies, all missed by the suite. Against it: it imitates Electron's window (as the suite already does for the shell) on Linux fonts, not the packaged Windows window. It needs Playwright, a browser-driving library, because neither Python's standard library nor plain JavaScript can lay out a page; hash-locked (decision 191), never shipped. A few claims only: screenshot comparisons break on every font change.

**How work changes.** Sessions touching the window run the screen check in their gate (the checks run before pushing); the review prompt (Prompt 4, pilot/PROMPTS.md) adds driving the app at three sizes. Jason's Windows check looks for the setup button and the filed list.

**The alternative rejected.** Fix the rule and rely on Jason's Windows check: one person, one size, once; the next card would shrink unseen.

**Where it lands.** The original, which owns the rule, merged before 0.1; the terms cue is a pilot addition. The screen check follows in 0.2.

**Size.** Small for the rule; one to two sessions for the check.

**Decision for Jason.**

| # | Date | Decision | Why |
|---|---|---|---|
| P-30a | 2026-09-29 | **Recommended.** Fix the rule in the original, merged before 0.1; the harness becomes a local screen check there for 0.2, run by every session touching the window; Playwright joins as a locked development tool. | The only check that saw the blockers stays. |
| P-30b | 2026-09-29 | Fix the rule in the original, merged before 0.1; screens checked by hand at three sizes in the Windows step. | No new tool; regressions surface only at release. |
| P-30c | 2026-09-29 | Fix the rule in the pilot only. Reopens P10. | Quickest; the original stays broken and merges conflict. |

### R-4. One release check on the office PC

**The problem.** With Actions off, GitHub's pre-release checks run nowhere. The clean-tree check cannot see files git ignores, exactly the client-data names, and the packager copies the app folder whole: a stray status page there ships to every tester (S-3). Nothing checks outside libraries for published flaws; Electron is four patches behind (S-4). The installer's fingerprint travels in its own email; the Guide trains testers to click "Run anyway" (S-5). The graphics pack is advertised with no safe delivery, and its files would run inside the process that reads every client document (S-6). Closes S-3, S-4, S-5, S-6; nits S-7, S-8.

**The rule.** No installer leaves J Park until the release check on the office PC has passed, and every tester can prove the file they got is the one J Park built. It lives in pilot/RELEASE.md.

**The test that enforces it.** tests/test_pilot_installer.py: "the build runs the release check before it compiles the installer" and "the release check forbids every client-data name the original's release workflow forbids".

**The change.** A standard-library Python script in pilot/, run by the build before compiling: refuse ignored files in the app folder (its libraries aside); scan the package for client-data names; run the dependency audit (outside libraries checked against published flaws; only names and versions are sent) and stop on a flaw; check every app script parses; read the version as data. Testers get the fingerprint by phone or a J Park web page and compare it before "Run anyway"; firm IT gets a short note. No graphics pack in 0.1; any later pack carries fingerprints the engine checks. Dependabot alerts (GitHub's emailed flaw warnings; no Actions minutes) go on.

**How work changes.** Jason's build passes or names what stopped it; nobody must remember the check. Testers compare one code.

**The alternative rejected.** Turn Actions back on for release tags: decisions 207 and 211 and pilot rule 4 keep tests off GitHub's budget, and the check needs the office PC's build.

**Where it lands.** The pilot, as an addition under P7: the build is the pilot's own. It extends P13.

**Size.** Small: one session.

**Decision for Jason.**

| # | Date | Decision | Why |
|---|---|---|---|
| P-31a | 2026-09-29 | **Recommended.** Before 0.1 the release check runs inside the pilot build; testers get the fingerprint separately and compare it; no graphics pack in 0.1; Dependabot alerts on. Extends P13; complements P4. | What is installed stays for the whole pilot. |
| P-31b | 2026-09-29 | The same in 0.2; for 0.1 Jason checks by hand from RELEASE.md. | Faster to 0.1; hand checks get skipped under a deadline. |

### R-5. One feedback contract from API reply to screen

**The problem.** The window shows messages 17 different ways. Before the first household, toolbar buttons do nothing and Sort & Scan answers with a command-line flag (U-5); New household takes three screens of typing, then refuses with a Python command (U-7). Dialog refusals hide behind the dialog, old errors sit above new successes (U-110, U-111), a to-do shows as success (U-11). Opening fails silently: reported review copies cannot open (S-2), no button opens Prepared or the originals (U-13, U-114), and a refused Status is dropped (U-6, U-115). Nothing refreshes after a scheduled pass, or sorting run (U-118). Closes S-2, U-5, U-6, U-7, U-11, U-13, U-110, U-111, U-114, U-115, U-118; nits U-16, U-124, U-125, U-126, S-105.

**The rule.** Every reply the engine gives (a result, a refusal or a path to open) has one place on screen, where the person is looking, and a control that cannot work yet is greyed with the reason. It lives in app/renderer/app.js.

**The test that enforces it.** The screen check (R-3): "every toolbar button, before and after a household and a pass, gives a visible sentence or is greyed with its reason". tests/test_single_source.py: "every path the engine reports can be opened, or says why not".

**The change.** One reply component, with three forms (in the open dialog or beside the control; a notice for failures; a success line that clears the notices it answers), replaces the 17 paths; each result says what changed and what still waits. Each control declares what it needs (a clients folder, a return, a first pass) and greys itself with that sentence. The page refreshes on focus and remembers the return. A review copy opens only inside its own return's Needs Review folder, never when it is a program (stricter than today's check, S-105); buttons open Prepared and the originals; "not made yet" gets its own sentence. Sentences name buttons, never command lines. Built from data (decision 52), with no new link to the shell.

**How work changes.** Staff see what happened where they clicked; a new button declares its needs, not a new message.

**The alternative rejected.** Adopt a user-interface framework: plain JavaScript is enough, and a framework adds outside code where untrusted names are shown (decisions 52, 176).

**Where it lands.** The original, which owns the page, shell and API (P10 forbids pilot edits); merged for 0.2, with care where P21 changed the page.

**Size.** Large: two to three sessions.

**Decision for Jason.**

| # | Date | Decision | Why |
|---|---|---|---|
| P-32a | 2026-09-29 | **Recommended.** One reply component and one open-paths contract in the original, merged for 0.2; a tour step shows its fallback whenever its button cannot work yet. Reopens P24. | Makes decision 193 true everywhere, once. |
| P-32b | 2026-09-29 | Fix the eleven findings one by one in the original for 0.2. | Smaller now; the next dialog repeats them. |
| P-32c | 2026-09-29 | Build it in the pilot only, relaxing P7 and P10 as P21 did. | Faster for the pilot; later merges conflict. |

### R-6. Client texts that are true on the day, plain, and for one household

**The problem.** What a client reads is assembled from internal fields with no check that it is true or theirs. A return made this autumn with a blank due date gets last April's, so its first letter is an "URGENT final notice" (U-103). The stage toggle claims the cutoff has passed sixteen days early (U-104). Adding a request makes the letter's count and list disagree (U-106); the card hides the draft's warning that the client's files still wait in Needs Review (U-105). The client's README names the client as their own contact (U-107); lines carry codes like "A02" and "TY2025" (U-108). One inbox link can sit on two households, sending client A's link to client B (S-103); a wrong-client document stays in the household's visible year folder (S-106). Closes S-103, U-103, U-104, U-105, U-106, U-107, U-108; nit S-106.

**The rule.** Nothing reaches a client that is false on the day it is read, speaks in the firm's internal codes, or could belong to another household. It lives in tracker/reminder.py.

**The test that enforces it.** tests/test_reminder.py: "a letter is true on the day it is drafted" (every stage, every distance from the due date) and "no client text carries an internal code or names the client as the firm's contact"; tests/test_households.py: "no two households record one inbox link".

**The change.** Engine. Letter and README draw from one set of client phrases: stage wording true before the date; the firm as contact; document names without codes. The wizard shows the computed due date and asks when it has passed; a save that adds rows re-scans first; staff warnings sit beside the letter, never in the copied text; inbox links must be Google Drive links no other household records; the runbook's wrong-client step moves the original out too. The letter stays a draft.

**How work changes.** Staff can trust the card on draft day; one test covers every stage and date.

**The alternative rejected.** Fix the six sentences by hand: the next field added to a letter would carry the same risk untested, as the engine's reason table learned for validation sentences.

**Where it lands.** The original, whose own clients receive these letters; merged for 0.2, the date check pulled into the merge before 0.1.

**Size.** Medium: two sessions.

**Decision for Jason.**

| # | Date | Decision | Why |
|---|---|---|---|
| P-33a | 2026-09-29 | **Recommended.** The client-text rule in the original for 0.2; the wizard's date check (U-103) rides the merge before 0.1. Reopens decisions 117, 118 and 137 (L5). | Every tester meets the "final notice" in week one; the check is small. |
| P-33b | 2026-09-29 | All of it in 0.2; for 0.1 the Guide tells testers to type a due date. Reopens the same decisions. | Keeps 0.1 smaller; relies on a Guide line. |

### R-7. A morning queue that says what to decide

**The problem.** Needs Review is where a person decides, and it speaks in engine fragments ("expected period not found (pattern: ...)", "matched no request") with no next step (U-113). The picker starts on the top suggestion even when the reason says the evidence is wrong, so one click files another person's W-2 under a green banner (U-102): the engine never guesses, but the page nudges a person to. A document from a zip does not name the zip (U-112). The Status Report leads with fingerprints and puts Status 15th of 18 columns (U-116); the practice page omits what is outstanding (U-117). Closes U-102, U-112, U-113, U-116, U-117; nits U-18, S-107.

**The rule.** Every item waiting for a person says why, where it came from and the next action, and the app pre-selects an answer only when nothing in the evidence doubts it. It lives in tracker/reasons.py, whose table already holds each reason's code and client sentence.

**The test that enforces it.** tests/test_reasons.py: "every reason has a staff sentence that ends in an action" and "a reason that doubts the evidence never lets the picker start on the suggestion".

**The change.** Engine and window page. The reason table gains two columns, the staff sentence and whether the reason doubts the suggestion; patterns and codes fold behind "details". The review row, the card deck and both status pages read from it; a document from a zip names its zip. Both status pages lead with each document, its status and what waits for a person; machine facts fold away; a step naming a command becomes an action in the app.

**How work changes.** The queue reads as a to-do list; filing against a doubt is deliberate and warned; a reason without a staff sentence fails the test.

**The alternative rejected.** Link each reason to the runbook: testers never get it, and a sentence on the row is read where a link is not.

**Where it lands.** The original, since P7 and P10 keep the pilot out of the engine and the page; merged in.

**Size.** Medium: two sessions (queue, then pages).

**Decision for Jason.**

| # | Date | Decision | Why |
|---|---|---|---|
| P-34a | 2026-09-29 | **Recommended.** Staff sentences and the doubt mark in the original for 0.2, the picker starting on "Belongs to…" when evidence is doubted; the status pages after testers' reports. Reopens decision 84. | Closes the one-click misfiling first. |
| P-34b | 2026-09-29 | Only the picker change in 0.2; wording and pages wait for testers. Reopens decision 84. | Smallest; the queue stays hard to read. |

## Order

**Before 0.1 ships to a firm**
- R-1: S-1, U-101 (blocking); U-3, U-4, U-8, U-9, U-10, U-14, U-15, U-119, U-121.
- R-2: S-101 (blocking); S-102.
- R-3, the stylesheet rule and terms cue: U-1, U-2 (blocking); U-12.
- R-4: S-3, S-4, S-5, S-6.
- R-6, the wizard's date check: U-103.

**0.2**
- R-3, the screen check: U-109, U-123.
- R-5: S-2, U-5, U-6, U-7, U-11, U-13, U-110, U-111, U-114, U-115, U-118.
- R-6, the rest: S-103, U-104, U-105, U-106, U-107, U-108.
- R-7, reasons and picker: U-102, U-112, U-113.
- R-1, the Help line: U-120.

**Later**
- R-7, the two status pages: U-116, U-117.
- R-4's graphics-pack fingerprint check, if the pack is ever offered.
- Appendix B's one-offs, as the fix job reaches them.

**Why the line falls there.** Before 0.1: every blocking finding, plus small items in the same files or release step, since what is installed cannot be taken back (P5: no expiry, no update channel). Nothing large. The original's pre-0.1 work (R-2, the R-3 rule, U-103) goes up as one proposed change, so its one paid test run (decision 211) covers it; then the upstream merge, R-1 and R-4, the gate, and Jason's Windows check. 0.2 is the next build round. Later waits for testers' reports.

## What not to change

- **The four standing rules, deterministic routing and the shortlist** (decision 84). R-2 marks copies, never originals; R-6 drafts, never sends; R-7 leaves every choice to a person.
- **The sandboxed window:** built from data, six fixed functions and no more (decisions 52, 176; P10).
- **The API as the wall; the record (each household's file of every move) as untrusted input** (decisions 176, 187, 188).
- **Errors said by class, the message only logged** (decision 193); R-1's report copies class and code only.
- **Attachments in memory, programs never written** (decisions 143, 190).
- **Client data's three homes and the deny list** (decision 186, P19); the harness uses invented clients only (decision 185).
- **Hash-locked dependencies, tag-only builds** (decision 191).
- **No Actions minutes** (decisions 207, 211; pilot rule 4); **one-time steps run themselves** (decision 209).
- **Small, named pilot differences** (P7, P10, P17).

## Appendix A: root-cause table

Root causes, with nits sharing them:
- **A** Tester words written from the SPEC, not the app (nits U-19, U-20, U-128, S-14).
- **B** A hand-kept dangerous-file list applied in one place (nit S-104).
- **C** Screens never checked as rendered (nit U-17).
- **D** Release checks lost with Actions (nits S-7, S-8).
- **E** Replies with no fixed place on screen (nits U-16, U-124, U-125, U-126, S-105).
- **F** Client texts built from internal fields (nit S-106).
- **G** A queue that speaks the engine's terms (nits U-18, S-107).

| Finding | Label | Root cause | Closed by |
|---|---|---|---|
| S-1 | blocking | A | R-1 |
| U-101 | blocking | A | R-1 |
| S-101 | blocking | B | R-2 |
| U-1 | blocking | C | R-3 |
| U-2 | blocking | C | R-3 |
| U-3 | should-fix | A | R-1 |
| U-4 | should-fix | A | R-1 |
| U-8 | should-fix | A | R-1 |
| U-9 | should-fix | A | R-1 |
| U-10 | should-fix | A | R-1 |
| U-14 | should-fix | A | R-1 |
| U-15 | should-fix | A | R-1 |
| U-119 | should-fix | A | R-1 |
| U-120 | should-fix | A | R-1 |
| U-121 | should-fix | A | R-1 |
| S-102 | should-fix | B | R-2 |
| U-12 | should-fix | C | R-3 |
| U-109 | should-fix | C | R-3 |
| U-123 | should-fix | C | R-3 |
| S-3 | should-fix | D | R-4 |
| S-4 | should-fix | D | R-4 |
| S-5 | should-fix | D | R-4 |
| S-6 | should-fix | D | R-4 |
| S-2 | should-fix | E | R-5 |
| U-5 | should-fix | E | R-5 |
| U-6 | should-fix | E | R-5 |
| U-7 | should-fix | E | R-5 |
| U-11 | should-fix | E | R-5 |
| U-13 | should-fix | E | R-5 |
| U-110 | should-fix | E | R-5 |
| U-111 | should-fix | E | R-5 |
| U-114 | should-fix | E | R-5 |
| U-115 | should-fix | E | R-5 |
| U-118 | should-fix | E | R-5 |
| S-103 | should-fix | F | R-6 |
| U-103 | should-fix | F | R-6 |
| U-104 | should-fix | F | R-6 |
| U-105 | should-fix | F | R-6 |
| U-106 | should-fix | F | R-6 |
| U-107 | should-fix | F | R-6 |
| U-108 | should-fix | F | R-6 |
| U-102 | should-fix | G | R-7 |
| U-112 | should-fix | G | R-7 |
| U-113 | should-fix | G | R-7 |
| U-116 | should-fix | G | R-7 |
| U-117 | should-fix | G | R-7 |
| U-122 | should-fix | File names carry the request, not the person | one-off |

## Appendix B: one-offs for the fix job

- **tracker/filer.py.** U-122 (should-fix): two people's W-2 copies differ only by "(2)" and "(3)"; add the confirmed person's name (reopens decision 168).
- **app/main.js.** S-9: close Electron's three debugging doors at build and refuse permission requests (original first). S-10: stop the packaged shell passing the engine its override settings.
- **tracker/scheduling.py.** S-11: call the Windows task command by its full System32 path.
- **tracker/reminder.py.** U-127: the plain-text copy breaks one paragraph mid-sentence; stop wrapping it.
- **.github/CODEOWNERS.** S-12: name owners for the installer, pilot build files, shell, bridge and window page.
- **.claude/settings.json.** S-13: deny the client README, the after-install note and the passes folder.
- **app/package.json.** U-23: the badge says 0.1, the program 1.1.0; show one version (reopens P13).
- **app/renderer/app.js.** U-21: wizard rows show raw matching rules; show names and counts. U-24: the amber "if the schedule is installed" line; show the next run in neutral colour. U-129: January's roll appears unannounced; confirm it, naming what retires.
- **app/renderer/index.html.** U-22: the footer quotes the standing rules verbatim; show plain lines, the exact wording behind a fold (Jason's ruling).
