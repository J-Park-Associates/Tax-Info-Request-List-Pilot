# Two-word reasons for the Folders Skipped dialog (S8b)

**Original file:** `pilot/handoffs/shell-S8b.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Build · Topic: Screen, Wording · Stage: S8b  
**Date:** not stated  

## In one sentence

This session gave each skipped folder a short code and a two-word reason for the Folders Skipped dialog, all except one reason that needs Jason.

## What this session was asked to do

Carry out Jason's ruling 18: show two-word reasons on the Folders Skipped dialog. Sonnet 5.5 built it on `claude/shell-s8b-misfit-reasons`, from `claude/shell-s8a-links`. Only wording changed. Discovery itself (how the program finds and skips folders) is the same in order and content, and the existing tests pass unchanged.

## What it did

A *misfit* is a folder the program finds that does not fit the layout, so it leaves it alone.

- In `tracker/registry.py`, each misfit now carries a required short code. An empty code is an error. All 12 places that create a misfit carry one. Two stopped entries are not misfits and carry no code.
- In `tracker/api.py`, the list reply now includes the code for each misfit (an additive change), and the vocabulary holds a code-to-phrase table.
- `pilot/wording-shell.tsv` has nine new rows for the phrases.

The phrases are: Unknown Folder, Old Layout, No Household, Unowned Folder, Name Refused, No Return, Cannot List, Look-Alike Folder, Old Workbook. The stage S5 screen should show the phrase beside the folder's name, or the name alone if the code has no phrase.

Tests: a misfit without a code fails; every creation in the registry passes a literal code; the phrases cover the codes and are two words in Title Case; the list reply carries the code. Eight deliberate breakages were all caught. The gate ran on Python 3.11 then 3.13 with the registry, API, every importer's own tests, and the guard tests, plus the code-cleanliness check.

## What it found wrong, or what was left to do

The approved wording "Not A Year" is three words, and an existing guard requires "Not a Year". The builder did not invent a replacement. The code `not_a_year` has no phrase yet, and the screen falls back to the name alone. When Jason gives a two-word phrase, add it to the vocabulary and the wording file and empty the one test exception.

## Decisions (made by Jason, or waiting for Jason)

- **Made by Jason:** ruling 18 (two-word reasons).
- **Waiting for Jason:** a two-word phrase for the `not_a_year` folder reason.

## Words to know

- **Misfit:** a folder that does not fit the expected layout.
- **Code:** a short fixed label for the reason.
- **Vocabulary:** the list of words the API sends to the screen.
- **TSV:** a plain text table file; here it lists the approved wording.
- **Title Case:** each main word starts with a capital letter.
- **Discovery:** the step that finds household folders.
