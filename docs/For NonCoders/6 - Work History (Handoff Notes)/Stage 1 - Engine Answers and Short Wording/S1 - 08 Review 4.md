# Fourth independent check of stage S1's firm-wide data

**Original file:** `pilot/handoffs/shell-S1-review-4.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Review · Topic: Screen, Engine, Wording · Stage: S1  
**Date:** not stated  

## In one sentence

A reviewer who built none of S1 checked the third fix round and confirmed all five of its claims, and found one small gap: a test was missing.

## What this session was asked to do

Check "rebuild 3", the third fix round of stage S1. S1 is the first build stage of the app's new screen, "the shell". It supplies the data behind the firm-wide pages. The reviewer read the project notes, earlier S1 reviews, the spec and the page code. It changed no code.

## What it did

It checked five claims from the rebuild:

1. **Each file's return is the return's path.** True. The page code needs exactly this to group files and look up names.
2. **Each file carries a handle.** True. It is found in the return's detail view.
3. **The counts are right.** True. The reviewer built six mixes on a made-up practice (parked files only, moved only, "Not requested", moved and marked missing, all four, and an unreadable record). The firm view and the return's own view agreed every time.
4. **The heading for a failed setup reads "Setup needs attention".** True. It matches the spec, and the runbook line moved with it. Old words survive only in decision 209, which is history.
5. **The year is on every row.** True. It comes from the record, else from the year folder. An unreadable return still has its year.

It also confirmed:
- The field names match the spec, plus two extras that were agreed (`year`, and `handle`).
- The firm view only reads. It writes nothing, takes no lock, opens no network connection and opens no client file.
- Earlier fixes still hold. Moved files are listed and counted, and a return whose only work is a file counts as "Need a person".

**Gate:** each test file ran alone, under Python 3.11 then 3.13, with the same results. The one visible pattern was six expected failures in `test_single_source`, all about the app's main window file. Ruff was clean and the map was current.  

Breaking the code on purpose (on a scratch copy) was caught by the tests in three cases. The fourth case was not caught (see below).

## What it found wrong, or what was left to do

**F1 (the one finding):** no test checked a moved file's handle and year in the firm-wide list. Setting the handle to nothing and the year to none passed all 14 firm tests. Smallest fix: make the existing test check both for each file. (Rebuild 4 did this.)  

**Notes for later stages:**
- **Marked-missing files.** The engine puts a file a person marked missing in "Set aside". The pages count only "dismissed" files as set aside. So the page tally can be one lower, and the return page never shows that row. Fix in the pages by using the engine's group. If Jason would rather these count nowhere, that is a spec ruling and a one-line change.
- The file list carries no `seq` number. Stage S5 should load the return's own detail view for the Check step.
- Spec section 9.2 should gain `year` and `handle` and say `return` is the return's path.
- Return link text "{Return Name} ({Year})" (ruling 13) is stage S5's job. The year is available; the page does not add it yet.

## Decisions (made by Jason, or waiting for Jason)

- **Waiting for Jason:** whether a file marked missing should count as set aside (as built) or nowhere. This is a ruling on spec 9.1.
- **Already made:** ruling 13, return links show the year.

## Words to know

- **Shell:** the app's new screen.
- **Review-4 / rebuild-3:** the fourth independent check, and the third fix round.
- **Handle:** the short name the program uses for one file in a return.
- **Parked file:** a file waiting for a person, not yet placed.
- **Set aside:** files a person put to one side. They count for nothing.
- **seq:** a version number a write must carry; the engine refuses a write with an out-of-date one.
- **Mutation check:** breaking the code on purpose to prove a test notices.
