# For NonCoders: start here

Every page in this folder explains one part of the Tax Document Tracker
in plain words, for a reader who does not write code. Each page names the
original file it explains, so a programmer can find it too.

These pages explain; the originals decide. If a page here and its original
ever disagree, the original is right, and this page needs fixing.

Start with the [maintenance guide](../maintenance-guide.md), the plain-English
overview of the whole system, then [where the pilot stands](<1 - Start Here/Where the Pilot Stands (main handoff).md>).

## How the folders are arranged

| Folder | What is in it |
|---|---|
| `1 - Start Here` | Where the pilot stands today. |
| `2 - How the Program Works` | The safety walls around the app window, the engine, and the Windows schedule. |
| `3 - Building and Installing` | How the program is built, packed into an installer, and kept safe from bad outside parts. |
| `4 - Testing and Checks` | The automatic checks: on this computer, on the office PC, and on GitHub. |
| `5 - Rules, Plans and Decisions` | The rules for AI helpers, the decision log, the build plan and the code map. |
| `6 - Work History (Handoff Notes)` | What each work session did, stage by stage, in the order it happened. |
| `7 - History` | Pages whose file was removed, and earlier versions of pages that were rewritten. |

## What the tags mean

Every page has a **Tags** line near the top, with up to three kinds of tag.

**Kind** - what sort of page it is:

| Kind | Meaning |
|---|---|
| Overview | Where the whole project stands. |
| Program file | Explains a file the program is made of. |
| Build | A work session that built something new. |
| Review | An independent check of a build, by a session that did not build it. |
| Fix round | A work session that fixed what a review found, and nothing more. |
| Final check | A last check of the whole screen before it is called done. |
| Rulings | Jason's decisions and the plan updated to match them. |

**Topic** - what part of the system the page is about:

| Topic | Meaning |
|---|---|
| Safety | The walls that keep client files safe from the app window. |
| App window | The part of the program you click on. |
| Engine | The part that sorts, renames and records documents. |
| Schedule | The Windows alarm clock that runs the sorting by itself. |
| Installer | The file that installs or upgrades the program on a computer. |
| Building | Turning the code into a program you can install. |
| Supply-chain safety | Checking every outside part the program uses has not been swapped. |
| Testing | The automatic checks. |
| GitHub costs | The rules that keep the GitHub bill down. |
| Rules and decisions | The written rules, plans and Jason's decisions. |
| Code map | The map of every file in the program. |
| Screen | The app's new screen, built in stages S1 to S8. |
| Wording | The exact words the app shows. |

**Stage** - for work history pages, which build stage of the new screen
(S1 to S8b) the session belonged to. Inside each stage folder the pages are
numbered in the order they happened: build, review 1, fix round 1, review 2,
and so on.

## Every page, by topic

### App window

- [Window control center](<2 - How the Program Works/Safety Walls/Window control center (main.js).md>) - Program file
- [Window doorway](<2 - How the Program Works/Safety Walls/Window doorway (preload.js).md>) - Program file
- [Window page and its safety rule](<2 - How the Program Works/Safety Walls/Window page and its safety rule (index.html).md>) - Program file
- [Start App: opening the app from source](<3 - Building and Installing/Building the App/Start App.md>) - Program file
- [Screen picture and click tests](<4 - Testing and Checks/Tests on This Computer/Screen picture and click tests (harness).md>) - Program file

### Building

- [Build App: making the portable program folder](<3 - Building and Installing/Building the App/Build App.md>) - Program file
- [The recipe that packs the engine into one ready-to-run program](<3 - Building and Installing/Building the App/Freezing recipe (api_entry.spec).md>) - Program file
- [Setup: preparing a computer to run the app from source](<3 - Building and Installing/Building the App/Setup.md>) - Program file
- [Start App: opening the app from source](<3 - Building and Installing/Building the App/Start App.md>) - Program file
- [Build Pilot Installer: making the Setup file](<3 - Building and Installing/Installer/Build Pilot Installer.md>) - Program file

### Code map

- [Code map](<5 - Rules, Plans and Decisions/Code map (repo_map.py).md>) - Program file
- [A check of the "closing best practices" list, and the gaps it filled](<6 - Work History (Handoff Notes)/Other Work/2026-09-30 Maintainer Handoff Audit.md>) - Build

### Engine

