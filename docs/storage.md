# Where the facts live

This is the storage plan: what the machine keeps about an engagement, which
file keeps it, and how the three stages of the move fit together. It is the
companion to the decision log — [ROADMAP.md](ROADMAP.md) rows 87 to 89 built
the journal and switched the readers onto it, row 101 added the store, and
row 102 moved the index into it.

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

- **In the engagement folder, synced:** the request list a person edits, its
  deferred-status sidecar, the status page, and `_ledger.jsonl` — the
  engagement's own history, travelling with the engagement. Copy the folder
  to another machine and its whole history goes with it.
- **On one machine, local, never synced:** `tracker.db`, one file per clients
  root, beside the settings file — which is beside the app, on the machine
  that runs the schedule. `store.path_for()` is the whole of that rule, and
  the suite walks a clients root after a build to prove nothing of the
  database landed under it. One machine per clients root was already the law
  (the engagement lock needs it), so one store per clients root takes nothing
  away.

The store is disposable. Delete it and every fact it held is still in the
journals; rebuild it and it says the same thing again. That is the test every
step of this plan has to pass, and it is why the migration writes the old
workbook's rows into the **journal** rather than only into the database.

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
drops, a person filing, dismissing or unfiling a parked document — builds
every event its decision produces and hands them to `record()` in one call.
Either the whole of what it decided is on the record or none of it is, and
the rollback that puts a moved file back asks exactly that question.

## The schema

One file, `PRAGMA user_version = 1`. A file at any other version is refused
by name rather than opened hopefully.

| table | what it holds |
|---|---|
| `engagements` | one row per engagement folder, keyed by its path relative to the clients root with forward slashes: the Engagement sheet's own fields, the rules workbook's digest and the journal's head as they were when the rows were built, how many lines have been applied, and when |
| `requests` | the person's rules, one row per identifier — everything the request list's own record holds that is not a scanner column. Tuples (keywords, extensions) are JSON text |
| `statuses` | one identifier's scanner columns: status, received date, file count, validation notes, and the sequence number that set them |
| `documents` | the index: one row per preserved original, every column the index row has, plus the identity it is keyed under, the place it holds in the index's own order, and the sequence number that last wrote it |
| `learned_keywords` | a keyword a person's filing taught one request |
| `events` | every journal line, in order, with the whole line kept as JSON text |

Indexes: documents by decision within an engagement, documents by digest,
statuses by status.

Every column holds what the frozen record holds, serialised the record's own
way — dates as ISO text, the yes/no cells as 0 and 1, tuples as JSON. The
column lists are **derived** from the records in `tracker/records.py`, so a
field added to an index row is a column without another edit. The one list
written out by hand is the rule half of a request row, because that record is
the schema of a sheet a person edits and stays in the module that parses it;
every rebuild checks the rows it is handed against the table and refuses a
set that has moved.

A row taken from the workbook rather than the journal carries sequence number
zero. That is how the store can always say which of the two readings a value
came from. Since stage 2 only the `statuses` table can hold such a row: the
`documents` are the journal's.

## Keeping it in step

Three functions, and the one a caller wants depends on what it can afford:

- **`store.follow_the_journal()`** is the reader's. It builds an engagement's
  rows from the journal where the database has none and replays the lines it
  has not applied where it is behind, and it opens no workbook, takes no lock
  and writes nothing in the engagement folder. `filer.read_index()` calls it
  before every read, which costs one digest of the journal file when nothing
  has happened — so no reader in the package has to know whether anything
  prepared the engagement first.
- **`filer.ensure()`** is the pass's and the app's. It migrates a folder that
  still keeps its index in a workbook (below), builds an engagement the store
  has never seen, syncs one that is behind, and reads the request list again
  when the rules workbook's digest has moved. `migrate=False` is for a caller
  that must not write in the engagement folder: a dry run, the practice's
  Status Report, the app showing an engagement a pass is holding.
- **`store.rebuild_engagement()`** deletes one engagement's rows and builds
  them again from the first line. It is the recovery, and what a person runs
  to prove a store they doubt (`python -m tracker.store <store> rebuild
  <root>`). It writes nothing to the journal: a rebuild is a reading of the
  record, not an event in it.

## The migration: the index moves into the record

