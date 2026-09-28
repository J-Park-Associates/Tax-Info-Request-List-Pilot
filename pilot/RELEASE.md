# Pilot 0.1 - release steps

Everything that can be done in the cloud is done. Builds A, B and C are
merged into `main` (merges 7a8432e, cca50a7, 96853df), each after an
independent review and a fix round (`pilot/reviews/review-1.md`,
`review-2.md`). What is left needs Windows, so it is Jason's, on the office
PC. Allow about 45 minutes.

## What is in 0.1

- **Its own names on the PC:** program *Tax Document Tracker Pilot*, data
  folder `%LOCALAPPDATA%\tax-document-tracker-pilot`, scheduled task
  *Tax Document Tracker Pilot* - it cannot touch the real product.
- **Pilot badge, terms screen and guided tour** (approved wording, P20/P22).
- **Schedule setting:** the Schedule button - on/off, first run time, how
  often - saved per computer and used everywhere the schedule is registered.
- **Installer:** per user, no admin rights, Start-menu shortcut; uninstall
  removes the program and its scheduled task only.
- **Tester Guide:** `pilot/Tester Guide.md`.

## The quick way: the Windows test kit (P28)

Any Windows 10/11 test machine will do - it need not be the office PC.
Install Claude Code there (the desktop app, so it can use computer use), open
it in an empty folder, and paste the prompt in
[`wintest/PROMPT.md`](wintest/PROMPT.md). It runs every check below itself -
the automated part with `wintest/run_checks.ps1`, the clicks through the
installed app, and the uninstall with `wintest/uninstall_checks.ps1` - on
made-up sample documents only (`wintest/make_samples.py`), and delivers
`RESULT.md` plus a `[WINTEST]` comment on board #5. It stops before tagging;
the tag and sending stay yours.

## Steps on the office PC (by hand)

Use a Windows account that does not run the firm's real schedule, and a
**copy** of a few client folders (P15).

1. **Install the tools once:** Python 3.11+, Node, git (already there for the
   main app), and **Inno Setup 6.3 or later** from jrsoftware.org (free).
2. **Get the code:**
   `git clone https://github.com/J-Park-Associates/Tax-Info-Request-List-Pilot.git`
   (or `git pull` in an existing copy). Make sure `git status` is clean.
3. **Run the whole suite under the office's Python** (the cloud could run
   Python 3.11 only, without the reading engines): `python -m pytest -q`.
   Every test should pass on the office PC. In the cloud the only failures
   were tests that need rapidocr/onnxruntime, extract-msg or the scanned-page
   reader, and each failed the same way on the untouched pre-pilot code. If
   anything fails on the office PC, stop and hand it to the orchestrator.
4. **Build:** double-click `pilot\Build Pilot Installer.bat`. It refuses an
   uncommitted tree, builds the app, compiles the installer, and prints its
   path (`build-portable\installer\Tax-Document-Tracker-Pilot-Setup-0.1.exe`)
   and SHA-256. Keep that hash.
5. **Install and try it** (the checklist testers will follow):
   - SmartScreen warns (unsigned): *More info* -> *Run anyway*.
   - First launch: the terms screen shows; Escape does nothing; tick the box,
     *I agree. Continue.*; the tour starts. Walk all 11 steps.
   - Choose a clients folder (the copy), create a household, drop a W-2, a
     1099, a phone photo and an unknown document into *Drop files here*,
     press **Scan**. Check: originals moved to the year folder, named copies
     in `Prepared`, the unknown file in Needs Review, Status opens.
   - **Schedule** button: turn it off -> the task disappears from Task
     Scheduler; turn it on at a new time -> the task shows that time; restart
     the app -> the choice is kept.
   - The header shows **Pilot edition 0.1**; the Tour button replays the tour.
6. **Uninstall** (Settings -> Apps -> Tax Document Tracker Pilot). Check: the
   scheduled task is gone; the clients folder copy, `settings.json` beside
   where the program was, and `%LOCALAPPDATA%\tax-document-tracker-pilot`
   are still there.
7. **Tag and send:** `git tag pilot-0.1 && git push origin pilot-0.1` (never a
   `v...` tag). Send testers the installer, its SHA-256 and
   `pilot/Tester Guide.md`. Problems come back to admin@jparkassociates.com.

## Known and accepted

- The installer is unsigned, so Windows warns once (P4).
- Scans read slowly without the optional graphics-card pack.
- The cloud checked Python 3.11 only; step 3 covers the office's Python.
- If anything in steps 3-6 fails, note what you saw and hand it back to the
  orchestrator session; nothing ships until it passes.
