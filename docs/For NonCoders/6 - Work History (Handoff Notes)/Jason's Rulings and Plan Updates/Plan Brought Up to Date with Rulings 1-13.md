# Bringing the shell plan up to date with Jason's rulings 1 to 13

**Original file:** `pilot/handoffs/shell-spec-sync.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Rulings · Topic: Rules and decisions, Screen  
**Date:** not stated in the note (it uses the date 2026-09-29 for the rulings)  

## In one sentence

This session changed only documents: it rewrote the shell plan (SPEC), the wording table and a
test survey so they say what Jason's rulings 1 to 13 decided. No code or test changed.

## What this session was asked to do

Bring `pilot/SPEC-shell.md` in line with the rulings and the builders' notes so far. It worked
on branch `claude/shell-spec-sync`. It read the rulings, the ledger, decisions P50 to P66, and
the notes of jobs S1, S2, S3, S4 and S7. Work in progress on S8a was looked at but not stated
as final.

## What it did

The SPEC got a note at the top ("Amended by rulings 1-13") and these changes:
- **Floating UI** (a small outside library that places hover tips) is vendored: two unedited
  files, their licences and a fingerprint check.
- **New section 3.9, Links:** a file name shows that copy in File Explorer ("Show in File
  Explorer"); household and return names move around the app; return links read
  "{Return Name} ({Year})"; no path is ever shown.
- **Menu bar** stays hidden until Alt. **Item words** in Title Case.
- **Error log:** Open Error Log opens the API's log, else a fallback log in the user's local app
  folder, with a 256 KB size limit and one older copy.
- **New section 5.7:** a "reveal" way to open, with the same safety checks.
- **Tooltips:** 300 ms delay on hover, shown at once on focus except in the search box.
- **`firm` and `state` answers** carry the year and file handles.
- **Title Case rule** for every word, with exceptions and examples.
- Tour titles, test lists, the job table and a new section 19 of open questions were updated.

The wording table gained two columns (`title_case`, `changed`). Only one word changed:
"Tracker failed". The test survey got two updated rows. No decision number was touched.

## What it found wrong, or what was left to do

Names from job S8a and the `year` and `handle` fields of S1 become final when those jobs' reviews
land; if their names differ, the SPEC lines change too.

## Decisions (made by Jason, or waiting for Jason)

Waiting for Jason (SPEC section 19):
1. Approve "Could Not Be Read".
2. Which tooltip wins on a cut name: the full name or the link's.
3. How a keyboard user acts on a name link inside a list.
4. Whether a file row's right-click menu gains "Show in File Explorer".
5. Whether `triage.places.footer` (a fragment inside a reason line) is Title Case.
6. Confirm "Tracker Failed".

## Words to know

- **SPEC:** the written plan for the shell.
- **Ruling:** a numbered decision of Jason's.
- **Vendored:** an outside library copied into the project unchanged and pinned.
- **Title Case:** Each Main Word Starts With A Capital.
- **Tooltip:** the small hover note that explains a control.
- **Error log:** a file that keeps error details.
- **Reveal:** show a file in File Explorer without opening it.
