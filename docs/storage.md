# Where the facts live

This is the storage plan: what the machine keeps about an engagement, which
file keeps it, and how the three stages of the move fit together. It is the
companion to the decision log — [ROADMAP.md](ROADMAP.md) rows 87 to 89 built
the journal and switched the readers onto it; row 101 adds the store.

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
  index workbook, the two sidecars, the status page, and `_ledger.jsonl` —
  the engagement's own history, travelling with the engagement. Copy the
  folder to another machine and its whole history goes with it.
- **On one machine, local, never synced:** `tracker.db`, one file per clients
  root, beside the settings file — which is beside the app, on the machine
  that runs the schedule. `store.path_for()` is the whole of that rule, and
  the suite walks a clients root after a build to prove nothing of the
  database landed under it. One machine per clients root was already the law
  (the engagement lock needs it), so one store per clients root takes nothing
  away.

The store is disposable. Delete it and every fact it held is still in the
journals; rebuild it and it says the same thing again.

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

## The schema

One file, `PRAGMA user_version = 1`. A file at any other version is refused
by name rather than opened hopefully.

| table | what it holds |
|---|---|
| `engagements` | one row per engagement folder, keyed by its path relative to the clients root with forward slashes: the Engagement sheet's own fields, the rules workbook's digest and the journal's head as they were when the rows were built, how many lines have been applied, and when |
| `requests` | the person's rules, one row per identifier — everything the request list's own record holds that is not a scanner column. Tuples (keywords, extensions) are JSON text |
| `statuses` | one identifier's scanner columns: status, received date, file count, validation notes, and the sequence number that set them |
| `learned_keywords` | a keyword a person's filing taught one request |
| `documents` | the index, folded: one row per preserved original, every column the index row has, plus the identity it is keyed under, the place it holds in the index's own order, and the sequence number that last wrote it |
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
came from.

## Rebuild is recovery, and recovery is the migration

`store.rebuild_engagement()` deletes one engagement's rows and builds them
again: the journal replayed from its first line, then — for every index row
and every identifier's status the journal does not carry — the workbook
reading the caller passes in. That is decision 88's rule, "the record
answers, the workbook falls back, per row and per identifier", done once at
build time instead of on every read.

One function answers three questions:

- how an engagement that predates the store gets into it (the migration),
- how a store deleted or doubted comes back (the recovery),
- and what a person runs to prove one (`python -m tracker.store <store> rebuild <root>`).

It is idempotent, and it writes nothing to the journal: a rebuild is a
reading of the record, not an event in it.

The rules and the Engagement sheet are never the journal's. They are the
person's, they come from the workbook every time, and they are passed in —
the store opens no workbook and imports nothing that does.

## The check is the gate

`store.check()` asks the live readers what they say and returns every
disagreement as a sentence naming the engagement, the row or identifier, the
field and both values. An empty list is the claim that a reader moved onto
these tables would answer exactly what it answers today.

The two sides are deliberately different readings. The rebuild is fed the
*workbooks'* own readings; the check asks `filer.read_index()` and
`manifest.load_manifest()`, which since decision 88 answer from the journal
and fall back to the workbook per row and per identifier. Comparing a rebuild
against the readings it was built from would be the store compared with
itself.

The autouse fixture in `tests/conftest.py` does exactly this after **every
test in the suite**: for every engagement folder the test left behind, build
a store in a throwaway database and assert the check says nothing. That runs
the store over every drop sorted, every parked file a person filed, every
locked-Excel sidecar and every journal path the suite has. It is the gate the
next two stages are built on, and it was green from the first full run.

## Nothing reads it yet

Stage 1 is purely additive:

- no reader answers from the store,
- no writer stops writing what it wrote before — both workbooks and both
  sidecars are written exactly as they were,
- the content cache's version is untouched,
- and deleting the database changes no behaviour at all.

That is the same shape decision 87 used for the journal, and it is what makes
the step reversible.

## What stages 2 and 3 take away

Stage 1 adds; the later stages are where files and code are removed. Written
down now so the shape of the whole move is on one page.

**Stage 2 — the readers answer from the store.** `read_index()` and
`load_manifest()` stop folding a journal on every call and read the tables
instead, with `sync()` first. What goes then:

- the per-read fold: `ledger.fold()` and `ledger.statuses()` become the
  rebuild's business rather than every reader's,
- `read_index_from_workbook()` and `statuses_from_workbook()` stop being the
  readers' fallback and keep only their migration and test roles,
- and the index workbook stops being read at all for facts.

**Stage 3 — a workbook write becomes a render.** The index stops being
written row by row and is rendered from the store when a person asks for it,
which is what decision 91 already made the status page. What goes then:

- the deferred-write machinery that exists only because Excel can hold a
  workbook open: the pending sidecar for the index, its snapshot merge, the
  quarantine of an unreadable one, and the retry-with-backoff around every
  workbook save,
- `write_index()` as a step of every pass,
- and with them the whole class of failure the decision log spent thirteen
  readings on — a row lost because the only place it lived was a file Excel
  could rewrite.

Neither stage may start until the gate above has been silent across the whole
suite for the stage before it.
