# Fixing the nine problems a checker found in the shell's data layer (stage S1)

**Original file:** `pilot/handoffs/shell-S1-rebuild-1.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Fix round · Topic: Screen, Engine, Wording · Stage: S1  
**Date:** not stated  

## In one sentence

A builder session fixed all nine problems that a checker found in the part of the program that feeds the new screen, and left the screen's own code for the next stage (S2).

## What this session was asked to do

The new screen is called "the shell". Stage S1 built the part of the program (the *API*, meaning the layer the screen talks to) that hands the screen its facts. A checker (a "review") looked at that work and listed nine findings, F1 to F9. This session, "rebuild 1", was asked to fix them. It ran on a work branch built on the checker's last commit, `49ddf9f`.

## What it did

The note says all nine findings were right. None was rejected. In plain words:

- **F1.** The lists the screen uses for sorting and filtering now match what the plan (section 11.4 of the shell plan) names. A test checks them.
- **F2.** The firm-wide summary now lists every file it counts, including files that a person moved by hand. A return with every request received but one parked file and one hand-moved file now counts as "needs a person", not "complete". A new test covers this.
- **F3.** Every file entry now also carries the folder path of its return, so the file can be tied to its return.
- **F4.** A return that cannot be read now shows the short line "Could not be read" (three words, no path). The details go to the error log. Such a return counts as "needs a person".
- **F5.** The reminder-draft status now works the way the single-return reminder works. A draft is "ready" until it is approved. Unsorted files in the inbox count as a hold. Reading the inbox is only a folder listing, so no document is read.
- **F6.** The page error message is now one short line everywhere. A second, longer version was deleted.
- **F7.** When adding an issuer fails to rescan, the reason goes to the error log and the person sees a plain fixed sentence.
- **F8.** The test that proves the firm summary is read-only now snapshots the store and the data folder before and after, and compares them.
- **F9.** Some code and comments were put back in the right order.

One item is only a proposal: the words "Could not be read" are not in the list of wording Jason approved.

The note also reports checks. Each test file ran in its own process under two Python versions (3.11 and 3.13). All passed, except six tests in one file that fail on purpose. They read the screen's program file (`app/main.js`), which is stage S2's job. The code-cleanliness check (ruff) passed and the repository map was refreshed.

## What it found wrong, or what was left to do

- Six tests fail on purpose until stage S2 updates `app/main.js`. That file still shows the old "no error log" behaviour (it prints the error text in the reply).
- One older decision-log row (decision 186) still names a deleted constant. It stays as written because it is history.
- One larger test file about the installer's build was not run, because one of its tests fails on the base version too.

## Decisions (made by Jason, or waiting for Jason)

- **Waiting for Jason:** approval of the new words "Could not be read".
- No other decision is stated.

## Words to know

- **The shell:** the app's new main screen.
- **S1, S2:** build stages of the shell. S1 is the data layer, S2 comes next.
- **Rebuild:** a fix round after a checker's review.
- **API:** the layer of the program that answers the screen's questions.
- **Branch:** a separate line of work in the code history, kept apart from the main one.
- **Error log:** a file where the details of failures are kept off the screen.
- **Repository map:** the generated guide to every file in the program.
- **Ruff:** a tool that finds unused code.
