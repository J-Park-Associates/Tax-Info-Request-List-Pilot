# Where the facts live

This is the storage plan: what the machine keeps about an engagement, which
file keeps it, and how the stages of the move fit together. It is the
companion to the decision log — [ROADMAP.md](ROADMAP.md) rows 87 to 89 built
the journal and switched the readers onto it, row 101 added the store, row
102 moved the index into it, row 103 the statuses and the person's rules, and
row 104 retired the last workbook: **everything is in the record.**

## What a person edits, and what the record holds

| | |
|---|---|
| **the record** holds the person's rules | the eleven accountant columns, and nothing else: a request's identifier, its document, its period, how many files are expected, which types and how small, its keywords, its date rule, a Manual Override and its Override Reason. Edited in the app's **Edit Request List** editor and nowhere else; every save is one `rules_changed` event. |
| **the record** holds the engagement's details | the client, the share link, the due date, the filing deadline, the sender, the firm, whether they are chased, whether the run skips them, what the engagement was rolled from and which catalog it was cut from. Written by the wizard, edited in the same editor, carried in the same event. |
| **the record** holds what the machine decided | every document and where it went, every request's Status, Received Date, File Count and Validation Notes, every keyword a person's filing taught a request. |

A person reads the last of those on the **Status Report**, which every pass
regenerates, and in the app; the first two they read and edit in the app.
There is no workbook for them to read anything from and none for them to
type over.

## The words, used exactly

Three words are used here and in the code with one meaning each, because the
earlier readings of this path went wrong wherever two of them were used
interchangeably.

| word | what it means |
|---|---|
| **the record** | what the machine keeps about an engagement: the journal **and** the store together |
| **the ledger** | the journal file alone — `_ledger.jsonl`, in the engagement folder, one JSON event per line |
| **the store** | the database alone — `tracker.db`, on the designated machine's local disk |

Neither half is a copy of the other. The journal is what is *written*; the
store is what is *queried*; and the arrow between them only ever points one
way — **the store is rebuilt from the journal, never the reverse.**

Standing rule 2 is worded in these words: *every move is recorded in the
record.* `records.THE_RECORD` is the phrase, owned once, and
`api.standing_rules()` fills it in.

## Why the journal syncs and the store does not

The engagement folders are synced between the office machine and the drive by
a cloud client. That client copies a file a piece at a time, knows nothing
about a write-ahead log, and will happily put an older copy back over a newer
one. A synced database file is a corrupted database file; that was decision
87's finding and nothing since has changed it. A text file that only ever
grows is the one shape a sync client can carry safely, and a torn last line
is the only damage a killed run can leave in it.

So the split is:

- **In the engagement folder, synced:** the status page and `_ledger.jsonl` —
  the engagement's own history, the request list a person edits included,
  travelling with the engagement. Copy the folder to another machine and its
  whole history goes with it.
- **On one machine, local, never synced:** `tracker.db`, one file per clients
  root, beside the settings file — which is beside the app, on the machine
  that runs the schedule. `store.path_for()` is the whole of that rule, and
  the suite walks a clients root after a build to prove nothing of the
  database landed under it. One machine per clients root was already the law
  (the engagement lock needs it), so one store per clients root takes nothing
  away.

The store is disposable. Delete it and every fact it held is still in the
journals; rebuild it and it says the same thing again. That is the test every
step of this plan has to pass, and it is why a person's edit of the request
list is written into the **journal** rather than only into the database.

## One store per process

`store.connect()` hands out one connection to one file for the life of the
process, created on first use and closed by `store.close()`. Where that file
is comes from the settings file's own location, unless the environment
variable `TRACKER_STORE` names an absolute path — which the suite sets per
test, so no test can leak rows into another, and which a person may set to
ask a question of a copy.

## Journal first, then apply

`store.record()` appends each event to the journal — under the engagement
lock, one `os.write` then `fsync` — and only then opens one immediate
transaction that inserts those events and folds them into the tables.

That order is the guarantee. If the machine dies between the two, the journal
is ahead of the store by some lines and **nothing is lost**: `store.sync()`
compares the journal's line count with the store's own `applied_seq` and
replays the difference, and a torn last line is simply not a line yet. The
other order would lose the event itself, and an event is the one thing
nothing can reconstruct.

