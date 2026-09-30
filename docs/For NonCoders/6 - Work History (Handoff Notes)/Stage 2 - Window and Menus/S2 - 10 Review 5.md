# Fifth independent check of stage S2 (the menus): no problems found

**Original file:** `pilot/handoffs/shell-S2-review-5.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Review · Topic: Screen · Stage: S2  
**Date:** not stated  

## In one sentence

The fifth reviewer confirmed that the two problems from review 4 are fixed and that Jason's three rulings were applied as ruled, with no new problems found.

## What this session was asked to do

Check "rebuild 4", the fourth fix round of stage S2 (the app's menus). The reviewer had not built S2 or any of its fixes. It changed no code and no settings. It only added this note and refreshed the repository map.

## What it did

- **Checked the first problem from review 4** (a test gap: nothing tested that the backup log refuses to write through a link). It broke the refusal on purpose on a scratch copy, and a test now fails as it should. The Open error log test now covers both a link and a folder.
- **Checked the second problem** (a return value nobody used, and a stale comment). Both are gone.
- **Checked a tricky case.** If a folder is sitting where the older-log copy should go, later writes still land and the size cap still holds. Three on-purpose breakages each failed a test.
- **Checked the backup log's location (ruling a).** On Windows it is under the local application-data folder, in a folder named after the product. It is not the roaming folder. Elsewhere it is the app's per-user folder. It cannot collide with the data folder, the older upstream folder, the install folder or the settings folder. Several breakages were caught.
- **Checked the deny list (ruling b).** Exactly eight new rules were added, and nothing was removed or loosened. They name the backup log's folder for Windows and for Linux, in the same style as the rules already there. They name the folder, not just `error.log`, because that is a common name. A test pins them, and removing any one rule fails it.
- **Checked for regressions (ruling c and the rest).** The words on screen are unchanged. No error details reach a reply. Open error log is safe. No screen file changed. Nothing new touches the network, reads a client document or sends anything.
- **Checked scope.** The fix round touched only the listed files, with no extras.
- **Ran the tests.** Each test file ran on its own on Python 3.11 and 3.13, with the same results. The passing counts included `test_shell` 23, `test_single_source` 171, `test_api` 380, `test_layers` 29, `test_repo_map` 80, `test_errors` 83 and `test_tripwire` 19. `test_build` passed 30 and failed 1. That one failure, about the scanning scratch folders, also fails on the base code, so it is not new. The tidiness check passed and the map was current.

## What it found wrong, or what was left to do

No findings. Four notes for Jason:

1. The deny rules only match the default profile on drive C. A moved application-data folder is not covered. The rules guard the assistants' file tools, not a shell command such as `type` or `cat`. This is true of every rule in that file.
2. A junction (a special folder shortcut) planted at the product folder is not refused. Whoever could plant one could already write to the account's profile, and the same is true of the data home. Not worth code.
3. Uninstalling leaves the backup log behind, as it leaves the data folder. It is at most about 512 KB and can name a client. The runbook's steps for moving to another machine could mention clearing it.
4. The commit labels on the fourth fix round again read "Claude Sonnet 5.5". `CLAUDE.md` says Opus 5.5 builds. The shared history is left as it is.

## Decisions (made by Jason, or waiting for Jason)

- Made by Jason earlier: rulings (a), (b) and (c). They were applied as ruled.
- Waiting for Jason: whether the runbook should mention clearing the backup log when moving machines.

## Words to know

- **Stage S2:** the build stage for the app's menus.
- **Rebuild 4:** the fourth round of fixes.
- **Fallback log:** a backup error log used when no other one exists.
- **Deny list:** a list of files the coding assistants are not allowed to read or edit.
- **Link (symbolic link):** a file that only points to another file.
- **Junction:** a Windows folder that points to another folder.
- **Mutation check:** breaking the code on purpose to prove a test notices.
- **Repository map:** a generated guide to every file in the program.
