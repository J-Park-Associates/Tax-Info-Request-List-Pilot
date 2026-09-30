# Building the new screen's frame (stage S3)

**Original file:** `pilot/handoffs/shell-S3.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Build · Topic: Screen · Stage: S3  
**Date:** 2026-09-29  

## In one sentence

The S3 builder made the frame of the app's new screen (side panel, path, search, sort icon, notices, colors, first-run setup) and left notes for the sessions that build the pages on top of it.

## What this session was asked to do

Build stage S3 of the new screen, "the shell", from `pilot/SPEC-shell.md`. It is the "renderer foundation": everything the pages will sit inside. It was built on the spec branch, and stage S4 starts from it once S3's latest review says "No findings". Nothing in it was reviewed yet when this note was written.

## What it did

- **Built the frame:** a side panel with four sections, counts, a last-sort line and a Pilot badge. Also the path across the top, the search box, one sort icon, the notice area and the page area. Light and dark colors work. The first-run setup page works, from a made-up folder to the Overview.
- **Colors:** every color is now a named light-and-dark pair.
- **Tour and Help:** the tour is one short line per step. Help can start the tour and show the terms again.
- **Shared page pieces:** the rows and groups every page will use are already in the style sheet.
- **The old screen** stays in the page, hidden, so the old code keeps working until the new pages take over.
- **Old code changes:** only six one-line hooks were added. No card code was touched.
- **Tests and harness:** 29 new tests in `test_shell`. A *harness* (a test rig) took 81 screenshots and ran 30 keyboard and mouse checks. It found and fixed one real bug.

**Notes it left for the next stages:**
- **S4 (pages)** gets a list of what the frame offers and the row styles. S4 must add its page file, delete each old card as it takes over, turn the hidden banners into notices, and remove a few unused styles.
- **S5 (sheet and dialogs)** gets the empty sheet frame. Esc closes the sheet before search and the tooltip.
- **S6 (join)** must supply the words, menu names, the firm command and a few fields from the real API.

## What it found wrong, or what was left to do

**Loud failures - read this.** Until S4 turns them into notices, the old warning banners are hidden and not drawn. They include the reader warning, machine warnings, the last-pass line, the after-install banner, the lock notice, the result banner, the folders-skipped card, the names-shortened card, "Two years open" and "Folder renamed" with Accept. That last one leaves a household's sorting paused until someone accepts, so it is a real silent failure. **This branch must not ship on its own.**

Other points:
- In an emulated high-contrast theme the selected section drew as white on white. The note blames the emulator; review 1 later found the real cause. It says to check on the Windows office PC.
- Some unused styles remain until S4 removes them.
- The Electron window itself was not run here.
- One build test fails on this branch and on the branch it started from. That is the cloud machine, not this work.
- **A slip:** two commits were also pushed by mistake to the spec branch. Jason decides whether to reset it.

## Decisions (made by Jason, or waiting for Jason)

Proposed decision rows for S6 to log:
1. The old screen stays hidden between S3 and S4/S5.
2. One keydown listener is kept as the old code owns it; new files add none.
3. Keyboard focus shows a tooltip everywhere except the search box (changed later by Jason's ruling 2).
4. The "no title attribute" test covers the new files now.
5. Two tour titles were changed to the spec's words.

Waiting for Jason: whether to reset the spec branch.

## Words to know

- **Shell:** the app's new screen.
- **Renderer:** the part of the app that draws what you see.
- **Harness:** a test rig that draws the screen with made-up data.
- **Notice:** a message drawn at the top of the page area.
- **Seam:** a small hook where new code plugs into old code.
- **Tooltip:** a small label that appears when you point at an icon.
