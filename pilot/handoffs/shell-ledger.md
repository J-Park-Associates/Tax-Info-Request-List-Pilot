# Shell decision ledger (kept current by the orchestrator)

As of 2026-09-29 (evening). One line per **live** decision. "Applied in" names the job and branch; "Status" is
what is true now. A decision is **done** only when a review that did not build it said "No findings".
Source of each decision: [`shell-rulings.md`](shell-rulings.md) (rows 1-13) and `DECISIONS.md` (P50-P66).

| # | Decision | Applied in | Status |
|---|---|---|---|
| P58 | Real menu bar (File/Edit/Client/View/Tools/Help), one `menu` channel | S2 `claude/shell-s2-menus` | **Done** (review 5, no findings) |
| P59 | Dark mode follows Windows | S3 tokens | **Done** (S3 review 3) |
| P60 | Sort is the one visible icon, next to the search bar | S3 | **Done** |
| P61 | Year always in the path | S3/S4 | **Done** in S3; S4 pages follow |
| P63/P64 | Five words at most, no paths, safeguards in Help | S1 words, S3/S4 renderer | Engine words **done** (S1); S4 renderer **in rebuild** |
| P65 | Every icon has a tooltip | S3, S7 | **Done** |
| 1 | Keydown listeners in tour/pilot accepted as built | none | **Accepted**; S6 logs the exception |
| 2 | Tip on keyboard focus except the search box | S7 `claude/shell-s7-tooltips` | **Done** (review 3, no findings) |
| 3 | Menu bar hidden until Alt | S2 | **Done** |
| 4 | Failure saved to a fallback log in a local folder, deny list rule | S2 | **Done** (review 5) |
| 5 | Floating UI (`@floating-ui/dom` 1.8.0, vendored, two files) | S7 | **Done**, supply chain verified by review |
| 6 | Failure text stays as built | S2 | **Done** (no change) |
| 7 | Tooltip hover delay 300 ms | S7 | **Done** |
| 8-12 | File names open File Explorer (item selected); household and return names navigate in the app; tooltips "Show in File Explorer", "Navigate to Client", "Navigate to Return" | Engine keys + reveal: **S8a** `claude/shell-s8a-links` (resumed, running). Page links: **S5** (waits for S4 clean) | **In progress** |
| 10 | Title Case throughout (rule in rulings row 10); "Needs Review"; "Could Not Sort" | Engine words: S8a. Renderer and tour literals: S5, S6 | **In progress** |
| 13 | Return links read "{Return Name} ({Year})" | Year on engine rows: **S1 rebuild 3** (running). Text: S5 | **In progress** |
| - | Rename "Open Client Folder" to "Open Client Window" | none | **Withdrawn by Jason** (no change) |

## Work that predates the rulings and needs updating

| Item | Out of date because | Fix in |
|---|---|---|
| S1 engine words | lower case; no year check | S8a (words), S1 rebuild 3 (year, `firm` reply mismatches) |
| S2 menu words | lower case, "Needs review" | S8a |
| S3 renderer literals, tour titles (`pilot-content.js`), `index.html` | lower case | S5 (renderer), S6 (tour) |
| S4 pages | no link kinds, no year on return names; open review 1 findings | S4 rebuild 1 (running), then S5 |
| `SPEC-shell.md`, `wording-shell.tsv`, `shell-test-pins.md` (SPEC branch) | written before rulings 1-13 (500 ms delay, roaming folder, no Title Case, no links, ...) | SPEC sync job (`claude/shell-spec-sync`) |
| Clickable mock-up (artifact) | **Current** through ruling 13 | - |
| `HANDOFF.md`, `DECISIONS.md` | do not yet log P67+ or the rulings as rows | S6 (rows from P85) |

## Defaults taken by the orchestrator (2026-09-29) pending Jason - the SPEC sync raised six questions

| # | Question | Default used for now | Why |
|---|---|---|---|
| 1 | Approve the Overview word "Could Not Be Read" (a return whose record cannot be read) | Keep | Follows the approved "Reminder Could Not Be Read"; five words or fewer |
| 2 | A cut name that is also a link: which tooltip wins? | The link's tooltip ("Show in File Explorer" / "Navigate to ...") wins; the full name is on the page heading and the side sheet title | Keeps one tooltip per element; the name is never lost |
| 3 | How does a keyboard user follow a name link inside a row (Enter runs the row step)? | Right-click menu or the context key on the row: "Show in File Explorer" for file rows; Enter keeps running the row step, which for return and household rows opens the page anyway | No new keyboard model |
| 4 | Add "Show in File Explorer" to a file row's right-click menu | Yes (the mock-up has it) | Gives question 3 its answer |
| 5 | `triage.places.footer` (a fragment spliced into a longer reason) | Stays lower case as a fragment; listed as a Title Case exception | It is not a phrase on its own |
| 6 | "Tracker Failed" (Title Case) vs ruling 6's "Tracker failed" | "Tracker Failed" (ruling 10 wins) | Casing rule applies to every drawn phrase |

## Still open for Jason

Nothing blocks the build. The Windows check (installer, contrast themes) comes after S6.