It is also why the store runs at `synchronous = NORMAL` with a write-ahead
log: a page the operating system has not flushed costs a replay, not a fact.

**One decision, one call, one transaction.** Every writer — a pass sorting
drops, a person filing, dismissing or unfiling a parked document, a person
saving the request list — builds every event its decision produces and
hands them to `record()` in one call.
Either the whole of what it decided is on the record or none of it is, and
the rollback that puts a moved file back asks exactly that question.

## The schema

One file, `PRAGMA user_version = 7` (decision 104 dropped the workbook's
digest column; decision 107 added the verdict cache's two tables; decision
116 added the `override_reason` column to `requests`; decision 117 added
the Filing Deadline to the engagement's details, and a detail is a column
of `engagements`; decision 119 added the `intents` table; decision 125 put
the household, the tax year and the return name into the engagement's
details, gave `engagements` the household record's own columns and a `kind`
saying which of the two a row holds; a file at an
earlier version is refused by name, and is deleted and rebuilt — nothing
is lost, the journals are what it is made
of). A file at any other version is refused by name rather than opened
hopefully.

| table | what it holds |
|---|---|
| `engagements` | one row per folder that has a journal — a return, or a household (decision 125); `kind` says which. Keyed by its path relative to the clients root with forward slashes — the root the settings file names whenever the folder is under it, whatever root a caller typed, so one folder is one key for the app, the scheduled pass and the command line alike (decision 106); a caller's own root, or the folder's parent, only on a machine with no settings file. For a return: its own details, which since decision 125 carry the household, the tax year and the return name. For a household: the `household_` columns — its name, the members a person typed, the contact and the inbox link. And for both: the journal's head as it was when the rows were built, how many lines have been applied, and when |
| `requests` | the person's rules, one row per identifier — everything the request list's own record holds that is not a status, in the order the person gave the rows. Tuples (keywords, extensions) are JSON text |
| `statuses` | what the last scan said about one identifier: status, received date, file count, validation notes, and the sequence number that set them |
| `documents` | the index: one row per preserved original, every column the index row has, plus the identity it is keyed under, the place it holds in the index's own order, and the sequence number that last wrote it - read back by `document_seqs()`, and the app carries it |
| `learned_keywords` | a keyword a person's filing taught one request, and has not taken back: a `keyword_learned` event inserts the row with the journal line's sequence number and a `keyword_unlearned` deletes it (decision 113), so the words come back in the order they were taught and one taught again comes back last |
| `events` | every journal line, in order, with the whole line kept as JSON text |
| `intents` | the moves begun and not finished (decision 119): one row per index row's identity, holding the whole `moving` line — the operations, the row the decision will record and the event that completes it. Empty after any pass that was not interrupted |
| `verdicts` | the tier-3 verdict cache (decision 107): one row per content digest and rules fingerprint, the verdict as JSON text - pass/fail, reason, the firm's own evidence terms, never client text - and the `CACHE_VERSION` it was written under. **Not the record's**: see below |
| `file_memos` | the cache's memo: one row per working copy or drop the pass has hashed, its size, mtime and digest, so an unchanged file is not read again. **Not the record's** either |

Indexes: documents by decision within an engagement, documents by digest,
statuses by status.

