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
| **the record** holds the person's rules | the fourteen accountant columns (`manifest.HEADERS`), and nothing else: a request's identifier, its document, its period, how many files are expected, which types and how small, its keywords, its date rule, a Manual Override and its Override Reason, whether the document it asks for carries a name, whether the client is asked for it, and the short name the firm's working files use. Edited in the app's **Edit Request List** editor and nowhere else; every save is one `rules_changed` event. |
| **the record** holds the engagement's details | the client, the share link, the due date, the filing deadline, the sender, the firm, whether they are chased, whether the run skips them, what the engagement was rolled from, which catalog it was cut from and who the return is for - the people whose names its documents print, with the spellings they print them in. Written by the wizard, edited in the same editor, carried in the same event. |
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
- **On one machine, local, never synced:** `tracker.db`, one file in the
  tracker's data folder on the machine that runs the schedule
  (`settings.data_home()`: `%LOCALAPPDATA%\tax-document-tracker`, decision
  186), never beside the app or in a checkout, every row keyed by its
  clients root. `store.store_path()` is the whole of that rule, and
  the suite walks a clients root after a build to prove nothing of the
  database landed under it. One machine per clients root was already the law
  (the engagement lock needs it), so one store on that machine takes nothing
  away.

The store is disposable. Delete it and every fact the journals still hold is
still in them; rebuild it and it says what they now say. A journal cannot yet
prove its own lines (audit A-3), so a line lost from one survives only in a
store that read it — which is why the runbook copies the store aside before
any rebuild (§1). That is the test every
step of this plan has to pass, and it is why a person's edit of the request
list is written into the **journal** rather than only into the database.

**But a rebuild is proved first** (decision 159). A journal can come back
from a sync client shorter, reordered or rewritten, and a rebuild from it
would say the new thing with confidence and lose the old. So:

- **Every line carries its link and its writer.** A line written since
  decision 159 names the SHA-256 of the line before it (`prev`), the
  machine that wrote it (`host`) and the record format (`fmt`, now 1). A
  broken link, a line without one past the first linked line, or a newer
  format stops the reader at that line, by name. What the three keys and
  a line's time hold - a link blank or a digest, a format this version
  writes, a writer that is a machine's name, a time as the tracker writes
  it - is held to decision 187's value rule at the store's one admission,
  like every other value a line carries (`records.host_problem`,
  `records.stamp_problem`); `record()` admits each line exactly as it will
  be written, writer included. Older lines without the three keys still
  read; the store's own version is unchanged.
- **The checkpoint** (`record-heads.db`, `tracker/checkpoint.py`, its own
  version 1) sits beside the store on the machine that writes, is never
  synced and survives deleting the store. It is kept in SQLite's
  write-ahead log at full sync (pilot P214), opened once a command and
  held by the store until the command closes it; its `-wal` and `-shm`
  sit beside it while a command runs, and move with it. Per return it keeps how many
  lines this machine has written or accepted and the hash of the last one,
  the clients root it belongs to, and the lines it has seen from other
  machines. The store checks every catch-up against it: a record shorter
  than the checkpoint, rewritten before its count, or with a line past it
  that claims this machine (in any case of its name) and is not one of the
  exact lines this machine said it was about to write - the chain each
  would have, not a count - is refused before anything is applied. A
  checkpoint that will not open is refused by name, never set aside by
  itself. A line from another machine is named on the practice
  page every pass until a person acknowledges it; whether such a line is
  ever refused instead is one function, `checkpoint.foreign_lines_refused()`,
  `False` until the multi-writer question is decided.
- **`rebuild` refuses what the checkpoint vouches for and the record no
  longer holds**, and `recover` is the way past it: it exports both copies
  into `recovered/` beside the store, lists the lines that differ, and
  replays only when a person types the return's folder name. It never
  rewrites a record. `verify` is the same comparison, firm-wide, read-only.

This detects accidents anywhere and, on the machine that writes, an append
or rewrite that machine did not make. It does not protect against a writer
who controls that machine itself, and it is not proof to a third party of
who wrote a line; decision 159 in the roadmap says why a secret key was
rejected.

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
is ahead of the store by some lines and **nothing is lost**: `store.catch_up()`
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

