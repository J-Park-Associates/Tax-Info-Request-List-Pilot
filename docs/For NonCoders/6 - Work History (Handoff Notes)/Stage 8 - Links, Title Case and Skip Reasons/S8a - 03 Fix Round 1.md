# Stage S8a fixes: file links that only show a file, and short notice words

**Original file:** `pilot/handoffs/shell-S8a-rebuild-1.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Fix round · Topic: Screen, Wording · Stage: S8a  
**Date:** not stated  

## In one sentence
This session fixed ten findings (F1 to F10) from the first check of stage S8a, mainly making file links "show in File Explorer" only, and added short notice words.

## What this session was asked to do
Answer review 1 of S8a (the engine's file links). It worked on branch `claude/shell-s8a-links`. Only made-up names were used and no client document was read. The coordinator also added one item: short words for the notices (from S4 rebuild 1).

## What it did
- **F1 (safety).** Filed and moved working copies are now "reveal-only": the app may show them in File Explorer but never open them in their program. Only a marked review copy still opens (decision 190). Tests on the real `main.js` show a moved `.xlsm` is refused a plain open and shown when asked to reveal.
- **F2.** Every file name can be a link. A new key `shown_copy` covers set-aside files and parked emails, zips and documents. A parked program has no copy, so no key.
- **F3.** A test shows that a moved copy whose file is gone has no key.
- **F4.** The refusal "That path is not one the tracker reported; nothing was opened." is tested five times and once before any report. A second test pins the safe default for a key with no kind.
- **F5.** The Title Case test now lower-cases small words in the middle ("Waiting on Clients").
- **F6.** A page filed under two requests (decision 94) gets two keys, matching the file names and places.
- **F7 and F8.** The footer words were restored. Exceptions to the Title Case test are listed one by one, each with a reason. The Active help is now "No: Sorting Skips This Return".
- **F9.** A comment in `app/preload.js` now says reveal shows a file, or opens a reported folder.
- **F10.** The handoff's list of leftover words is complete.
- **Notice words** (five words or fewer, Title Case, no path): "Install Folder Name Too Long", "Machine Needs Attention", "Folder Renamed", "Two Years Open; Sorting Paused", "Prior Year Data Not Found", and the existing "Drive Not Signed In". Jason approved several (ruling 14). A test covers every kind.
- It broke the code on purpose in a copy to prove tests catch it; each breakage was caught.

## What it found wrong, or what was left to do
SPEC 5.7 and 9.3 should name the reveal-only kind and `shown_key`.

## Decisions (made by Jason, or waiting for Jason)
- Made by Jason: ruling 14 approved "Machine Needs Attention", "Two Years Open; Sorting Paused" and the feed word "Prior Year Data Not Found" (changed from the proposed "Feed Return Not Found").
- Ledger default 5 is applied: pieces spliced into longer lines stay lower case, listed as exceptions.
- Other words came from the plan: "Install Folder Name Too Long" (E28) and "Folder Renamed" (E47).

## Words to know
- **Reveal-only:** the app may show the file's place in File Explorer but never run it.
- **Working copy:** the copy the program keeps for its own work; originals are never altered.
- **Key:** a label the engine gives a file; the page uses it, and the real path is looked up only when clicked.
- **Allow-list:** the list of paths the app may open or show.
- **Title Case:** Each Main Word Capitalised.
- **Mutation:** deliberately breaking code to prove a test would notice.
- **Ledger:** a file recording default choices for open questions.
