# Mac check - prompt for Claude Code on the test Mac (SPEC-mac R33, pilot decision P254)

This is `pilot/wintest/PROMPT.md` for a Mac: the same safety rules, the same
shape (an automated script, then a hands-on part, then a result file), and
the steps the port needs a real Mac for. The port is not accepted until this
has been run once on an Apple silicon Mac and every step has a result.

Before you start, on the test Mac:

1. The Mac must have Apple silicon and macOS 14 or later, and the Terminal
   must not be running under Rosetta. The walk below is meant for a Mac that
   has never had the Console: the app, its data folder and its schedule
   absent (the prompt checks, and stops and asks if any of them is there).
2. Install, from their own sites, the tools the script will ask for if it
   cannot find them: Python 3.14 (the macOS installer from python.org),
   Node.js LTS (nodejs.org) and the Command Line Tools
   (`xcode-select --install`). The script installs nothing itself.
3. Get the code into an empty folder directly in your home folder, such as
   `~/pt` (not under Desktop, Documents or Downloads, which macOS guards, and
   not in Google Drive or iCloud). A git clone is best; without GitHub
   sign-in, download it from GitHub (Code -> Download ZIP) and unzip it.
4. For the Google Drive steps: Google Drive for desktop signed in, and an
   empty folder you made there for this test only, such as `PilotTest-Clients`
   (a folder in a shared drive is best, because that is how the firm uses it).
   Nothing but the made-up sample documents is ever put in it.
