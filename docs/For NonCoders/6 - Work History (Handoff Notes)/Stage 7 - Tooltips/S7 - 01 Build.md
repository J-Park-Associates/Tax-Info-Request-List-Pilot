# Building the tooltips stage (S7): placement by Floating UI

**Original file:** `pilot/handoffs/shell-S7.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Build · Topic: Screen · Stage: S7  
**Date:** not stated  

## In one sentence

This session moved the placing of tooltips onto a small, unedited outside library, and let keyboard focus show tips everywhere except in the search box.

## What this session was asked to do

Build stage S7 on the branch `claude/shell-s7-tooltips`, built from S3's clean tip (`afd566d`). It carries out two of Jason's rulings: ruling 2 (focus tips) and ruling 5 (the library).

## What it did

1. **Placement is now Floating UI's.** The tip sits below its control, 4 px away. It flips above when there is no room, and shifts to stay 8 px inside the window. The app's own code still handles timing (hover delay, focus, Esc, mouse-out), the one tip element, and the words. The tip is placed when shown and again on resize or scroll.
2. **Ruling 2.** Keyboard focus shows a tip on every control except the search box. Hover shows it everywhere, including the search icon.
3. **Floating UI is vendored, unedited.** It is copied into the app as two script files, three licence files and a README. The README lists the versions and fingerprints. There is no outside download, no bundler and no change to the package file. The security policy is unchanged.

**The exact packages** are `@floating-ui/dom` 1.8.0, `@floating-ui/core` 1.8.0 and `@floating-ui/utils` 0.2.12. Their fingerprints were compared with the registry's before copying. Two files ship, not one, because joining them would break the match with the published bytes. The third package's code is already inside the core file.

**Tests added.** One checks the fingerprint of every vendored file and that no extra file is there. The loading-order test now checks every script is the app's own. One checks the tooltip uses the library only through its one global. One checks that only the search box shows no tip on focus. A browser script checks tips stay inside the window at three edges and still show in a contrast theme. The test server now serves subfolders.

**Checks.** Ten test files passed on Python 3.11 and 3.13. One build test fails on the base too (an OCR reader is missing) and was ignored. The code-cleanliness check is clean. Deliberate breakages on a scratch copy were caught by tests.

## What it found wrong, or what was left to do

Left for stage S6:
- Merge this branch. The page file will conflict with S4's edits at the script block. Keep both, with the two library lines before the app script.
- Update plan section 8.5: the hover delay is 300 ms (ruling 7, replacing 500), focus shows the tip except in the search box, placement is Floating UI's, and a tip hidden by scrolling returns only on the next hover or focus.
- Log the decision row and the next number in `pilot/DECISIONS.md`.
- The installer needs no change.

## Decisions (made by Jason, or waiting for Jason)

- **Made by Jason:** ruling 2, ruling 5, ruling 7 (300 ms).
- **Proposed decision row (for S6 to log):** placement by Floating UI 1.8.0, vendored unedited, fingerprints pinned by a test, no outside download. Keyboard focus shows the tip except in the search box. Tippy.js was rejected: it is built on the older Popper.js, is about 2 MB, and was last released in 2021.
- **For Jason:** a scroll used to hide the tip. Now the tip follows its control, and is hidden when the control scrolls out of view.

## Words to know

- **Tooltip:** the small label that shows when you hover over or focus a control.
- **Floating UI:** a small library that decides where a tooltip goes.
- **Vendored:** copied into the project.
- **Fingerprint (SHA-256, integrity):** a number showing a file has not been changed.
- **Flip, shift:** moving the tip to the other side, or sideways, to stay in view.
- **Content-security policy:** rules about what code the screen may load.
- **Stage S6:** the later stage that merges branches and logs decisions.
