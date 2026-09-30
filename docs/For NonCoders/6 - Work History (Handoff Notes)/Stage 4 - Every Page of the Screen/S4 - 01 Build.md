# Building every page of the new screen (stage S4)

**Original file:** `pilot/handoffs/shell-S4.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Build · Topic: Screen · Stage: S4  
**Date:** 2026-09-29  

## In one sentence

The S4 builder drew every page of the new screen, removed the old cards, turned every hidden warning into a visible notice, and fixed several faults in a half-finished first attempt.

## What this session was asked to do

Build stage S4 of the new screen, "the shell": the pages listed in section 6 of `pilot/SPEC-shell.md`. A container restart had cut the first session off mid-build. The first session left an unfinished commit with no handoff. This session treated all of it as unchecked, audited it, fixed it and finished it. It was built on S3's clean tip. Nothing was reviewed yet.

## What it did

**Pages now drawn** by the new `pages.js`:
- **Overview:** three figures and "Work waiting", one row per return.
- **Needs review:** one group per return with files waiting.
- **Reminders:** one list of drafts ready.
- **Clients:** a switch between Work waiting and All, one row per household (500 draw in one pass).
- **Household, year and return pages.** A return shows Needs you, Waiting on client, Received, and a closed Set aside.
- Firm pages have no heading. The household, year and return pages open with one.
- Every row shows a name, a detail, one status word and an end column with the date, and the row's one step on hover or focus. Rows work by keyboard.

**Old screen removed:** the toolbar, banners, request table, household card, setup card, review deck and more. About 1,000 lines left the old code.  

**Loud failures are now notices:** reader warning, machine warnings, setup needs attention, the lock, folders skipped, names shortened, two years open, folder renamed (with Accept) and feeds that do not resolve. The last-sort line moved into the side panel as "Sorted 6:00 AM" or "Sort failed".

## What it found wrong, or what was left to do

**Faults it found and fixed in the first attempt:**
- A household page never read its return's detail, so its notices never showed.
- Sub-headings drew long sentences instead of short words. The renderer is right; the API must shorten them (S1's job).
- The real app died at start-up because the code still set two buttons that had been deleted.
- A return whose record could not be read was left off the Overview. It now leads the "Need a person" rows.
- The Edit step silently did nothing while a return was locked. It is now simply not offered.
- Cut-off text had no tooltip. The old review deck was still in the code.

**Left to do:**  
- **S5:** the Check sheet, reminder, misfits list and the right-click wiring. Until then, those steps raise one notice, never silence.
- Some old cards stay hidden until S5 takes them over.
- Nothing was run in Electron; the Windows check covers that.
- **For S6:** the API's bucket labels must be the two words "Emails and zips" and "Not documents". Several words and keys are listed for the join. Docs mentioning the removed screen are S1's and S6's.
- A long status word such as "Came in email or zip" is cut with "..." (full text in the tooltip).

Tests: all named files passed under Python 3.11 and 3.13. Four mutation checks each made a test fail as intended.

## Decisions (made by Jason, or waiting for Jason)

Proposed decision rows for S6:
1. Return groups come from the API's `group`; a missing group is a loud failure, never a guess.
2. The page redraws from data and keeps the person's place.
3. An unreadable return leads the Overview and is never counted as complete.
4. The Edit step is not offered while a live lock holds the return.
5. A household's notices come with its state.
6. The review deck (Cards/List) is removed.

Waiting for Jason: two departures from S3 stand (separate tour and pilot keydown listeners; no tooltip on a focused text box). If he wants the last-pass line as a notice too, it is one call. If he wants long status words such as "Came in email or zip" shown uncut, either the words get shorter or the status column gets wider (the 1100px layout is already exactly full).

## Words to know

- **Shell:** the app's new screen.
- **Group:** a labelled section of rows on a return's page.
- **Notice:** a message at the top of the page area.
- **Listbox:** a list you move through with the arrow keys.
- **Mutation check:** breaking the code on purpose to prove a test notices.
- **Electron:** the tool that turns the web page into a Windows app.
