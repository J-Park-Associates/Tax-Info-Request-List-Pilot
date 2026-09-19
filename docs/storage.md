# Where the facts live

This is the storage plan: what the machine keeps about an engagement, which
file keeps it, and how the three stages of the move fit together. It is the
companion to the decision log — [ROADMAP.md](ROADMAP.md) rows 87 to 89 built
the journal and switched the readers onto it, row 101 added the store, row
102 moved the index into it, and row 103 finished the move: **the plan is
done.**

## What a person edits, and what the record holds

| | |
|---|---|
| **`_manifest.xlsx`, Requests sheet** | the person's rules: the ten accountant columns, and nothing else. A request's identifier, its document, its period, how many files are expected, which types and how small, its keywords, its date rule and a Manual Override. The machine reads this every pass and writes it at three moments only: when the engagement is created, when a year is rolled forward, and once, to slim a workbook from before row 103. |
| **`_manifest.xlsx`, Engagement sheet** | the client, the share link, the due date, the sender, the firm, whether they are chased, whether the run skips them, what the engagement was rolled from and which catalog it was cut from. Also the person's, also read every pass. |
| **the record** | everything the machine decided: every document and where it went, every request's Status, Received Date, File Count and Validation Notes, every keyword a person's filing taught a request — and, since row 103, a copy of the person's rules as at each import. |

A person reads the second half on the **Status Report**, which every pass
regenerates, and in the app. There is nothing in a workbook for them to
read it from and nothing for them to type over.

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

- **In the engagement folder, synced:** the request list a person edits, the
  status page, and `_ledger.jsonl` — the engagement's own history,
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
| `requests` | the person's rules, one row per identifier — everything the request list's own record holds that is not a status. Tuples (keywords, extensions) are JSON text |
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
because a rule row travels in the journal now, and the store attaches an
affinity to each of them. Every rebuild checks the rows it is handed
against the table and refuses a set that has moved.

A row taken from the workbook rather than the journal carries sequence number
zero. That is how the store can always say which of the two readings a value
came from. Since stage 3 the only such row is one the index migration
imported: the documents, the statuses and the rules are all the journal's.
The one thing that says "no import has read this sheet yet" is an empty
`manifest_digest` on the engagement's row.

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
  still keeps facts in a workbook (below), builds an engagement the store
  has never seen, syncs one that is behind, and **imports the request list**
  when the workbook's digest has moved from the one the record holds.
  `migrate=False` is for a caller that must not write in the engagement
  folder: a dry run, the practice's Status Report, the app showing an
  engagement a pass is holding. Such a caller imports nothing, and the rules
  the record already holds stay in force for it.
- **`store.rebuild_engagement()`** deletes one engagement's rows and builds
  them again from the first line — the index, the statuses **and the rules**,
  all from the journal, for an engagement whose journal carries an import.
  It is the recovery, and what a person runs to prove a store they doubt
  (`python -m tracker.store <store> rebuild <root>`). It writes nothing to
  the journal: a rebuild is a reading of the record, not an event in it. The
  workbook reading its caller passes in is used for one engagement only: the
  one no import has ever read.

## The import: the rules travel too

The request list is the person's file, and the machine reads it once a pass.
It compares the workbook's SHA-256 with the digest the record holds; when
they differ it reads the sheet — once, both halves — diffs it against what
the record already says, and appends **one `rules_imported` event**: the
rows that changed or were added, whole, as `records.rule_to_json` writes
them; the identifiers that are gone; the Engagement fields that moved; and
the digest this reading came from. Nothing at all is appended when nothing
changed; the digest alone is noted in the store, which is bookkeeping and
not a fact about anybody's rules, and a rebuild loses it and reads once
more.

The first import carries the whole list, so the fold of every import *is*
the sheet — which is what lets the store be rebuilt from the journals
alone. A workbook that does not validate is not imported at all: the error
is what the engagement's pass reports, and every reader goes on answering
from the last rules that did.

Why journal it rather than simply write it into the database: the workbook
is a file Excel holds open, silently re-types, validates nothing at entry
and keeps no history of. That was the owner's own list on 2026-09-18. The
record cannot stop a keyword being mistyped, but it can say when it changed
and to what. The app's rules editor, after season one, is what replaces the
import — and the journal is what will let that editor be introduced without
losing a season of edits.

