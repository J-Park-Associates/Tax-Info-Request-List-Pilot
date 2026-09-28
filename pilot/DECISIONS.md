# Pilot decision log

Decisions for the pilot edition only. `main`'s decisions stay in
`docs/ROADMAP.md`; this log never borrows its numbers.

| # | Date | Decision | Why |
|---|------|----------|-----|
| P1 | 2026-09-28 | The pilot lives on its own long-lived branch, `pilot/first-edition`, cut from `main`, worked in its own worktree folder. | Main keeps landing features; the pilot must never block it or be mixed into it (Jason). |
| P2 | 2026-09-28 | `main` is merged into the pilot before each pilot build, never the other way without Jason's say. | Testers get the latest sorting fixes (Jason). |
| P3 | 2026-09-28 | Testers are other CPA firms using their own clients' files. | Jason. |
| P4 | 2026-09-28 | Delivery is a real Windows installer, unsigned; the SmartScreen warning is explained in the tour and the tester guide. | Jason; a code-signing certificate can come later. |
| P5 | 2026-09-28 | The pilot adds a one-time terms screen. No sample sandbox, no feedback button, no expiry. | Jason. |
| P6 | 2026-09-28 | The marketing piece is a guided tour inside the app showing strengths and current limits; it covers intake, sorting, working copies, Needs Review, the status page and drafted reminders. | Jason. |
| P7 | 2026-09-28 | Pilot code is additive: new files under `pilot/` and new renderer files, hook lines only in existing files, nothing under `tracker/`. | Keeps merges from `main` conflict-free. |
| P8 | 2026-09-28 | The badge, terms and tour wording ship as `app/renderer/pilot-content.js` (plain JSON between two marker lines), not a separate JSON file. | The app window is sandboxed: no file access, `fetch` banned by test and CSP. The markers let tests and the build read it as JSON. |
| P9 | 2026-09-28 | Terms acceptance and "tour seen" are kept in the window's local storage. | No new channel or engine change needed; if storage is lost the terms show again, which is the safe direction. |
| P10 | 2026-09-28 | No new IPC channel and no edit to any existing JavaScript; `index.html` gets four added lines only. The badge and Tour button are created at run time. | Many tests pin the existing files' exact text; untouched files never conflict with `main`. |
| P11 | 2026-09-28 | `productName` stays "Tax Document Tracker"; "Pilot" shows on the header badge, installer, Start-menu shortcut and uninstall entry. The product name is never typed in pilot renderer files. | Changing `productName` ripples through tests, the task name and the data folder (Jason chose the name "Tax Document Tracker - Pilot"). |
| P12 | 2026-09-28 | Uninstall removes the installed files and this computer's scheduled task, nothing else: never the clients root, the data folder or `settings.json`. | A leftover task would fail every day; client data is never the installer's to delete. |
| P13 | 2026-09-28 | The pilot build refuses uncommitted changes and stamps no file; the version comes from `pilot-content.js`, the commit from `BUILD-INFO.txt`. | The installer is exactly what is committed, and the version has one home. |
| P14 | 2026-09-28 | The schedule on/off setting Jason asked for is built on `main` as a real feature with its own decision number; pilot 0.1 is not released until the pilot has merged it. | The after-install step re-registers the schedule at every launch, so an off switch must live in the engine, which the pilot does not change (P7) (Jason chose `main`). |
| P15 | 2026-09-28 | The pilot is tested at J Park only under a Windows account that does not run the firm's real schedule, on a copy of client folders. | The pilot shares the real product's data folder and task names. |
| P16 | 2026-09-28 | The `main`-lane schedule setting also sets the run time: the time of day it first runs and how often it repeats. The chosen values are saved per computer and used by every re-registration, never reset to the defaults. | Jason. Today the after-install step re-registers with 07:00 / every 120 minutes, which would undo a chosen time. |
