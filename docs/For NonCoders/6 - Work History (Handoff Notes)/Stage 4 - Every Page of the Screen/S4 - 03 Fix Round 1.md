# Stage S4 (the pages), first fix round: eight problems fixed

**Original file:** `pilot/handoffs/shell-S4-rebuild-1.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Fix round · Topic: Screen · Stage: S4  
**Date:** 2026-09-29  

## In one sentence

This session fixed the eight problems the first reviewer found in stage S4, plus one more the coordinator added, and proved each fix by breaking the code on purpose.

## What this session was asked to do

Stage S4 builds the pages of the app's new screen (Overview, Needs Review, Reminders, Clients, household, year and return pages). A first attempt at the fixes had stopped early. This session picked up from it. It audited the earlier half-finished work instead of trusting it. It fixed review 1's problems F1 to F8 and nothing more.

## What it did

- **F1: one bad row no longer blanks a return page.** A row that cannot be built is left out. One notice names it, "{row name}: The app hit an error". The technical details go to the error log. Every other row and group is still drawn. If a whole page cannot be built, it keeps what it showed before, or at least draws its title. An error after a write's reply can no longer make a successful write look failed.
- **F2: the lock notice is one short line**, such as "In use on {host}". The longer sentences are no longer drawn.
- **F3: reader, machine, pause and feed notices are short words.** The long sentences go to the error log. Where the word list lacks a short word, the approved setup line "Setup needs attention" stands in. Nothing is invented. Two different failures with the same words no longer merge into "(2 times)".
- **F4: a household with an unreadable return is never called Complete** on the Clients page.
- **F5: the "Set aside" fold is shut each time a page opens.** It stays open across redraws of the same page.
- **F6: contrast theme.** A focused row's text now uses the operating system's highlight-text colour. Measured contrast was 19.04 to 1 in the light theme and 13.76 to 1 in the dark one.
- **F7: the year page's rows start 24 pixels below the title**, the same as Reminders.
- **F8: missing tests added.** They cover removed old parts, no folder path drawn anywhere, and every loud failure of the old screen reaching a notice.
- **Coordinator's addition (from S1 review 4): files count by the engine's group.** A moved file that a person marked missing goes under Set aside. The page's counts now equal the firm's counts. Opening such a return no longer re-reads the firm data each time.
- **Mutation checks.** 26 on-purpose breakages on a scratch copy; all were caught.
- **Tests run.** Every named file passed on Python 3.11 and 3.13, including `test_shell` 57, `test_single_source` 165 and `test_api` 368. The tidiness check was clean. The interaction script passed. The screenshot script took 125 shots with no page errors.

## What it found wrong, or what was left to do

- **Missing words.** Five short notice words do not exist yet in the word list: `reader`, `machine`, `renamed`, `paused` and `feed`. The app falls back to the setup line until they exist. The plan names words for some of them, for example "Install folder name too long" and "Folder renamed". Stages S6 and S1 must add them.
- **Out of scope, left for later.** The link kinds and the year on return names belong to stage S5. The mismatches between the page and the real firm reply, from review 1's list, are another job's.
- **A fields list** in the note says exactly which fields the pages read from the engine, so the job that fixes the real firm reply knows what to send. It notes that the firm's files must carry the return's path and a handle.

## Decisions (made by Jason, or waiting for Jason)

The note asks for no new decision. It leaves the missing notice words for stages S6 and S1 to add.

## Words to know

- **Shell:** the app's new screen.
- **Stage S4:** the build stage that draws the pages.
- **Rebuild 1:** the first round of fixes after a review.
- **Notice:** a short message shown at the top of the screen.
- **Error log:** a file where failure details are kept for a person to read.
- **Set aside:** files a person decided are not needed for any request.
- **Contrast theme:** a high-contrast display mode.
- **Harness:** a test setup that runs the screen with made-up data.
- **Mutation check:** breaking the code on purpose to prove a test notices.
