# Fourth fix round for the menus stage: the fallback error log

**Original file:** `pilot/handoffs/shell-S2-rebuild-4.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Fix round · Topic: Screen · Stage: S2  
**Date:** not stated  

## In one sentence

This session fixed two findings from a fourth check of the menus stage, made the emergency error log safer, and put Jason's two rulings into the program.

## What this session was asked to do

Fix everything found by "review 4" of stage S2, and apply Jason's rulings on where the emergency log lives and on which files the assistant may not open. It ran on the branch `claude/shell-s2-menus`, built on rebuild 3 (`690905f`). The code commit is `5a681b4`.

## What it did

**The fallback log.** When the app has no data folder, a failed command's details are saved in a small *fallback log* file called `error.log`.

- **Finding 1, no test for links.** The program already refused to write to that log if it was a *symbolic link* (a shortcut that points to another file). Now two tests prove it. The session also proved the tests work: it broke the refusal on a scratch copy and a test failed.
- **Finding 2, dead value and old comment.** A leftover return value and a stale test comment were removed.
- **An edge case, a folder named `error.log.1`.** Before, it stopped every later write. Now, if the old log cannot be rotated out, it is removed and writing goes on. The size cap of 256 KB still holds.

**Jason's rulings, put in place.**

1. The fallback log is *local and non-roaming*. On Windows it is under the local application-data folder, in a folder named "Tax Document Tracker Pilot". It is not in the roaming folder, the data home, or the upstream program's folder. A test checks the names differ.
2. A *deny list* (a list of files the coding assistant may not read or edit) now names this log and its rotated copies. The rules were added to `.claude/settings.json`. A bare rule for any `error.log` was not used, because it would block a person's unrelated file.

Text was updated in the app's main file, two sections of the shell plan, the runbook, the map's notes and the tests.

## What it found wrong, or what was left to do

- The reply text is unchanged: the failure's own sentence, a blank line, then "Tracker failed". If Jason wants only those two words shown, that is a one-line change.
- No renderer file changed. Nothing touches the network, reads a client document, or sends anything.
- Tests passed under both Python versions. One test in the build file fails on the base too (an OCR test).
- Two decision rows are proposed for stage S6: the fallback log is local, non-roaming and denied to the assistant; and the log is never written through a link, and a stuck `.1` never stops it.

## Decisions (made by Jason, or waiting for Jason)

- **Made by Jason:** the log location, and the deny list (both above).
- **Waiting for Jason:** whether the screen should show only the two words "Tracker failed".
- **For S6 to log:** the two proposed decision rows.

## Words to know

- **Fallback log:** a small error file used only when there is no data folder.
- **Rotation:** when a log reaches its size limit, the old copy is renamed and a fresh file starts.
- **Symbolic link:** a file that only points to another file.
- **Deny list:** rules that stop the coding assistant from opening named files.
- **Roaming folder:** a Windows folder that follows a person between computers.
- **Stage S6:** the later stage that writes decision rows.
