# Final review C: is the whole new screen complete and consistent?

**Original file:** `pilot/handoffs/shell-final-review-C.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Final check · Topic: Screen  
**Date:** 2026-09-30  

## In one sentence

A reviewer checked the whole joined screen for completeness and consistency and found two problems that block the merge, plus several documents and records that are out of date.

## What this session was asked to do

Area C of the final review: were all of Jason's rulings built or logged; do the decision log and documents agree with the code; is the Windows check and handoff ready; is the build set up; does the whole test suite pass; is the Git history clean. The branch is `claude/shell-join` at `0b278d9`, compared with `origin/main`. The reviewer built none of the shell and changed no code.

## What it did

- **Rulings 1 to 22 (and 18a)** were each traced to the code or the log. Most were confirmed, often by deliberately breaking the code and watching a test fail.
- **Decision log.** P85 to P107 quote the rulings in order and agree with the code, except stale statuses. The standing-rules wording is unchanged and its test passes. The unused-code check is clean and the map is current.
- **Build config.** The packager takes the whole app folder, so all the new screen files and the library ship with no list to update. The test rig stays outside the app.
- **Whole suite.** All 55 files ran under Python 3.11 and 3.13. Each had 3982 passed and the same 7 failures. One is new (C1). Five also fail on `main`, because the OCR reader (the part that reads scanned text) is not installed here. The last, a test on the firm's sample documents, could not be compared with `main`; it is almost certainly the missing reader too, to be confirmed on the office PC.
- **Git hygiene.** All shell branches are contained in the join, the merges are real merge commits, and nothing was rewritten. No secrets or real client data were found. Made-up names only.

## What it found wrong, or what was left to do

**Block the merge:**  
- **C1.** The vocabulary coverage report is stale, so a guard test fails. Only two file fingerprints differ, so no routing changed. Rebuilding and committing the report fixes it.
- **C2.** The new "Sort Failed" notice with Retry cannot clear itself. The record it reads is written only by the scheduled pass, but Retry runs a by-hand sort. On a firm page, Retry also shows a command-line sentence. Jason must choose the wording of the fix. Step 11 of the Windows check cannot produce this notice as written.

**Should fix:**  
- **C3.** The rulings file on the branch stops at ruling 14. Rulings 15 to 22 are only on another branch, yet the decision rows cite the file.
- **C4.** Decision rows and the ledger still say "S5 rebuild 2" or "in progress", although that work is now joined.
- **C5.** "Waiting on Jason" is incomplete. Also open: six SPEC section 19 questions, and the nine misfit reason words, which are marked "Approved by Jason" although ruling 18 says they need approval and 18a calls "Bad Year" a working word.
- **C6.** The SPEC lacks rulings 16, 17 and 20, and still uses old names such as "Mark missing" and "Needs review".
- **C7.** The Windows check prompt has steps Jason cannot complete as written (steps 11 to 14, and the code-checkout step).
- **C8.** The runbook and README still describe the old app (Sort & Scan, the engagement picker, cards, the toolbar, "Not asked", and more).

**Notes:** the in-repo mock-up still has old wording; two approved words and one runbook note are not pinned by any test.  

## Decisions (made by Jason, or waiting for Jason)

- **Waiting for Jason:** how to fix Retry on the Sort Failed notice (C2).
- **Waiting for Jason:** approval of the eight two-word misfit reasons and the working word "Bad Year" (nine rows in all), and the open SPEC section 19 items (C5). One of them, "Show in File Explorer" in right-click menus, was built without a ruling.

## Words to know

- **Join branch:** the branch where all the shell's stages were merged together.
- **Ruling:** a decision by Jason, written down.
- **Decision log:** the numbered record of why things are the way they are.
- **Vocabulary coverage report:** a generated report on the words that route documents. It must be rebuilt after a change.
- **Scheduled pass:** the automatic overnight sort.
- **Mutation check:** breaking code on purpose to see if a test notices.
- **OCR reader:** software that reads text from scanned pages.
- **Merge commit:** a Git entry that records joining two lines of work.
