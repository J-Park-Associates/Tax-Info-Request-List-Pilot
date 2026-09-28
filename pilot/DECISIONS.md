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
