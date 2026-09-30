# Stage S5 built: the side sheet, file links, right-click menus and dialogs

**Original file:** `pilot/handoffs/shell-S5.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Build · Topic: Screen · Stage: S5  
**Date:** 2026-09-30  

## In one sentence

This session built the side sheet, the three kinds of links, the right-click menus and four dialogs for the app's new screen, and listed the points where it departed from the plan.

## What this session was asked to do

Build stage S5 of the new screen ("the shell"), from section 16 of the shell plan. It was built on the reviewed end of stage S4 (the pages). The engine side of file-name links, from stage S8a, was still in review and not merged. So the test setup copied its documented shape and words. Nothing here was reviewed yet. Made-up names only; nothing reads a client document.

## What it did

- **The side sheet.** One panel slides in from the side to check a file or draft a reminder.
  - It opens from a row's step, from Enter, from a double click or from a right-click item.
  - Focus moves into it, Tab stays inside, and Esc or a click outside closes it. Focus then returns to the row.
  - Checking a file shows its name, a status line, a "Belongs To" picker with the reasons, a box for the issuer of a K-1, a one-click "file where it waits" block, and a "More" fold. The footer has the two answer buttons.
  - Next moves to the next file without writing. After a write that works, the sheet shows the next file, or closes after the last.
  - The reminder letter shows in the same sheet. Its existing functions are unchanged. A held reminder shows the hold and no Copy or Approve.
- **The links.** A file name links to show that exact copy in File Explorer. A household name and a return name move around the app. A refused open shows a notice. The folder path is never drawn, and a test walks every page to prove it. Return links read "{Return Name} ({Year})".
- **Right-click menus.** Every row carries what kind of row it is. A right-click, Shift+F10 or the menu key shows the items that apply. A live lock greys the writing items. File items open the sheet and press its own button, so the write is the sheet's own.
- **Four dialogs.** Roll forward, Safeguards, About and Folders Skipped.
- **Help lines cut.** Many explanatory lines were removed from the household editor, the schedule, the new-household wizard and the editor. The sharing and feed warnings and the Active warning were kept.
- **Review 2's notes for S5** were handled: the old drawing code outside the safety net is gone, the stub carries the fields S5 needs, and a menu channel that throws now gives a notice and does not stop navigation.
- **Tests.** On Python 3.11 and 3.13: `test_shell` 81 (24 new), `test_pilot_ui` 11, `test_single_source` 165, `test_layers` 29, `test_tour` 8, `test_pilot` 18, `test_api` 368, and the repository-map tests passed. The tidiness check was clean. Mutation checks were caught after two extra tests were added for the survivors.

## What it found wrong, or what was left to do

Departures and questions:

1. Return link text uses the return's name plus its year. The brief said to use the engine's `label`, but that already carries household and year and would repeat them.
2. The Folders Skipped dialog has no two-word reason yet. The engine sends only a long sentence. It needs a word from stage S1.
3. The three info dialogs close with "Dismiss". The plan says "Close", and the engine has no such word.
4. "Unfile" is not offered for a request answered by several files. Which original would it be? This needs a decision.
5. A filed request with several copies has no link, and a request with several files shows "{n} Files" as plain text.
6. A moved file's link text is its original name.
7. The reveal call and the "Show in File Explorer" item need stage S6's join. Do not run this branch in Electron before the join, or a file link would open the file in its default program.
8. The shape of the engine's list of file paths was built from the plan and must be checked against the real reply.
9. Not done from the audit: the single "Advanced" switch, and the removal of two of the three Cancel buttons. Custom rows' columns were cut to Document.
10. The reminder sheet has no client name in its title.
11. Some cut help words still exist in the engine and can be dropped.
12. Next's order leaves out files already set aside.
13. A right-click write item writes at once and then the sheet moves on. Jason may want a confirming look first.
14. A return read only for the sheet stays marked active. Closing the sheet clears its lock notice.

**For stage S6:** merge the other branches, join the menu item and the reveal argument and the missing words, delete the temporary word copy, do the tour and Title Case lines, and write decision rows for rulings 1 to 15.  

## Decisions (made by Jason, or waiting for Jason)

- Waiting for Jason: departure 4 (Unfile on a request with several files needs a decision),
  departure 10 (Jason may want the return's name in the reminder sheet's title) and departure 13
  (Jason may want a right-click write item to stop at the open sheet for a confirming look).
- Departures 2 and 3 need words from stage S1; departure 1 is for S6 to keep or change.
- Jason's rulings 8 to 13 (links) and 15 (links on the firm-wide Needs Review page) were applied.

## Words to know

- **Shell:** the app's new screen.
- **Stage S5:** the build stage for the side sheet, links, menus and dialogs.
- **Side sheet:** a panel that slides in from the side to check one file or reminder.
- **Parked file:** a file the program would not file.
- **Join:** merging the separate stage branches into one.
- **Test stub / harness:** a stand-in for the engine, with made-up answers.
- **Mutation check:** breaking the code on purpose to prove a test notices.
- **Unfile:** take a file back out of a request.
