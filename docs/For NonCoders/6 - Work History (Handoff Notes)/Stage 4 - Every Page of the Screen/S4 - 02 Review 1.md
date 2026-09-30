# First check of the pages stage (S4): eight findings

**Original file:** `pilot/handoffs/shell-S4-review-1.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Review · Topic: Screen · Stage: S4  
**Date:** 2026-09-29  

## In one sentence

A separate reviewer found the pages stage mostly right but listed eight findings, and also listed places where the real data layer (S1) does not match what the pages expect.

## What this session was asked to do

Check stage S4, the screen's pages (Overview, Needs review, Reminders, Clients, household, year and return pages). The branch is `claude/shell-s4-pages`, reviewed at `2006aad`. The reviewer did not build S4. It compared the work with the shell plan and with Jason's rulings.

## What it did

- **Tests.** Ten test files passed on Python 3.11 and 3.13, and the code-cleanliness and map checks were clean. The screenshot run took 125 shots with no page errors.
- It compared the pages with the design mock-up in the same browser at two window sizes. They match, except for one spacing item (F7).
- It broke the code on a scratch copy several ways. Most breakages were caught by tests. Some were not (F8).
- It tried twelve kinds of loud failure. All showed a visible notice. But the first seven used the test rig's short words, not the real API's.
- It confirmed many things match the plan: every page and state, the row lists and keyboard use, and the removed old parts.

## What it found wrong, or what was left to do

- **F1.** One item with no group blanks the whole return page. Worse, after a write that worked, it could show the write as failed. Fix: set such an item aside and show one notice.
- **F2.** The lock notice adds two long API sentences to "In use on {host}". It should show only the short line.
- **F3.** Four notices show the API's own long sentence, one with a path, where the plan asks for a short line (reader, machine warnings, folder renamed, feeds).
- **F4.** The Clients page calls a household whose record cannot be read "Complete".
- **F5.** The "Set aside" fold stays open when a person comes back.
- **F6.** In a contrast theme, the focused row's step text is barely readable.
- **F7.** The year page's rows sit right under its heading, with too little space.
- **F8.** Tests miss removed parts and the "no path on screen" rule.

**For stage S6, where the real data reply differs from the plan:**
1. A file's `return` field holds a label, not a path.
2. A file's handle is missing.
3. The counts leave out parked and hand-moved files. A return with only parked files would be missing from Work waiting and would show "Complete".
4. Several wordings are still long sentences or old headings.
5. Other field names do match.

## Decisions (made by Jason, or waiting for Jason)

Notes for Jason:

1. **Status column width.** A few long status words may be cut on Windows. Advice: change nothing now, look at it in the Windows check.
2. **A failed overnight sort** shows only in the side panel foot. Jason may want a notice too.
3. **A paused household** is visible only on its own pages. Showing it on the Overview would need the API to send a paused flag.
4. A test clash on a shared temporary folder name is outside S4. Running the two Python versions one after the other avoids it.
5. The harness README does not list one test script.

## Words to know

- **Stage S4:** the build stage that made the pages.
- **Group:** a heading such as Waiting or Received that rows sit under.
- **Notice:** a small message bar on the screen.
- **Harness, stub:** the test rig, and its fake replies.
- **Mock-up:** the design picture the screen should match.
- **Mutation check:** breaking the code on purpose to see if a test notices.
- **Set aside:** requests a person put aside.