One file, `PRAGMA user_version = 19` (decision 104 dropped the workbook's
digest column; decision 107 added the verdict cache's two tables; decision
116 added the `override_reason` column to `requests`; decision 117 added
the Filing Deadline to the engagement's details, and a detail is a column
of `engagements`; decision 119 added the `intents` table; decision 125 put
the household, the tax year and the return name into the engagement's
details, gave `engagements` the household record's own columns and a `kind`
saying which of the two a row holds; decision 128 put the return's people
into its details and the `named` mark into `requests`; decision 129 put the
household's feed list — the return lines in other households its drop
folder also feeds — into the household's own columns; decision 132 changed
no column and changed the fold, so that a `released` line takes a row out
of the index; decision 134 changed no column and changed the key, so that
two years of one return are never one row; decision 137 added the applied
chain, `applied_digest`, to `engagements`; decision 142 added the `asked`
mark to `requests`, decision 143 `container` to `documents`, decision 144
`short_title` to `requests`, and decision 146 `answers` to `documents` -
the other requests a consolidated statement answers without a copy; decision
204 added `waits_for` to `documents`, decision 190 `code` and `subfolder` to
`documents` and `note_codes` to `statuses`, and decision 209 (R3b) `admitted_by` to
`engagements` - which admission judged the lines a row applied, so a line an
earlier version applied is judged again when the rule tightens - each in
place, where the file stands; a file at any older version is set aside and
rebuilt (decision 159) — nothing is lost, the journals are what it is made
of). A file at a newer version is refused by name rather than opened
hopefully.

| table | what it holds |
|---|---|
| `engagements` | one row per folder that has a journal — a return, or a household (decision 125); `kind` says which. Keyed by its path relative to the clients root with forward slashes — the root the settings file names whenever the folder is under it, whatever root a caller typed, so one folder is one key for the app, the scheduled pass and the command line alike (decision 106); else a caller's own root; else, for a return in the layout of decision 125, the root its position names - four levels up, when its parent is a year folder and its household sits in the private tree - so the key always carries household, year and return and two years of one return are two rows (decision 134); the folder's parent only for a folder outside that layout. For a return: its own details, which since decision 125 carry the household, the tax year and the return name. For a household: the `household_` columns — its name, the members a person typed, the contact, the inbox link and the feed list a person built (decision 129), each feed a household and a return line, as JSON text. And for both: the journal's head as it was when the rows were built, how many lines have been applied, the chain over exactly those lines (`applied_digest`, decision 137), and when |
| `requests` | the person's rules, one row per identifier — everything the request list's own record holds that is not a status, in the order the person gave the rows. Tuples (keywords, extensions) are JSON text |
| `statuses` | what the last scan said about one identifier: status, received date, file count, validation notes, and the sequence number that set them |
| `documents` | the index: one row per preserved original, every column the index row has, plus the identity it is keyed under, the place it holds in the index's own order, and the sequence number that last wrote it - read back by `document_seqs()`, and the app carries it |
| `learned_keywords` | a keyword a person's filing taught one request, and has not taken back: a `keyword_learned` event inserts the row with the journal line's sequence number and a `keyword_unlearned` deletes it (decision 113), so the words come back in the order they were taught and one taught again comes back last |
| `events` | every journal line, in order, with the whole line kept as JSON text |
| `intents` | the moves begun and not finished (decision 119): one row per index row's identity, holding the whole `moving` line — the operations, the row the decision will record, the identity that row is leaving where it moves, the event that completes it, the events that travel with it in this same record and - for a release - the sentence it will say. Nothing an intent carries is ever written into another return's record (decision 132); a line carrying decision 129's `also_in` is refused by name. Empty after any pass that was not interrupted |
| `verdicts` | the tier-3 verdict cache (decision 107): one row per content digest and rules fingerprint, the verdict as JSON text - pass/fail, reason, the firm's own evidence terms, never client text - and the `CACHE_VERSION` it was written under. **Not the record's**: see below |
| `file_memos` | the cache's memo: one row per working copy or drop the pass has hashed, its size, mtime and digest, so an unchanged file is not read again. **Not the record's** either |

