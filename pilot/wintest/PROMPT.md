# Pilot 0.1 Windows check - prompt for Claude Code on the test PC

Before you start, on the Windows test PC:

1. Get the code into an empty folder with a short path, such as `C:\pt` (not under
   `C:\Users\...\Documents`; Windows limits how long a path may be). A git clone is best; if this PC has no
   GitHub sign-in, download it from GitHub (Code -> Download ZIP) and unzip it.
2. Open the **Claude desktop app** and turn on **computer use** (it lets
   Claude click through the installed program). Without it, Claude walks you
   through the clicks and records your answers.
3. Open Claude Code in the folder that holds the code, and paste everything
   in the box below.

```
You are running the Windows check for Tax Document Tracker Pilot 0.1 on this computer, for Jason
Park (a CPA, not a programmer - report in plain English). Follow these rules the whole time:

SAFETY - never break these:
- Generative AI never reads client financial documents. Use ONLY the made-up sample documents
  this test creates under %USERPROFILE%\PilotTest\Clients. Never open, list or read any other
  folder or document on this computer. If a file picker or dialog shows other folders, do not
  read their contents; go straight to %USERPROFILE%\PilotTest\Clients.
- Nothing is ever sent: do not send email, do not upload files anywhere except the one results
  commit described in step 6.
- Do not tag, release or send the installer. Do not change the program's code; this is a test,
  not a fix. If something fails, record it.
- Stop and ask Jason if: an install asks for administrator rights, a Windows dialog cannot be
  handled, or any step would touch a folder outside %USERPROFILE%\PilotTest and the pilot checkout.

1. GET THE CODE. If the pilot code is not already in this folder, clone
   https://github.com/J-Park-Associates/Tax-Info-Request-List-Pilot (main). If it came as a
   downloaded ZIP, use it as it is: the script makes a local snapshot commit and marks the tree
   check NOT VERIFIED. Read pilot/RELEASE.md and pilot/wintest/RESULTS-TEMPLATE.md.

2. AUTOMATED PART. Run:
     powershell -ExecutionPolicy Bypass -File pilot\wintest\run_checks.ps1
   It checks the tools, installs the environment, runs the whole test suite, builds the
   installer, installs it silently for this user, and makes the sample clients folder. Results go
   to %USERPROFILE%\PilotTest\results\checks.json. If it stops because a tool is missing, show
   Jason the winget command it printed, ask once, run it if he agrees, then run the script again.
   A failing test suite is recorded, not fixed; carry on if the installer still built.

3. HANDS-ON PART on the installed app (Start menu: "Tax Document Tracker Pilot"), with computer
   use. If you have no computer use, do not skip this part: tell Jason exactly what to click and
   what to look for, one step at a time, and record his answers. Take a screenshot at each step into %USERPROFILE%\PilotTest\results\screens. If
   Windows SmartScreen appears, choose "More info" then "Run anyway". Check, in order:
   a. The header shows the badge "Pilot edition 0.1".
   b. The terms screen appears. Press Escape: it must stay. "I agree. Continue." must be greyed
      out until the checkbox is ticked. Tick it, press "I agree. Continue.": the tour starts.
   c. Walk all 11 tour steps with Next. Each either highlights a part of the screen or shows a
      short "appears after..." line. The row of stages at the top fits inside the card. The last
      step shows two columns: Strengths and Current limits. Finish. Press the Tour button: the
      tour starts again; close it.
   d. Set the clients folder to %USERPROFILE%\PilotTest\Clients and save.
   e. New household: create "Test Household", return type 1040, tick a few documents, create it.
   f. Choose the "Smith Family" return and press Scan; wait for it to finish. Then check (in the
      app and, if needed, in File Explorer inside the sandbox only): originals moved out of
      "Drop files here" into the year folder; named copies in the return's Prepared folder;
      anything the rules could not place in "00 - Needs Review"; the Status button opens the
      status page.
   g. Schedule button: turn it Off and Save. Run
        schtasks /Query /TN "Tax Document Tracker Pilot"
      - it must report that the task does not exist. Turn it On, first run 06:30, every 4 hours,
      Save. Run
        schtasks /Query /TN "Tax Document Tracker Pilot" /XML
      - the XML must show a start time of 06:30 and an interval of PT240M.
   h. Close the app and open it again: the Schedule dialog still shows On, 06:30, every 4 hours;
      the terms and the tour do not appear again.

4. UNINSTALL. Close the app, then run:
     powershell -ExecutionPolicy Bypass -File pilot\wintest\uninstall_checks.ps1
   Results go to %USERPROFILE%\PilotTest\results\uninstall.json.

5. REPORT. Fill in pilot\wintest\RESULTS-TEMPLATE.md from checks.json, uninstall.json and what you
   saw, and save it as %USERPROFILE%\PilotTest\results\RESULT.md. Then tell Jason, in plain
   English: PASS or FAIL overall, the test-suite counts, the installer's SHA-256, and each failure
   with what was expected and what happened.

6. DELIVER. If this PC can push to GitHub: in the pilot checkout create branch wintest-results,
   copy RESULT.md to pilot/wintest/results/RESULT-<today's date>.md (no screenshots, no other
   files), commit with a message that includes "[skip ci]", push the branch, and post one short
   comment on pull request #5 of J-Park-Associates/Tax-Info-Request-List-Pilot starting
   "[WINTEST] PASS" or "[WINTEST] FAIL" with the one-line summary. If it cannot, leave RESULT.md
   at %USERPROFILE%\PilotTest\results\RESULT.md, tell Jason its path so he can hand it to the
   orchestrator, and stop.
```
