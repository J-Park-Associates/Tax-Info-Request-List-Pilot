# A tool that keeps these plain-English pages up to date

**Original file:** `pilot/handoffs/noncoder-automation-build.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Build · Topic: Rules and decisions, Testing  
**Date:** 2026-09-30  

## In one sentence

This session built a small program that notices when a plain-English page is missing or out of date, and makes a helper fix it before the work counts as finished.

## What this session was asked to do

Build what the written plan `pilot/SPEC-noncoder.md` describes. Jason had asked for the pages in this folder to be kept current in a way that is "completely automated", with a test that enforces it.

## What it did

- Wrote `tools/noncoder_pages.py`. It remembers a *fingerprint* (a short code that changes if even one letter of a file changes) of every file a page explains. It keeps them in `pages.json`.
- Made this folder's start page a generated file. The tool builds it from the Tags line at the top of every page.
- Added a check that runs at the end of every AI helper session (a *Stop hook*, a small command the helper's tool runs when it is about to finish). If a page is missing or stale, the helper is told which page to write and where to find the style rules.
- Added a test file for the tool, which also fails whenever the pages fall behind.
- Later the same day, added a filing helper (`organize`). It moves and renames pages into the right folders, renumbers a stage when a note is inserted, and moves a page whose file was removed into a `7 - History` folder. `stamp` also keeps the earlier text of a page it replaces there. The end-of-session check runs the filing helper first, so only the writing is left for the AI helper.
- Wrote the style rules into `docs/noncoder-style.md`, and added notes to `CLAUDE.md`, the maintenance guide, the code map and the decision log (row P116).
- Checked the three pages whose originals it had changed, added a sentence to two, and re-stamped them.
- Rebuild 1, after a review: the end-of-session check can no longer trap a session when its script is missing; a renamed file is no longer mistaken for a removed one (a page is retired only when its file is gone from Git too); a new stage with no folder is reported instead of crashing; a filing run that fails halfway puts everything back; and the tool no longer breaks on a Windows console's character set.
- Review 2, fixed by the lead: if a filing run fails halfway, putting pages back can no longer write one page over another, and anything that cannot be put back is named with where it is; a note renamed before it was ever saved in Git no longer sends its page to History; and a session that already tried once is told what would move instead of having pages moved behind its back.
- Ran the tool's checks, the linter, the code-map check and the five guard test files. All passed. The end-of-session check was tried by hand: it stayed quiet on a current tree, objected after one handoff note was touched, and went quiet again when the note was restored.

## What it found wrong, or what was left to do

Nothing is left to do. Places where the plan was read loosely:
- The plan says both page layouts have six headings. The style file also gives six for each, so the check follows the style file.
- "Existing tracked file" is checked as "the file exists", so the check stays fast and works in test copies.
- A new stage letter with no pages yet starts its numbering at 01. The two Stage 6 pages were renamed to match (S6a and S6b).
- The plan said the library already fit the filing rules. Mostly it did; the filing helper keeps any well-shaped existing name and fixes only the stage prefix and number.
- The code map page no longer lists the generated map files as originals, because the map records this tool's fingerprints and the two could never both be current.
- The `stamp` command reports a failure code when something is still wrong after it runs.

## Decisions (made by Jason, or waiting for Jason)

Jason's request is recorded as decision P116. Nothing in the note waits on Jason.

## Words to know

- **Fingerprint (hash):** a short code worked out from a file's contents. Change the file and the code changes.
- **Stale page:** a page whose original file changed after the page was last checked.
- **Stamp:** to record the current fingerprints once a page is written or confirmed accurate.
- **Stop hook:** a small command an AI helper's tool runs when the helper is about to finish.
- **Generated file:** a file a program writes. It is never edited by hand.
