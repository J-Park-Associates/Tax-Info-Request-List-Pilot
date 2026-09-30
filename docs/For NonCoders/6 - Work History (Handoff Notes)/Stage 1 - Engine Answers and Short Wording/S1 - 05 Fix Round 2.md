# Fixing two out-of-date notes in the first stage's handoff

**Original file:** `pilot/handoffs/shell-S1-rebuild-2.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Fix round · Topic: Screen, Engine, Wording · Stage: S1  
**Date:** not stated  

## In one sentence
This short session fixed the words in an older handoff note so they matched what the program really does; it changed no program code.

## What this session was asked to do
An earlier check of stage S1 (review 2, finding F1) said that `shell-S1.md` still described a "draft is ready" rule the old way. Also, a new message, "Could not be read", was missing from the list of proposed decision rows. (S1 is the first build stage of the app's new screen, called "the shell".) This session worked on the branch `claude/sharp-goldberg-jmfynk`.

## What it did
- It changed two places in `shell-S1.md`: the notes and the first proposed decision row. Both now say:
  - A draft is *ready* when it was drafted this draft-week and has not been approved yet. If the letter was edited after it was approved, that approval does not count.
  - A return is *held* when it has holding rows, plus files still sitting unsorted in the inbox.
  - Being held does not make a draft "not ready" (SPEC 6.3, the written plan for the screen).
- It added a new proposed decision row. It says that when the firm-wide view cannot read a return, it shows "Could not be read". The technical detail goes to the error log. That return counts as needing a person. Jason must approve these words, because they are not in the approved word list (`wording-shell.tsv`).
- It touched documentation only, no code.

## What it found wrong, or what was left to do
Nothing else is stated in the note. The last commit is the one that adds this file.

## Decisions (made by Jason, or waiting for Jason)
Waiting for Jason: approval of the words "Could not be read".

## Words to know
- **Branch:** a separate line of work in the program's history, kept apart from the main one.
- **Handoff note:** a message one work session leaves for the next.
- **Review / finding:** a check by a second person or agent; a finding is a problem it reports.
- **Error log:** a file where the program writes technical detail for a person to read later.
- **Decision row:** one numbered entry in the list of decisions about why the program works as it does.
- **Commit:** one saved step in the program's history.
