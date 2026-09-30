# Windows test kit

**Original file:** `pilot/wintest/run_checks.ps1` (and `pilot/wintest/uninstall_checks.ps1`)  
**Kind of file:** Windows PowerShell scripts (automatic checkers)  
**Tags:** Kind: Program file · Topic: Testing, Installer  

## In one sentence
These two scripts test the pilot installer on a real Windows computer and write down PASS, FAIL or NOT VERIFIED for each step, with the evidence.

## What it is
*PowerShell* is Windows' scripting language. The kit was set up by decision P28 so Claude Code can run the Windows check on any Windows test PC. It has three parts: `run_checks.ps1` for the automatic half, on-screen clicking done by the AI for the hands-on half, and `uninstall_checks.ps1` for uninstalling. It works in Windows PowerShell 5.1 and PowerShell 7, from a git copy or a downloaded ZIP. It uses only made-up sample documents and installs no tool by itself.

## What it does, step by step
**run_checks.ps1** records each result in `checks.json` (with a log beside it) in a `PilotTest\results` folder under the user's profile:
1. **Tools:** checks for Python 3.11 or newer, Node.js, git and Inno Setup 6.3 or newer. If one is missing, it names the exact command to install it and stops.
2. **Code source:** for a git copy, it checks the work is clean and on an up-to-date `main`. For a ZIP, it makes a local snapshot so the build can proceed and marks it NOT VERIFIED.
3. **Environment:** installs the pinned parts, checking their fingerprints, and notes the path length limit for this PC (decision P29).
4. **Checks:** runs the dead-code check, the code map check, and the tests. With `-Tests` it runs only the named test files, each as its own process, in parallel with the build. Without it, it runs the whole suite.
5. **Build:** builds the installer and records its SHA-256 fingerprint.
6. **Install:** silently installs for one user and checks the program, Start-menu shortcut and uninstall entry exist.
7. **Sample folder:** makes a sample Clients folder of made-up documents if none exists.

**uninstall_checks.ps1** runs the uninstaller silently and checks: the program is removed; the scheduled task is removed (or NOT VERIFIED if no task existed, since removal was then never tested); and the data folder, sample clients folder and settings file are all kept.

## Why it matters to the firm
The installer will go to other CPA firms. This kit proves on a real PC that it installs without administrator rights and that uninstalling never touches client or tracker data. It labels honestly what was not proven.

## What must never be changed without a programmer
- The rule that only made-up documents in the test folder are used.
- The honest NOT VERIFIED verdicts. A step that was not exercised must not be marked PASS.
- The keep-data checks in the uninstall script.
- Running it on a computer that holds real client files or the firm's real schedule.

## Words to know
- **PowerShell:** Windows' scripting language.
- **PASS / FAIL / NOT VERIFIED:** worked, did not work, could not be proven.
- **Silent install:** installing with no windows or questions.
- **SHA-256 fingerprint:** a long code that changes if the file changes at all.
- **Inno Setup:** the tool that builds the installer.
- **Pytest:** the tool that runs Python tests.