The events that carry a whole index row are `tracker.ledger.ROW_EVENTS`,
and their fold **is** the index: `preserved`, `filed`, `parked`,
`duplicate`, `assigned_by_person`, `dismissed_by_person`,
`unfiled_by_person`, `restored_by_person`, `bytes_recorded`, `copy_moved`
and the `imported` line a seeded row carries. `copy_moved` is decision
109's: the pass found a row's working copy somewhere other than where
the record last said — away from its request folder, away again, or back
where it belongs — and the row the line carries says which. One name in
either direction, because the fold is the same fold whichever way the
copy went. `restored_by_person` is decision 110's and the newest of them,
and it is the answer to that one: a person put the copy back where the
record put it, whatever the click found — the bytes moved home, copied
home from the client's original, already home, or refused a home holding
a different file and sent to review instead. One name again, because the
row the line carries says which. The rest of the names are not row events and fold their own
way: `scanned` (the statuses), `keyword_learned`, `rules_changed`,
`drafted`, `draft_approved`, `moving`, `move_abandoned` and
`household_changed`, and the retired
`rules_imported` and `migrated`. `household_changed` is decision 125's and
the only line a household's own journal ever carries: the fields of the
household record that moved, and nothing else. It is folded into the
`household_` columns, not into any index row — a household holds no
documents and no requests. `draft_approved` is decision 118's and the
newest of them: a person read the week's draft in the app and said it is
the one to send. It carries the stage, the draft file, the fingerprint in
that file's header and the requests it asks for — a number, a name and
identifiers, and not one word of the letter — and nothing folds it: it is
a fact about a week, like `drafted`, not a row of the index. Until the next
draft day the pass reads it and leaves that file exactly as it leaves one
somebody edited.

## The intent is the decision

The record has been all-or-nothing since decision 102 and each step on the
disk is atomic on its own; what sat between them was a run killed after a
file had moved and before the row that explains it was written. A pass
that had copied a document and not yet recorded the batch, a person's
filing killed between the move and the record, a copy the power cut in
half — each left the folder ahead of the record, and only a person could
tell.

So **what a decision is about to do goes on the record before it does it**
(decision 119). One `moving` line, under the lock the writer already
holds, keyed by the row's own identity: the file operations in order with
the digest each end is expected to hold, the row the decision will record,
the event that will complete it, and whether a pass or a person decided.
The row event that follows *is* the completion — it names the same key, and
both folds drop the intent when they see it — so nothing has to be closed
by hand and a decision that lands leaves nothing behind. A refusal is not a
crash: the rollback that puts the files back appends `move_abandoned`, so
the next pass does not finish forward a move the record would not take.

**Recovery is at the start of every pass**, before anything else looks.
Each operation is checked by its fingerprint and finished where reality
matches — a move not yet made is made, a copy already in place is simply
recorded, a stand-down already done is done — and then the intent's own
row is recorded as the intent said: a person's filing as theirs, dated
the day they made it, with the keyword it taught in the same transaction.
Where a destination holds a different file nothing there is touched and the
row parks, naming it; where the bytes are at neither end the row parks and
says so. A person's action on an engagement with a move open is refused
until a pass — which the app's **Run now** is — has finished it.

**The fingerprint identifies; the record decides.** Recovery completes a
decision the record already holds, and the fingerprint says only which half
of it happened. It is the line decisions 109, 110 and 111 draw: no file is
ever moved on the strength of what it looks like, only on the strength of
what was decided.

Every column holds what the frozen record holds, serialised the record's own
way — dates as ISO text, the yes/no cells as 0 and 1, tuples as JSON. The
column lists are **derived** from the records in `tracker/records.py`, so a
field added to an index row is a column without another edit. That includes
the rule half of a request row: `records.RULE_FIELDS` names those fields,
because a rule row travels in the journal, and the store attaches an
affinity to each of them; `tests/test_store.py` holds the two lists
together, so the table cannot drift away from the record in silence.

Every row carries the sequence number of the journal line that last wrote
it. There is no other reading a row could have come from.

## The cache is in the store and not in the record

The verdict cache — what tier 3 decided about each document's bytes under
each row's rules, and the memo that spares an unchanged file its hash —
used to be a JSON file in the engagement folder that every pass rewrote.
The owner's rule, 2026-09-19 (decision 107): **nothing the machine can
derive lives in the synced folder.** A file rewritten every two hours
beside the client's documents is the workbook failure class one file over.
So it is two tables here, `verdicts` and `file_memos`, per engagement.

**Why it is not journalled.** A verdict is not a fact about the engagement;
it is a derivation of two things the record already holds or can
recompute — the bytes in the folder and the rules in `requests`. The
journal is the list of moments something *happened*, and a cache hit is
not one; journalling every reading of every document would make
`_ledger.jsonl` grow with every pass, which is the sync-churn problem moved
one file over. So: no event, no line. A `rebuild` cascade-deletes the two
tables with the rest of the engagement's rows and does **not** refill
them — the next pass reads each document once and is slower, never wrong.
`check` compares only what the journal can vouch for and never looks at
them; `state` is untouched; `export` does not export them.

