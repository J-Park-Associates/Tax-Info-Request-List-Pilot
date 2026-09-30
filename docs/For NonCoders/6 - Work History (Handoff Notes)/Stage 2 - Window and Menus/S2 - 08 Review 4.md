# Fourth independent check of stage S2: the error-log fallback

**Original file:** `pilot/handoffs/shell-S2-review-4.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Review · Topic: Screen · Stage: S2  
**Date:** not stated  

## In one sentence

A reviewer confirmed that Jason's ruling on saving failures to a backup log was built correctly, and found two small problems: one missing test and one bit of dead code.

## What this session was asked to do

Check the third fix round ("rebuild 3") of stage S2. S2 builds the menus and the window side of the app's new screen, "the shell". This round carried out Jason's ruling: when the tracker fails and names no error log, save the failure to a *fallback log* and show only "Tracker failed" on screen. The reviewer had built none of it. It changed no code.

## What it did

It checked, and found correct:
- **The word.** The on-screen extra line is exactly "Tracker failed", the same in the window code and the API. Two tests pin it.
- **No stderr on screen.** *Stderr* is a program's error output, which can name a client. It goes only into a local file, never into a reply.
- **The fallback log.** It lives in the app's own local folder. It is capped at 256 KB, with one older copy kept. Every write is wrapped so a failed write cannot block the reply. It does not touch the data folder or the settings folder, and the installer package does not ship it.
- **Help > Open error log.** It opens the named log if there is one, else the fallback. The page cannot open the fallback or any path of its own choosing. The reviewer tried five attempts to trick it, and all were refused.
- **Standing rules.** No network use and no client document read.
- **Mutation checks.** The reviewer broke the code twelve ways on a scratch copy. Eleven were caught. One was not (finding 1).
- The docs match the code, and the diff touched only the expected files.

## What it found wrong, or what was left to do

**Finding 1: one refusal has no test.** The code never writes the fallback log through a symbolic link (a shortcut that points at another file). If someone planted one, a client-naming error could be redirected into another file. The code prevents it today, but no test keeps it that way. Fix: add a link case to two tests, and skip it where links cannot be made.

**Finding 2: dead code and a stale comment.** A function still returns a yes/no answer that nobody reads. One test comment says a write is asynchronous, but it is now synchronous. Fix: drop the return value and reword the comment.

**Notes for Jason:**  
1. **The agent deny list does not cover the fallback log.** The deny list stops Claude's own file tools from reading client-naming files. The fallback log is not on it, and it can name a client. The builder did not add it because a test pins the list, so a change needs Jason's approval. The reviewer edited no settings.
2. **What "just" means.** The screen shows the failure's own sentence, a blank line, then "Tracker failed". The spec says the notice "says just 'Tracker failed'". If Jason meant only the two words, that is a one-line change plus its test.
3. **Roaming profiles.** On a roaming domain profile the fallback log would travel with the profile. It is local on the office's setup today.
4. The wrong model name in the commit trailer again. History is left as is.
5. A very rare case: if a folder named `error.log.1` ever exists, later fallback writes are dropped quietly. Not worth code today.

**Gate:** each test file ran alone under Python 3.11 and 3.13 with the same results. Every file passed except one build test that also fails on the base version. Ruff and the map check passed.  

## Decisions (made by Jason, or waiting for Jason)

- **Made by Jason (before this review):** save a failure to a fallback log and show "Tracker failed".
- **Left for Jason by this note:** add the fallback log to the deny list; confirm whether "just" means the added line only; the roaming-profile point.
- **Answered later** (in `shell-rulings.md`, not in this note): ruling 4 moves the fallback log to a local, non-roaming folder and adds it to the deny list; ruling 6 leaves the on-screen failure text as built.

## Words to know

- **Fallback log:** a backup error file the app keeps when no error log was named.
- **Stderr:** a program's error output.
- **Symbolic link:** a shortcut file that points to another file.
- **Deny list:** the list of files Claude's own file tools may not read.
- **Mutation check:** breaking the code on purpose to prove a test notices.
- **Dead code:** code that nothing uses.
