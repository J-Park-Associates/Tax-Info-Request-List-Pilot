# Stage S5 (the side sheet), second fix round: Jason's rulings 16 to 21

**Original file:** `pilot/handoffs/shell-S5-rebuild-2.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Fix round · Topic: Screen · Stage: S5  
**Date:** 2026-09-30  

## In one sentence

This session built exactly what Jason's six rulings (numbers 16 to 21) asked for, and nothing else.

## What this session was asked to do

Jason had ruled on several open questions from the first fix round. This session applied those rulings. It used made-up names only, and nothing here reads a client document. The standing rules held: no generative AI, no folder path drawn, no sentences typed by the screen, five words at most in Title Case.

## What it did

- **Ruling 16, Unfile asks for a reason.** A right-click Unfile no longer writes at once. It opens a small dialog with the file's name, a box "Reason (Optional)", and Cancel and Unfile buttons. Esc and Cancel close it with no write. Confirming sends the trimmed reason as the note.
- **Ruling 17, several files under one request.** A request answered by more than one file keeps its "{n} Files" row and gets one child row per file. A file filed under this request links to its own copy. Its right-click has Show in File Explorer and Unfile. A file that only answers the request, with no copy here, has no link.
- **Ruling 18, Folders Skipped.** Each folder name gets a short two-word reason from the word list. The long sentence still goes to the error log. A code with no word draws the name alone and logs nothing. No path is shown.
- **Ruling 19.** No change. The sheet moves on after a right-click write.
- **Ruling 20, sort failure.** When the last sort failed, one notice "Sort Failed" with a Retry button shows on every page. It clears when a later sort works. The side-panel line stays.
- **Ruling 21, paused household.** Clients shows "Two Years Open; Sorting Paused" beside the household's name. The household counts as Work Waiting. Overview leads Work Waiting with one row per paused household. If the field is missing, nothing is drawn.
- **Tests.** New tests cover each ruling. Fifteen on-purpose breakages were tried. Thirteen were caught at once. Two survived: an empty reason span, and paused rows dropped from Overview. Stronger checks were added and they are now caught.

## What it found wrong, or what was left to do

**For stage S6:**  

- Ruling 21 needs the engine's firm reply to mark each return of a household paused for two open years with `paused: true`. Where a household is not paused, the field must be absent, not false.
- The word for reason code `not_a_year` does not exist until Jason gives one. "Bad Year" is the working word (ruling 18a). When added to the engine it draws with no other change.
- The two Unfile calls still send a note and a sequence number. Nothing new is needed from the API.
- The temporary word copy gains only the Folders Skipped reasons, and is deleted with the rest at the join.
- The join checklist from rebuild 1 still stands. Its second item now also covers the right-click menu on a filed file.

The gate results are given on the note's last line, which was not written into the note itself.

## Decisions (made by Jason, or waiting for Jason)

- **Made by Jason:** rulings 16, 17, 18 (with 18a, "Bad Year" as the working word), 19, 20 and 21.
- **Waiting for Jason:** the final word for the `not_a_year` reason, if "Bad Year" is not the one.

## Words to know

- **Shell:** the app's new screen.
- **Stage S5:** the build stage for the side sheet, right-click menus and dialogs.
- **Rebuild 2:** the second round of fixes.
- **Ruling:** a decision Jason made, numbered in a list.
- **Unfile:** take a file back out of a request and return it to the review list.
- **Paused household:** a paused household is one where the program has stopped sorting because two tax years are open.
- **Notice:** a short message at the top of the screen.
- **Error log:** a file where failure details are kept.
- **Join:** merging the separate stage branches into one.
- **Mutation check:** breaking the code on purpose to prove a test notices.
