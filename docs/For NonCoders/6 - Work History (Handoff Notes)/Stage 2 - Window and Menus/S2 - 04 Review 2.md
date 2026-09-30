# Second independent check of the menus job (S2): two findings

**Original file:** `pilot/handoffs/shell-S2-review-2.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Review · Topic: Screen · Stage: S2  
**Date:** not stated in the note  

## In one sentence

The second reviewer confirmed the first round of fixes worked, fixed one leftover error in a
note, and found one new gap in another note.

## What this session was asked to do

Review job S2 (window and menus) again after its first fix round. The reviewer did not build
S2 or the fixes. It could change this handoff, one note in the repository map, and the map
refresh.

## What it did

- **Checked F1 (the unknown-id test).** Broke the code on purpose so it kept every id; the
  test failed as it should. It also would catch a mix-up between menu-bar ids and popup ids.
  The file was restored and its fingerprint was the same before and after.
- **Checked F2 (map notes)** against the code and found them true, except one clause.
- **Checked F3 (runbook)** and found it correct and clear.
- **Searched other documents** for claims that failed-command details are shown on screen.
  Three remain; none is a finding. One is an old decision row that is history and will be
  replaced in a later job (S6). One test survey names an old test, left to S6.
- **Confirmed the rebuild changed nothing beyond its findings,** and checked there is no
  regression: the menu bar, the keyboard shortcuts, the six right-click popups and the
  security rules of the channel all match the plan.

## What it found wrong, or what was left to do

1. **A leftover of the earlier F2: fixed by the reviewer.** The map said there are two
   channels from the app's main part to the screen. There are three (progress, menu, and
   after-install-done). The note now says three, and the map was refreshed. Tests were re-run.
2. **New: the `app/preload.js` note says "Nothing else crosses"** but leaves out two calls the
   file exposes (one that logs an error and one that hears progress). The gap is older than S2.
   The smallest fix is written out; it is left to the builder.

Test results (Python 3.11 and 3.13, same on both): `test_shell` 20, `test_single_source` 168,
`test_layers` 29, `test_repo_map` 80, `test_api` 380, `test_errors` 83, `test_tripwire` 19,
`test_pilot` 15. Style checks passed and the map is current.

## Decisions (made by Jason, or waiting for Jason)

Nothing is stated in the note.

## Words to know

- **Preload:** a small file that decides what the screen may ask the app's main part to do.
- **Channel:** a named path for messages between the app's main part and the screen.
- **Repository map:** the generated guide to every file in the project.
- **Popup:** a right-click menu.
- **Regression:** something that used to work and now does not.
- **Fingerprint (sha256):** a short code that changes if a file changes at all.
