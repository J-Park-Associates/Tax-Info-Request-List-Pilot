# First independent check of stage S3: the screen's frame

**Original file:** `pilot/handoffs/shell-S3-review-1.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Review · Topic: Screen · Stage: S3  
**Date:** 2026-09-29  

## In one sentence

A reviewer checked the new screen's frame (side panel, path bar, search, colors) against the spec and found 10 problems: one that loses data, one that makes text unreadable in a high-contrast theme, and eight smaller mismatches.

## What this session was asked to do

Check stage S3 of the app's new screen, "the shell". S3 built the frame: the side panel, the path across the top, the search box, the sort icon, the notice area and the colors in light and dark. The reviewer was a separate session that did not build S3.

## What it did

- Ran the affected tests under Python 3.11 and 3.13. All passed. Ruff was clean and the map was current.
- Took 81 screenshots of many screens, in light and dark, at two window sizes, and drove the app by keyboard and mouse. It found no page errors.
- Recomputed a sample of color-contrast numbers by hand. Every one matched the spec.

It confirmed these hold:
- The old page code gained only small one-line hooks, and no card code changed.
- The standing rules hold: no network call, no document read, nothing sent.
- Every icon has a name and a short tooltip. Motion turns off when asked. Spacing follows the grid. Long names are cut with "..." and show a tooltip. Search works.
- The words match the approved wording table.

## What it found wrong, or what was left to do

- **F1 (loses data):** File > Change clients folder... erases the firm's name and phone. The setup page starts with empty boxes, and pressing Start saves the empties over the real values. The client reminder letter prints both. Fix: fill the boxes from the saved values, and add a test.
- **F2:** in a high-contrast theme, the selected section's name (for example "Clients") is unreadable. Fix: turn off automatic color forcing on three rules.
- **F3:** the focus ring uses the wrong system color. It should be `CanvasText`.
- **F4:** firm pages show a heading in some states, though firm pages should have none.
- **F5:** the path bar can show a full folder path as a name. The spec says never show a path.
- **F6:** the last-sort line says "Scanning...", which is not an approved word.
- **F7:** two tour step titles ("Scan", "Needs Review") should be "Sort" and "Needs review" per the spec.
- **F8:** section names sit 24px from the panel edge, not 16px.
- **F9:** the handoff left out four hidden warnings (folders skipped, names shortened, two years open, folder renamed with Accept). The last one leaves a household's sorting paused until someone accepts, so it is a real silent failure. Also the "locked" screenshot shows a notice the real app would not draw.
- **F10:** one stray size in the style sheet and one unused size setting.

**Not findings, for Jason and S6:** two departures from the spec were raised openly and need Jason's yes, not a rebuild. Three vocabulary tests from the spec may not exist yet; S6 should check. The notice still says "Look again" and "Dismiss", which is S4's work.

## Decisions (made by Jason, or waiting for Jason)

- **Waiting for Jason:** the two departures (separate keydown listeners for the tour and pilot pieces; no tooltip on a focused text box). Later rulings 1 and 2 settled them.

## Words to know

- **Shell:** the app's new screen.
- **Contrast theme (forced colors):** a Windows setting that replaces the app's colors with a few system colors for easier reading.
- **Focus ring:** the outline that shows which control the keyboard is on.
- **Tooltip:** a small label that appears when you point at an icon.
- **Notice:** a message drawn at the top of the page area.
- **Harness:** a test rig that draws the screen with made-up data and takes screenshots.
