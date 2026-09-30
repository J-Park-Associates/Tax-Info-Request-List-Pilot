# Stage S2, third fix round: what the app says when a command fails and no error log exists yet

**Original file:** `pilot/handoffs/shell-S2-rebuild-3.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Fix round · Topic: Screen · Stage: S2  
**Date:** 2026-09-29 (the date of Jason's ruling in the note)  

## In one sentence

This session made the app save a failure to a backup log file and show only the two words "Tracker failed" on screen, as Jason ruled.

## What this session was asked to do

Stage S2 builds the app's menus. Sometimes a tracker command fails before the program has made its data folder. Then the engine has named no error log. Jason ruled on 2026-09-29 that:

- The failure must still be saved to a log.
- The screen must say just "Tracker failed".
- The menu bar stays hidden until the Alt key is pressed. This is unchanged, and it is only recorded here.

## What it did

- **Changed the words.** The old text was "Tracker failed; no error log". It is now "Tracker failed". The message keeps its shape: the failure sentence, a blank line, then those two words. The line appears only when the failure wrote something to its error output.
- **Added a backup log.** When there is no engine-named log, the details go to a file called `error.log` in the app's own per-user folder. The details are never shown on screen. Errors from the screen's own code go the same way. Writing to the log never causes a crash. A log path that is a link, or is not a plain file, is left alone. The backup log is capped. Past 256 KB it becomes `error.log.1`, replacing any older copy. So it never holds more than about 512 KB.
- **Changed Help > Open error log.** It opens the engine's log if one is named. Otherwise it opens the backup log if that exists. If neither exists, the page is told the log is missing.
- **Updated the documents:** the shell plan (sections 5.5 and 11.2), the word list, the runbook, and the notes in the repository map.
- **Explained why the backup lives there.** It is not in the data folder, because "no data folder yet" is exactly the case. Making that folder from the window code would step on the engine's own rules. The name `error.log` is also different from the engine's log name, and a test forbids the engine's name in that file.
- **Privacy.** The raw details can contain client names. They stay on this PC, in that log only. They are never shown, never put in a reply, and never sent anywhere.
- **Tests added.** They cover: the failure being saved to the backup and the reply ending in exactly "Tracker failed"; a named log getting the details instead; the size cap; a log path that is a folder; and Open error log falling back. Two on-purpose breakages (ignoring the backup log) were each caught by tests, then undone.

## What it found wrong, or what was left to do

Two things for Jason to know:

1. The list of files the coding assistants are forbidden to read (`.claude/settings.json`) does not cover the backup log. An assistant could read it. If wanted, a rule for it can be added in a separate change, with its test.
2. On a work computer with a roaming profile, the backup's location can roam between machines. On the office's setup it is local. If that changes, the note names other places it could go.

## Decisions (made by Jason, or waiting for Jason)

- **Made by Jason (2026-09-29):** with no error log named, save the failure to a fallback log and show just "Tracker failed". This replaces the earlier wording "no error log / details dropped".
- **Made by Jason (2026-09-29):** the menu bar stays hidden until Alt. No change.
- Both are proposed as decision rows for stage S6 to write into the decision log.
- Waiting for Jason: whether to add a deny-list rule for the backup log.

## Words to know

- **Shell:** the app's new screen.
- **Stage S2:** the build stage for the app's menus.
- **Rebuild 3:** the third round of fixes.
- **Error log:** a file where failure details are kept for a person to read.
- **Fallback log:** a backup error log used when no other one exists.
- **Data folder:** the folder where the program keeps its own records.
- **Deny list:** a list of files the coding assistants are not allowed to read.
- **Roaming profile:** a Windows setup where a user's settings follow them from PC to PC.
