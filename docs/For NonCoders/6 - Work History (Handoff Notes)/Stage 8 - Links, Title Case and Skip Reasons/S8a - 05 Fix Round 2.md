# Link keys job (S8a): second round of fixes

**Original file:** `pilot/handoffs/shell-S8a-rebuild-2.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Fix round · Topic: Screen, Wording · Stage: S8a  
**Date:** not stated in the note  

## In one sentence

Two problems from the second review of the link-keys job were fixed: a file could be named
twice under two kinds of key, and three words still carried "proposed" marks after Jason
approved them.

## What this session was asked to do

A Sonnet 5.5 builder, on branch `claude/shell-s8a-links`, was to fix only the two findings of
the second review of S8a.

## What it did

- **Finding 1, a parked document's Open.** For a parked PDF that was read, the engine now
  gives one key that serves both "show" and "open", so no path is reported under two kinds.
  Files with no opening copy (set aside, email, zip, docx) keep their "show" key. Two tests
  were added, one of which runs the real app main program under node: a plain open of the
  review copy opens it, "reveal" shows it, and a shown-only docx refuses a plain open but is
  shown on reveal. With the fix reverted on a scratch copy, both tests failed; with it
  restored, both passed.
- **Finding 2, paperwork for ruling 14.** Jason approved three words: "Two Years Open; Sorting
  Paused", "Prior Year Data Not Found" (changed from "Feed Return Not Found") and "Machine Needs
  Attention" (one line for all three machine warnings). The PROPOSED marks were removed from
  the wording table, a code comment and an earlier handoff.
- **Gate.** Dead code: none. Tests in both Python versions: `test_api`, `test_shell`,
  `test_layers`, `test_single_source`, `test_repo_map`; style check and map check.

## What it found wrong, or what was left to do

`test_build` has a known failure about the OCR (text-reading) scratch roots. It fails the same
way on the base, so it was not run.

## Decisions (made by Jason, or waiting for Jason)

Made by Jason: ruling 14 (the three words above). Nothing is waiting.

## Words to know

- **Key (link key):** a label the engine gives a file so the app can open or show it safely.
- **Reveal:** show a file in File Explorer without opening it.
- **Parked file:** a file set aside for a person.
- **PROPOSED mark:** a note that a word is not yet approved.
- **Ruling:** a decision of Jason's, recorded in a numbered row.
- **Mutation check:** breaking code on purpose to see a test fail.
