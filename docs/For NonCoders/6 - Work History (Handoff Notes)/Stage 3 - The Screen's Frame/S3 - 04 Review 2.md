# Second check of stage S3 (after the first fix round)

**Original file:** `pilot/handoffs/shell-S3-review-2.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Review · Topic: Screen · Stage: S3  
**Date:** 2026-09-29  

## In one sentence
A separate reviewer confirmed nine of the ten earlier fixes, fixed one leftover problem itself, and reported six more findings, two of which were caused by the fix round.

## What this session was asked to do
Check stage S3 (part of the app's new screen) after fix round 1. The reviewer was a separate Opus 5.5 session at high effort that built neither S3 nor its rebuild. It worked on branch `claude/friendly-archimedes-33y9uk` at commit `e973147`, and compared against the plan (SPEC-shell sections 10, 3-5, 6, 8, 11, 12 and 14).

## What it did
- Ran the tests on Python 3.11 and 3.13, one file per process. All passed. The code checker was clean and the repository map current.
- Took 81 screenshots and looked at many, in light and dark, at two window sizes, including the contrast theme. It also wrote its own throwaway browser probes.
- Checked review 1's ten findings: F1, F4 to F10 fixed; F2 fixed but the fix caused finding 3 below; F3 had **survived**.
- Confirmed that the rebuild changed only what the findings named. The standing rules hold: no network call, no document read, nothing sent. The page's security policy is unchanged, and spacing stays on the grid.

## What it found wrong, or what was left to do
1. **Focus ring still the wrong colour (fixed in this review).** In a contrast theme, the ring on the search box, notices and setup page was still the "Highlight" colour instead of the text colour. The reviewer added one rule and measured every control afterwards; the test now pins it.
2. **The fix for F4 broke the interaction test script** (`interact.mjs`). It waited for a big title that firm pages no longer draw. Fix: wait for the page to be drawn instead.
3. **Grey text on the selected fill.** After the F2 fix, the count on the selected section and the caption on the selected search option stayed grey on a dark or bright fill, about 2:1 and 1.1:1. Fix: give them the "HighlightText" colour.
4. **Test pages still draw a big title** on the four firm pages, teaching stage S4 the layout that decision P75 removed. Fix: drop those four titles.
5. **The handoff is out of date.** It still says the last-sort line shows the word `scan.scanning`; since F6 only the bar shows.
6. **The real-app smoke test says "0 page errors" while the page shows an error notice.** The pretend reply has no `items`, so the app catches an error and draws it. Fix: give the reply `items: []` and make the test also fail on anything logged.
7. **An empty crumb button.** If a household is not in the list, the path draws a clickable button with no name. Fix: leave that segment out.

## Decisions (made by Jason, or waiting for Jason)
Both departures from the plan remain **proposed**, not settled (proposed decisions 2 and 3 in `shell-S3.md`): the tour and pilot files keep their own key listeners (plan says "one listener"), and a focused text box shows no tooltip (plan SPEC 8.5). The rebuild file names both openly.

## Words to know
- **Reviewer / review:** a check by someone who did not build the work.
- **Finding:** a problem the checker reports.
- **Crumb (path):** the row of clickable names at the top showing where you are, such as Clients › year.
- **Regression:** a new problem caused by a fix.
- **Forced colours / contrast theme:** a Windows setting replacing an app's colours for readability.
- **Focus ring:** the outline showing where the keyboard is.
- **Smoke test:** a quick test that the whole thing starts and shows something.
- **Harness / stub:** a test setup and its pretend replies.
- **Security policy (CSP):** rules that stop a page from running code it should not.
- **Commit:** one saved step in the program's history; a short code like `e973147` names one.
