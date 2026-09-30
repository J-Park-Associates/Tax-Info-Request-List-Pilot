# Stage S2: the window and its menus

**Original file:** `pilot/handoffs/shell-S2.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Build · Topic: Screen · Stage: S2  
**Date:** not stated  

## In one sentence
Stage S2 built the app's menu bar, its right-click menus and the window's first colour, and set the shell's own messages to the engine's wording.

## What this session was asked to do
Build exactly the S2 row of the written plan (SPEC-shell section 16). It started from stage S1's branch (whose latest check said "No findings") and worked on `claude/shell-s2-menus`. No screen (renderer) file was touched.

## What it did
- **The menu bar** has File, Edit, Client, View, Tools and Help, with only the keyboard shortcuts the plan lists (such as Ctrl+N, Ctrl+E, Ctrl+1 to 4, Ctrl+F, F5, F9). There is no Reload, Zoom, Full screen or Developer tools item in either build.
- **The words** are exactly the engine's 44 menu words. The engine can replace a word, but never add, remove or rename an item.
- **Turning items on and off:** the page tells the menu which items to enable. Eight items need nothing from the page and are always enabled, such as change clients folder, tour, terms and about.
- **Right-click menus:** six pop-ups (household, return, file, moved, request, received). Each item is enabled only if that pop-up says so.
- **The menu channel** is a one-way message line each way between the page and the window. The window ignores anything from another source, drops unknown items, and refuses over-long tokens.
- **Open error log** goes through the existing safe "open" path. If there is no log, the page is told, and it shows "No error log yet".
- **First paint:** the window's first colour is read from the style sheet for light or dark, and is left alone in a high-contrast theme.
- **Shell words** were set to the engine's. With no error log, a failed command now says "Tracker failed; no error log" and the technical output is dropped, not shown.
- **Tests:** a new file `tests/test_shell.py` (20 tests) and changes to `tests/test_single_source.py`. All named checks passed on Python 3.11 and 3.13; the code checker was clean and the map current. `test_build` was not run because it already fails on the base.

## What it found wrong, or what was left to do
- Later stages must join two things: `tests/test_shell.py` also exists on S3's branch (S6 merges both), and the two window colours in `pilot-ui.css` come from S3's branch.
- The page's half of the "every menu id is answered" test is not written yet (S6).
- The page must not act on a shortcut key that the menu already handled, or it will act twice. S6 should check this on Windows.
- The menu bar stays hidden until Alt is pressed; showing it always is a one-line change.
- A survey file, `pilot/shell-test-pins.md`, still names some renamed tests.

## Decisions (made by Jason, or waiting for Jason)
Nothing blocking. Jason may want to say two things: whether the menu bar stays hidden until Alt or is always shown, and whether dropping the technical output entirely when there is no error log is what he intended.
Proposed decision rows for S6: the menu is the app's own in both builds (P58); the menu channel is untrusted on arrival; Open error log is the shell's alone; with no log the reply drops the output (replacing decision 186's earlier rule); the first colour is read from the style sheet (P59, P73).

## Words to know
- **Renderer:** the part of the app that draws the screen.
- **Accelerator:** a keyboard shortcut for a menu item.
- **Channel (IPC):** a named message line between the page and the app's window.
- **Token:** a short label the page sends so its row can be recognised in the reply.
- **stderr:** the technical error output a program prints.
- **Error log:** a file of technical detail for a person to read later.
- **Forced/contrast theme:** a Windows setting that replaces an app's colours for readability.
