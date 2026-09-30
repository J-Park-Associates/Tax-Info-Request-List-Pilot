# Third independent check of stage S2 (the menus)

**Original file:** `pilot/handoffs/shell-S2-review-3.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Review · Topic: Screen · Stage: S2  
**Date:** not stated  

## In one sentence

A reviewer checked the second fix round of stage S2 and found the code fine, but found the repository map out of date, and fixed that.

## What this session was asked to do

Check the second fix round ("rebuild 2") of stage S2. S2 builds the menus and the small bridge between the app window and the page. The reviewer had not built S2 or either fix round. It added its own note and refreshed the *repository map*, and changed nothing else.

## What it did

- **The rebuild changed no program code.** Only the map files and its own handoff note changed.
- **The bridge (the "preload") matches its description.** It offers exactly eight things to the page: run a command, open a path, pick a folder, log an error, hear progress, hear that setup finished, hear a menu command, and send a menu command. Its claim that nothing else crosses is true. Its claim that errors are kept only in the log the API named is also true.
- **Three channels run from the window to the page**, and the bridge listens on all three: progress, the menu, and "setup finished".
- **Review 2's finding 2 is fixed.**
- The results match review 2, test for test.

## What it found wrong, or what was left to do

**Finding 1: the map was stale.** The fix round added its handoff note but did not refresh the map afterward. The note said the map was current, which was only true before the note was added. The map check failed and one map test failed.

- **Fix:** the map refresh this review had to run anyway fixed it. After it, the check passes and the map test passes (80).
- **Lesson:** a builder should refresh the map after writing its handoff, as the last step before the commit.

**A note, not a finding:** the fix round's commit says "Claude Sonnet 5.5" as co-author. The project notes say Opus 5.5 builds. The commit is on a shared branch and the history of the main line is never rewritten, so it stays. It is recorded here for Jason.  

## Decisions (made by Jason, or waiting for Jason)

- **For Jason to know:** the wrong model name in the commit trailer. No action is proposed.

## Words to know

- **Shell / S2:** the app's new screen, and its second build stage (menus).
- **Preload:** a small piece of code that passes messages between the app window and the page.
- **Channel:** one named route for messages.
- **Repository map:** the generated guide to what every file is for. It must be refreshed with every change.
- **Rebuild-2 / review-3:** the second fix round, and the third independent check.
