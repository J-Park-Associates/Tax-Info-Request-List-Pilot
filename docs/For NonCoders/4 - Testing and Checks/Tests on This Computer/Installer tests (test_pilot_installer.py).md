# Installer tests

**Original file:** `tests/test_pilot_installer.py`  
**Kind of file:** automatic test file (Python)  
**Tags:** Kind: Program file · Topic: Testing, Installer  

## In one sentence
These tests read the installer's recipe and the build script as plain text and prove that installing is safe for a tester and that uninstalling never touches client data.

## What it is
A *test* is a small program that checks one claim and reports pass or fail. This file checks the pilot's installer recipe (`pilot/installer/setup.iss`, written for a tool called Inno Setup) and the build script (`pilot/Build Pilot Installer.bat`). Because both are just text, the tests do not need Windows or Inno Setup. Its own heading points to the pilot decisions P4, P12 and P13.

## What it does, step by step
The tests check these claims. Each test is named as the claim it makes.
1. The installer installs for one user and needs no administrator rights.
2. Uninstalling removes the scheduled task the program made, and nothing else.
3. Uninstalling never deletes client data, the tracker's data folder or the settings file. The recipe has no uninstall-delete section at all.
4. An upgrade clears only the old program code (two named folders) before copying the new one (decision P115), and the recipe has just one such deletion section.
5. An upgrade closes the running app and does not restart it.
6. The recipe refuses to compile without a version number and a source folder.
7. The installer has the right name, place and file name, and a fixed identity number.
8. The desktop icon is offered but not ticked.
9. The build script refuses uncommitted work, checks it is inside a git checkout first, and follows the root scripts' rules.
10. The Tester Guide names the folders the pilot leaves alone and the "More info / Run anyway" steps for the Windows warning.
11. The version the build reads is the one shown on the badge in the app (this test is skipped if Node.js is not installed).
12. Every batch file the build calls is named with its folder path, because Windows will not find a bare name (decision P29).

## Why it matters to the firm
A tester's own client folders must never be harmed by installing, upgrading or uninstalling. These tests turn that promise into a check that runs with the rest of the tests. They also make sure a leftover scheduled task cannot fail every day after uninstall (decision P12).

## What must never be changed without a programmer
- Loosening a test so a deletion is allowed. If a test fails, fix the installer, not the test.
- Editing the recipe or build script without running these tests.
- The expected list of the two folders an upgrade may clear.

## Words to know
- **Test:** a small program that checks one claim.
- **Inno Setup:** the tool that turns a recipe file into a Windows installer.
- **Installer recipe (`setup.iss`):** the text file telling Inno Setup what to install.
- **Batch file (`.bat`):** a Windows script of commands.
- **Scheduled task:** a job Windows starts at set times.
- **Decision number (P-number):** a numbered ruling in the pilot decision log.
