# Third independent check of the link-keys job (S8a): no findings

**Original file:** `pilot/handoffs/shell-S8a-review-3.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Review · Topic: Screen, Wording · Stage: S8a  
**Date:** not stated in the note  

## In one sentence

A reviewer who built none of the S8a work checked its second and third fix rounds and found
nothing wrong.

## What this session was asked to do

Review branch `claude/shell-s8a-links` (rebuild 2, rebuild 3 and a map refresh) against review 2's
two findings, Jason's rulings 1 to 15, and the two rebuild notes. Opus 5.5 did the review and
changed no code.

## What it did

- **Ran the tests** in Python 3.11 and 3.13: `test_api` 404, `test_shell` 32, `test_layers` 29,
  `test_single_source` 171, `test_repo_map` 80. All passed. Style and map checks were clean.
- **Finding 1 of review 2 is fixed:** a parked read document is named once, and a test that runs
  the real app main program proves it.
- **Finding 2 is fixed:** the "proposed" marks are gone and the words are approved and in Title Case.
- **Ruling 15 (file names in the firm's Needs Review view are links)** was checked in detail:
  the shape of the answer, one key per kind, reveal-only where required, no path shown, and a
  rule for keys that would collide. Under node with the real main program, opens and reveals
  behaved correctly, and 7 of 7 improper requests (unreported files, network paths, `..` paths,
  a key given as a path) were refused.
- **No client document was read.** The firm command was watched while running: 0 writes, 0
  network connections, 0 locks, and no working copy opened.
- **Size and cost.** With 750 households and 3000 files, the reply grew from 1.21 MB to 2.14 MB
  and took 3 to 5 percent longer (6.7 seconds to about 7 seconds).
- **Mutation checks:** 11 of 11 deliberate breakages were caught; one more was an equivalent
  change that cannot reach the reply.

## What it found wrong, or what was left to do

No findings. Notes for later jobs: the plan's `firm` section does not yet name the new fields
(S6 adds them); the app's main part keeps one allow-list across all replies, so the firm and
`state` answers must always agree on a file's key kind; and ruling 15's row names "rebuild 2"
though the work landed as rebuild 3. The time budget (750 returns under 3 seconds on the office
PC) is already exceeded in this test machine before the change; the Windows check will measure it.

## Decisions (made by Jason, or waiting for Jason)

Made: ruling 14 (the words) and ruling 15 (links). Nothing is waiting in this note.

## Words to know

- **Firm command:** the read-only summary of all returns.
- **Allow-list:** the list of files the app may open; anything else is refused.
- **Reveal:** show a file in File Explorer.
- **Working copy:** the tracker's own copy of a file; the original is never changed.
- **Mutation check:** breaking code on purpose to see a test fail.
- **Equivalent mutant:** a deliberate breakage that changes nothing anyone can see.
