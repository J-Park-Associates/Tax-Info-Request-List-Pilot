# Second independent check of stage S4 (the pages): eight fixes confirmed, three findings

**Original file:** `pilot/handoffs/shell-S4-review-2.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Review · Topic: Screen · Stage: S4  
**Date:** 2026-09-29 to 2026-09-30  

## In one sentence

A second reviewer confirmed all eight fixes from the first fix round, then found one small problem it fixed itself, one word-list gap that must be solved before the pilot, and one test-harness detail it also fixed.

## What this session was asked to do

Check "rebuild 1" of stage S4, which draws the pages of the app's new screen. The reviewer had built neither S4 nor the fix round. It compared the work against the screen plan, review 1, the builder's notes, Jason's rulings and the real engine code from stage S1.

## What it did

- **Ran the tests.** Ten test files, each on its own, on Python 3.11 and then 3.13, all passed. That included `test_shell` 57, `test_single_source` 165, `test_api` 368 and `test_repo_map` 80. The tidiness check was clean and the map was current. The interaction script passed, and the screenshot script took 125 shots with no page errors.
- **Looked at the real pages** in a browser: Overview, Needs review, Reminders, Clients, household, year, return, loading, locked and the contrast themes, in light and dark, at two window sizes.
- **Re-checked review 1's problems.** F1 to F8 and the coordinator's addition were all fixed. Examples seen in the browser:
  - A single broken row left 17 of 18 rows drawn, with one notice naming it.
  - The locked page says only "In use on OFFICE-PC".
  - Clients shows an unreadable household as "Could not be read", never Complete.
  - Contrast was fully readable in both contrast themes.
  - The year page's first row sat 24 pixels under the title.
  - The page's counts equalled the firm's counts.
- **Checked the fields the pages read** against the real engine reply. No field the pages read is missing.
- **Broke the code on purpose 21 times** on a scratch copy. 20 were caught. The one not caught: a notice call left in place but switched off. That test only reads the source text, so a switched-off call still passes. Deleting the call is caught. It is noted, not a finding.

## What it found wrong, or what was left to do

- **F1 (fixed by the reviewer).** When the word list lacks a short notice word, the screen quietly drew the setup line and told no one a word was missing. Now the missing word's name is written once to the error log, and a test pins it.
- **F2 (blocking before the pilot; belongs to S6 and S1, not S4).** The real word list has none of the five short notice words. So five different problems all read "Setup needs attention", one in red and four in amber. On a household page, the notice that means sorting has stopped reads the same, with a button "Accept the folder's name". A person cannot tell them apart. Nothing is lost, and no word is invented, so it is acceptable while pages are built but not for the pilot. The smallest fix is to add words to the engine's list in Title Case: "Install Folder Name Too Long", "Folder Renamed", and words for the year pause, feed and machine, and to pin them with one test.
- **F3 (fixed by the reviewer).** The test setup's stub gave a different after-install heading than the real one. It now uses the real "Setup needs attention".
- **Notes for stages S5 and S6.**
  - Old drawing code still runs outside the safety net that F1 added. This is not reachable today because the engine never sends a null row. Keep it in mind when S5 moves those cards.
  - The stub lacks some fields that S5 will need. It also gives moved rows an empty request.
  - If the menu channel throws, navigation stops. Electron does not throw there in practice.
  - The loud-failure test only reads source text.
  - Older notes still stand: one status word is cut off in one font, a paused household is visible only on its own pages, and two test runs sharing a temporary folder can clash.

## Decisions (made by Jason, or waiting for Jason)

- Waiting for Jason: approve the five short notice words for the engine's word list (F2). The reviewer suggests "Install Folder Name Too Long" and "Folder Renamed", and needs words for the year pause, the feed and the machine warnings.
- Jason's rulings on link kinds, Title Case and the year on return names are stage S5's, so they are not reported here.

## Words to know

- **Shell:** the app's new screen.
- **Stage S4:** the build stage that draws the pages.
- **Review 2 / rebuild 1:** the second check, and the first round of fixes it checked.
- **Notice:** a short message shown at the top of the screen.
- **Stub:** a stand-in for the engine, with made-up answers, used for testing the screen.
- **Harness:** the test setup that runs the screen against the stub.
- **Error log:** a file where failure details are kept.
- **Mutation check:** breaking the code on purpose to prove a test notices.
- **Title Case:** Capitalising The Main Words, as in this phrase.
