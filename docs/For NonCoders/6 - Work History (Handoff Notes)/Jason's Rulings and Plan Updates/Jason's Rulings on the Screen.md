# Jason's rulings on the shell build

**Original file:** `pilot/handoffs/shell-rulings.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Rulings · Topic: Rules and decisions, Screen  
**Date:** 2026-09-29 (later rows are dated 2026-09-30)  

## In one sentence

This is the numbered list of Jason's rulings on the app's new screen, with what each one told the joining stage (S6) to do.

## What this session was asked to do

Record Jason's answers to the questions the build stages raised. S6, the joining stage, applies each ruling and logs it as a decision row starting from P85. A note at the top says the current state is in `shell-ledger.md`. Rows 8, 9 and 11 were changed by later rows. For link behavior, 12 beats 11, which beats 9, which beats 8. For spelling, 10 beats any lower-case spelling in rows 8 and 13.

## What it did

The note records these rulings:
1. The tour and pilot code keep their own keyboard listeners. Accepted exception.
2. Show a tooltip on keyboard focus everywhere except the search box.
3. Keep the menu bar hidden until Alt.
4. If no error log is named, save the failure to a fallback log in a local folder. The screen says only "Tracker failed". Add its path to the agent deny list.
5. Use Floating UI for tooltip placement (`@floating-ui/dom` 1.8.0, copied into the project with its licence and a fingerprint test, no download at run time). Tippy.js is not used.
6. Leave the failure text as built for this pilot.
7. Tooltip hover delay is 300 ms.
8. Changes made on the clickable mock-up: file names are live links to File Explorer, "Needs Review" capitalised, "Could Not Sort".
9. Household names are live links to the client folder. Amended by rows 11 and 12.
10. **Title Case throughout.** Every drawn phrase capitalises each word except small ones (a, an, the, and, but, or, nor, for, of, on, in, to, by, at, as, up, vs) when they are not first or last. Exceptions: the pilot terms, the client reminder letter and its subject, the error log and prose in docs.
11. A household name navigates to the client's page, tooltip "Navigate to Client".
12. A return name navigates to the return's page, tooltip "Navigate to Return". Only a file name opens File Explorer, tooltip "Show in File Explorer".
13. Return links show the tax year, like "1120-S - Rivera Design LLC (2025)" (a made-up example name).
14. Notice words: "Two Years Open; Sorting Paused" approved, "Prior Year Data Not Found" for the feed, and "Machine Needs Attention" approved as the one line for all three machine warnings. "Could Not Be Read" is dropped as a general notice; it stays only as a reason in the reminder and for a file's text.
15. Firm-wide Needs Review file names are live links too.
16. Unfile opens a small confirm box with "Reason (Optional)".
17. Each file under a request gets its own row.
18 and 18a. A two-word reason beside each skipped folder. The working word "Bad Year" replaces "Not A Year", which was three words.
19. After a right-click write, the sheet moves on to the next file needing a person. Kept as built.
20. A failed overnight sort shows a notice on every page. Later changed by row 28.
21. A household paused for two open years shows a marker on Clients and a row on Overview.
22. A runbook note says where the fallback log is saved.
23. "Pick a Request First" and "Name Each Custom Request" are approved.
24. Email and zip names are plain text, with no link (decision 190).
25. A failed sort banner says "Sort Failed" plus a short reason.
26. Retry greyed on firm pages. Superseded by row 28.
27. Return links may wrap to two lines so the year always shows.
28. The Sort Failed notice has no Retry and clears itself when the next scheduled overnight sort succeeds.
29. Six failure-reason words approved: Another PC Sorting, Drive Not Signed In, Folder Not Found, Two Years Open, Ran Too Long, Unexpected Error.
30. Record that Jason approved the skipped-folder reason words. "Bad Year" stays a working word.

## What it found wrong, or what was left to do

Nothing is stated in the note as wrong. Each row names who builds it (S1, S5, S6, S8a, S8b or the fix pass).

## Decisions (made by Jason, or waiting for Jason)

All rows are Jason's rulings. Row 10 (Title Case) was flagged to him because it overrides his own typed "Could not Sort". "Bad Year" is a working word he may change.

## Words to know

- **Ruling:** a decision Jason made, numbered.
- **Shell:** the app's new screen.
- **S6:** the stage that joins all the pieces and logs the decision rows.
- **Title Case:** capitalising the main words of a phrase.
- **Fallback log:** a backup error file the app keeps locally.
- **Deny list:** files Claude's own tools may not read.
- **Vendored:** an outside file copied into the project on purpose.
