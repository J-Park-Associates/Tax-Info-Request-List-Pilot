# Stage S1: the engine's new answers and the shortened wording

**Original file:** `pilot/handoffs/shell-S1.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Build · Topic: Screen, Engine, Wording · Stage: S1  
**Date:** not stated  

## In one sentence
Stage S1 taught the program's engine to answer the new screen's questions and put Jason's approved shorter wording into it, without touching the screen itself.

## What this session was asked to do
Build exactly the S1 row of the written plan (SPEC-shell section 16). S1 is the first of the build stages for the app's new screen ("the shell"). It worked on branch `claude/sharp-goldberg-jmfynk`, using a "sonnet" session.

## What it did
- **A new read-only firm view (section 9, decision P79).** A new command, `firm`, shows all returns at once. It does not lock anything, write anything or read any client document.
  - A draft is "ready" when drafted this draft-week and not yet approved. An edit after approval cancels the approval.
  - "Held" means the holding rows plus unsorted inbox files. A hold does not make a draft "not ready".
  - Other answers now say which group an item is in, and give the clients-folder and status-page places, and whether the last sort worked and when it started.
- **Shorter wording (section 11).** It added the menu words (44), a short reason for each of 60 reason codes, short stage names, short safeguard names, labels for the override reasons, and a warning for moving the schedule.
- **The approved rewording** (67 reword, 5 merge, 10 error-log rows, exactly as in `wording-shell.tsv`) was applied. Where the status report or console still reads a longer sentence, that sentence was left alone, and the app says a short one beside it.
- It updated the runbook lines that quoted changed words. The four standing rules were not changed.
- Tests were added or changed. The checks ran under Python 3.11 and 3.13, and all passed except six on purpose (see next section). The code checker was clean and the repository map was current.

## What it found wrong, or what was left to do
- **Six tests fail on purpose.** They read the screen's file `app/main.js`, which S1 was not allowed to touch. Stage S2 must set six of its default words to the engine's words: "Sort stopped: ran too long", "No reply from the tracker", "The tracker could not start", "Could not send; nothing changed", "Tracker failed; no error log", and "Not opened; it has changed". Then those tests pass unchanged.
- **78 "cut" words are still in the engine's word list** (`_vocab()`), because the current screen still reads them. Stage S6 removes them once S4 and S5 stop reading them.
- **Left to others:** tour text (S3), the safeguards pop-up (S5), and docs naming buttons that move into the menu (S6).
- The stage names and the standing rules keep their full wording.

## Decisions (made by Jason, or waiting for Jason)
Proposed decision rows for S6 to record:
- How `firm` counts groups and decides "ready" and "held" (as above).
- A return the firm view cannot read says "Could not be read", the detail goes to the error log, and it counts as needing a person. **Waiting for Jason:** these words are not in the approved list.
- Where another reader still reads a long sentence, the app's short word is kept beside it, not a change to that sentence.
- The checks that "the screen types no word" now look for a word at the start of a string, because short words can appear inside code.

## Words to know
- **The shell:** the app's new screen and its window.
- **Stage (S1 to S8a):** one step of building the shell, taken in order.
- **Engine:** the part of the program that does the sorting and answers the screen's questions.
- **Command:** a named request the screen sends to the engine, such as `firm`.
- **Read-only:** looks but changes nothing.
- **Lock:** a marker that stops two things changing one return at the same time.
- **Vocabulary / word list:** the set of words the screen shows; the engine supplies them.
- **Branch:** a separate line of work in the program's history.
- **Repository map:** a generated guide to every file in the program.
