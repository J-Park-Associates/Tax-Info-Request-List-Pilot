# First independent check of the menus stage (S2)

**Original file:** `pilot/handoffs/shell-S2-review-1.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Review · Topic: Screen · Stage: S2  
**Date:** not stated  

## In one sentence

A separate reviewer found the menus stage sound and safe, with three small findings: one weak test and two documents that still describe old behaviour.

## What this session was asked to do

Check stage S2 (the menus of the new screen) against the plan, without having built it. The branch is `claude/shell-s2-menus`, reviewed at `adf4902`.

## What it did

The reviewer checked and found these correct:

- **Words.** All 44 menu words in the app match the API's list, word for word and in order.
- **Menu layout.** File, Edit, Client, View, Tools and Help are in the planned order. Only the planned keyboard shortcuts exist. There is no Reload, Zoom, full screen or developer-tools item.
- **Right-click menus.** The six pop-up menus hold exactly the planned items.
- **The message channel.** The screen can send only a menu id and a token. Bad senders and unknown ids are dropped. Exit and Open error log are never sent to the page.
- **Open error log.** A missing file, a folder or a link reports "missing" instead of opening.
- **First paint.** Window colours are read by name, with a safe fallback.
- **No log.** With no error log, the details are dropped and only "Tracker failed; no error log" shows.
- **Security and standing rules.** The security settings, the content-security policy and the renderer files are untouched. No network call. No client document read. Nothing sent.
- **Tests.** Eight deliberate breakages of the code were each caught by a test. One was not (F1). Two test names differ from the plan and are handed to S6.
- **Gate.** Eight test files passed under Python 3.11 and 3.13. The unused-code check passed.

## What it found wrong, or what was left to do

- **F1.** The test for "unknown ids are dropped" still passes if the drop is removed. Fix: send an unknown id and check the menu is not rebuilt.
- **F2.** The repository map still describes the removed "show the error on screen" behaviour, calls one channel "the only" one, and misses that the error log is now openable. It needs four wording fixes and a refresh.
- **F3.** The runbook still says the details are shown in the message. It should say the message says there is no error log and the details are not kept or shown.
- Notes only: the menu bar hides until Alt is pressed (the builder asked Jason). The survey file of test names still uses old names, left for S6.

## Decisions (made by Jason, or waiting for Jason)

- **Waiting for Jason:** whether the menu bar must always show, or may hide until Alt.

## Words to know

- **Review:** a check done by someone who did not build the work.
- **Mutation check:** deliberately breaking the code on a scratch copy to see whether a test notices.
- **Channel:** a named path for messages between two parts of the app.
- **Token:** a short label the page attaches so it can tell which menu row was chosen.
- **Repository map, runbook:** the generated code guide, and the operator's manual.
- **Gate:** the set of checks run before work is pushed.