An engagement that still has an `_index.xlsx` beside it is migrated once, by
`filer.ensure()`, inside the engagement lock, in an order chosen so that a
crash or a refusal leaves nothing half done:

1. the workbook and its snapshot sidecar are read the generous way —
   the header row hunted for rather than assumed, rows above it read, the
   sidecar's rows winning and its extras kept — because this is the last
   time this code will ever read that file;
2. every row the record does not already carry is appended to the **journal**
   as `imported`. Into the journal, not just the database, because the
   database is disposable and a row that lived only there would go with it;
3. the engagement is built into the store;
4. `_index.xlsx` becomes `_index.migrated.xlsx` and `_index.pending.json`
   becomes `_index.pending.migrated.json`. This is the **last** step: until
   it lands, the folder still has a legacy index and the next pass does all
   of this again, harmlessly, because steps 2 and 3 are idempotent;
5. one `migrated` event names the files that were moved.

If Excel holds the workbook the rename is refused, loudly, and that
engagement's pass fails — exactly as a locked manifest refuses a scan. The
pass records the error and goes on to the next engagement, and the next pass
tries again. An engagement with neither workbook nor rows is simply created.
An engagement whose journal already carries every row (ledger-first since
decision 88) migrates the same way, and the workbook contributes nothing.

The renamed files are kept rather than deleted, beside the engagement they
describe. `docs/runbook.md` says when they may go: once the Status Report
shows the same rows.

## The check is the gate

`store.check()` asks what else holds the same facts and returns every
disagreement as a sentence naming the engagement, the row or identifier, the
field and both values. An empty list is the claim that the store says what
the other copies say.

Since stage 2 each half has a different other copy, and that is the point:

- the **documents** are compared with `ledger.replay()` over the journal,
  which is the only second copy of them now that `read_index()` answers from
  the tables;
- the **requests and statuses** are compared with the live manifest readers,
  which answer from the record and fall back to the sheet per identifier,
  while a rebuild is fed the sheet's own reading. Comparing a rebuild against
  the readings it was built from would be the store compared with itself.

The autouse fixture in `tests/conftest.py` does exactly this after **every
test in the suite**: for every engagement folder the test left behind, build
a store in a throwaway database and assert the check says nothing. That runs
the store over every drop sorted, every parked file a person filed, every
locked-Excel sidecar and every journal path the suite has. It was the gate
stage 2 was built on, and it is the gate stage 3 will be built on.

## What each stage did, and what is left

**Stage 1 (decision 101) — the store, and nothing reads it.** Purely
additive: no reader answered from it, no writer stopped writing what it
wrote, both workbooks and both sidecars were written exactly as they were,
and deleting the database changed no behaviour at all. That is the same shape
decision 87 used for the journal, and it is what made the step reversible.

**Stage 2 (decision 102) — the index moves into the store.** `_index.xlsx` is
never written again. `read_index()` answers from the `documents` table;
every writer that used to rewrite the workbook calls `store.record()`
instead. What went with it:

- `write_index()` and the workbook writer under it,
- the deferred-write machinery that existed only because Excel can hold a
  workbook open: the pending sidecar for the index, its snapshot merge, the
  quarantine of an unreadable one, the retry-with-backoff around every index
  save, and `index_deferred` everywhere it was reported,
- the per-read fold for the index: `ledger.fold()` is the store's business
  now, not every reader's,
- and with them the whole class of failure the decision log spent thirteen
  readings on — a row lost because the only place it lived was a file Excel
  could rewrite.

The workbook reader survives, private, as the migration's own
(`filer._legacy_index_reading`), and goes when the last folder is migrated.

**Stage 3 (decision 103) — the manifest's scanner columns.** The request list
is still a workbook a person edits, and it still carries Status, Received
Date, File Count and Validation Notes, written back by `write_statuses()`
with the same retry and the same deferred sidecar the index used to have.
`load_manifest()` still folds the journal on every call for them. What goes
then:

- the scanner columns leave the sheet a person edits, so the sheet holds
  only the person's own rules and nothing the machine writes,
- `statuses_from_workbook()` stops being the readers' fallback and keeps
  only its migration and test roles,
- `manifest.pending_updates()` and the manifest's own deferred sidecar,
- and the manifest half of `python -m tracker.ledger --compare`, which is
  all that is left of it.

Stage 3 may not start until the gate above has been silent across the whole
suite for stage 2.
