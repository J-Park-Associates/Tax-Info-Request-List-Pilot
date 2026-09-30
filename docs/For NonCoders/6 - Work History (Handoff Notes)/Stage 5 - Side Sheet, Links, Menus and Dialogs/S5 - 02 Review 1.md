# First check of stage S5: the side sheet, links, right-click menus and dialogs

**Original file:** `pilot/handoffs/shell-S5-review-1.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Review · Topic: Screen · Stage: S5  
**Date:** 2026-09-30  

## In one sentence
A reviewer ran the tests and 15 deliberate breakages against stage S5 and found 15 problems; four of them (F3, F4, F10, F15) hold choices only Jason can make.

## What this session was asked to do
Do the first review of S5 (the side sheet, the links, right-click menus and dialogs of the new screen). The reviewer was an "opus" session that did not build S5. It reviewed branch `claude/shell-s5-sheet` at commit `04de3d5`, against the plan (SPEC-shell), the approved word list, the rulings and stage S8a's real reply. Only made-up names were used and no client document was read.

## What it did
- All tests passed on Python 3.11 and 3.13. The code checker was clean, the map current (292 entries), and the interaction script said "all interactions pass".
- It made 15 deliberate breakages ("mutations") to see whether the tests notice. 12 were caught by `test_shell`, 2 more by `test_single_source`, and 3 slipped through.
- It confirmed the hard rules: no generative AI, nothing sent, no network call. No path is shown anywhere, only keys, and the path is looked up when clicked.

## What it found wrong, or what was left to do
- **F1:** After "Not Requested" (or a Put Back that parks the file), the side sheet stays on the same stale file. A later "File It" sends an out-of-date number and fails.
- **F2:** The held reminder shows request codes and the engine's long sentence. The plan wants five words and no codes.
- **F3:** Right-click Unfile and Mark Missing have no "busy" state (a second click gives a false failure notice), and they lost the Reason box.
- **F4:** A request answered by several files can no longer be unfiled or revealed at all.
- **F5:** Some right-click items are offered when they cannot work, and choosing one says the page failed.
- **F6:** The page still types a few sentences in pop-up messages, in the wrong case.
- **F7:** The one "Advanced" switch is not built; the old per-row switches remain.
- **F8:** Two of three "Cancel" buttons in the wizard should be cut, as the plan says.
- **F9:** The three info dialogs say "Dismiss", not "Close". An acceptable stopgap; S1/S6 add the word.
- **F10:** "Folders Skipped" has no two-word reason.
- **F11:** Some links have no keyboard route.
- **F12:** A row's menu item, answered after moving to another page, does not re-check the lock.
- **F13:** Stage S6's join with S8a is not pinned, so half of it could be missed.
- **F14:** Smaller gaps: a moved copy shows no received date, and request codes still appear in a picker and a button.
- **F15:** Two behaviours the plan allows but Jason may not want.

Departures the builder named: the return link text is fine; the "Close" word and the interim Folders Skipped (name only) are acceptable for now; the Advanced switch, the Cancels and the decision-94 copies link need fixes; unfiling several files and the right-click move-on need Jason.

## Decisions (made by Jason, or waiting for Jason)
Waiting for Jason:
- F3: where the optional reason for Unfile goes (a small confirm box, or no note).
- F4: how to unfile or reveal one of several files under one request.
- F10: the two-word reasons for Folders Skipped, or the name alone as built.
- F15a: after a right-click write, should the sheet move to the next file, stay, or close?
- F8 (only if he wants it): a visible Cancel on every wizard step would mean changing the plan instead of cutting two.
- F15b: whether the reminder sheet needs a caption saying whose draft it is (a plan change).

## Words to know
- **Side sheet:** a panel that slides in beside the page to show one file's details.
- **Mutation check:** deliberately breaking the code to see whether a test fails.
- **Handle / seq:** a file's identifier and a version number; an out-of-date number is refused.
- **Right-click menu (pop-up):** the menu shown when you right-click a row.
- **Ledger:** a file recording default choices made for open questions.
- **Rulings:** Jason's numbered decisions in `shell-rulings.md`.
- **Reveal:** show a file in File Explorer without opening it.
- **Forced colours:** a Windows high-contrast setting.
