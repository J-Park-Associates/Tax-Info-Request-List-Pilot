# Stage S3 fixes after the first check

**Original file:** `pilot/handoffs/shell-S3-rebuild-1.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Fix round · Topic: Screen · Stage: S3  
**Date:** 2026-09-29  

## In one sentence
This session fixed all ten findings from the first check of stage S3, and left three questions for Jason.

## What this session was asked to do
Answer `shell-S3-review-1.md`. It was built by a Sonnet 5.5 session at default effort, on branch `claude/friendly-archimedes-33y9uk`, starting from commit `7e199c2`.

## What it did
All ten findings were right; none was refused.
- **F1:** Changing the clients folder now keeps the firm's name and phone, so Start no longer sends empty text. A test pins this.
- **F2:** In a high-contrast theme, the selected section, selected search option and focused row are now readable.
- **F3:** The focus ring in a contrast theme uses the text colour.
- **F4:** Firm-wide pages draw no big title; that includes the loading and failed states. One bug ("null" printed as a word) was caught and fixed.
- **F5:** If a household or return is not in the list, its path is never shown as its name. A test pins this.
- **F6:** While the count is unknown, the side panel's foot shows only the bar, no text.
- **F7:** The tour titles are now "Sort" and "Needs review".
- **F8:** Section names sit 16px from the panel edge.
- **F9:** The handoff now lists all the loud-failure banners, including one real silent failure. The test scene no longer fakes a notice.
- **F10:** The underline spacing follows the grid and an unused size was deleted.
- It added one test for F2, F3 and F8. Checks ran on Python 3.11 and 3.13; the code checker was clean, the map current, and screenshots were re-taken and looked at. `test_build`'s scratch-roots test was not run because it already fails on the base.

## What it found wrong, or what was left to do
Three items are left as built, not decided: two departures from the plan (below), and S6 should make sure the plan's vocabulary tests (SPEC 14.1) exist, since none of S1 to S3 owns them.

## Decisions (made by Jason, or waiting for Jason)
Waiting for Jason:
1. Two files, `tour.js` and `pilot.js`, keep their own key listeners, but the plan (SPEC 14.1) says "one listener". Approve, or ask S6 to fold them in (proposed decision 2).
2. No tooltip appears when a text box is focused, unlike SPEC 8.5 as written; hovering still shows it (proposed decision 3).

## Words to know
- **Rebuild:** a round of fixes after a check.
- **Finding (F1 to F10):** one problem a checker reported.
- **Contrast theme (forced colours):** a Windows setting that swaps an app's colours for high-contrast ones.
- **Focus ring:** the outline showing which control the keyboard is on.
- **Keydown listener:** code that reacts when a key is pressed.
- **Tooltip:** a small note shown when you hover over something.
- **Harness:** a test setup that runs the screen with pretend data and takes screenshots.
- **Loud failure:** a banner that tells the person something went wrong.
