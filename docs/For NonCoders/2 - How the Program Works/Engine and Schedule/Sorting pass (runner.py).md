# The sorting pass: the unattended run over every client

**Original file:** `tracker/runner.py`  
**Kind of file:** Python program module (about 3,100 lines; this page summarizes its opening explanation)  
**Tags:** Kind: Program file · Topic: Engine, Schedule  

## In one sentence
This is the program that does the daily work by itself: for every client household it files what was dropped in the inbox, scans, drafts the weekly chase email on the draft day, and leaves a status page.

## What it is
The scheduled job runs this module. The job names no clients folder. It names only the app's settings folder, and the clients folder is read from the settings file at every run (decision 131). Changing the folder in the app is enough. There is nothing to register: a folder that holds an engagement's own record is an engagement, so creating one in the app is all it takes for the next run to pick it up.

## What it does, step by step
1. **Works a household at a time** (decision 125). A household has one permanent inbox, `Drop files here`, and a folder per tax year, and a folder per return inside that. The pass takes every open return's lock, sorts the one inbox across all of them, then scans, drafts and draws each return. A household with two open years sorts nothing from its inbox and says so, until a person retires a year.
2. **Files only when sure.** A drop is filed only where exactly one return's requests accept it. Several or none: it is parked for a person. A drop folder may also feed named returns in other households (decision 129), but only when a person set that up. Nothing is inferred.
3. **Sweeps leftovers first** (decision 155). Every file is written through a temporary copy and renamed whole. A pass killed half way leaves a temp file and never half a file. The pass removes those temps before reading anything.
4. **Drafts weekly.** The draft day is Saturday (`DRAFT_WEEKDAY`). Filing and scanning run on every pass. `--reminders always` forces a draft any day. `--reminders never` suppresses it. A client whose details say Reminders = NO is never drafted, whatever the settings.
5. **Never sends anything.** It writes a draft text file and stops. A person edits and sends it. A draft a person has edited is never overwritten: a new file is written beside it instead.
6. **Holds a draft when it should** (decisions 115, 133). An ambiguous request holds the whole reminder. So does a file still waiting in the inbox. The hold is said on the status page and in the app.
7. **Leaves two kinds of page.** One page for the whole practice (`status.html` in the clients folder): what every engagement owes, what is parked, what failed, and folders that do not fit the layout. Each engagement gets its own view page. Both are self-contained and reach no network.
8. **One failure never stops the rest** (decision 189). Each problem is recorded against its household and the run moves on. The run exits with a failure code if anything failed, so the scheduler shows red. The run log and status page are each attempted even if something else broke, and messages name a code, never a client's path.
9. **No household hogs the pass.** Each gets 15 minutes (`HOUSEHOLD_BUDGET_SECONDS`), checked between files. One that runs out stops, records what it did and drafts nothing. Households run least-recently-finished first. A household missed two passes running ends the pass with exit code 3.

## Why it matters to the firm
This is the engine of the whole system. It keeps client documents moving without a person, and it follows the standing rules: no generative AI reads a client document, originals are never altered, nothing is guessed, nothing is ever sent.

## What must never be changed without a programmer
- **The rules that decide where a file goes,** and the choice to park unclear files.
- **Lock order,** which stops two passes running at once from each holding one return the other needs and waiting forever.
- **The draft protections:** never overwrite an edited draft, never draft over a hold, honor Reminders = NO.
- **The rule that it sends nothing.**
- **The log's wording,** which names a kind of problem or a code, never an error's raw text (that text can carry a client's file path).

## Words to know
- **Pass:** one full run of filing, scanning and drafting.
- **Household:** a client folder, with a folder for each tax year and return.
- **Engagement / return:** one client's return for one year.
- **Inbox (Drop files here):** the one folder a client drops files into.
- **Parked (Needs Review):** set aside for a person to decide.
- **Lock:** a marker that stops two jobs from changing the same thing at once.
- **Status page:** the one page showing what the practice owes.
- **Draft day:** the weekday the chase email is drafted.
