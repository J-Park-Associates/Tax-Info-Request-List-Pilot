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

## Not checked by hand tonight

- 1100 px window width (SPEC-firm-columns, the combined review's S5): the window was used at its default size.
- F6 by hand (uninstall, reinstall the same build, schedule on): the schedule stays off at Jason's word; covered by `tests/test_after_install.py`.
- `run_checks.ps1` whole (P200): it builds and installs; its parts are covered by `tests/test_pilot.py`.
