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
| **the record** holds the person's rules | the ten accountant columns, and nothing else: a request's identifier, its document, its period, how many files are expected, which types and how small, its keywords, its date rule and a Manual Override. Edited in the app's **Edit Request List** editor and nowhere else; every save is one `rules_changed` event. |
| **the record** holds the engagement's details | the client, the share link, the due date, the sender, the firm, whether they are chased, whether the run skips them, what the engagement was rolled from and which catalog it was cut from. Written by the wizard, edited in the same editor, carried in the same event. |
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

One file, `PRAGMA user_version = 2` (decision 104 dropped the workbook's
digest column; a version-1 file is refused by name, and is deleted and
rebuilt — nothing is lost, the journals are what it is made of). A file at
any other version is refused by name rather than opened hopefully.

| table | what it holds |
|---|---|
| `engagements` | one row per engagement folder, keyed by its path relative to the clients root with forward slashes: the engagement's own details, the journal's head as it was when the rows were built, how many lines have been applied, and when |
| `requests` | the person's rules, one row per identifier — everything the request list's own record holds that is not a status, in the order the person gave the rows. Tuples (keywords, extensions) are JSON text |
| `statuses` | what the last scan said about one identifier: status, received date, file count, validation notes, and the sequence number that set them |
| `documents` | the index: one row per preserved original, every column the index row has, plus the identity it is keyed under, the place it holds in the index's own order, and the sequence number that last wrote it |
| `learned_keywords` | a keyword a person's filing taught one request |
| `events` | every journal line, in order, with the whole line kept as JSON text |

Indexes: documents by decision within an engagement, documents by digest,
statuses by status.

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
documents, the statuses and the rules the edits fold to are all compared
with `ledger.replay()` over it. Asking the readers instead would be the
store compared with itself — they answer from these very tables. An
engagement whose journal carries no rules event has no rules on either
side.

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
