# Second fix round for the screen's frame stage (S3)

**Original file:** `pilot/handoffs/shell-S3-rebuild-2.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Fix round · Topic: Screen · Stage: S3  
**Date:** not stated  

## In one sentence

A builder fixed six problems from the second check of the screen's frame, and none of the findings was wrong.

## What this session was asked to do

Fix findings 2 to 7 of "review 2" of stage S3, and nothing more. The work was done by Sonnet 5.5 at default effort on the branch `claude/friendly-archimedes-33y9uk`. Two departures that need Jason (the tour and pilot keyboard listeners, and no tooltip on a focused text box) were left alone. They stay proposed decisions 2 and 3 in the file `shell-S3.md`.

## What it did

The session also confirmed that review 1's finding 3 still holds: in a high-contrast theme, the keyboard focus ring is drawn in the system text colour, and a test pins it.

1. **A test script timed out on a firm page with no data.** It now waits for anything to be drawn, not for a page heading. It ends with "all interactions pass".
2. **Grey text on the selected highlight.** The selected section's count and the selected search result's caption were grey on the highlight colour. One style rule now makes them the highlight-text colour. Measured: white on navy in light contrast, black on cyan in dark contrast. The session looked at both screenshots.
3. **The test pages drew a heading on the four firm pages.** Those headings were removed from the test stand-in. The household page keeps its name as a heading, as the plan says.
4. **A wrong sentence in the S3 handoff.** It said the last-sort line shows a scan word. It now says the bar shows alone when its numbers are missing, and no word is supplied for that case.
5. **The real-app smoke test hid an error notice.** The stand-in reply was made complete. The test now reports any logged error or visible error notice as a problem. It printed "0 page errors, 0 logged, no visible error". Before the fix, the same run failed, so the check works.
6. **An empty button in the path bar.** A household or return that is not in the list is now left out of the path, so it shows "Clients" then the year, with no unnamed control. A test pins this.

Checks: the screenshot run took 81 shots with a clean real-app line, and all interactions pass. Test files ran in parallel under Python 3.11 and 3.13, and the code-cleanliness and map checks were clean. The API test file was not rerun, because no Python module it imports changed.

## What it found wrong, or what was left to do

Nothing new. Two Jason decisions remain open (below).

## Decisions (made by Jason, or waiting for Jason)

- **Waiting for Jason:** proposed decisions 2 (the tour and pilot keyboard listeners against plan section 14.1) and 3 (no tooltip on a focused text box, against plan section 8.5).

## Words to know

- **Stage S3:** the build stage that made the screen's frame (side panel, search, path bar).
- **Rebuild, review:** a fix round, and an independent check.
- **High-contrast theme:** a Windows display mode with strong system colours.
- **Harness:** a test rig that runs the screen in a browser with made-up data.
- **Stub:** a stand-in that fakes the real program's replies.
- **Smoke test:** a quick run to see that the app starts and does not fail.
- **Crumb, path bar:** the trail such as Clients, year, household at the top.