**The write is the store's own transaction, under the lock, never
`record()`.** `record()` is for events — it appends to the journal first and
numbers a `seq`. A cache save has neither, so it goes in one immediate
transaction of its own (`store.remember_verdicts()`), whole or nothing. It
still refuses outside the engagement lock, by the same sentence `record()`
uses: every writer already holds it, and the memo ties a *path* to a
digest, so a writer racing a pass over the same files could memo a path
against bytes the pass had just replaced. Reads take no lock. A cache built
with no engagement — the command line's, a test's — is memory only and
never touches the store.

**The same key, the same rule.** `(digest, rules_fingerprint)` is still the
key, the `(size, mtime_ns)` memo still spares the hash, a transient verdict
(no OCR installed, OCR failed this once) is still never cached, and
`CACHE_VERSION` is carried on every verdict row: a row at another version is
ignored on load and deleted on save, so a matcher change still invalidates
every earlier verdict without a store version. **Nothing was read from the
old file.** The next real pass removes it from the folder and reads each
document once.

## Keeping it in step

Three functions, and the one a caller wants depends on what it can afford:

- **`store.follow_the_journal()`** is the reader's. It builds an engagement's
  rows from the journal where the database has none and replays the lines it
  has not applied where it is behind; it takes no lock and writes nothing in
  the engagement folder. `filer.read_index()`, `manifest.load_manifest()`
  and `manifest.load_engagement_info()` call it before every read, which
  costs one digest of the journal file when nothing has happened — so no
  reader in the package has to know whether anything prepared the
  engagement first.
- **`filer.ensure()`** is the pass's and the app's: the same top-up, and
  then the three words — current, behind or unknown — that say whether the
  store describes the engagement. It writes nothing in the engagement
  folder, so a dry run, the practice's Status Report and the app showing an
  engagement a pass is holding all call it as freely as a pass does.
- **`store.rebuild_engagement()`** deletes one engagement's rows and builds
  them again from the first line — the index, the statuses, the rules and
  the details, all from the journal and nothing else. It is the recovery,
  and what a person runs to prove a store they doubt (`python -m
  tracker.store <store> rebuild <root>`). It writes nothing to the journal:
  a rebuild is a reading of the record, not an event in it.

A fourth thing is kept in step, and it is a person rather than a reader:
**the row's own sequence number is the freshness handle** (decision 112).
`document_seqs()` answers, per engagement, which journal line last wrote each
index row. The app's state carries it beside every row, a person's File it,
Not requested or Unfile carries it back, and the filer refuses - before a byte
is read or a file is touched - when the record's is not the one the card was
drawn on, naming what the record now says. Per row and not the engagement's
head: a scan between the card being drawn and the button being pressed appends
a line and rewrites no row, and must not refuse the click. It is a check and
never a lock, so nothing is left frozen; a caller with no view, a script or a
test, sends none and is not checked. A rebuild numbers the same lines the same
way, so the handle survives the recovery.

## The edit: the rules travel as events

The request list is created, edited and read only in the record. The
wizard's create is `manifest.create_engagement()`: the list is validated
whole — identifiers, duplicates without case, the counts, the date pattern
compiled or derived from the Period, the narrowing names — before a line is
written, and then **one `rules_changed` event** carries every row and every
field of the engagement's details. A person's edit in the app's editor is
`manifest.save_rules()`: validated the same way, then diffed against what
the store holds, and one `rules_changed` event carries the rows that changed
or were added, whole, as `records.rule_to_json` writes them (a row's
position in the list is part of the row, so a row moved is a row changed);
the identifiers that are gone; and the details that moved. The diff is by
the identifier's exact spelling, and the fold — the journal's and the
store's alike — applies the removals before the rows, so an identifier
retyped as `a01` is one event that names `A01` removed and carries `a01`,
and the record holds one row, not two; the store deletes by that exact
spelling as well, never by SQLite's ASCII-only `lower()`. A line of the
wrong shape - a rule that is not a row, statuses that are not a mapping -
is refused by the store with the engagement and the line named, and is
that folder's problem on the Status Report, never the end of the pass. Nothing at all is appended when
nothing changed. A refused row records nothing and names the row and the
column. In the editor a detail sent blank is cleared, and one the editor
leaves out keeps its recorded value.

