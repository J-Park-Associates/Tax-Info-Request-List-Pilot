# Shell decision ledger (refreshed by the fix pass)

As of 2026-09-30 (after the final reviews A, B and C and the fix pass). One line per **live** decision. "Applied in"
names the job and branch; "Status" is what is true now. Source of each decision:
[`shell-rulings.md`](shell-rulings.md) (rulings 1-29) and `DECISIONS.md` (P50-P114). "Built/fixed" means built and
joined, with the final reviews' findings on it fixed in [`shell-fixpass.md`](shell-fixpass.md); the reviewer that did
not build the fix pass still says whether it is **done**.

| # | Decision | Applied in | Status |
|---|---|---|---|
| P58 | Real menu bar (File/Edit/Client/View/Tools/Help), one `menu` channel | S2 | **Done** (review 5, no findings) |
| P59 | Dark mode follows Windows | S3 tokens | **Done** |
| P60 | Sort is the one visible icon, next to the search bar | S3 | **Done** |
| P61 | Year always in the path | S3/S4 | **Done** |
| P63/P64 | Five words at most, no paths, safeguards in Help | S1 words, S3-S5 renderer | **Done**; the safeguards words are pinned (fix pass) |
| P65 | Every icon has a tooltip | S3, S7 | **Done** |
| 1 | Keydown listeners in tour/pilot accepted as built | none | **Accepted**, logged (P85) |
| 2 | Tip on keyboard focus except the search box | S7 | **Done** |
| 3 | Menu bar hidden until Alt | S2 | **Done** |
| 4 | Failure saved to a fallback log in a local folder, deny list rule | S2 | **Done** |
| 5 | Floating UI (`@floating-ui/dom` 1.8.0, vendored, two files) | S7 | **Done** |
| 6 | Failure text stays as built | S2 | **Done** (no change) |
| 7 | Tooltip hover delay 300 ms | S7 | **Done** |
| 8-12 | File names open File Explorer (item selected); household and return names navigate in the app; tooltips "Show in File Explorer", "Navigate to Client", "Navigate to Return" | S8a engine keys + reveal; S5 pages | **Built/fixed**; links are now underlined (final review B, finding 6) |
| 10 | Title Case throughout; "Needs Review"; "Could Not Sort" | S8a engine; S5, S6a renderer and tour | **Built/fixed**; "Could Not Be Read" as the firm row's word (fix pass) |
| 13 | Return links read "{Return Name} ({Year})" | S1 rebuild 3 (year); S5 | **Built/fixed**; the year no longer cut (ruling 27) |
| 14 | Notice words: "Two Years Open; Sorting Paused", "Prior Year Data Not Found", "Machine Needs Attention" | S8a, S6a | **Built/fixed** |
| 15 | Firm-wide Needs Review file names are live links | S8a rebuild 2 (`firm.files[].open_key`, `firm.paths`); S5 | **Built/fixed** (email and zip names are plain text, ruling 24) |
| 16 | Unfile opens a confirm box with "Reason (Optional)" | S5 rebuild 2 | **Built/fixed**; in the SPEC (fix pass) |
| 17 | Each file under a request gets its own row | S5 rebuild 2 | **Built/fixed**; in the SPEC (fix pass) |
| 18, 18a | Folders Skipped: a two-word reason beside each folder; "Bad Year" | S8b, S6a, S5 rebuild 2 | **Built/fixed**; words approved by Jason; "Bad Year" is a working word he may change |
| 19 | The sheet moves on to the next file after a write | none | **Kept as built** |
| 20 | A failed overnight sort is a notice on every page | S5 rebuild 2 | **Built/fixed**, amended by 28 (no Retry) |
| 21 | Paused household: marker on Clients, row on Overview | S6a (`firm.returns[].paused`); S5 rebuild 2 | **Built/fixed**; the words wrap so they are never cut |
| 22 | Runbook note on the fallback log's place | S6a | **Built/fixed**; the note is pinned by a test (fix pass) |
| 23 | "Pick a Request First" and "Name Each Custom Request" approved | fix pass | **Built/fixed** (PROPOSED marks removed) |
| 24 | Email and zip names are plain text, no reveal key | fix pass (`_shown_copy_key`) | **Built/fixed** |
| 25, 29 | A failed sort says "Sort Failed: {reason}"; the six words approved | fix pass (`vocab.scan.reasons`, `code` on the final line) | **Built/fixed**; Drive Not Signed In and Ran Too Long are not mapped (the engine does not tell them apart there) |
| 26 | Retry on the Sort Failed notice greyed on firm pages | none | **Superseded by 28** |
| 27 | Return links wrap so the year always shows | fix pass (`.row-wrap`) | **Built/fixed** |
| 28 | The Sort Failed notice has no Retry and clears with the record | fix pass | **Built/fixed** |
| - | Rename "Open Client Folder" to "Open Client Window" | none | **Withdrawn by Jason** (no change) |

## Work that predated the rulings: all of it is done

The engine words (S8a), the menu words (S8a), the renderer literals and tour titles (S5, S6a), the pages (S4, S5),
the SPEC, the wording table and the test pins (SPEC sync, fix pass), and the clickable mock-up (fix pass: "Could Not
Sort") follow rulings 1-29. `HANDOFF.md` and `DECISIONS.md` log P85-P114.

## Still open for Jason

See the list in [`../HANDOFF.md`](../HANDOFF.md): SPEC section 19 defaults O1-O6 (O4 was built without a ruling),
"Bad Year", firm speed on Windows, and the status word "Came in Email or Zip", which is cut. Nothing blocks the
build. The Windows check (installer, contrast themes) is `pilot/wintest/PROMPT-shell.md`.