Indexes: documents by decision within an engagement, documents by digest,
statuses by status.

The events that carry a whole index row are `tracker.ledger.ROW_EVENTS`,
and their fold **is** the index: `preserved`, `filed`, `parked`,
`duplicate`, `assigned_by_person`, `dismissed_by_person`,
`unfiled_by_person`, `restored_by_person`, `renamed_by_person`,
`answer_withdrawn_by_person`,
`bytes_recorded`, `copy_moved`, `copy_remade`, `original_returned`
and the `imported` line a seeded row carries. `released` is not among them
and is decision 132's: a person filed a parked document under a request of
another return this drop folder feeds, so the row here is released — it
leaves the index, and the journal line says which return took it — while
the row that return holds is its own `assigned_by_person`, written by its
own intent in its own record. The `handed_over_by_person` line decision 129
wrote is retired: read as a release of its key, never written. `copy_moved` is decision
109's: the pass found a row's working copy somewhere other than where
the record last said — away from where it was filed, away again, or back
where it belongs — and the row the line carries says which. One name in
either direction, because the fold is the same fold whichever way the
copy went. `restored_by_person` is decision 110's,
and it is the answer to that one: a person put the copy back where the
record put it, whatever the click found — the bytes moved home, copied
home from the client's original, already home, or refused a home holding
a different file and sent to review instead. One name again, because the
row the line carries says which. `renamed_by_person` is decision 160's: a
person gave a request another identifier with the editor's Rename, and the
row names the new one - its working copies moved into the request's renamed
folder under renamed names, or, for a row with no copy there, only the
identifier it names changed, in its `answers` column too where a
consolidated statement answers the request (decision 146). The
`rules_changed` that renames the request and one `moving` intent per row
are written first, in one write, and each `renamed_by_person` closes one
intent. `answer_withdrawn_by_person` is decision 146's: a person marked a request
missing again that a consolidated statement filed under another request
was answering, and the row it carries is the statement's with that request
taken off its `answers` column - nothing moves on disk. Since decision 157
it also says a person marked a row's own request missing on a row whose
working copy and original are both gone: the row it carries names no
working copy and answers nothing. `copy_remade` and `original_returned`
are decision 157's and the newest: the pass (or a person's Put it back)
made a gone working copy again from the row's own original, and a row's own
original came back into the inbox and was moved to the place the row
names, with no new row. Each closes the `moving` intent written before it,
and both fold like every other row event - no column, no schema change. The rest of the names are not row events and fold their own
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
- **`filer.ensure()`** is the pass's and the app's: the same top-up by
  count rather than by head (`store.catch_up()`, decision 135), and
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

**A read never outruns a write** (decision 135). The readers take no lock,
and the app's process and the pass's share one store, so a reader can be
waiting for the pass's transaction to finish at the very moment it catches
up. Everything that applies journal lines — `catch_up()`, the top-up's slow
path, `record()`'s apply and the rebuild — therefore reads the
engagement's row, the journal's lines and the journal's head *inside* its
own `BEGIN IMMEDIATE`, and takes the lines and the head from one read of
the file (`ledger.read_with_head()`). Read before the transaction, a
reader could re-apply a slice the pass had already overtaken and then save
the head of the whole file: the store said an old decision, called itself
current, and refused every later pass for that return until somebody
rebuilt it. Now a stored head always names exactly the lines applied.
`record()` applies what the journal holds past the store when its
transaction begins, not the batch it was handed, so a reader that caught
part of the batch up in between has none of it applied twice. The
readers keep the fast path — a head that has not moved is one digest and
no parse — and the pass catches up **by count** at `ensure()`, so a store
an earlier version left bent that way is repaired by the next pass, with
no rebuild and no new store version. A catch-up that finds nothing to
apply takes no lock at all: it reads the row and the journal first,
outside any transaction, and only a decision to write takes the store's
lock and reads both again inside. `ensure()` runs after nearly every
action in the app and for every engagement in the Status Report, so this
is what keeps them from holding the lock a pass's `record()` waits on.

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

## What the store is now

