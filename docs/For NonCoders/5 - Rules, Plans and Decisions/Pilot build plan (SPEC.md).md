# Pilot build plan

**Original file:** `pilot/SPEC.md`  
**Kind of file:** written build plan (a specification, called a SPEC)  
**Tags:** Kind: Program file · Topic: Rules and decisions  

## In one sentence
This is the detailed plan for building the first pilot edition: what to make, the rules every new file must follow, and how the work is split and checked.

## What it is
The project rule is that nothing is built without a written SPEC. This one is about 1,000 lines, titled "Pilot edition 0.1 - SPEC". A note at the top (dated 2026-09-29) says it built the first edition, while the shipped label is now 0.2, and everything else still describes what was built. Numbers like P18 point to rows in the pilot decision log. The file has numbered sections; the main ones are below.

## What it does, step by step
1. **Section 1, what this is.** A Windows installer for Tax Document Tracker Pilot, for a first group of other CPA firms. Sorting works exactly as in the main product. The pilot adds a "Pilot edition" badge, a terms screen shown once that must be accepted, and a guided tour. It also lists non-goals: no sample sandbox, no feedback button, no usage tracking, no expiry, and no network calls.
2. **Section 2, rules every pilot file obeys.** These come from tests already running: for example, no inline scripts, no building the page from HTML text, no network call even in comments, no new message channel, and no product name typed into new screen files.
3. **Sections 3 and 3a.** The small edits to the page, and the pilot's own names on the computer (decisions P18, P19).
4. **Sections 4 to 9.** The wording file, the scripts for the badge, terms and tour, the exact terms text and tour copy approved by Jason (P20, P22), and the pilot's style file.
5. **Section 10, the installer.** The installer recipe and the build script.
6. **Section 11, tests.** The tests to write, each named as the claim it proves.
7. **Section 12, the schedule setting.** A switch for the daily schedule: on or off, start time and how often (P16, P21). It needed real engine changes.
8. **Sections 13 and 14.** The Tester Guide, and a safety note for testing at J Park.
9. **Section 15, build split and done criteria.** Work is split into Builds A, B and C, run in parallel and merged in the order B, A, C. It is done when the checks pass and a separate reviewer has no open findings.

## Why it matters to the firm
The plan states in writing what "done" means, and it protects the main product. Most pilot code is new files, so testers get the latest sorting without the pilot disturbing it. It is also the record a reviewer checks the finished work against.

## What must never be changed without a programmer
- The rules in section 2, which tests enforce.
- The approved terms and tour wording. Only Jason changes them.
- The list of files the pilot may not edit, except where the plan names an exception.
- Any change to the plan without a matching decision-log row.

## Words to know
- **SPEC (specification):** a written plan for what to build.
- **Pilot:** the first test edition.
- **Build A, B, C:** the three parts of the work run side by side.
- **Terms screen:** the agreement a tester must accept before using the app.
- **Guided tour:** a walk-through over the real screen.
- **Non-goal:** something the plan says not to build.
- **CSP:** the page's rule that only the app's own files may load.
