# A check of the "closing best practices" list, and the gaps it filled

**Original file:** `pilot/handoffs/maintainer-handoff-audit.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Build · Topic: Installer, Safety, Code map  
**Date:** 2026-09-30  

## In one sentence

Jason asked for a check of a closing checklist (packaging, installer upgrades, hash locks, testing, security notes, the repository map), and this session found three real gaps and filled them.

## What this session was asked to do

- Check the project against a "closing best practices" checklist. It covers packaging, installer upgrades, *hash locks*, local testing, security and infrastructure notes, and the *repository map* transition points.
- Make whatever was missing. The new pieces had to be written for a maintainer who does not code.

A *hash lock* is a list of every outside part the program uses, with a fingerprint for each. The *repository map* is the generated guide that says what every file is for.

## What it did

**Already in place (no change needed):**
- The security walls around the app window: a sandboxed window, a short list of allowed commands, a list of paths the app may open, and a strict rule about what the page may load.
- The recipe that builds the reader names its hidden parts explicitly, and it builds in a fresh clean setup from the locks.
- Every install uses the hash-checked mode. A helper tool holds the lock checks.
- The Windows scheduled job, the Drive notes, the one-machine rule and the cost rule are all written down.

**Corrections to the checklist's guesses:**
- The office Python is 3.14 and the lowest supported is 3.11 (not 3.13).
- The overnight sort fails loudly, never silently. It gives a non-zero exit, a "Sort Failed" notice and a run log.
- The page-loading rule lives in the page file `index.html`, not in the main process.

**Three gaps it filled:**  
1. **Upgrades left old files behind.** Jason approved the fix (P115). The installer now clears only two named program folders before copying new files in. It asks to close a running app or sort, and closes it by force when allowed. The GPU pack and `settings.json` sit outside those folders and are kept. Guard tests were updated and two were added. `pilot/SPEC.md` and `pilot/DECISIONS.md` were updated.
2. **No plain-language maintainer guide.** A new `docs/maintenance-guide.md` covers security walls, the schedule, Drive, building, locks, testing, the cost rule, the transition points and a glossary. `README.md` links to it.
3. **The map did not show the installer or build recipes.** The map tool now reads those file kinds. New map entries were added for the build recipe, the installer script, the installer build batch file and the guide. "TRANSITION POINT" notes were added to five files.

## What it found wrong, or what was left to do

**A known risk, written down:** if a person says no to closing the app and then cancels the installer, the install can be left half-deleted. Running the installer again repairs it. Blocking that outright would need a check that cannot be tested off Windows. It is a candidate for the office PC.

**Not run:** Python 3.14 (not on the cloud machine) and anything that only runs on Windows.  

**Left to do on the office PC:**
- Run the four named test files under Python 3.14.
- Build the installer.
- Do one hands-on upgrade over the previous pilot version. Confirm the app starts, the schedule still runs, and `settings.json` and any GPU folder survive.
- Land this with the next batch. No pull request was opened, because of the cost rule.

## Decisions (made by Jason, or waiting for Jason)

- **Made by Jason:** P115, the installer clears only its own two folders on upgrade.
- **Wording fix:** review 2 said the "force close" wording overstated what force does, because it still asks the person. The lead reworded it.
- **Still open:** the stronger check against a declined close (see above) is only named as a candidate for the office PC; the note does not say it waits on Jason.
- **Review 1** found six problems; they were fixed in the second commit.

## Words to know

- **Hash lock:** a list of every outside part the program uses, with a fingerprint for each part.
- **Repository map:** the generated guide that says what every file is for and how the files connect.
- **Installer:** the program that puts the app on a computer.
- **Sandboxed window:** an app window kept in a walled-off space so it cannot reach much on the computer.
- **Transition point:** a place where one part of the system hands off to another, such as where the schedule starts the overnight sort, or where the app window starts the engine.
- **Review 1 and review 2:** independent checks of this work by other sessions.