## The migration: what a folder still keeps in a workbook

An engagement that still keeps something in a workbook is migrated once, by
`filer.ensure()`, inside the engagement lock, in an order chosen so that a
crash or a refusal leaves nothing half done. Two halves, because two
decisions took two different workbooks.

### The index (decision 102)

1. the workbook and its snapshot sidecar are read the generous way —
   the header row hunted for rather than assumed, rows above it read, the
   sidecar's rows winning and its extras kept — because this is the last
   time this code will ever read that file;
2. every row the record does not already carry is appended to the **journal**
   as `imported`. Into the journal, not just the database, because the
   database is disposable and a row that lived only there would go with it.

### The statuses (decision 103)

3. a Requests sheet that still carries Status, Received Date, File Count
   and Validation Notes is read once for those cells, with
   `_manifest.pending.json` — the sidecar a locked Excel used to defer a
   scan into — laid on top of it, because a status that went to the sidecar
   was applied as far as every reader was concerned. Only the identifiers
   the record has never answered for are taken, so an engagement that has
   been keeping a record since decision 87 contributes nothing;
4. they are appended to the **journal** as one `scanned` event.

### Then, once, the files

5. the engagement is built into the store;
6. the Requests sheet is rewritten without those four columns — a
   non-`data_only` load so a person's formulas survive, `delete_cols` so
   their column widths, the Engagement sheet and any sheet of their own
   survive, and an atomic replace so the file is the old one or the new one
   and never half of each;
7. `_index.xlsx` becomes `_index.migrated.xlsx`, `_index.pending.json`
   becomes `_index.pending.migrated.json`, and `_manifest.pending.json`
   becomes `_manifest.pending.migrated.json`. These are the **last** steps:
   until they land, the folder still looks unmigrated and the next pass does
   all of this again, harmlessly, because the imports are idempotent;
8. one `migrated` event names the files that were moved and the columns that
   were removed.

If Excel holds either workbook the write is refused, loudly, and that
engagement's pass fails. The pass records the error and goes on to the next
engagement, and the next pass tries again; nothing is half done, because
each write is atomic and every step before them is idempotent. An
engagement with neither workbook nor rows is simply created. An engagement
whose journal already carries every row (ledger-first since decision 88)
migrates the same way, and the workbook contributes nothing.

The renamed files are kept rather than deleted, beside the engagement they
describe. `docs/runbook.md` says when they may go: once the Status Report
shows the same rows.

## The check is the gate

`store.check()` asks what else holds the same facts and returns every
disagreement as a sentence naming the engagement, the row or identifier, the
field and both values. An empty list is the claim that the store says what
the other copy says.

Since stage 3 there is **one** other copy, and that is the point: the
journal. The documents, the statuses and the rules the imports fold to are
all compared with `ledger.replay()` over it. Asking the readers instead
would be the store compared with itself — they answer from these very
tables now. An engagement whose journal carries no import is checked on its
documents and statuses alone: its rules are a first reading of a workbook,
and a first reading has no second copy to differ from.

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

**Stage 3 (decision 103) — the manifest goes thin.** `_manifest.xlsx` keeps
its name and its place, and is the person's file and nothing else: the ten
accountant columns, and an Engagement sheet. The machine reads it every
pass and writes it at create, at rollover, and once to slim an old one.
What went with the scanner columns:

- `write_statuses()` and the workbook writer under it,
- the deferred-write machinery that existed only because Excel can hold a
  workbook open — the pending sidecar for the manifest, its merge, the
  quarantine of an unreadable one, the retry-with-backoff around the save,
  and `manifest_deferred` everywhere it was reported,
- `statuses_from_workbook()`, `pending_updates()` and `with_pending()`: the
  readers answer from the record and there is no second reading to overlay,
- `add_any_keyword()` and its formula-cell refusal: a keyword a filing
  teaches is recorded in the same call as the filing,
- and the manifest half of the ledger command line's comparison, which was
  all that was left of it.

And what came the other way: the person's rules travel in the journal now
(the import, above), so the store is rebuildable from the journals alone —
which is what this whole plan was for.

**The plan is finished.** What a workbook holds is what a person typed;
what the machine decided is in the record; and the only thing the two share
is the identifier that joins them.
