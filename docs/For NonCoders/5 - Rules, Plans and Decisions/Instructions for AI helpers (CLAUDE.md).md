# Instructions for AI helpers

**Original file:** `CLAUDE.md`  
**Kind of file:** standing instructions for AI coding helpers (a project rulebook)  
**Tags:** Kind: Program file · Topic: Rules and decisions, GitHub costs  

## In one sentence
This is the rulebook that every AI helper working on the project reads first: how to find its way, the four safety rules, and how and when to test and save work.

## What it is
`CLAUDE.md` is a file that the AI coding tool, Claude Code, reads at the start of every session. It is about 330 lines and is written for the AI, not for people. It says: "Tax Document Tracker - working notes for agents." It describes a system where the client gets one folder to drop documents into, and scheduled jobs sort, rename, index and check what arrives, then draft (never send) reminder emails.

## What it does, step by step
The file is organized in these parts:
1. **Start here.** Do not re-scan the whole project. Use the code map (`docs/repo-map.md`), one entry at a time, and confirm it is current with a check command first.
2. **Keeping the map current.** Refresh the map in the same save as any code change. Hand-written descriptions go in one file. Generated files are never edited by hand.
3. **The routing tools.** Points to `docs/tools.md` for the vocabulary report, learned keywords and the backtest. No sorting change may lower the recorded backtest score.
4. **The standing rules.** Four rules that hold across everything:
   - No generative AI ever reads a client financial document. Every decision comes from fixed rules.
   - Originals are never altered. Files are moved byte for byte, and every move is recorded.
   - Nothing is guessed. A document is filed only when exactly one request accepts it (with two narrow exceptions for documents that name several forms, such as a broker's combined statement); unclear ones go to `00 - Needs Review` for a person.
   - Nothing is ever sent. The system drafts emails and stops. No mail or network call exists in that path.
5. **The folder layout.** One client folder per household, with a folder per tax year inside. There are two trees: `Clients` holds each household's `Drop files here` inbox and, per year, the originals moved out of it; `J Park & Associates` holds the firm's record and, per year, one folder per return. Only the `Clients` tree is ever shared with a client.
6. **How work flows.** Nothing is built without a written plan. Jason owns every decision. A separate reviewer, who did not build the change, checks it.
7. **One-time steps run themselves** (decision 209). A step that must happen after installing or upgrading is built into the installer and the app's launch. No person is ever told to remember a manual step.
8. **Working on this repo.** How to install parts, run tests, and the coding habits to follow (plain paths, one part per file, clear failure messages, tests named as claims).
9. **Cost discipline.** Automatic online testing costs money, so tests run on the local machine. Run the dead-code check first, then only the tests the change touched, and save work to the shared branch in big, infrequent groups. No online test runs on every small save. Jason set this on 2026-09-22, revised through decisions 207 and 211, and on 2026-09-29.

## Why it matters to the firm
Client tax documents are sensitive. This file makes every AI helper obey the same safety rules and work in the same careful way, so the rules do not depend on a helper's memory. A test (`tests/test_single_source.py`) checks that the four rules are quoted exactly the same everywhere.

## What must never be changed without a programmer
- The four standing rules. Only Jason may change them.
- The testing and saving rules, which are Jason's standing decisions.
- The exact wording of the rules; tests compare it across files.
- Any line telling a person to run a manual step after installing.

## Words to know
- **AI helper / agent:** a program like Claude Code that reads and edits code.
- **Code map:** the guide to every file (see the code map page).
- **Backtest:** a check of the sorting rules against the firm's own past documents.
- **CI:** automatic tests that run online and cost money.
- **Branch / merge:** a separate line of saved work, and the act of joining it in.
- **Byte for byte:** an exact copy with no change at all.
- **Decision number:** a numbered ruling in the decision log.
