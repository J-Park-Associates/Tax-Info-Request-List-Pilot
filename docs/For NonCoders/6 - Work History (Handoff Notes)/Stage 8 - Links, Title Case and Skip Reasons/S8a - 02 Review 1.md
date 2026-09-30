# First independent check of stage S8a: file-name links and Title Case words

**Original file:** `pilot/handoffs/shell-S8a-review-1.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Review · Topic: Screen, Wording · Stage: S8a  
**Date:** not stated  

## In one sentence

A reviewer checked stage S8a, found most of it sound, and listed ten findings: two that change what may be opened or shown, four test gaps, two wording points, one wrong code comment and one incomplete list in the handoff.

## What this session was asked to do

Stage S8a gives the engine and the window the file-name links (a file's name shows that file's copy in File Explorer) and puts the screen's words in Title Case. The reviewer did not build it. It checked the S8a work and its merge against Jason's rulings 8 to 13, the ledger, and the plan. It changed no code.

## What it did

- **Ran the tests.** Each test file ran on its own on Python 3.11 then 3.13. All passed except `test_build`, which passed 30 and failed 1. That failure is about the scanning scratch folders, also fails on the base, and was ignored as briefed. The tidiness check was clean and the map was current.
- **Checked the engine keys.** The links are made of tokens (keys) that the screen looks up in a list of paths. They are correct, in the right order, and empty where no copy exists.
- **Proved the engine read-only.** A scratch test wrapped file opens, network sockets and locks. It showed no sockets, no locks and no writes. No client document was opened.
- **Checked no path is drawn.** S8a added none. What the scan finds is older and is listed in the notes.
- **Checked the window's reveal.** It uses the same channel, allow-list and file checks. The reviewer tried odd paths, and all were refused. Only reported copies were revealed.
- **Checked the words.** The Title Case rule was applied as Jason wrote it. The window's 44 menu words equal the engine's. The docs changed only the casing of quoted labels.
- **Checked the merge.** No test functions were lost.
- **Broke the code on purpose** on a scratch copy. Some breakages were caught. Four were not, and they are findings F3, F4, F5 and F6.

## What it found wrong, or what was left to do

Ten findings:

- **F1.** Filed and moved-by-hand copies can now be opened in their default program, not only shown in File Explorer. Ruling 12 and decision 190 allow only showing. This widens decision 190's Open. The fix is a reveal-only kind, or Jason's yes to keep it as built.
- **F2.** Set-aside files and some parked files have no key, so they cannot be links, although the plan says every file name is a link. The fix is a new "shown copy" key, or the plan must say which names are plain text.
- **F3.** A test about a moved copy whose bytes are nowhere tests nothing (it is vacuous). It needs a real moved row.
- **F4.** No behaviour test pins the allow-list for opening paths. Disabling it passed every test.
- **F5.** The Title Case check never lowers a capitalised small word, so "Waiting On Clients" would pass. No such word exists today.
- **F6.** The order of a filed page's several copies is not tested.
- **F7.** One word, `triage.places.footer`, was put in Title Case against the default that it stays lower case. Sibling phrases stay lower case, so a reason line could read inconsistently. Four other scan phrases are named for Jason.
- **F8.** Two drawn phrases are skipped by a broad exemption: the "Short name" column heading, and the "No: sorting skips this return" Active warning.
- **F9.** A comment in the window file says reveal opens a return's folder. It should say a reported folder.
- **F10.** The handoff's list of screen words left in the old casing is incomplete. The review adds the missing ones, for example "No content rules", "Belongs to…", "Use this folder", "Clear lock", "Tax year", and three tour titles.

**Notes for stages S5 and S6:**

- Keys are tokens. Look them up in the path list, and never draw them or put them in a tooltip.
- The list of which rows have a link today.
- The call is to open the path with "reveal"; an empty answer means success.
- Return links read "{Return Name} ({Year})".
- A list of fields that hold paths on replies today. Two are drawn sentences from the household sharing checklist. A rule (P63) says no path on screen, so that needs an engine change.
- Some words are still in old casing, including the tour and pilot files.
- "Nothing Outstanding; No Reminder Needed" now sits beside lower-case log sentences.
- The word list's `title_case` column and the re-cased `proposed` column need reconciling by S6.

## Decisions (made by Jason, or waiting for Jason)

- Waiting for Jason: F1 (does Open widen, or must copies be reveal-only?), F2 (should set-aside names link?), and the phrases flagged for him in F7, plus the "Nothing Outstanding" wording.
- Rulings 8 to 13 were the standard used.

## Words to know

- **Stage S8a:** the stage that gives the engine and window the file-name links and the Title Case words.
- **Reveal:** show a file selected inside File Explorer, without opening it.
- **Key / token:** a short code the engine sends instead of a path. The screen looks it up.
- **Allow-list:** the list of paths the window is allowed to open.
- **Parked file:** a file the program would not file.
- **Working copy:** the program's copy of a file. The original is never changed.
- **Title Case:** Capitalising The Main Words.
- **Vacuous test:** a test that can never fail.
- **Mutation check:** breaking the code on purpose to prove a test notices.