- [The engine's front door](<2 - How the Program Works/Engine and Schedule/Engine front door (api_entry.py).md>) - Program file
- [The sorting pass: the unattended run over every client](<2 - How the Program Works/Engine and Schedule/Sorting pass (runner.py).md>) - Program file
- [The recipe that packs the engine into one ready-to-run program](<3 - Building and Installing/Building the App/Freezing recipe (api_entry.spec).md>) - Program file
- [Stage S1: the engine's new answers and the shortened wording](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 01 Build.md>) - Build (S1)
- [First independent check of the shell's engine job (S1): nine findings](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 02 Review 1.md>) - Review (S1)
- [Fixing the nine problems a checker found in the shell's data layer (stage S1)](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 03 Fix Round 1.md>) - Fix round (S1)
- [Second independent check of stage S1 (the shell's engine side), after the first fix round](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 04 Review 2.md>) - Review (S1)
- [Fixing two out-of-date notes in the first stage's handoff](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 05 Fix Round 2.md>) - Fix round (S1)
- [Third independent check of the first stage's fix](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 06 Review 3.md>) - Review (S1)
- [Shell engine, fix round 3: the `firm` answer now matches the plan](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 07 Fix Round 3.md>) - Fix round (S1)
- [Fourth independent check of stage S1's firm-wide data](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 08 Review 4.md>) - Review (S1)
- [Adding a missing test to the firm-wide list (S1, fix round 4)](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 09 Fix Round 4.md>) - Fix round (S1)
- [Fifth independent check of stage S1: no problems found](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 10 Review 5.md>) - Review (S1)
- [Second half of the join: the shell now runs on the real engine](<6 - Work History (Handoff Notes)/Stage 6 - Joining the Screen to the Real Engine/S6b - 01 Build, Part 2.md>) - Build (S6b)

### GitHub costs

- [GitHub's automatic checks, and the rule that keeps them cheap](<4 - Testing and Checks/Checks on GitHub/GitHub automatic checks (workflows).md>) - Program file
- [Instructions for AI helpers](<5 - Rules, Plans and Decisions/Instructions for AI helpers (CLAUDE.md).md>) - Program file

### Installer

- [Build Pilot Installer: making the Setup file](<3 - Building and Installing/Installer/Build Pilot Installer.md>) - Program file
- [The recipe that builds the Pilot installer](<3 - Building and Installing/Installer/Installer recipe (setup.iss).md>) - Program file
- [Installer tests](<4 - Testing and Checks/Tests on This Computer/Installer tests (test_pilot_installer.py).md>) - Program file
- [Windows test kit](<4 - Testing and Checks/Tests on the Office PC/Windows test kit (run_checks.ps1).md>) - Program file
- [A check of the "closing best practices" list, and the gaps it filled](<6 - Work History (Handoff Notes)/Other Work/2026-09-30 Maintainer Handoff Audit.md>) - Build

### Rules and decisions

- [The pilot's main hand-off page: where the new app screen stands](<1 - Start Here/Where the Pilot Stands (main handoff).md>) - Overview
- [Instructions for AI helpers](<5 - Rules, Plans and Decisions/Instructions for AI helpers (CLAUDE.md).md>) - Program file
- [Pilot build plan](<5 - Rules, Plans and Decisions/Pilot build plan (SPEC.md).md>) - Program file
- [Pilot decision log](<5 - Rules, Plans and Decisions/Pilot decision log (DECISIONS.md).md>) - Program file
- [Jason's rulings on the shell build](<6 - Work History (Handoff Notes)/Jason's Rulings and Plan Updates/Jason's Rulings on the Screen.md>) - Rulings
- [The shell's list of live decisions](<6 - Work History (Handoff Notes)/Jason's Rulings and Plan Updates/Live Decisions List.md>) - Rulings
- [Bringing the shell plan up to date with Jason's rulings 1 to 13](<6 - Work History (Handoff Notes)/Jason's Rulings and Plan Updates/Plan Brought Up to Date with Rulings 1-13.md>) - Rulings
- [A tool that keeps these plain-English pages up to date](<6 - Work History (Handoff Notes)/Other Work/2026-09-30 Noncoder Automation Build.md>) - Build

### Safety

- [Window control center](<2 - How the Program Works/Safety Walls/Window control center (main.js).md>) - Program file
- [Window doorway](<2 - How the Program Works/Safety Walls/Window doorway (preload.js).md>) - Program file
- [Window page and its safety rule](<2 - How the Program Works/Safety Walls/Window page and its safety rule (index.html).md>) - Program file
- [A check of the "closing best practices" list, and the gaps it filled](<6 - Work History (Handoff Notes)/Other Work/2026-09-30 Maintainer Handoff Audit.md>) - Build

### Schedule

- [The engine's front door](<2 - How the Program Works/Engine and Schedule/Engine front door (api_entry.py).md>) - Program file
- [The sorting pass: the unattended run over every client](<2 - How the Program Works/Engine and Schedule/Sorting pass (runner.py).md>) - Program file
- [The Windows schedule: making the daily job](<2 - How the Program Works/Engine and Schedule/Windows schedule (scheduling.py).md>) - Program file

### Screen

- [The pilot's main hand-off page: where the new app screen stands](<1 - Start Here/Where the Pilot Stands (main handoff).md>) - Overview
- [Final review A: safety of the engine and the app window](<6 - Work History (Handoff Notes)/Final Checks/1 Final Review A.md>) - Final check
- [Final check of the screen's display code against the plan and Jason's rulings](<6 - Work History (Handoff Notes)/Final Checks/2 Final Review B.md>) - Final check
- [Final review C: is the whole new screen complete and consistent?](<6 - Work History (Handoff Notes)/Final Checks/3 Final Review C.md>) - Final check
- [The fix round after the final reviews A, B and C](<6 - Work History (Handoff Notes)/Final Checks/4 Fix Pass After the Final Reviews.md>) - Fix round
- [Final re-check of the whole shell after the fix pass](<6 - Work History (Handoff Notes)/Final Checks/5 Final Re-review.md>) - Final check
- [Final check of the second fix pass on the joined screen](<6 - Work History (Handoff Notes)/Final Checks/6 Final Check of the Second Fix Pass.md>) - Final check
- [Jason's rulings on the shell build](<6 - Work History (Handoff Notes)/Jason's Rulings and Plan Updates/Jason's Rulings on the Screen.md>) - Rulings
- [The shell's list of live decisions](<6 - Work History (Handoff Notes)/Jason's Rulings and Plan Updates/Live Decisions List.md>) - Rulings
- [Bringing the shell plan up to date with Jason's rulings 1 to 13](<6 - Work History (Handoff Notes)/Jason's Rulings and Plan Updates/Plan Brought Up to Date with Rulings 1-13.md>) - Rulings
- [Stage S1: the engine's new answers and the shortened wording](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 01 Build.md>) - Build (S1)
- [First independent check of the shell's engine job (S1): nine findings](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 02 Review 1.md>) - Review (S1)
- [Fixing the nine problems a checker found in the shell's data layer (stage S1)](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 03 Fix Round 1.md>) - Fix round (S1)
- [Second independent check of stage S1 (the shell's engine side), after the first fix round](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 04 Review 2.md>) - Review (S1)
- [Fixing two out-of-date notes in the first stage's handoff](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 05 Fix Round 2.md>) - Fix round (S1)
- [Third independent check of the first stage's fix](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 06 Review 3.md>) - Review (S1)
- [Shell engine, fix round 3: the `firm` answer now matches the plan](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 07 Fix Round 3.md>) - Fix round (S1)
- [Fourth independent check of stage S1's firm-wide data](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 08 Review 4.md>) - Review (S1)
- [Adding a missing test to the firm-wide list (S1, fix round 4)](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 09 Fix Round 4.md>) - Fix round (S1)
- [Fifth independent check of stage S1: no problems found](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 10 Review 5.md>) - Review (S1)
- [Stage S2: the window and its menus](<6 - Work History (Handoff Notes)/Stage 2 - Window and Menus/S2 - 01 Build.md>) - Build (S2)
- [First independent check of the menus stage (S2)](<6 - Work History (Handoff Notes)/Stage 2 - Window and Menus/S2 - 02 Review 1.md>) - Review (S2)
- [Menus and window job (S2): first round of fixes](<6 - Work History (Handoff Notes)/Stage 2 - Window and Menus/S2 - 03 Fix Round 1.md>) - Fix round (S2)
- [Second independent check of the menus job (S2): two findings](<6 - Work History (Handoff Notes)/Stage 2 - Window and Menus/S2 - 04 Review 2.md>) - Review (S2)
- [Correcting one sentence in the program's map (stage S2, second fix round)](<6 - Work History (Handoff Notes)/Stage 2 - Window and Menus/S2 - 05 Fix Round 2.md>) - Fix round (S2)
- [Third independent check of stage S2 (the menus)](<6 - Work History (Handoff Notes)/Stage 2 - Window and Menus/S2 - 06 Review 3.md>) - Review (S2)
- [Stage S2, third fix round: what the app says when a command fails and no error log exists yet](<6 - Work History (Handoff Notes)/Stage 2 - Window and Menus/S2 - 07 Fix Round 3.md>) - Fix round (S2)
- [Fourth independent check of stage S2: the error-log fallback](<6 - Work History (Handoff Notes)/Stage 2 - Window and Menus/S2 - 08 Review 4.md>) - Review (S2)
- [Fourth fix round for the menus stage: the fallback error log](<6 - Work History (Handoff Notes)/Stage 2 - Window and Menus/S2 - 09 Fix Round 4.md>) - Fix round (S2)
- [Fifth independent check of stage S2 (the menus): no problems found](<6 - Work History (Handoff Notes)/Stage 2 - Window and Menus/S2 - 10 Review 5.md>) - Review (S2)
- [Building the new screen's frame (stage S3)](<6 - Work History (Handoff Notes)/Stage 3 - The Screen's Frame/S3 - 01 Build.md>) - Build (S3)
- [First independent check of stage S3: the screen's frame](<6 - Work History (Handoff Notes)/Stage 3 - The Screen's Frame/S3 - 02 Review 1.md>) - Review (S3)
- [Stage S3 fixes after the first check](<6 - Work History (Handoff Notes)/Stage 3 - The Screen's Frame/S3 - 03 Fix Round 1.md>) - Fix round (S3)
- [Second check of stage S3 (after the first fix round)](<6 - Work History (Handoff Notes)/Stage 3 - The Screen's Frame/S3 - 04 Review 2.md>) - Review (S3)
- [Second fix round for the screen's frame stage (S3)](<6 - Work History (Handoff Notes)/Stage 3 - The Screen's Frame/S3 - 05 Fix Round 2.md>) - Fix round (S3)
- [Third check of the screen's frame stage (S3): no findings](<6 - Work History (Handoff Notes)/Stage 3 - The Screen's Frame/S3 - 06 Review 3.md>) - Review (S3)
- [Building every page of the new screen (stage S4)](<6 - Work History (Handoff Notes)/Stage 4 - Every Page of the Screen/S4 - 01 Build.md>) - Build (S4)
- [First check of the pages stage (S4): eight findings](<6 - Work History (Handoff Notes)/Stage 4 - Every Page of the Screen/S4 - 02 Review 1.md>) - Review (S4)
- [Stage S4 (the pages), first fix round: eight problems fixed](<6 - Work History (Handoff Notes)/Stage 4 - Every Page of the Screen/S4 - 03 Fix Round 1.md>) - Fix round (S4)
- [Second independent check of stage S4 (the pages): eight fixes confirmed, three findings](<6 - Work History (Handoff Notes)/Stage 4 - Every Page of the Screen/S4 - 04 Review 2.md>) - Review (S4)
- [Stage S5 built: the side sheet, file links, right-click menus and dialogs](<6 - Work History (Handoff Notes)/Stage 5 - Side Sheet, Links, Menus and Dialogs/S5 - 01 Build.md>) - Build (S5)
- [First check of stage S5: the side sheet, links, right-click menus and dialogs](<6 - Work History (Handoff Notes)/Stage 5 - Side Sheet, Links, Menus and Dialogs/S5 - 02 Review 1.md>) - Review (S5)
- [Stage S5 (the side sheet), first fix round: many findings fixed](<6 - Work History (Handoff Notes)/Stage 5 - Side Sheet, Links, Menus and Dialogs/S5 - 03 Fix Round 1.md>) - Fix round (S5)
- [Stage S5 (the side sheet), second fix round: Jason's rulings 16 to 21](<6 - Work History (Handoff Notes)/Stage 5 - Side Sheet, Links, Menus and Dialogs/S5 - 04 Fix Round 2.md>) - Fix round (S5)
- [Stage S6a: the first half of joining the screen's branches together](<6 - Work History (Handoff Notes)/Stage 6 - Joining the Screen to the Real Engine/S6a - 01 Build, Part 1.md>) - Build (S6a)
- [Second half of the join: the shell now runs on the real engine](<6 - Work History (Handoff Notes)/Stage 6 - Joining the Screen to the Real Engine/S6b - 01 Build, Part 2.md>) - Build (S6b)
- [Building the tooltips stage (S7): placement by Floating UI](<6 - Work History (Handoff Notes)/Stage 7 - Tooltips/S7 - 01 Build.md>) - Build (S7)
- [First check of the tooltips stage (S7)](<6 - Work History (Handoff Notes)/Stage 7 - Tooltips/S7 - 02 Review 1.md>) - Review (S7)
- [Stage S7 fixes: how the small hint boxes load and behave](<6 - Work History (Handoff Notes)/Stage 7 - Tooltips/S7 - 03 Fix Round 1.md>) - Fix round (S7)
- [Second check of stage S7 (after the fix round)](<6 - Work History (Handoff Notes)/Stage 7 - Tooltips/S7 - 04 Review 2.md>) - Review (S7)
- [Small document fix for the tooltips stage (S7, second fix round)](<6 - Work History (Handoff Notes)/Stage 7 - Tooltips/S7 - 05 Fix Round 2.md>) - Fix round (S7)
- [Third independent check of stage S7 (tooltips): no findings](<6 - Work History (Handoff Notes)/Stage 7 - Tooltips/S7 - 06 Review 3.md>) - Review (S7)
- [File names become links, and words go to Title Case (stage S8a)](<6 - Work History (Handoff Notes)/Stage 8 - Links, Title Case and Skip Reasons/S8a - 01 Build.md>) - Build (S8a)
- [First independent check of stage S8a: file-name links and Title Case words](<6 - Work History (Handoff Notes)/Stage 8 - Links, Title Case and Skip Reasons/S8a - 02 Review 1.md>) - Review (S8a)
- [Stage S8a fixes: file links that only show a file, and short notice words](<6 - Work History (Handoff Notes)/Stage 8 - Links, Title Case and Skip Reasons/S8a - 03 Fix Round 1.md>) - Fix round (S8a)
- [Second check of stage S8a (after the first fix round)](<6 - Work History (Handoff Notes)/Stage 8 - Links, Title Case and Skip Reasons/S8a - 04 Review 2.md>) - Review (S8a)
- [Link keys job (S8a): second round of fixes](<6 - Work History (Handoff Notes)/Stage 8 - Links, Title Case and Skip Reasons/S8a - 05 Fix Round 2.md>) - Fix round (S8a)
- [Third independent check of the link-keys job (S8a): no findings](<6 - Work History (Handoff Notes)/Stage 8 - Links, Title Case and Skip Reasons/S8a - 06 Review 3.md>) - Review (S8a)
- [Stage S8a: file names on the firm-wide Needs Review page become links](<6 - Work History (Handoff Notes)/Stage 8 - Links, Title Case and Skip Reasons/S8a - 07 Fix Round 3.md>) - Fix round (S8a)
- [Two-word reasons for the Folders Skipped dialog (S8b)](<6 - Work History (Handoff Notes)/Stage 8 - Links, Title Case and Skip Reasons/S8b - 01 Build (Two-Word Skip Reasons).md>) - Build (S8b)

### Supply-chain safety

- [Setup: preparing a computer to run the app from source](<3 - Building and Installing/Building the App/Setup.md>) - Program file
- [Lock files: the list of every outside part, with fingerprints](<3 - Building and Installing/Supply-Chain Safety/Lock files and lockfiles.py.md>) - Program file

### Testing

- [GitHub's automatic checks, and the rule that keeps them cheap](<4 - Testing and Checks/Checks on GitHub/GitHub automatic checks (workflows).md>) - Program file
- [Installer tests](<4 - Testing and Checks/Tests on This Computer/Installer tests (test_pilot_installer.py).md>) - Program file
- [Screen picture and click tests](<4 - Testing and Checks/Tests on This Computer/Screen picture and click tests (harness).md>) - Program file
- [Windows test kit](<4 - Testing and Checks/Tests on the Office PC/Windows test kit (run_checks.ps1).md>) - Program file
- [A tool that keeps these plain-English pages up to date](<6 - Work History (Handoff Notes)/Other Work/2026-09-30 Noncoder Automation Build.md>) - Build

### Wording

- [Stage S1: the engine's new answers and the shortened wording](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 01 Build.md>) - Build (S1)
- [First independent check of the shell's engine job (S1): nine findings](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 02 Review 1.md>) - Review (S1)
- [Fixing the nine problems a checker found in the shell's data layer (stage S1)](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 03 Fix Round 1.md>) - Fix round (S1)
- [Second independent check of stage S1 (the shell's engine side), after the first fix round](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 04 Review 2.md>) - Review (S1)
- [Fixing two out-of-date notes in the first stage's handoff](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 05 Fix Round 2.md>) - Fix round (S1)
- [Third independent check of the first stage's fix](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 06 Review 3.md>) - Review (S1)
- [Shell engine, fix round 3: the `firm` answer now matches the plan](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 07 Fix Round 3.md>) - Fix round (S1)
- [Fourth independent check of stage S1's firm-wide data](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 08 Review 4.md>) - Review (S1)
- [Adding a missing test to the firm-wide list (S1, fix round 4)](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 09 Fix Round 4.md>) - Fix round (S1)
- [Fifth independent check of stage S1: no problems found](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 10 Review 5.md>) - Review (S1)
- [File names become links, and words go to Title Case (stage S8a)](<6 - Work History (Handoff Notes)/Stage 8 - Links, Title Case and Skip Reasons/S8a - 01 Build.md>) - Build (S8a)
- [First independent check of stage S8a: file-name links and Title Case words](<6 - Work History (Handoff Notes)/Stage 8 - Links, Title Case and Skip Reasons/S8a - 02 Review 1.md>) - Review (S8a)
- [Stage S8a fixes: file links that only show a file, and short notice words](<6 - Work History (Handoff Notes)/Stage 8 - Links, Title Case and Skip Reasons/S8a - 03 Fix Round 1.md>) - Fix round (S8a)
- [Second check of stage S8a (after the first fix round)](<6 - Work History (Handoff Notes)/Stage 8 - Links, Title Case and Skip Reasons/S8a - 04 Review 2.md>) - Review (S8a)
- [Link keys job (S8a): second round of fixes](<6 - Work History (Handoff Notes)/Stage 8 - Links, Title Case and Skip Reasons/S8a - 05 Fix Round 2.md>) - Fix round (S8a)
- [Third independent check of the link-keys job (S8a): no findings](<6 - Work History (Handoff Notes)/Stage 8 - Links, Title Case and Skip Reasons/S8a - 06 Review 3.md>) - Review (S8a)
- [Stage S8a: file names on the firm-wide Needs Review page become links](<6 - Work History (Handoff Notes)/Stage 8 - Links, Title Case and Skip Reasons/S8a - 07 Fix Round 3.md>) - Fix round (S8a)
- [Two-word reasons for the Folders Skipped dialog (S8b)](<6 - Work History (Handoff Notes)/Stage 8 - Links, Title Case and Skip Reasons/S8b - 01 Build (Two-Word Skip Reasons).md>) - Build (S8b)

## Every page, by kind

### Overview (1)

- [The pilot's main hand-off page: where the new app screen stands](<1 - Start Here/Where the Pilot Stands (main handoff).md>)

### Program file (21)

- [The engine's front door](<2 - How the Program Works/Engine and Schedule/Engine front door (api_entry.py).md>)
- [The sorting pass: the unattended run over every client](<2 - How the Program Works/Engine and Schedule/Sorting pass (runner.py).md>)
- [The Windows schedule: making the daily job](<2 - How the Program Works/Engine and Schedule/Windows schedule (scheduling.py).md>)
- [Window control center](<2 - How the Program Works/Safety Walls/Window control center (main.js).md>)
- [Window doorway](<2 - How the Program Works/Safety Walls/Window doorway (preload.js).md>)
- [Window page and its safety rule](<2 - How the Program Works/Safety Walls/Window page and its safety rule (index.html).md>)
- [Build App: making the portable program folder](<3 - Building and Installing/Building the App/Build App.md>)
- [The recipe that packs the engine into one ready-to-run program](<3 - Building and Installing/Building the App/Freezing recipe (api_entry.spec).md>)
- [Setup: preparing a computer to run the app from source](<3 - Building and Installing/Building the App/Setup.md>)
- [Start App: opening the app from source](<3 - Building and Installing/Building the App/Start App.md>)
- [Build Pilot Installer: making the Setup file](<3 - Building and Installing/Installer/Build Pilot Installer.md>)
- [The recipe that builds the Pilot installer](<3 - Building and Installing/Installer/Installer recipe (setup.iss).md>)
- [Lock files: the list of every outside part, with fingerprints](<3 - Building and Installing/Supply-Chain Safety/Lock files and lockfiles.py.md>)
- [GitHub's automatic checks, and the rule that keeps them cheap](<4 - Testing and Checks/Checks on GitHub/GitHub automatic checks (workflows).md>)
- [Installer tests](<4 - Testing and Checks/Tests on This Computer/Installer tests (test_pilot_installer.py).md>)
- [Screen picture and click tests](<4 - Testing and Checks/Tests on This Computer/Screen picture and click tests (harness).md>)
- [Windows test kit](<4 - Testing and Checks/Tests on the Office PC/Windows test kit (run_checks.ps1).md>)
- [Code map](<5 - Rules, Plans and Decisions/Code map (repo_map.py).md>)
- [Instructions for AI helpers](<5 - Rules, Plans and Decisions/Instructions for AI helpers (CLAUDE.md).md>)
- [Pilot build plan](<5 - Rules, Plans and Decisions/Pilot build plan (SPEC.md).md>)
- [Pilot decision log](<5 - Rules, Plans and Decisions/Pilot decision log (DECISIONS.md).md>)

### Build (12)

- [A check of the "closing best practices" list, and the gaps it filled](<6 - Work History (Handoff Notes)/Other Work/2026-09-30 Maintainer Handoff Audit.md>)
- [A tool that keeps these plain-English pages up to date](<6 - Work History (Handoff Notes)/Other Work/2026-09-30 Noncoder Automation Build.md>)
- [Stage S1: the engine's new answers and the shortened wording](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 01 Build.md>)
- [Stage S2: the window and its menus](<6 - Work History (Handoff Notes)/Stage 2 - Window and Menus/S2 - 01 Build.md>)
- [Building the new screen's frame (stage S3)](<6 - Work History (Handoff Notes)/Stage 3 - The Screen's Frame/S3 - 01 Build.md>)
- [Building every page of the new screen (stage S4)](<6 - Work History (Handoff Notes)/Stage 4 - Every Page of the Screen/S4 - 01 Build.md>)
- [Stage S5 built: the side sheet, file links, right-click menus and dialogs](<6 - Work History (Handoff Notes)/Stage 5 - Side Sheet, Links, Menus and Dialogs/S5 - 01 Build.md>)
- [Stage S6a: the first half of joining the screen's branches together](<6 - Work History (Handoff Notes)/Stage 6 - Joining the Screen to the Real Engine/S6a - 01 Build, Part 1.md>)
- [Second half of the join: the shell now runs on the real engine](<6 - Work History (Handoff Notes)/Stage 6 - Joining the Screen to the Real Engine/S6b - 01 Build, Part 2.md>)
- [Building the tooltips stage (S7): placement by Floating UI](<6 - Work History (Handoff Notes)/Stage 7 - Tooltips/S7 - 01 Build.md>)
- [File names become links, and words go to Title Case (stage S8a)](<6 - Work History (Handoff Notes)/Stage 8 - Links, Title Case and Skip Reasons/S8a - 01 Build.md>)
- [Two-word reasons for the Folders Skipped dialog (S8b)](<6 - Work History (Handoff Notes)/Stage 8 - Links, Title Case and Skip Reasons/S8b - 01 Build (Two-Word Skip Reasons).md>)

### Review (22)

- [First independent check of the shell's engine job (S1): nine findings](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 02 Review 1.md>)
- [Second independent check of stage S1 (the shell's engine side), after the first fix round](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 04 Review 2.md>)
- [Third independent check of the first stage's fix](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 06 Review 3.md>)
- [Fourth independent check of stage S1's firm-wide data](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 08 Review 4.md>)
- [Fifth independent check of stage S1: no problems found](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 10 Review 5.md>)
- [First independent check of the menus stage (S2)](<6 - Work History (Handoff Notes)/Stage 2 - Window and Menus/S2 - 02 Review 1.md>)
- [Second independent check of the menus job (S2): two findings](<6 - Work History (Handoff Notes)/Stage 2 - Window and Menus/S2 - 04 Review 2.md>)
- [Third independent check of stage S2 (the menus)](<6 - Work History (Handoff Notes)/Stage 2 - Window and Menus/S2 - 06 Review 3.md>)
- [Fourth independent check of stage S2: the error-log fallback](<6 - Work History (Handoff Notes)/Stage 2 - Window and Menus/S2 - 08 Review 4.md>)
- [Fifth independent check of stage S2 (the menus): no problems found](<6 - Work History (Handoff Notes)/Stage 2 - Window and Menus/S2 - 10 Review 5.md>)
- [First independent check of stage S3: the screen's frame](<6 - Work History (Handoff Notes)/Stage 3 - The Screen's Frame/S3 - 02 Review 1.md>)
- [Second check of stage S3 (after the first fix round)](<6 - Work History (Handoff Notes)/Stage 3 - The Screen's Frame/S3 - 04 Review 2.md>)
- [Third check of the screen's frame stage (S3): no findings](<6 - Work History (Handoff Notes)/Stage 3 - The Screen's Frame/S3 - 06 Review 3.md>)
- [First check of the pages stage (S4): eight findings](<6 - Work History (Handoff Notes)/Stage 4 - Every Page of the Screen/S4 - 02 Review 1.md>)
- [Second independent check of stage S4 (the pages): eight fixes confirmed, three findings](<6 - Work History (Handoff Notes)/Stage 4 - Every Page of the Screen/S4 - 04 Review 2.md>)
- [First check of stage S5: the side sheet, links, right-click menus and dialogs](<6 - Work History (Handoff Notes)/Stage 5 - Side Sheet, Links, Menus and Dialogs/S5 - 02 Review 1.md>)
- [First check of the tooltips stage (S7)](<6 - Work History (Handoff Notes)/Stage 7 - Tooltips/S7 - 02 Review 1.md>)
- [Second check of stage S7 (after the fix round)](<6 - Work History (Handoff Notes)/Stage 7 - Tooltips/S7 - 04 Review 2.md>)
- [Third independent check of stage S7 (tooltips): no findings](<6 - Work History (Handoff Notes)/Stage 7 - Tooltips/S7 - 06 Review 3.md>)
- [First independent check of stage S8a: file-name links and Title Case words](<6 - Work History (Handoff Notes)/Stage 8 - Links, Title Case and Skip Reasons/S8a - 02 Review 1.md>)
- [Second check of stage S8a (after the first fix round)](<6 - Work History (Handoff Notes)/Stage 8 - Links, Title Case and Skip Reasons/S8a - 04 Review 2.md>)
- [Third independent check of the link-keys job (S8a): no findings](<6 - Work History (Handoff Notes)/Stage 8 - Links, Title Case and Skip Reasons/S8a - 06 Review 3.md>)

### Fix round (19)

- [The fix round after the final reviews A, B and C](<6 - Work History (Handoff Notes)/Final Checks/4 Fix Pass After the Final Reviews.md>)
- [Fixing the nine problems a checker found in the shell's data layer (stage S1)](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 03 Fix Round 1.md>)
- [Fixing two out-of-date notes in the first stage's handoff](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 05 Fix Round 2.md>)
- [Shell engine, fix round 3: the `firm` answer now matches the plan](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 07 Fix Round 3.md>)
- [Adding a missing test to the firm-wide list (S1, fix round 4)](<6 - Work History (Handoff Notes)/Stage 1 - Engine Answers and Short Wording/S1 - 09 Fix Round 4.md>)
- [Menus and window job (S2): first round of fixes](<6 - Work History (Handoff Notes)/Stage 2 - Window and Menus/S2 - 03 Fix Round 1.md>)
- [Correcting one sentence in the program's map (stage S2, second fix round)](<6 - Work History (Handoff Notes)/Stage 2 - Window and Menus/S2 - 05 Fix Round 2.md>)
- [Stage S2, third fix round: what the app says when a command fails and no error log exists yet](<6 - Work History (Handoff Notes)/Stage 2 - Window and Menus/S2 - 07 Fix Round 3.md>)
- [Fourth fix round for the menus stage: the fallback error log](<6 - Work History (Handoff Notes)/Stage 2 - Window and Menus/S2 - 09 Fix Round 4.md>)
- [Stage S3 fixes after the first check](<6 - Work History (Handoff Notes)/Stage 3 - The Screen's Frame/S3 - 03 Fix Round 1.md>)
- [Second fix round for the screen's frame stage (S3)](<6 - Work History (Handoff Notes)/Stage 3 - The Screen's Frame/S3 - 05 Fix Round 2.md>)
- [Stage S4 (the pages), first fix round: eight problems fixed](<6 - Work History (Handoff Notes)/Stage 4 - Every Page of the Screen/S4 - 03 Fix Round 1.md>)
- [Stage S5 (the side sheet), first fix round: many findings fixed](<6 - Work History (Handoff Notes)/Stage 5 - Side Sheet, Links, Menus and Dialogs/S5 - 03 Fix Round 1.md>)
- [Stage S5 (the side sheet), second fix round: Jason's rulings 16 to 21](<6 - Work History (Handoff Notes)/Stage 5 - Side Sheet, Links, Menus and Dialogs/S5 - 04 Fix Round 2.md>)
- [Stage S7 fixes: how the small hint boxes load and behave](<6 - Work History (Handoff Notes)/Stage 7 - Tooltips/S7 - 03 Fix Round 1.md>)
- [Small document fix for the tooltips stage (S7, second fix round)](<6 - Work History (Handoff Notes)/Stage 7 - Tooltips/S7 - 05 Fix Round 2.md>)
- [Stage S8a fixes: file links that only show a file, and short notice words](<6 - Work History (Handoff Notes)/Stage 8 - Links, Title Case and Skip Reasons/S8a - 03 Fix Round 1.md>)
- [Link keys job (S8a): second round of fixes](<6 - Work History (Handoff Notes)/Stage 8 - Links, Title Case and Skip Reasons/S8a - 05 Fix Round 2.md>)
- [Stage S8a: file names on the firm-wide Needs Review page become links](<6 - Work History (Handoff Notes)/Stage 8 - Links, Title Case and Skip Reasons/S8a - 07 Fix Round 3.md>)

### Final check (5)

- [Final review A: safety of the engine and the app window](<6 - Work History (Handoff Notes)/Final Checks/1 Final Review A.md>)
- [Final check of the screen's display code against the plan and Jason's rulings](<6 - Work History (Handoff Notes)/Final Checks/2 Final Review B.md>)
- [Final review C: is the whole new screen complete and consistent?](<6 - Work History (Handoff Notes)/Final Checks/3 Final Review C.md>)
- [Final re-check of the whole shell after the fix pass](<6 - Work History (Handoff Notes)/Final Checks/5 Final Re-review.md>)
- [Final check of the second fix pass on the joined screen](<6 - Work History (Handoff Notes)/Final Checks/6 Final Check of the Second Fix Pass.md>)

### Rulings (3)

- [Jason's rulings on the shell build](<6 - Work History (Handoff Notes)/Jason's Rulings and Plan Updates/Jason's Rulings on the Screen.md>)
- [The shell's list of live decisions](<6 - Work History (Handoff Notes)/Jason's Rulings and Plan Updates/Live Decisions List.md>)
- [Bringing the shell plan up to date with Jason's rulings 1 to 13](<6 - Work History (Handoff Notes)/Jason's Rulings and Plan Updates/Plan Brought Up to Date with Rulings 1-13.md>)

## History

Pages whose file was removed, and earlier versions of pages that were rewritten.
They record what a page said then; they are not kept up to date.

### Retired Pages (0)

- none

### Earlier Versions (2)

- [A tool that keeps these plain-English pages up to date](<7 - History/Earlier Versions/2026-09-30 Noncoder Automation Build - until 2026-09-30.md>)
- [Code map](<7 - History/Earlier Versions/Code map (repo_map.py) - until 2026-09-30.md>)

---

Generated by tools/noncoder_pages.py stamp; do not edit by hand.
