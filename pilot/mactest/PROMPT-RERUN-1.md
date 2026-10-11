# Mac check, re-run 1 - prompt for Claude Code on the test Mac

This re-run checks the fixes from the first Mac check (2026-10-10, commit
`6f88e3e`) and walks the steps that check could not. It is the standing
prompt, `pilot/mactest/PROMPT.md`, narrowed to what changed and what has not
run: read that file first and keep every one of its SAFETY rules; this file
says only what is different. Decisions P256 to P259 and
`pilot/SPEC-mac-check-fixes.md` are the source of every expectation below.

## For Jason, before the session starts

1. The branch is `claude/trusting-tesla-or0wm2` at commit `20e02e6` or later.
2. In the session's permission settings, allow reading these before you
   start, so the steps the first check left NOT VERIFIED can be verified:
   `~/Library/Application Support/tax-document-tracker-pilot` (the data
   folder, its run log `runs.log` and `tracker-errors.log`),
   `~/PilotTest` whole (the inbox included), and the launchd plist named in
   the safety rules. If a rule still denies one, the prompt's safety
   paragraph says what the session records.
3. Turn on computer use in the Claude desktop app. The first check drove the
   app through its own page because the tools were absent; the Gatekeeper
   steps, the Finder steps and the dialogs need the real thing.
4. Say whether Google Drive for desktop is signed in and which Drive test
   folder to use. The first check ran on a plain folder, so every Drive step
   is still open.
5. Say whether this Mac has had the Console since the first check (it has:
   the app was left in Applications on purpose). Step 2 of the standing
   prompt then does not stop; record what it found.

## 1. Get the code

As the standing prompt's step 1, on the branch above. Read
`pilot/SPEC-mac-check-fixes.md` whole (it is short) and section 3 of
`pilot/SPEC-mac.md`, which now says what the app shows.

## 2. A clean Mac

As the standing prompt's step 2, but a Mac that has had the Console is
expected: the app in Applications and its data folder from the first check.
Record them. Do not delete anything. Quit the app if it is open, then remove
only what the walk itself re-creates: nothing, unless Jason says otherwise.

## 3. Automated part

Run:

    bash pilot/mactest/run_checks.sh --tests test_api,test_after_install,test_shell,test_shell_menu,test_pilot,test_pilot_ui,test_runner,test_single_source,test_layers,test_repo_map,test_tripwire,test_errors

Why these and not the first check's twenty-six: the first check ran those on
this Mac at `6f88e3e` and they passed; this re-run tests the files the three
jobs since then changed, each on the system it is for. `test_api` and
`test_after_install` cover the `last-pass` command, the `running` flag and the
reply's `wait` sentence (P256, P257); `test_shell` and `test_shell_menu` the
side panel's "Sorting" line, the watcher, the Details disclosure and the
toasts (P256, P257, P259); `test_pilot` the kit's run-log check, the three new
sample files and the prompt's wording (P258); `test_pilot_ui` the stylesheet
and the screenshot harness; `test_runner` because one comment in the runner
changed and its dataclass must not have moved; the last five are the guards
every change runs. Not the sorting engine's tests (Jason, 2026-09-29), and
not the whole suite unless Jason asks.

The script also rebuilds the disk image, checks the bundle, makes the frozen
smoke and builds the sample pile. Two things in it changed since the first
check, so look at them in `checks.json`:

- `frozen_smoke` must now say `reader=processor` without a note: the check
  reads the run log's summary line, not its first line (note 3 of the first
  result was the kit's own bug).
- `sample_folder` must hold 17 files, the first check's 14 plus
  `Donation Receipts 2025 with macros.xlsm`, `Email from John Smith.msg` and
  `Scanned forms.zip`.

## 4. The hands-on part

With computer use, on the installed app, screenshots into
`~/PilotTest/results/screens`, PASS only when seen. Steps the first check
passed on code that did not change are not repeated; each step below says
why it runs. The order matters for the same reason as in the standing
prompt.

### 4a. The fixes (P256 to P259): the walk's steps where the app now says something new

Run the standing prompt's H2 steps 1 to 3, 5 to 9, 10, 12 and 14, with these
changed expectations. Every other detail of a step is as the standing prompt
says.

- **Step 1 and 3, Download and Open Anyway.** NOT VERIFIED last time. Mark
  the disk image as downloaded with the standing prompt's `xattr` line, so
  Gatekeeper blocks the first open, and walk Open Anyway with Jason typing
  the password. Record every dialog word for word. Chosen because it is the
  first thing a buyer meets and nobody has seen it yet.