The create carries the whole list, so the fold of every event *is* the list
— which is what lets the store be rebuilt from the journals alone. The
retired `rules_imported` event that journals from before decision 104 carry
folds exactly the same way and is never written again.

Why journal it rather than simply write it into the database: the record
cannot stop a keyword being mistyped, but it can say when it changed and to
what, which is the difference between a rule that went wrong and a rule
nobody can account for.

## History

Two migrations existed and are gone. Decision 102 read a folder's index
workbook and its sidecar once, into the journal, and renamed them aside;
decision 103 read the four scanner columns an older request list still
carried, into the journal, and slimmed that workbook; and until 104 the
request list itself was a workbook, read once a pass and journalled as
`rules_imported` when its digest moved. Decision 104 retired all of it —
the readers, the import, the migration and the tests that proved them are
set aside in `Retired - Excel manifest` outside the tree, with a README
saying how they would come back. A folder that still holds only the old
workbook and no record is listed by the registry as a legacy folder, not an
engagement, and is set up again in the app; nothing imports it, by the
owner's word.

## The check is the gate

`store.check()` asks what else holds the same facts and returns every
disagreement as a sentence naming the engagement, the row or identifier, the
field and both values. An empty list is the claim that the store says what
the other copy says.

There is **one** other copy, and that is the point: the journal. The
documents, the statuses, the rules the edits fold to and — since decision
113 — the keywords filings taught are all compared with `ledger.replay()`
over it. Asking the readers instead would be the
store compared with itself — they answer from these very tables. An
engagement whose journal carries no rules event has no rules on either
side.

A household's row is checked the same way and by the same call
(`_check_household`, decision 125): the `household_` columns against the
fold of that folder's own journal, one sentence per field that differs.

The learned keywords were the last thing here the record could not vouch
for. The table only ever grew, the journal's fold did not know the event
at all, and the check never looked: a row planted or dropped behind the
journal's back said nothing. `ledger.Folded.learned` gives the journal the
fold — learn appends, unlearn removes, a word taught again lands last —
and `_check_learned()` compares it with the table, one sentence per
request whose words differ, in the order each side holds them. The
identifier is folded without case on both sides before they are compared,
because the table keys it that way and the journal keeps the spelling each
line carried.

The autouse fixture in `tests/conftest.py` does exactly this after **every
test in the suite**: for every engagement folder the test left behind, build
a store in a throwaway database and assert the check says nothing. That runs
the store over every drop sorted, every parked file a person filed, every
rules edit and every journal path the suite has. It was the gate each stage
was built on.

## What each stage did, and what is left

**Stage 1 (decision 101) — the store, and nothing reads it.** Purely
additive: no reader answered from it, no writer stopped writing what it
wrote, both workbooks and both sidecars were written exactly as they were,
and deleting the database changed no behaviour at all. That is the same shape
decision 87 used for the journal, and it is what made the step reversible.

**Stage 2 (decision 102) — the index moves into the store.** The index
workbook was never written again: `read_index()` answers from the
`documents` table, every writer calls `store.record()`, and the deferred-write
machinery that existed only because Excel could hold a workbook open went
with it — the whole class of failure the decision log spent thirteen
readings on.

**Stage 3 (decision 103) — the statuses and the person's rules move into
the record.** The scanner records a `scanned` event, a filing records the
keyword it taught in the same call, and the request list's differences
were journalled from the one workbook that remained.

**Stage 4 (decision 104) — the workbook is gone.** The request list and
the engagement's details are created, edited and read only in the record:
`manifest.create_engagement()` and `manifest.save_rules()` write
`rules_changed` events, the app's editor is the only way a rule is entered,
there is no import and no export, and the store is at `user_version` 2
without the workbook's digest. What went with it: the workbook reader, the
thin workbook's writer, the import, the migration and its legacy index
reader, the Carried Forward page of the rollover workbook, and decision 98's real-handle fixture —
all set aside outside the tree. `openpyxl` stays for the tier-3 reader of a
client's own spreadsheet and for nothing else.

