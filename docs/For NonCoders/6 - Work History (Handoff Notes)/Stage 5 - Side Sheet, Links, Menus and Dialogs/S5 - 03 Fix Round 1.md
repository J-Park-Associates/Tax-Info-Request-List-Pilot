# Stage S5 (the side sheet), first fix round: many findings fixed

**Original file:** `pilot/handoffs/shell-S5-rebuild-1.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Fix round · Topic: Screen · Stage: S5  
**Date:** 2026-09-30  

## In one sentence

This session fixed the problems review 1 found in stage S5, left some for Jason to decide, and wrote a checklist for the job that joins the branches.

## What this session was asked to do

Stage S5 builds the side sheet (the panel that opens to check one file or one reminder), the right-click menus and the dialogs. Review 1 had listed findings, called F1 to F15. This fix round handled them, except the ones Jason was still deciding. It used made-up names only, and nothing here reads a client document. The standing rules held: no generative AI, no folder path drawn, the screen types no sentences of its own, five words at most in Title Case, and a 4 and 8 pixel grid.

## What it did

- **F1.** The sheet no longer sticks after "Not Requested" or after a "Put Back" that parks the file. It moves on when the file it shows has been answered.
- **F2.** A held reminder row now shows its document name alone. It no longer shows codes or a 25-word hold sentence.
- **F3(a).** A second identical Unfile or Mark Missing sent while the first is still running is not sent. The menu item is greyed meanwhile.
- **F4.** The Received row of a request links to its one filed copy, when that file is filed under that request.
- **F5.** Menu items now show only where they can work. For example, "Another Return" appears only for a parked document of the return on screen. "Put Back" is not offered when the moved copy's original is gone.
- **F6.** Two toasts (small pop-up messages) now come from the word list. A missing word is a loud failure, never a blank. A test forbids typed sentences in any toast.
- **F7.** The editor has one "Advanced" switch instead of per-row folds.
- **F8.** Two extra Cancel buttons in the wizard were removed.
- **F11.** A keyboard route to file links: a "Show in File Explorer" menu item.
- **F12.** A client-row menu item is answered only if its rule still holds after navigating.
- **F13.** The exact set of right-click items each row type can offer is now pinned by a test.
- **F14.** The received date on a moved copy is read from the right row. Request codes are never drawn; the request's name is. Three test gaps were closed.
- **Tests.** Named test files ran on Python 3.11 and 3.13, one at a time. The tidiness check was clean. The interaction script passed. All mutation checks (breaking the code on purpose) were caught.

## What it found wrong, or what was left to do

**Left untouched while Jason decides** (current behaviour stays):

- F3(b): a reason box for Unfile and Mark Missing (a right-click Unfile still sends an empty note).
- F4: several files under one request (no Unfile and no link on a "{n} Files" row).
- F10: two-word reasons in Folders Skipped.
- F15: the right-click write items moving the sheet on, and the reminder sheet's title.
- F9: whether the info dialogs say "Dismiss" or "Close" is stage S6's.

**Checklist for stage S6, the join.** Add the "Show in File Explorer" word to two places in the window code. Make the window's menu list match the screen's exactly. Amend two tables in the plan. Switch the open call to the newer form from stage S8a. Add three new words to the engine and then delete the temporary word copy. Re-check the new menu behaviour against the live engine's data shape.

## Decisions (made by Jason, or waiting for Jason)

- **Waiting for Jason (new words, decision row P66):**
  - "Pick a Request First" (replaces an eight-word sentence)
  - "Name Each Custom Request" (needs his approval)
  - "Advanced"
- Those words were added only to a temporary copy for the test setup. Stage S1 owns the real word list.
- Jason is still deciding F3(b), F4, F10 and F15 as listed above.
- Open for Jason (F11): the return and household links in group headings and row details
  cannot be reached with the Tab key; a keyboard user goes through the path row or presses
  Enter on the row. If Jason wants them reachable by Tab, the note says to record it for S6.

## Words to know

- **Shell:** the app's new screen.
- **Stage S5:** the build stage for the side sheet, right-click menus and dialogs.
- **Side sheet:** a panel that slides in from the side to check one file or one reminder.
- **Toast:** a small pop-up message that disappears.
- **Parked file:** a file the program would not file, left for a person.
- **Join:** merging the separate stage branches into one.
- **Harness:** a test setup that runs the screen with made-up data.
- **Mutation check:** breaking the code on purpose to prove a test notices.
- **Title Case:** Capitalising The Main Words.
