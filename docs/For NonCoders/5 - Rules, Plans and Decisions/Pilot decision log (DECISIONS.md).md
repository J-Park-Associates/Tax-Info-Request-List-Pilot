# Pilot decision log

**Original file:** `pilot/DECISIONS.md`  
**Kind of file:** decision log (a table of numbered rulings)  
**Tags:** Kind: Program file · Topic: Rules and decisions  

## In one sentence
This is the pilot edition's diary of decisions: each row says what was decided, when, and why.

## What it is
It is a table of 114 rows, from P1 to P115 (P115 dated 2026-09-30). Its first lines say it holds decisions for the pilot edition only. The main product's decisions live in `docs/ROADMAP.md`, and this log never borrows its numbers.

Each row has four columns:
- **#** - the decision's number, with a leading **P** for *pilot*. P-numbers mean "the pilot's decision number 1, 2, 3 and so on", in the order they were made. Elsewhere in the project a plain number, like decision 209, points to the main product's log.
- **Date** - the day it was decided.
- **Decision** - what was ruled.
- **Why** - the reason. Usually this names Jason ("Jason." means he made the call) or the review that found the problem.

Some rows end with a "Status" note, and some say they supersede (replace) an earlier row. One number (P25) is skipped. Read the newest row on a topic first, because it may replace an older one.

## What it does, step by step
How to read it:
1. Find a topic by searching for a word (for example "installer" or "glass").
2. Read the row and its Why. The Why often explains a choice that looks strange.
3. Check for later rows that replace it (words such as "supersedes" or "removed").
4. Follow references: "P17" means row 17 here; "SPEC section 3a" means the pilot build plan.

Examples of what the rows cover, without listing them all:
- **P1-P17:** where the pilot lives (in its own private repository since P17), who tests it (other CPA firms) and the plan for the terms screen and guided tour.
- **P12:** uninstall removes only installed files and the scheduled task, never client or tracker data.
- **P18:** the pilot has its own names on the PC, so it does not collide with the original.
- **P30-P50:** a "glass" look was designed, then removed entirely in P50.
- **P51 onward:** the new screen structure, and later shell rulings.
- **P115:** upgrades clear only the old program code.

## Why it matters to the firm
The reasons behind rules are easy to forget. This log keeps them, so nobody undoes a careful choice by accident. It is also how Jason's rulings are written down.

## What must never be changed without a programmer
- Never rewrite or delete an old row. Add a new row that supersedes it.
- Never reuse a number or borrow numbers from the main log.

## Words to know
- **Pilot:** the first test edition given to other CPA firms.
- **P-number:** a pilot decision number.
- **Supersedes:** replaces an earlier ruling.
- **Ruling:** a decision Jason made.
- **Build / review:** making the change, and a separate check by someone who did not make it.
- **Repository:** the project's folder with all its history.
