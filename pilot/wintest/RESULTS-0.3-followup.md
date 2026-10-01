# Pilot 0.3 follow-up - hands-on result on the office PC (2026-10-01)

- **Build:** `main` at `adb2b41` (pull request #23, P193-P201), built in a fresh clone at `C:\Users\User\pl\release-adb2b41`. Installer `Tax-Document-Console-Setup-0.3.exe`, SHA-256 `a58984e74f0ecdaa9737fb3c1a5a4afe7f142b9f68566ef98f947f81b1333c20`.
- **Run by:** the orchestrator session, controlling the screen at Jason's word ("Take control of the pc to test the app"), made-up sample data only. No document was opened.
- **How it was started:** always outside the Claude app (SPEC-F7 R4): the silent install through a command file handed to `explorer.exe`, the app through its Start-menu shortcut handed to `explorer.exe`.

## Before the install: SPEC-F7 R6

| Check | Result | Evidence |
|---|---|---|
| The logo build, started from the Start menu, reads every return | PASS | Overview: Need a Person 14, Waiting 13, all 27 returns with their statuses; no "Setup Needs Attention", no "Could Not Be Read" (12:57 AM). |
| The real store (made-up sample data) is whole | PASS | Read-only (`immutable=1`, no side files): `user_version` 20, 51 engagements, 26 returns with documents, 3 with none received yet. |
| The Claude private copy is gone | PASS | `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local` holds no `tax-document-tracker-pilot` (moved to the Recycle Bin by Jason, SPEC-F7 Q1 (a)). |

## The merged build

| Check | Result | Evidence |
|---|---|---|
| Install, after closing the open app | PASS | The app was closed through its own Close button first (N7); the silent install exited 0 at 3:35 AM; the program landed in the real `Programs\Tax Document Console` and no private copy was made. |
| First start runs the one-time step cleanly | PASS | `after-install.json`: ran 3:35:29 AM, reason launch, schedule off, 0 findings, nothing failed. |
| The schedule stays off (Jason's word) | PASS | `settings.json` `"schedule_enabled": false`; no task under either name. |
| One field per column (P194, P195) | PASS | Overview: Tax Year, Taxpayer, Form Type, Status, Date; "Chidi & Ada Okafor" with no "1040 -" and no "(2025)"; the form once, as its chip. |
| Household in the tooltip (P195) | PASS | Hovering a Taxpayer link: "Navigate to Return (Okafor Family)". |
| Taxpayer and Household words (P196) | PASS | "Waiting on Taxpayers", "Taxpayer Types", "Households" page with "Household Name", "No Taxpayer Name Found"; the search box "Households and Returns". |
| Needs Review says each field once (P195) | PASS | "2025 · Chidi & Ada Okafor · 1040 · Okafor Family". |
| View > Show Under Construction (P197) | PASS | Ticked on a new install; Alt+V then U hides the five items and the Workspace heading; still hidden after closing and starting again from the Start menu; turned back on to leave the default. |
| A tooltip after a keyboard page change | **FAIL** -> P202 | The tip "Navigate to Return (Okafor Family)" stayed on screen after Ctrl+4, Ctrl+2 and Ctrl+3 and did not clear when the mouse moved. Cause and fix: `pilot/SPEC-stuck-tip.md`. |

## The build of `4b55bc4` (pull request #24, P202)

- Installer SHA-256 `764d156959e7315d775e8f3d7ec94e55b27523887a00c6cc06fcb0c0dffeb78c`. The first install attempt (4:00 AM) met the open app and stopped with exit 5, rolling itself back (N7): the close click had been blocked by Windows' text-input layer, which the screen tool may not control. The app was then closed through its own window message (`CloseMainWindow`, never forced) and the install exited 0 at 4:03 AM, into the real `Programs` folder.

| Check | Result | Evidence |
|---|---|---|
| The tooltip after a keyboard page change (P202) | NOT VERIFIED by hand | Every key and click sent while the mouse rested on a link was refused by the screen tool ("Textinputhost is in front"); access to it was declined. Covered by the three P202 tests, which drive the real `tooltip.js` and `shellGo` and fail on the code before the fix. |
| Overview at the minimum window | **FAIL** -> P203 | The window shrunk by `MoveWindow` stopped at 1100 wide; `GetClientRect` gave its page 1084 wide; the Work Waiting list showed a sideways scrollbar with a nearly full-width handle. Cause and fix: `pilot/SPEC-min-page-width.md`. |

## The build of `6a2d87f` (pull request #25, P203) - the one left installed

- Installer SHA-256 `6b74ca206f3d1aaa31b3455d182fa5e7ddf6c7e6b6ad508bbcebc7674b151028`. The app was closed through its own window message, the silent install exited 0 at 4:14 AM into the real `Programs` folder, and the app was started from its Start-menu shortcut through Explorer.

| Check | Result | Evidence |
|---|---|---|
| Overview at the minimum window (P203) | PASS | Shrunk by `MoveWindow`: the window stops at 1116 wide and its page (`GetClientRect`) is 1100 wide, 861 tall; Overview's five columns show whole with no sideways scrollbar. The window was then set back to its default size and left open. |

## Not checked by hand tonight

- F6 by hand (uninstall, reinstall the same build, schedule on): the schedule stays off at Jason's word; covered by `tests/test_after_install.py`.
- `run_checks.ps1` whole (P200): it builds and installs; its parts are covered by `tests/test_pilot.py`.