- **Step 5, opened from the wrong place** (after step 14, as always). The
  first screen shows **Machine Needs Attention**, and because it is the setup
  page its **Details** is already open (P259 Q2), showing the engine's
  sentence ("The app is running from /Volumes/…, a disk image or a disk other
  than this Mac's own. Drag it into Applications…"). Record the sentence from
  the screen, not the error log. Do the `~/Downloads` variant too, quarantined
  as in step 1: its sentence begins "macOS is running the app from a
  temporary copy". No schedule is set up (`launchctl print` finds no service).
  Chosen because the first check saw only the heading (finding 2) and never
  tried the Downloads copy.
- **Step 7, the clients folder.** On Jason's Drive test folder this time, if
  he has Drive for desktop; the iCloud and Dropbox refusals first, as the
  standing prompt says. Record the Drive permission dialog's exact words
  (H14). Chosen because the whole first check ran on a plain folder.
- **Step 8, the schedule installs itself.** After Start, a **toast** at the
  bottom of the window, six seconds, says "This computer (<name>) now runs
  the schedule for this clients folder: every day from 07:00, every 120
  minutes." Read it at once; it is not a notice. The Time Machine job shows
  nothing when it works (the first check's kit expected a sentence that
  never existed); prove it with H9's `tmutil` line right after. "Background
  Items Added" is recorded as before. Chosen because the toast is new (P257)
  and the Time Machine expectation was wrong.
- **Step 9, the first pass.** While the pass runs, the side panel's last-sort
  line says **Sorting** with a quiet bar and there is **no** "Sort Failed"
  anywhere. When it ends, within a minute and without Refresh, the line says
  "Sorted <time>", the Overview's counts change and Needs Review shows its
  files. Then click into another window and back: the page is already
  current. Record the three states with times. Then the engine's line reads
  "Last scheduled pass: <time>, succeeded." and the originals have moved byte
  for byte, as before. Chosen because this is finding 1 of the first check,
  the one a buyer sees.
- **Step 10, open a review copy.** The pile now holds the three files. In
  Needs Review open `Donation Receipts 2025 with macros.xlsm`: it opens in
  Excel (or the default spreadsheet program), and the app shows the Mac's
  Protected View sentence as a page notice each time (open it twice). Also
  open `Email from John Smith.msg` and `Scanned forms.zip` from their rows and
  record what the app says for each and what the pass did with what they
  held: the email's PDF (a 1099-INT from Riverside Savings Bank) and the
  zip's scan should have been filed from inside them. Chosen because the
  first check could not walk this step at all (note 4).
- **Step 12, an upgrade.** Build a second disk image, install over the first
  with Replace, Open Anyway again. At the first open the schedule
  re-registers itself and a **toast** repeats step 8's sentence; record
  whether the Drive prompt came back (H14). Chosen because the first check
  saw nothing at all at an upgrade's first open (finding 2).
- **Step 14, removal.** As before; it passed, but it must run so step 5 can
  follow it. Record only that the sentence is unchanged.

Two cosmetic points the review left for a real window, during step 5 or
whenever a notice with Details is on the screen: (a) is the notice's first
line shorter in height than a notice without Details beside it, and by how
much (a screenshot); (b) press Tab from the search box through the notice:
record the order in which Details, Retry (if any) and Dismiss take focus.
Neither is a FAIL; both are recorded for Jason.

### 4b. The steps the first check could not run, on unchanged code

Each is NOT VERIFIED today, which is why it runs; none is a repeat.

- **Step 11 and H13, the next morning.** Leave the Mac on and signed in
  overnight after step 9 (before step 12). The last-pass line the next day
  names a pass from that morning and is not amber. Around one scheduled time
  of that day, do H13: sleep five minutes before, wake ten minutes after, a
  pass starts within about a minute of waking. Record the times from the run
  log and the Overview.
- **Step 13 and H5, switched off by hand.** System Settings, General, Login
  Items, Allow in the Background: turn the Console off. The app's next start
  shows **Setup Needs Attention**, and under its Details the sentence that
  begins "macOS has switched the schedule off for this app". Turn it back on and confirm the next pass runs.
- **H3's missing half.** With the app closed, drop one more made-up file
  (copy any sample from `~/PilotTest/smoke` under a new name) into Drop files
  here before a scheduled time; after the pass, the file has moved and the
  app, opened afterwards, shows it filed. The first check could not drop a
  file because the inbox was denied to it.
- **H4, H6, H7, H8, H12, H14 on the Drive test folder**, as the standing
  prompt says each, only if Jason has Drive for desktop. If not, record all
  six NOT VERIFIED with that reason in one line and move on.
- **H10, the season-sized pass**, last, only if Jason says yes: it is a
  working day on its own and decides nothing about these fixes.
- **H1b** last of all, as the standing prompt says.

Not in this re-run: step 4 (no Intel or macOS 13 Mac is at hand), H11 (the
menu bar passed on unchanged code), H2 step 6 (the terms passed on unchanged
code; it is walked only because step 7 follows it).

## 5. What every step records, 6. Report

As the standing prompt's steps 5 and 6. In the result's "Summary", say in
one line each whether findings 1 and 2 of the first check are gone on this
build, and whether notes 3 and 4 are. Use the standing template; its rows
5, 8, 9, 10 and 12 already say the new expectations.

## 7. Deliver

No pull request carries this branch yet. Leave `RESULT.md` at
`~/PilotTest/results/RESULT.md`, tell Jason its path, and stop. Do not create
the results branch or post anywhere unless Jason says so.
