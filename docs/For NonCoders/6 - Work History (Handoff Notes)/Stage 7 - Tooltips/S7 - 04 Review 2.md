# Second check of stage S7 (after the fix round)

**Original file:** `pilot/handoffs/shell-S7-review-2.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Review · Topic: Screen · Stage: S7  
**Date:** not stated  

## In one sentence
A reviewer confirmed all four earlier S7 fixes and Jason's 300 ms delay, and found one small leftover: a handoff still said 500 ms.

## What this session was asked to do
Check stage S7 (the hover hints, or tooltips) after fix round 1. The reviewer built neither S7 nor the fix. It looked at branch `claude/shell-s7-tooltips` at `99defa4` (code commit `99aba3e`). It changed no code; it only added this file and refreshed the repository map.

## What it did
- **Script order (F1):** confirmed by running the screenshot script over every scenario (81 shots, no problems) and the real-app run three times, plus the interaction script ("all interactions pass").
- **Hiding when scrolled away (F2):** checked in a browser. The hint followed its control at a small scroll and hid once the control was fully clipped, and stayed hidden. It read the outside library's code, confirmed it really has that feature, and re-downloaded the library independently to confirm its fingerprints (SHA-256) still match, so no bundled file was altered.
- **CDN check (F3):** tested six sneaky tags. Five failed the test as they should. One, an upper-case `<SCRIPT SRC=...>`, passed.
- **Decision numbers (F4):** "P86" is gone and no new number appears.
- **300 ms delay (ruling 7):** in a browser, no hint at 260 ms, hint at 320 ms, immediate on keyboard focus, and none on the search box.
- **No regressions:** hints stay 8 px inside the window at all eight edges and corners; words are short; no network call; standing rules hold.
- All test files passed on Python 3.11 and 3.13. Only the known `test_build` OCR failure remained, and was ignored.

## What it found wrong, or what was left to do
**F1:** `pilot/handoffs/shell-S7.md` still tells S6 the hover delay "stays 500 ms", and that a scrolled-away hint is "clipped, not hidden". S6 might set the plan back to 500 ms against the ruling. Fix: say 300 ms (ruling 7), add "hidden when scrolled out of view", and mark two "For Jason" bullets as settled. Documentation only.  

Notes for Jason:
- The upper-case script tag would pass the check, but the page's security policy would still block it. Adding a case-insensitive flag would close the gap.
- Once hidden, a hint does not return until the next hover or focus. That seems right and deserves one line in the plan.
- The harness tests only three edges; the reviewer checked all eight by hand.

## Decisions (made by Jason, or waiting for Jason)
Nothing new. Ruling 7 (300 ms) is built as Jason asked.

## Words to know
- **Tooltip:** a small hint shown when you hover on or tab to a control.
- **Fingerprint (SHA-256):** a short code from a file that changes if the file changes.
- **CDN:** a web server hosting code; the app must not load from one.
- **Security policy (CSP):** rules that stop a page running code it should not.
- **Regression:** a new problem caused by a change.
- **Harness:** a test setup running the screen with pretend data.