5. Open the **Claude desktop app** and turn on **computer use** (it lets
   Claude click through macOS's dialogs and the installed app). Without it,
   Claude walks you through the clicks and records your answers. You type the
   Mac's password yourself when macOS asks; Claude never does.
6. Open Claude Code in the folder that holds the code, and paste everything
   in the box below.

```
You are running the Mac check for Tax Document Console on this computer, for Jason Park (a CPA,
not a programmer - report in plain English). Follow these rules the whole time:

SAFETY - never break these:
- Generative AI never reads client financial documents. Use ONLY the made-up sample documents
  this test creates under ~/PilotTest (Clients, smoke, season), and the one Google Drive test
  folder Jason names, which holds copies of those made-up documents and nothing else. Never open,
  list or read any other folder or document on this computer. If a file picker, Finder window or
  Drive's sidebar shows other folders, do not read their contents; go straight to the test
  folder. If a screenshot shows a name that is not made up (a client's folder in Drive's list),
  delete that screenshot, say so, and never describe the name.
- Nothing is ever sent: do not send email, and do not upload files anywhere except (a) the one
  results commit described in step 7, only if Jason says yes, and (b) the made-up samples copied
  into Jason's Drive test folder, which Google Drive syncs, only after Jason says yes once.
- Do not tag, release or send the disk image. Do not change the program's code; this is a test,
  not a fix. If something fails, record it.
- Never type, read, store or ask for the Mac's password: macOS asks Jason, and Jason types it.
  Never use sudo. Never turn off Gatekeeper (no spctl --master-disable) and never remove the
  quarantine mark from the app or the disk image: the walk tests exactly what a buyer sees.
- Never toggle iCloud's "Desktop & Documents Folders", Time Machine's settings, or Google Drive's
  Stream/Mirror setting: they move or sync real files. Ask Jason which state they are in.
- Start the app only from /Applications (or ~/Applications), never from build-portable or the
  checkout. Quit it with Command-Q, never force it.
- Stop and ask Jason if: macOS asks for a password or an administrator, a dialog cannot be handled,
  or any step would touch a folder outside ~/PilotTest, the checkout, /Applications, the app's own
  folders (~/Library/Application Support/tax-document-tracker-pilot, ~/Library/Application
  Support/Tax Document Console, ~/Library/Application Support/Tax Document Tracker Pilot and
  ~/Library/LaunchAgents/com.jparkassociates.taxdocumentconsole.schedule.plist), the empty folders
  named PilotTest-Empty that H6 and step 7 of the walk make (in ~/Documents, in iCloud Drive and in
  Dropbox or OneDrive), ~/Downloads (only the disk image and the app copied there for steps 1 and 5,
  removed afterwards), ~/pt-source (the fresh clone H1b makes), or Jason's Drive test folder.
- If this session's permission rules deny a folder the walk needs (the app's data folder, the run
  log, the inbox), record that step NOT VERIFIED naming the rule and tell Jason; never work around
  a rule. If desktop computer use is absent, the app may be driven through its own page
  (Electron's debugging port) with the folder picker stood in for at the app's picker boundary;
  say so at the top of the result, and every step that needs a macOS dialog or the Mac's password
  is NOT VERIFIED.

1. GET THE CODE. If the code is not already in this folder, clone
   https://github.com/J-Park-Associates/Tax-Info-Request-List-Pilot (the branch Jason names; main if
   he names none). If it came as a downloaded ZIP, use it as it is: the script makes a local
   snapshot commit and marks the tree check NOT VERIFIED. Read pilot/RELEASE.md, pilot/SPEC-mac.md
   sections 3 and 4, and pilot/mactest/RESULTS-TEMPLATE.md.

2. A CLEAN MAC. Check, without opening any of them, whether any of these exist: the app in
   /Applications or ~/Applications; the three folders and the file named in the safety rules above.
   If any exists, stop and tell Jason what you found: the walk is for a Mac that has never had the
   Console, so he decides whether to continue (and nothing is deleted without his word). Record
   the answer under "Machine" in the result file.

3. AUTOMATED PART. Run:
     bash pilot/mactest/run_checks.sh --tests test_settings,test_after_install,test_scheduling,test_runner,test_locking,test_fsio,test_checkpoint,test_store,test_ledger,test_layout,test_filer,test_validators,test_ocr,test_api,test_api_entry,test_build,test_shell,test_shell_menu,test_single_source,test_layers,test_repo_map,test_tripwire,test_content_check,test_pilot,test_errors,test_lockfiles
   Why these: the first twenty-two are the files this port changes (SPEC-mac R33), each run on the
   system it changes for; test_content_check and test_pilot are the files the port's last job
   changes (R36), and test_errors and test_lockfiles are named by the jobs that changed the
   wording and the build lock. Not the whole suite: the sorting engine's own tests are not rerun
   (Jason, 2026-09-29). Run the whole suite (the script with no --tests) only if Jason asks.
   The script checks the tools, makes the environment, runs ruff and the map check, runs each test
   file in its own process, builds the disk image, checks what the bundle holds, makes the frozen
   smoke (the package answers, reads the pile as the source does and starts a reading child), and
   makes the sample clients folder. Results go to ~/PilotTest/results/checks.json, a log beside it.
   If it stops because a tool is missing, show Jason the line it printed, ask once, and run the
   script again once he has installed it. A failing test file is recorded, not fixed; carry on if
   the disk image still built. A test file that fails only on the Mac is the point of this check:
   record its name and the first failing assertion, word for word.

4. THE HANDS-ON PART. With computer use, on the installed app. If you have no computer use, do
   not skip this part: tell Jason exactly what to click and what to look for, one step at a time,
   and record his answers. Take a screenshot at each step into ~/PilotTest/results/screens. Each
   step names what the person should see; anything else is a FAIL with a screenshot. A step that
   cannot be done on this Mac (no second network, no PC, no macOS 13) is NOT VERIFIED with the
   reason, never PASS. Steps that already passed on unchanged code are not repeated.

   The order, because several steps need the app in a state another step ends: the automated part;
   H2's steps 1 to 3 and 6 to 9 (H9 right after step 8, H14's words as they appear); H3; H4, H6, H7,
   H8 and H12 on the Drive test folder; step 10; H11; step 11 the next morning (H13 around one
   scheduled time of that day); step 12; step 13 with H5; step 14; then step 5's two variants,
   step 4, H10 and last H1b. Each step says why it is chosen.

   H1. The build and the frozen smoke (R13, R16, R17, R31). Chosen because the freeze, the reading
   child under "spawn", the ad-hoc seal and the disk image can only be made and checked on a Mac.
   The script of step 3 does it: its checks build, bundle and frozen_smoke are H1's result. The
   other half of H1, setup.command and start.command from a clean clone, is H1b, done last.

   H2. THE BUYER'S WALK (SPEC-mac section 3, steps 1 to 14). Chosen because the walk is the
   product: it is the day a buyer's first office Mac goes through.
     1. Download. The disk image is build-portable/installer/Tax-Document-Console-<version>-mac-arm64.dmg
        and its .sha256 file, built above. Jason would download it; the built file has no download
        mark, so make one the way a browser does, and say which you did: ask Jason first whether he
        can bring the file in the way a buyer does (AirDrop, or Safari from a link he controls); if
        not, copy it to ~/Downloads and run
          xattr -w com.apple.quarantine "0083;$(printf '%x' $(date +%s));Safari;" ~/Downloads/<the .dmg>
        Then, in Terminal, shasum -a 256 <file> must print the same 64 characters the .sha256 holds.
     2. Install. Double-click the .dmg. A window shows Tax Document Console and an Applications
        folder. Drag the app onto Applications, then eject the disk image.
     3. First open. Open the app from Applications. On macOS 15 or later: "“Tax Document Console”
        Not Opened" and "Apple could not verify …"; click Done. On macOS 14: the app "can't be opened
        because Apple cannot check it for malicious software"; click OK. Open System Settings,
        Privacy & Security, scroll to Security: "“Tax Document Console” was blocked…". Click Open
        Anyway, Jason enters the Mac's password, then Open Anyway again. Record the macOS version and
        the exact words of each dialog you saw.
     4. The wrong Mac. This Mac passes the floor, so the refusal cannot be seen here: on a macOS 13
        Mac (if one is at hand; the bundle claims 13.0, Electron's own floor) the app shows the floor
        sentence ("Tax Document Console needs a Mac with Apple silicon running macOS 14 or later; this
        Mac has …") and quits, and nothing is written: on a Mac that never had the Console, none of
        the data folder (~/Library/Application Support/tax-document-tracker-pilot), the settings
        folder (~/Library/Application Support/Tax Document Console) or the window's own folder
        (~/Library/Application Support/Tax Document Tracker Pilot) exists afterwards; check each.
        An Intel Mac gets macOS's own message. With no such Mac at hand, NOT VERIFIED, with the
        reason.
     5. Opened from the wrong place. Done after step 14, so the first launches of the walk are the
        right ones. Mount the disk image again and open the app straight from it, and once from
        ~/Downloads (copy it there first with ditto, quarantined as in step 1; delete the copy after).
        The first screen must show the heading Machine Needs Attention; its Details shows the
        sentence for that place ("The app is running from … a disk image or a disk other than this
        Mac's own …", and "macOS is running the app from a temporary copy …"), each ending "the
        schedule runs only the copy in Applications", and no schedule is set up: check that
          launchctl print gui/$(id -u)/com.jparkassociates.taxdocumentconsole.schedule
        answers that it cannot find the service. Record both sentences word for word, from Details.
        (Open Anyway may be needed again for these copies; quit each with Command-Q.)
     6. The terms. The app opens on "Before you start: this is a Pilot". Tick "I have read this and
        will keep my own backups", type a name (a made-up one), and click Sign and Accept.
     7. The clients folder. "Choose Your Clients Folder" appears. First the refusals, without
        browsing anyone's real folders: with Jason's yes, make an empty folder named PilotTest-Empty
        in iCloud Drive and one in Dropbox or OneDrive (if this Mac has any; otherwise NOT VERIFIED
        for that one), choose each by typing its path in Choose Folder (Command-Shift-G) and never by
        clicking through the sidebar, and remove each afterwards. Each must be refused with the app's
        sentence ("... is in iCloud Drive ..." or "... is kept by <service> ..."). Then click Choose Folder…, pick the test folder (~/PilotTest/Clients
        for a plain folder; for the Drive part, Jason's Drive test folder under Google Drive in
        Finder's sidebar, after the made-up samples have been copied into it with Jason's yes:
        ditto ~/PilotTest/Clients "<the Drive test folder>"), then click Start. macOS may ask to let
        Tax Document Console access files in Google Drive. Click Allow, and record the prompt's exact
        words (this is H14, below). Do the walk on the Drive folder if Jason has Google Drive for
        desktop; on ~/PilotTest/Clients otherwise, and say which.
     8. The schedule installs itself. macOS shows "Background Items Added": record which name it
        gives (the app's, or its developer's). A toast (bottom of the window, six seconds) says
        "This computer (<name>) now runs the schedule for this clients folder: every day from 07:00,
        every 120 minutes."; read it at once. No button was pressed. The Time Machine job runs here
        too, and the app says nothing when it works (H9 checks the exclusion with tmutil). If it was
        refused, Details under Setup Needs Attention says "The app's data folder (...) could not be
        left out of Time Machine backups ..."; record it word for word.
     9. The first pass. Within a minute the schedule's first pass runs. If macOS asks again whether
        the schedule may use Google Drive's files, click Allow (record the words). While the pass
        runs the side panel says Sorting; when it ends the counts and Needs Review follow by
        themselves within a minute (sooner on a click into the window), with no Refresh. Then the
        Overview's line reads "Last scheduled pass: <time>, succeeded." The sample documents are
        filed and their originals have moved, byte for byte, into the client's folder for the year.
     10. Open a review copy. The sample pile holds three files for this step, made up by make_samples.py:
        Donation Receipts 2025 with macros.xlsm (the macro workbook; no macro is inside, its name is
        what marks it), Email from John Smith.msg (an email holding one made-up PDF) and Scanned
        forms.zip (a zip holding one made-up scan). In Needs Review, open the sample macro workbook.
        It opens in Excel (or the default spreadsheet program), and the app shows "Protected View
        does not exist on a Mac, so this file opened normally. Keep macros off in Excel, Word and
        PowerPoint: Settings > Security > Macro Security > Disable all macros without notification."
        as a notice on the page, not a dialog, each time it is opened (open it twice). Record where
        the email and the zip ended up (the _Opened folder for the year, and what Needs Review holds).
     11. The next morning. Leave the Mac on and signed in overnight (asleep is fine; Jason closes the
        lid or lets it sleep). The next day, the last-pass line names a pass from that morning and
        is not amber. Record the time.
     12. An upgrade. Quit the app (Command-Q). Run ./build-mac.sh a second time to make a second disk
        image from the same commit (an ad-hoc signed rebuild is a different build to macOS, which is
        what an upgrade is to its permissions; record its SHA-256 beside the first), mark it as
        downloaded as in step 1, install it as in step 2, choosing Replace, and repeat step 3's Open
        Anyway. At its first open the app sets the schedule up again by itself, and a toast repeats step
        8's sentence. The clients folder is still chosen. If the next pass reports "macOS did not let
        the schedule read the clients folder", open the app and allow it when asked; the pass after
        that succeeds. Record whether the Drive prompt came back (it should, for an unsigned build).
     13. Switched off by hand. In System Settings, General, Login Items, under Allow in the
        Background, turn Tax Document Console off. The app's next start shows "macOS has switched the
        schedule off for this app (System Settings > General > Login Items, Allow in the Background).
        Switch Tax Document Console back on there; the app cannot do it for you." Turn it back on.
     14. Removal. Choose Tools, then Remove the Schedule From This Mac…. The app says "The schedule
        is removed from this Mac. To remove the app, quit it now and drag it from Applications to the
        Bin; opening it again sets the schedule up again." Quit, then drag the app to the Bin. Then
          launchctl print gui/$(id -u)/com.jparkassociates.taxdocumentconsole.schedule
        answers that it cannot find the service, and the plist is gone from ~/Library/LaunchAgents.
        The data folder, the settings and the clients folder remain (decision P12): check each exists.

   H3. The launchd job runs a pass with nobody at the Mac, and Repair (R24, R28, R30). Chosen
   because launchd, not the app, starts the pass, and only a Mac shows whether it works unattended.
   Do this between steps 9 and 11, with the app installed and the schedule on. Put one new made-up
   PDF in a household's Drop files here. Then run in Terminal
     ( sleep 30; launchctl kickstart gui/$(id -u)/com.jparkassociates.taxdocumentconsole.schedule ) &
   and ask Jason to lock the screen (Control-Command-Q) within 30 seconds and come back after two
   minutes. The Overview's "Last scheduled pass" must now name that time and say it succeeded, and
   the new document must be filed: a locked Mac must not need a permission prompt. Then choose
   Tools, Repair the Schedule: record the output of launchctl print for the label before and after
   (state, program, the plist's path), anything macOS or launchctl said about bootout or bootstrap
   ("5: Input/output error" is worth the exact words), run  plutil -lint
   ~/Library/LaunchAgents/com.jparkassociates.taxdocumentconsole.schedule.plist , and confirm a
   Repair does not start a second first pass for the same program.

   H4. The lock race on the Drive folder, and runbook section 6 L2 (R19, R22). Chosen because
   decision 171 measured the engagement lock on Windows' Drive only; a Mac's File Provider must be
   measured on its own. In Jason's Drive test folder (a return's folder inside it is fine), run
     .venv/bin/python -m tracker.locking race "<a folder in the Drive test folder>" --processes 8 --rounds 30
   It must print "one holder in every round"; record the whole output, and if any round fails, the
   lines it names. Also record whether the volume refused a full flush: look in the data folder's
   tracker-errors.log for "This volume refuses a full flush to the disk" (it is said once, and is
   not a failure). For L2 you need a second computer signed in to the same Drive: if Jason has the
   office PC at hand, he makes one small change to a test return there, Drive syncs, and the Mac's
   next pass must name that line as written on the PC; otherwise NOT VERIFIED.

   H5. The Allow in the Background switch (R27). Chosen because R27 assumed macOS reports the
   switch through launchctl print-disabled, and the tests assume macOS unloads a switched-off agent;
   nobody has checked either. During step 13, before switching it off, after switching it off and
   after switching it on again, run both
     launchctl print-disabled gui/$(id -u) | grep taxdocumentconsole
     launchctl print gui/$(id -u)/com.jparkassociates.taxdocumentconsole.schedule ; echo "exit $?"
   and record the exact output of the first, and the second's exit code and its "state =" line, each
   time (print-disabled: true or false for the label, or nothing; print: loaded, with its state, or
   "Could not find service"). If print-disabled does not change when the switch does AND the agent
   stays loaded when switched off (print still answers 0), say so: then the app cannot tell, the
   last-pass line's amber is the only signal, and R27's sentence will not be shown.
   Re-run 1 found that on macOS 26 print-disabled stays "enabled" while the switch is off, and the
   agent is unloaded (print answers 113) with its file still in ~/Library/LaunchAgents; the app
   reads that as the switch (P260). So also record, after switching it off and quitting and
   starting the app: that Setup Needs Attention shows, with the sentence "macOS has switched the
   schedule off for this app..." under Details; that the switch stays off in Login Items (the app
   registered nothing); and, after switching it on again and starting the app once more, that the
   sentence is gone.

   H6. iCloud's Desktop & Documents signal (R5). Chosen because R5 detects the setting by a folder
   existing, and nothing has shown that is reliable. Ask Jason whether iCloud Drive's "Desktop &
   Documents Folders" is on or off on this Mac (never change it). Run
     ls -d "$HOME/Library/Mobile Documents/com~apple~CloudDocs/Desktop"
   and record whether the folder exists. Make an empty folder  ~/Documents/PilotTest-Empty  and try
   to choose it in the app's Choose Folder: with the setting on it must be refused with the iCloud
   sentence, with it off it must be accepted. If the folder's presence does not match what Jason
   says, the signal is unreliable and R5 must refuse Desktop and Documents outright: FAIL, say so.
   Remove the empty folder afterwards. With only one state available, the other is NOT VERIFIED.

   H7. The machine name on two networks (R21). Chosen because locks and the schedule's designation
   name the Mac by it. Record, on the first network:
     scutil --get LocalHostName
     .venv/bin/python -c "from tracker import locking; print(locking.this_host())"
     .venv/bin/python -c "import platform; print(platform.node())"
   Jason then moves the Mac to a second network (a phone's hotspot) and you record the same three
   again. this_host() must be identical on both; platform.node() changing (a "-2" suffix, a router's
   name) is exactly what R21 avoids and is worth recording. Without a second network, NOT VERIFIED.

   H8. A Stream-mode Drive file (R10). Chosen because a file Drive has not downloaded must make the
   pass wait, not download it. Only if Google Drive for desktop is in Stream mode (ask Jason; never
   change the mode). In the Drive test folder, in a household's Drop files here, take one made-up
   PDF and in Finder choose Remove Download (Offline access: Online only). Confirm it is not
   downloaded: ls -lO "<file>" shows the flag "dataless". Run a pass (the Sort icon, or the
   schedule). The pass must leave the file where it is and report it as waiting for sync, and the
   file must still be "dataless" afterwards (ls -lO again); open the Overview and check the same.
   In Mirror mode, or with no Drive, NOT VERIFIED.

   H9. Time Machine (R7). Chosen because the exclusion is a command only a Mac can check. After
   step 8:
     tmutil isexcluded "$HOME/Library/Application Support/tax-document-tracker-pilot" "$HOME/Library/Application Support/Tax Document Tracker Pilot"
   must print [Excluded] for both folders. Record the output. (It is checked before step 14, which
   leaves the folders in place.)

   H10. A season-sized pass, timed on the CPU reader (R32, P247). Chosen because it decides whether
   CoreML is built: the pass must finish well inside the two-hour schedule slot. This is the worst
   case, a first pass over a whole season's scans. Build the made-up season (400 households, 3
   distinct scans each, so the reader has 1,200 to read; the reader keeps a verdict by content, so
   scans that were alike would be read once). Do this once the walk is done and the app is quit,
   with the frozen API from the build, in throwaway folders (never the app's own data folder). Save
   the program printed under "THE SEASON BUILDER" at the end of this prompt as
   ~/PilotTest/season_builder.py (outside the checkout), then, from the checkout:
     mkdir -p ~/PilotTest/season-data ~/PilotTest/season-settings
     TRACKER_DATA_HOME=~/PilotTest/season-data .venv/bin/python - ~/PilotTest/Clients-season 400 3 < ~/PilotTest/season_builder.py
   then set the root and time the pass the way the schedule runs it:
     TRACKER_SETTINGS_DIR=~/PilotTest/season-settings TRACKER_DATA_HOME=~/PilotTest/season-data .venv/bin/python -m tracker.settings ~/PilotTest/Clients-season
     TRACKER_PRODUCT_NAME="Tax Document Console" TRACKER_DATA_HOME=~/PilotTest/season-data /usr/bin/time -l "<the frozen API in build-portable/dist/.../Contents/Resources/tracker-api/tracker-api>" --run --settings ~/PilotTest/season-settings --reminders never --log ~/PilotTest/results/season-runs.log
   Record the elapsed minutes, the peak memory footprint /usr/bin/time prints, how many files were
   read (the run log), and whether the log says "memory limit" for any reading. PASS when the pass
   ends within 60 minutes (half the slot, the kit's reading of "well inside"; Jason may change the
   number) and no reading hit its 4 GB limit; otherwise FAIL, and CoreML becomes its own measured
   job. If 400 households cannot be built or read in a working day, say how many were, and the
   per-household time.

   H11. The menu bar and Command-Q (R14). Chosen because only a Mac shows Electron's menu. With the
   app open: the first menu is the app's own (About, Hide, Hide Others, Quit) and Command-Q quits;
   Command-H hides it; File has no Quit item; no menu or item shows a leading "&" or an underlined
   letter (Tools, Help, not &Tools); Tools holds "Remove the Schedule From This Mac…". After Command-Q, no waiting helper is left:  pgrep -f tracker-api
   prints nothing (a scheduled pass that is running is the only exception; check which). Record the
   exact menu titles and the icon in the Dock, in Finder and in the disk image's window (the app's
   icon, not Electron's). Right-click a moved file in the app: the item reads "Show in Finder".

   H12. An accented name written on the PC and moved on the Mac (decision 190 (5)). Chosen because a
   PC writes é as one composed character and a Mac may hand it back decomposed. Preferably on the
   office PC: in the Drive test folder, in a household's Drop files here, save a made-up file named
   "Zoë Müller W-2.pdf". On the Mac, once Drive has synced it, run a pass. The original must move
   under its own name to the client's folder for the year, the record must find it (Show in Finder
   from its row works), and  .venv/bin/python -c "import os,unicodedata,sys; [print(unicodedata.is_normalized('NFC', n), n.encode('unicode_escape')) for n in os.listdir(sys.argv[1])]" "<that folder>"
   shows which form each name has on disk. With no PC, make the file on the Mac in the composed
   form with Python (os.open of "Zoë Müller W-2.pdf" in the inbox), say that is how it was
   made, and record NOT VERIFIED for the PC half.

   H13. Sleep and wake around a scheduled time (R23). Chosen because launchd must run a time
   missed while asleep when the Mac wakes, and not one missed while off. Pick the next scheduled
   time (every 120 minutes from 07:00: 07:00, 09:00, 11:00 …). Five minutes before it, Jason puts
   the Mac to sleep (the Apple menu, Sleep), and wakes it ten minutes after. A pass must start
   within about a minute of waking: check the run log's times and the Overview. Record the times.

   H14. The Drive prompt's exact words (R30). Chosen because the prompt belongs to a program macOS
   attributes by its signature, and an unsigned build is attributed to the exact build. Record, word
   for word, every macOS dialog about Google Drive that appeared: at step 7 (the app), at step 9
   (the schedule's pass) and at step 12 (after the upgrade), and which program name each dialog
   gave. Say whether any pass reported "macOS did not let the schedule read the clients folder"
   before Allow was clicked.

   H1b. setup.command and start.command from a clean clone (R16). Do this LAST, after the walk and
   the removal, because setup.command's after-install step makes Electron's folder and leaves it
   out of Time Machine, and the walk needs the Mac never to have had them. In a fresh clone made
   for this (git clone into ~/pt-source), run in Terminal, with a throwaway data folder:
     TRACKER_DATA_HOME=~/PilotTest/source-data ./setup.command
   It makes .venv, installs both locks by hash and npm ci, and ends "Set up." with no question and
   no step left for a person. Then  TRACKER_DATA_HOME=~/PilotTest/source-data ./start.command
   opens the app from source; quit it with Command-Q. Also record  /bin/bash --version  (it must be
   3.2: the scripts are written for it). A second ./start.command with a changed lock file must
   say in one sentence that setup.command must run again; do not change a lock to test it, and
   say NOT VERIFIED for that sentence.

5. WHAT EVERY STEP RECORDS. For each step: PASS, FAIL or NOT VERIFIED; what was seen, in plain
   English, with the exact words of any dialog or notice (a notice's words are the evidence); and
   the screenshot's file name. Never write a client's name: the only people in this check are made
   up (Smith, Test, Zoë Müller). In Drive's path write GoogleDrive-<account>, never the address.

6. REPORT. Fill in pilot/mactest/RESULTS-TEMPLATE.md from checks.json and what you saw, and save
   it as ~/PilotTest/results/RESULT.md. Then tell Jason, in plain English: PASS or FAIL overall,
   the test counts per file, the disk image's SHA-256, the macOS version, and each failure and
   each NOT VERIFIED with what was expected and what happened. A step is PASS only if you saw it.

7. DELIVER. Only if Jason says yes: in the checkout create branch mactest-results, copy RESULT.md
   to pilot/mactest/results/RESULT-<today's date>.md (no screenshots, no other files), commit with
   a message that includes "[skip ci]", push the branch, and post one short comment on the pull
   request that carries the Mac port (Jason names its number) starting "[MACTEST] PASS" or
   "[MACTEST] FAIL" with the one-line summary. Otherwise leave RESULT.md at
   ~/PilotTest/results/RESULT.md, tell Jason its path so he can hand it to the orchestrator, and
   stop.

THE SEASON BUILDER (the program H10 runs; it writes only under the folder it is given):

import sys
from pathlib import Path

from tests import samples as s

root, households, scans = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
for number in range(1, households + 1):
    household = f"Smith {number:04d} Family"
    folder = s.private_household_dir(root, household)
    folder.mkdir(parents=True, exist_ok=True)
    s.create_household(folder, s.HouseholdInfo(name=household, contact=s.SCRATCH_CLIENT))
    engagement = s.return_dir_for(root, household, s.YEAR, s.SCRATCH_RETURN)
    engagement.mkdir(parents=True, exist_ok=True)
    s.create_engagement(engagement, s.DEMO_ITEMS, s.EngagementInfo(
        client=s.SCRATCH_CLIENT, firm=s.SCRATCH_FIRM, household=household, tax_year=s.YEAR,
        return_name=s.SCRATCH_RETURN, people=s.SCRATCH_PEOPLE))
    inbox = s.scaffold_engagement(engagement).inbox
    s.build_samples(inbox)
    for scan in range(1, scans + 1):
        # A different employer in every scan, so no two share their bytes: the
        # reader keeps a verdict by content, and identical scans are read once.
        lines = s.w2_lines(s.SCRATCH_CLIENT, f"Northwind Traders {number:04d}-{scan}", s.YEAR)
        s.scanned_pdf(inbox / f"scan {number:04d}-{scan}.pdf",
                      [part for line in lines for part in line.split("  ", 1) if part.strip()])
print(f"{households} made-up households, {scans} scan(s) each, under {root}")
```