The plan these rows built is finished: what a person typed and what the
machine decided are both in the record, there is no workbook to read, import
or write over, and the only file a person opens is the page. A folder that
holds only an old workbook and no record is listed by the registry as a
legacy folder, not an engagement, and is set up again in the app; nothing
imports it. How it got here, stage by stage, is in the decision log
([ROADMAP.md](ROADMAP.md), rows 101 to 104 and the rows after them).

Rules that came with the later rows and hold now:

- **A working copy is proved against the record each pass** (decision 109).
  The fingerprint each row carries is read against the file, so a working
  copy that is not where the record put it is identified and said rather
  than silently counted or silently lost. Every hash of a file under the
  firm's folder goes through `file_memos`, so a second pass over an unchanged
  tree reads one file per preserved original and no working copy at all.
- **Learning can be un-learned** (decision 113). A person takes a taught
  keyword back in the app's editor as one `keyword_unlearned` event carrying
  the request and the word. A pair nobody taught is refused by name, and the
  request is re-scanned at once, because its rules just moved. Firm-wide
  keywords are untouched: `tracker/templates.py` and a commit.
- **The override is recorded with its reason** (decision 116). The second
  override value is `Not Applicable`; the spelling older journals hold for it
  is folded to it on every read by the one reader of a stored rule row and
  is never written again. The journal and the store keep their bytes; a list
  read out and saved back unchanged is not an event.
- **The firm's phone number is not in the record** (decision 117). It
  belongs to the firm rather than to an engagement, and is kept beside the
  firm's name in the settings file.
- **A return's household, tax year and return name are written at creation
  and at rollover and never edited** (decision 125), so a folder somebody
  renames is still processed as the record says.
- **The record notices a rewrite that keeps the line count** (decision
  137). `engagements` keeps `applied_digest`, the running chain over exactly
  the lines applied: `d0` is empty and each line's step is the SHA-256 of the
  chain so far followed by that line's own bytes as the file holds them
  (`ledger.read_with_chain()`, from the same one read that gives the lines
  and the head). Before anything is applied - in `catch_up()`, in its
  look that takes no lock (equal counts with a
  different chain is a refusal, never "nothing to do"), in `record()` before
  it appends, and in a reader whose head moved - the chain over that many
  lines of the journal as it is now must equal the one kept, or the
  engagement is refused: *"The record for <return> was changed behind the
  tracker's back (line N onward no longer matches). Nothing was applied. Run
  recover (runbook §6)."* Recover exports the store's copy itself, and a
  conflict copy is never deleted and is named every pass. `check()` names it
  too. It never repairs itself. The line named is the first whose event the
  store holds differently; a rewrite that changed only bytes (a key
  reordered) is named from line 1. Every new journal line also carries the
  previous line's chain (`prev`), its writer and its format (decision 159),
  older lines still read, and the store's chain is computed as it replays.

## The check is the gate

`store.check()` asks what else holds the same facts and returns every
disagreement as a sentence naming the engagement, the row or identifier, the
field and both values. An empty list is the claim that the store says what
the other copy says.

There is **one** other copy, and that is the point: the journal. The
documents and the rules the edits fold to are compared with
`ledger.replay()` over it; the statuses and — since decision 113 — the
keywords filings taught are folded from the same lines by the store's case
rule (decision 136, below). Asking the readers instead would be the
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
and `_check_learned()` compares the same fold, keyed without case
(decision 136), with the table, one sentence per
request whose words differ, in the order each side holds them.

A request is one request whatever its case (decision 136). The store keys a
status and a taught word by `records.identifier_key`; `ledger.replay()` keys
them by the spelling each line carried, because the journal's module sits
below `records` and has no case rule. So for those two the check does not
use the journal's fold: it folds the same lines again, keyed without case
and in journal order (`_recorded_statuses`, `_recorded_learned`) — the last
scan of a request wins, a word taught again moves last, a word taken back
under either spelling is gone. A request the person retyped by case is one
request to the gate, as it is to the store; the index rows, the rules, the
intents and the household are compared exactly as before.

The autouse fixture in `tests/conftest.py` does exactly this after **every
test in the suite**: for every engagement folder the test left behind, build
a store in a throwaway database and assert the check says nothing. That runs
the store over every drop sorted, every parked file a person filed, every
rules edit and every journal path the suite has. It was the gate each stage
was built on.
