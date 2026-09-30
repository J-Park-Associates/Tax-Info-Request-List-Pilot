# Final review A: safety of the engine and the app window

**Original file:** `pilot/handoffs/shell-final-review-A.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Final check · Topic: Screen  
**Date:** not stated  

## In one sentence

An independent reviewer checked the engine and window code for the whole new screen and said nothing blocks the merge, but listed three findings that should be fixed and four notes.

## What this session was asked to do

Review one area of the joined shell branch against the main branch: the engine (`tracker/api.py` and related files), the app window code, and the agent deny list in `.claude/settings.json`. The reviewer built none of it.

## What it did

**Verdict:** nothing in this area blocks the merge.  
- No new code reads, moves or alters a client document.
- The firm-wide view only reads. A test checks it.
- Sorting and filing behave as before. The engine changes are word changes plus one small code label on skipped folders.
- A file that may only be revealed cannot be plainly opened. An unreported path or a link is refused. No error output or path reaches the screen.

It tested the affected files under Python 3.11 then 3.13, and all passed. It also ran the engine's own tests, because the API file changed. Ruff and the map check were clean. It made 17 mutation checks (breaking the code on purpose). Fourteen were caught, two survived as harmless equivalents, and one (M14) survived as a test gap.

## What it found wrong, or what was left to do

1. **The move-schedule warning is never shown.** It exists in the vocabulary, but the only confirm box still shows the bare question. Someone on a second PC could say yes and both computers would run the sort. Fix: add the warning to that confirm.
2. **The "do not open" warnings on emails, zips and non-documents are gone,** while their names became reveal links. One more click could open a zip on the Drive machine, which decision 190 says never happens. Jason's call: keep a short warning, or make these names plain text.
3. **The firm row's problem word "Could not be read" is not Title Case.** One-line fix; the reviewer suggests "Record Not Readable", or Jason's word.
4. A stale "PROPOSED" comment remains on two approved words.
5. A command that is not a sort, if killed at the 30-minute cap, is reported as "Sort Stopped: Ran Too Long". A neutral word would fit better.
6. A failed sort no longer says why on the return's own banner. Only Jason needs to decide if he wants a short reason shown.
7. **Speed:** on local disk, 100 returns took about 1.3 seconds for the firm view. About 10 seconds for 750 returns. Google Drive was not measured. Not a blocker.

**Test gap (M14):** the read-only test does not cover a case where the program's store has fallen behind the record. It is a test gap, not harm to documents.  

No findings on the message bridge, the menu channel, the fallback log, the deny list, first paint, skipped-folder codes or the paused flag.

## Decisions (made by Jason, or waiting for Jason)

- **Waiting for Jason:** finding 2 (emails and zips: warning or plain text); the word for finding 3, if he wants his own; and, only if wanted, finding 6 (show a reason).
- Later rulings 24 (plain text for emails and zips), 25 and 29 (failure reasons) answered findings 2 and 6.

## Words to know

- **Engine:** the rules and code that sort and file documents.
- **Deny list:** files Claude's own tools may not read.
- **Reveal-only:** a file that may be shown in File Explorer but never opened.
- **Mutation check:** breaking the code on purpose to prove a test notices.
- **Store:** the program's own quick-lookup copy of what each record says.
- **Vocabulary:** the approved words the screen draws.
- **Title Case:** capitalising the main words of a phrase.