**The plan is finished.** What a person typed and what the machine decided
are both in the record, and the only file a person opens is the page.

**Afterwards (decision 107) — the verdict cache leaves the synced folder.**
Not a stage of the plan, but the same lesson applied to the one derived
file the plan had left in the engagement folder: the tier-3 verdict cache
moved into two tables of the store, `user_version` 3, not journalled, and
a pass now writes nothing under the clients root but the journal, the
Status Report and the client's own files.

**Afterwards (decision 109) — every working copy is proved against the
record each pass.** Not a stage of the plan either, but what the record
being the whole of the truth is *for*: the fingerprint each row has
carried since decision 50 is now read against the file each pass, so a
working copy that is not where the record put it is identified and said
rather than silently counted or silently lost. One new event name,
`copy_moved`, in `ROW_EVENTS`, folding like every other row event; no
column, no schema change, `user_version` still 4. And every hash of a file
under the firm's folder now goes through `file_memos`, so a second pass
over an unchanged tree reads one file per preserved original and no
working copy at all.

**Afterwards (decision 113) — learning can be un-learned.** A keyword a
person's filing taught one request is taken back by a person, in the app's
editor, as one `keyword_unlearned` event carrying the request and the word.
No schema change: the table is the same table and the event is the fold's
business. What did change is that the fold is now in both places — the
journal's `Folded.learned` and the store's insert and delete — and that
`check()` compares them, so the one part of the store the record could not
vouch for is inside the gate, and the suite's rebuild-and-check fixture
proves it after every test. A pair nobody taught is refused by name, and
the request is re-scanned at once, because its rules just moved. Firm-wide
is untouched: `tracker/templates.py` and a commit, as before.

**Afterwards (decision 116) — the override is recorded with its reason.**
`override_reason` is a rule field: it travels in the `rules_changed` event
beside the override and is a column of `requests` (`user_version` 4). The
second override value is `Not Applicable`; the spelling journals written
before that decision hold for it is folded to it on every read by the one
reader of a stored rule row and is never written again — the retired-value
rule of decision 104 applied to a value. The journal and the store keep
their bytes; a list read out and saved back unchanged is not an event.

**Afterwards (decision 117) — the engagement records its filing deadline.**
The reminder escalates in four stages against the Due Date and names the
statutory date beside it from the third stage on, so the date is a detail
of the engagement: it travels in the `rules_changed` event with the rest of
them and is a column of `engagements` (`user_version` 5). The columns of
that table are the fields of the details record itself, so the column cost
nothing; the version is what a file written before it cannot have. The
firm's phone number, which only the final notice says, is **not** here at
all: it belongs to the firm rather than to an engagement, and it is kept
beside the firm's name in the settings file.

**Afterwards (decision 118) — a person approves the week's draft.** No
schema change at all: `draft_approved` is an event in `events`, folded by
nothing, exactly as `drafted` is. The reminder is a fact about a week
rather than about a row, and both lines say the same kind of thing — this
is what the week's letter asked for, this is the file it is in, this is the
fingerprint of that file's header — so the store answers "was this draft
approved this week?" with the same `last_event` query it already answers
"when was this engagement last drafted?" with. Nothing about the letter's
words goes in either line, and neither is ever rewritten.

**Afterwards (decision 125) — the household is a row of the same table
(`user_version` 7).** A client folder is a household with one folder per
year inside it and one folder per return inside that, and the household has
a record of its own: its name, the members a person typed as who its folder
is meant to be shared with, the contact its letters greet and the inbox link
they paste. It is a `_ledger.jsonl` in the private tree like any other, and
it is held in `engagements` like any other — a `kind` column says whether a
row is a `return` or a `household`, the four `household_` columns hold the
record, and `_check_household` compares them with the fold of that journal.
A household holds no documents, no requests and no statuses. In the same
version each return's details gain three fields it could previously only
infer from its path — the household, the tax year and the return name —
written at creation and at rollover and never edited, so a folder somebody
renames is still processed as the record says. Nothing else about the
tables changed, and a version-6 file is refused by name, deleted and built
again from the journals.
