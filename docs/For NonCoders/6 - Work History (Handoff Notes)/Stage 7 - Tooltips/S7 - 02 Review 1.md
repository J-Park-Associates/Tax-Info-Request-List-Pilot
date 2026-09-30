# First check of the tooltips stage (S7)

**Original file:** `pilot/handoffs/shell-S7-review-1.md`  
**Kind of file:** handoff note (a message from one work session to the next)  
**Tags:** Kind: Review · Topic: Screen · Stage: S7  
**Date:** not stated  

## In one sentence

A separate reviewer found the outside tooltip library clean and safe, but listed four findings, one of which broke the app's start-up test.

## What this session was asked to do

Check stage S7, which moved tooltip placement onto a small outside library called Floating UI. The branch is `claude/shell-s7-tooltips`, reviewed at `430aa27`. The reviewer did not build it and changed no code.

## What it did

- **Supply chain.** The reviewer downloaded the three library packages itself and computed their fingerprints. All matched the registry and the numbers in the handoff. The two shipped files are byte for byte the published ones. The licences are the MIT licence and match. The code has no network calls, no storage use, no code-loading tricks. It is positioning maths only. No package file or bundler changed. The folder ships with the installer.
- **Jason's rulings 2 and 5.** Placement now comes only from the library. The search box shows no tip on keyboard focus, while other controls do. Hover shows tips everywhere. The words are unchanged, the security policy is unchanged, and there is no inline script.
- **Behaviour.** The interaction script passed. Screenshots in light and dark look right. In a contrast theme the tip is drawn inside the window.
- **Mutation checks.** Eight deliberate breakages were tried. Seven were caught. One survived (F3).
- **Gate.** Ten test files passed under Python 3.11 and 3.13. One build test fails on the base too. The code-cleanliness and map checks were clean.
- **Scope.** The extra changes (the test server now serves subfolders; one wording change in the S3 handoff) are all within the brief.

## What it found wrong, or what was left to do

- **F1.** The app's real start-up smoke test fails on this branch and passes on the base. Two new script tags sit between two existing ones, so a needed function does not exist yet when a reply arrives. Fix: load the two library scripts before the app script, and update the test's order list and the merge note.
- **F2.** When a page scrolls, a tip can stay on screen over the path bar, pointing at nothing. Fix (Jason picks): use the library's hide feature, or go back to hiding on scroll.
- **F3.** The "no outside script" test misses a script tag written with single quotes. The security policy would still block it, so this is a test gap only.
- **F4.** A test cites decision "P86", which is not this stage's number. Cite Jason's ruling 5 for now.

## Decisions (made by Jason, or waiting for Jason)

- **Waiting for Jason:** the hover delay. It is 500 ms; the brief said about 300. (Later notes show Jason ruled 300 ms.)
- **Waiting for Jason:** the scroll behaviour (F2). The reviewer recommends the hide feature.
- **For Jason to know:** ruling 5 said "one file", but two files ship, so their bytes match the published package. The reviewer agrees.
- **For Jason to know:** a text box counts as focused when clicked. A future tip on another text box would show on a click.

## Words to know

- **Floating UI:** a small library that places tooltips.
- **Vendored:** copied into the project instead of downloaded when running.
- **Fingerprint (hash, SHA-256, SHA-512):** a number computed from a file. Any change to the file changes it.
- **Supply chain:** the outside parts a program relies on.
- **Content-security policy:** rules about what code the screen may load.
- **Smoke test:** a quick run to see the app starts.
- **Mutation check:** breaking code on purpose to test the tests.
