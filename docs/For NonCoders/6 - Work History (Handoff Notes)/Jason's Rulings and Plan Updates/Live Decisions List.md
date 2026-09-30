# The shell's list of live decisions

**Original file:** `pilot/handoffs/shell-ledger.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Rulings · Topic: Rules and decisions, Screen  
**Date:** 2026-09-30  

## In one sentence

This is a one-line-per-decision list of every choice that is still in force for the app's new screen, where each was built, and whether it is done.

## What this session was asked to do

Refresh the *ledger* after the three final reviews (A, B and C) and the fix pass that followed. A ledger is a short running list. Each line says what was decided, which stage or job built it, and what is true now. The sources are `shell-rulings.md` (rulings 1 to 29) and `DECISIONS.md` (P50 to P114). A separate reviewer still has to say whether the fix pass is done.

## What it did

It lists each decision with its status. Summary:

- **Done:** the real menu bar (P58); dark mode follows Windows (P59); Sort as the one visible icon (P60); the year always in the path (P61); five words at most, no paths, safeguards in Help (P63 and P64); a tooltip on every icon (P65); tooltip on keyboard focus except the search box (ruling 2); menu bar hidden until Alt (3); failure saved to a fallback log (4); Floating UI for tooltips (5); failure text as built (6); 300 ms hover delay (7).
- **Built and fixed:**
  - File names open File Explorer, while household and return names navigate inside the app (8 to 12). Links are now underlined.
  - Title Case throughout (10).
  - Return links read "{Return Name} ({Year})" and wrap so the year always shows (13, 27).
  - Notice words (14).
  - Needs Review file names are live links (15).
  - Unfile asks for an optional reason (16).
  - Each file under a request gets its own row (17).
  - Skipped-folder reasons, with "Bad Year" as a working word (18, 18a).
  - A failed overnight sort shows a notice on every page, with no Retry (20, 28).
  - A paused household is marked on Clients and Overview (21).
  - A runbook note on the fallback log (22).
  - Two words approved (23).
  - Email and zip names are plain text (24).
  - "Sort Failed" plus a short reason, six words approved (25, 29).
- **Accepted as built:** the tour and pilot pieces keep their own keyboard listeners (ruling 1), logged as P85.
- **Kept as built:** the sheet moves on to the next file after a write (19).
- **Superseded:** the greyed Retry on firm pages (26), replaced by ruling 28.
- **Withdrawn by Jason:** renaming "Open Client Folder" to "Open Client Window".

Work that came before the rulings (engine words, menu words, page literals, the spec, tests and the clickable mock-up) is all done.

## What it found wrong, or what was left to do

Two failure kinds ("Drive Not Signed In" and "Ran Too Long") are not mapped, because the engine does not tell them apart there.

**Still open for Jason** (listed in `pilot/HANDOFF.md`):
- The spec's section 19 defaults O1 to O6 (O4 was built without a ruling).
- The working word "Bad Year".
- How fast the firm view is on Windows.
- The status word "Came in Email or Zip", which is cut on screen.

Nothing blocks the build. The Windows check (installer and contrast themes) is in `pilot/wintest/PROMPT-shell.md`.

## Decisions (made by Jason, or waiting for Jason)

The numbered rulings are Jason's; the P rows come from the project's decision list, `DECISIONS.md`. The open ones are listed under the section above.

## Words to know

- **Ledger:** a running list of decisions and their status.
- **Ruling:** a decision Jason made, numbered.
- **Fix pass:** a round that fixes what the final reviews found.
- **Title Case:** capitalising the main words of a phrase.
- **Notice:** a message at the top of the page area.
- **Fallback log:** a backup error file the app keeps locally.
