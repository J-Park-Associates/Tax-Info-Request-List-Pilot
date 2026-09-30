# File names become links, and words go to Title Case (stage S8a)

**Original file:** `pilot/handoffs/shell-S8a.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Build · Topic: Screen, Wording · Stage: S8a  
**Date:** not stated  

## In one sentence

S8a made every filed document's name into something the page can turn into a link that shows the file in File Explorer, and re-cased every drawn word to Title Case, on the engine and window side only.

## What this session was asked to do

Carry out Jason's rulings 8 to 13 (see `shell-rulings.md`; the note itself names rulings 10, 11 and 12) on the engine and the app window, not the page code. The branch was built from S2's clean tip. A first session left unfinished work. This session audited it, finished it and gated it. No page (renderer) file was touched.

## What it did

1. **Only a file name opens File Explorer.** The engine gives each filed document's working copy, and each moved-by-hand copy, a key. The real path is kept in a separate list of allowed paths. Households and returns carry no such key (rulings 11 and 12). This is read-only: no lock, no write, no document read.
2. **The window's `open-path` takes an optional "reveal" argument** on the same channel. A reported file is shown selected in File Explorer. A reported folder opens as before. Anything the API did not report, or a link, is refused.
3. **Return links can read "{Return Name} ({Year})".** Every row that names a return carries its year.
4. **Words in Title Case** for every drawn phrase of five words or fewer, including "Needs Review" and "Could Not Sort". The rule is one small function in `tests/test_api.py`. Words like "with" and "from" get capitals because they are not on Jason's small-word list.

New words: "Show in File Explorer", "Navigate to Client", "Navigate to Return". "Open Client Folder" is not renamed.

**Merge with S1 rebuild 3:** conflicts were resolved. The setup heading is now "Setup Needs Attention". In the firm file list, S1's shape won: `return` is the return's path, plus year, handle, name, code, received and suggestion. The note lists the final field names for the pages.

**Audit of the first session's work:** docs and tests that quoted old-cased button names were fixed, firm rows gained a label and year, and a stale comment was corrected. Three mutation checks were made.

## What it found wrong, or what was left to do

- **Flag for Jason:** "Could not tell" became "Could Not Sort", not his earlier "Could not Sort", because the Title Case ruling wins.
- **Page and pilot words still to change (S5 and S6):** many literals in the page files, the tour and the safeguard names. Examples: "Look again", "Add a return", "Needs review", "New household", and tour step titles. Two refusal messages in the window file are not drawn in normal use.
- **The page file `pages.js` does not exist on this branch.** File links and return links are S5's to draw.
- **Proposed spec edits for S6:** right-click "Show in File Explorer" acts on file rows only; name the reveal option; add the new words and the Title Case rule; add decision rows.
- The build test for scratch-root scanning was not run because it fails on the base.

## Decisions (made by Jason, or waiting for Jason)

- **Made by Jason:** rulings 8 to 13 (file links, household and return behavior, Title Case). Ruling 10 wins over earlier spellings.
- **Waiting for Jason:** confirming "Could Not Sort" as the spelling.

## Words to know

- **Engine:** the rules and code that sort and file documents.
- **Working copy:** the copy of a document the program works on. Originals are never altered.
- **Reveal:** show a file selected inside File Explorer instead of opening it.
- **Title Case:** capitalising the main words of a phrase.
- **Key:** a short label the page uses to ask for a file's real path.
- **Mutation check:** breaking the code on purpose to prove a test notices.
