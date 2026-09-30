# Second check of stage S8a (after the first fix round)

**Original file:** `pilot/handoffs/shell-S8a-review-2.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Review · Topic: Screen, Wording · Stage: S8a  
**Date:** not stated  

## In one sentence
A reviewer confirmed all ten earlier S8a fixes, but found that a fix broke the Open button for parked documents, and that Jason's ruling 14 was not fully recorded.

## What this session was asked to do
Check the first fix round of S8a (the engine's file links and words). The reviewer (Opus 5.5, high effort) built neither S8a nor the rebuild. It reviewed branch `claude/shell-s8a-links` at `67fd9df` and `7771aba` (the ruling 14 word change pushed during the review). It changed no code.

## What it did
- Ran the tests on Python 3.11 then 3.13; all passed, except the known OCR failure in `test_build`. The code checker was clean and the map current (286 entries).
- Confirmed F1 to F10 all hold. For example, it fed the real `main.js` many odd inputs (a `.exe`, a `.lnk`, a symbolic link, an upper-cased path, a `..` path) and every plain open was refused, while reveal worked. It confirmed the new key adds no writes, no network use and no locks, and that no new field carries a path.
- Confirmed the fix round changed only what its handoff names.

## What it found wrong, or what was left to do
1. **A parked read document's Open button is now refused.** The same copy is named twice, once as a review copy (may open) and once as a shown copy (reveal only). The app's list remembers the last kind for a path, so the reveal-only kind wins. It fails safe (nothing unmarked opens), but says "Not Opened; It Has Changed" when nothing changed. Smallest fix: return the review copy's own key where the row has one, so a path is never under two kinds. Add tests for it.
2. **Ruling 14 is applied in the word but not in the record.** The word is in, but the word list still counts 4 words for the feed notice (it is 5), and several notes and a code comment still say "PROPOSED". Fix: update those. "Machine Needs Attention" and "Could Not Be Read" stay proposed.

Notes for S5 and S6:
- Which key a file name uses: filed rows one link per name; moved rows the moved key; parked or set-aside rows the shown key. An empty key means plain text.
- The firm-wide page had no keys; S5 should raise it (this became ruling 15).
- SPEC 5.7 and 9.3 need the reveal kind and `shown_copy`.
- Some tour text and step titles are still in old casing.

## Decisions (made by Jason, or waiting for Jason)
Made by Jason (ruling 14): "Two Years Open; Sorting Paused" approved; the feed notice reads "Prior Year Data Not Found". Still waiting: "Machine Needs Attention" and "Could Not Be Read".

## Words to know
- **Reveal-only:** the app may show a file in File Explorer but never run it.
- **Review copy:** a marked copy a person may open in its normal program (decision 190).
- **Allow-list:** the list of paths the app may open or show.
- **Regression:** a new problem caused by a change.
- **Mutation check:** deliberately breaking code to prove a test would notice.
- **Symbolic link:** a shortcut that points at another file.
- **Ruling:** one of Jason's numbered decisions.
