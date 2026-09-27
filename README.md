# Tax Document Tracker (Income Tax Information Requests)

Deterministic tax-document request tracking for J Park & Associates, CPA —
the tax-season sibling of the
[Audit-PBC-List](https://github.com/JPClaude99/Audit-PBC-List) tracker,
built on the same workflow principles. Pick the type of return being
prepared (1040, 1120, 1120-S, 1065, 1041, 990) and get a request list
tailored to that form. **The client gets one folder and drops everything
into it** — no sorting, no naming, no matching files to a list. A scheduled
job then files what arrives: their originals are preserved untouched in
the client's folder for the year, renamed working copies sit side by side
in one folder on the firm's side, each named by its request, and the return's own record holds
every rename, every move and each request's validated status.

A client folder is a **household**, with one folder per **tax year** inside
it and one folder per **return** inside that (decision 125). Two trees sit
under the clients root: `Clients`, the only one a client is ever shared,
and `J Park & Associates`, which never is.

The standing rules, worded once in `tracker/__init__.py` and upheld by every
module:

- **No generative AI ever reads a client financial document.** Every routing
  and status decision comes from deterministic rules in the manifest.
- **Originals are never altered.** Files are moved byte for byte under their own names out of `Drop files here` into the client's folder for the year; all work happens on copies, and every move is
  recorded in the record.
- **Nothing is guessed.** A document is filed only when exactly one request
  accepts it - or, when one document names several forms as itself, when each
  of those forms is accepted by exactly one request, or, when a broker's
  consolidated statement is accepted by several requests, when exactly one of
  them accepts it for its 1099-B, which then holds the whole statement.
  Ambiguous, contested and unrecognized files go to `00 - Needs Review` for a
  person - misfiling a tax document is worse than not filing it.
- **Nothing is ever sent.** The system drafts client emails and stops. There
  is no SMTP, no mail client and no network call in the reminder or scheduling
  path.

Works with **Google Drive for desktop syncing a Shared Drive**, and nothing
else. The rules above hold because of how that Shared Drive is shared: the
firm owns every file in it, the client is a Viewer on their year folders and
a Contributor on their inbox ([docs/runbook.md](docs/runbook.md) §1,
*Sharing a household with a client*). **OneDrive is not supported**: that
sharing model is Google Drive's, and nothing here has been checked against
any other. Online-only placeholder files are detected (and never
force-downloaded), Google Drive's `.tmp.drive*` transfer temps are ignored,
and Google-native documents (`.gdoc`, `.gsheet`) are flagged with a note
asking the client for an exported PDF/Excel copy.

**Full design & build status: [docs/ROADMAP.md](docs/ROADMAP.md)**

## How it works

```
{ClientsRoot}/
├── Clients/                      ← the only tree a client is ever shared
│   └── Park Family/              ← the household, shared as Viewer
│       ├── Drop files here/      ← the inbox, shared as Contributor
│       │   └── _README.txt       ← "just drop everything here"
│       └── 2026/                 ← their originals for the year: same names, same bytes
│           └── scan0012.pdf
└── J Park & Associates/          ← never shared
    └── Park Family/              ← the household's record
        └── 2026/
            └── 1040 - John & Maria Park/    ← the return
                ├── _ledger.jsonl            ← the return's record: the request list, every original, every status, every rules edit
                ├── Status Report.html       ← this return on one page, redrawn by every pass
                └── Prepared/                ← the firm's working set (the client never sees it)
                    ├── 00 - Needs Review/   ← couldn't be identified; a person decides
                    ├── A01 - W-2 - TY2025.pdf        ← named by its request (decisions 144, 168)
                    └── A02 - 1099-INT-DIV - TY2025.pdf
```

**One inbox per household.** A household with a business and its owner's
1040 has one folder to drop into, and a pass judges each drop against every
return of the open year: it is filed where exactly one accepts it, and
parked for a person where several or none do. **The engagement is the
software's word for one return in one year** - the return folder is the
engagement folder.

**The request list and the engagement's details are in the record.** The
fourteen columns an accountant edits, and the client, link, due date, the
people the return is for and the rest, are edited in the app's **Edit Request List** editor and nowhere
else; every save is journalled as one event and folded into one database
in the tracker's data folder on the machine that runs the schedule ([docs/storage.md](docs/storage.md)),
beside each request's Status, Received Date, File Count and Validation
Notes and every original's index row. Nothing in the folder is a
spreadsheet, and the machine reads and writes no workbook.

**Every index row says what became of one original**, and there are six
answers: `Filed`, `Needs Review`, `Duplicate`, `Not Requested` — a
document a person said no request asks for — `File Moved`, which is
what a pass says when a working copy is not in the folder the record filed
it into and its bytes turn up somewhere else under `Prepared/`, and
`Opened`, an email or a zip whose attachments were taken out. Each pass
proves every working copy against the fingerprint its own row carries, so
a copy somebody dragged is identified and said rather than counted under
whatever request it now sits in; nothing is moved over it and a person
decides. `docs/runbook.md` §4 is what each answer means in plain words.

**An email or a zip is opened** (decision 143). A client who forwards an
email (`.msg`, `.eml`) or a zip with the documents attached is not asked to
send them again: the pass moves the container into their folder for the
year like any original, untouched, and records it `Opened`; each attachment
is taken out into a hidden `_Opened` folder beside the year's returns in
the private tree - never the client's - and sorted as a document of its
own, its row naming the container it came in. Nothing inside is ever run;
inline pictures and the message's own text are left inside and named on
the container's record line. A locked, damaged or empty container, or one
past a limit (nested more than two deep, more than 200 attachments, more
than 250 MB unpacked, a file that unpacks past 100 times its packed size),
parks for a person with the reason, and a document that came inside one is
never filed into another household's return. The client README's list of
what has arrived shows each attachment that filed, under its request.

1. Roll a returning client's list forward from last year (the default), or
   pick the tax form type for a new client — the catalog lives in
   `tracker/templates.py` and nowhere else. A new household's name is
   unique across both trees by how it reads, not how it is spelled: the
   wizard refuses a name that reads as a household already in the list and
   points at it there - add a first name or a middle initial, then the
   city, to tell two households apart (decision 188)
2. List the engagement's document requests (and validation rules) in the
   app's request-list editor
3. `python -m tracker.scaffold <return_dir>` — builds the household's
   inbox and the year's folder, and this return's `Prepared/` with its
   review folder - no folder per request: the working copies sit in
   `Prepared/` itself, named by their request (decision 168). Folders
   only: the client's README is written by the pass and by the app,
   decision 130
4. Share the household's folder with the client as Viewer and its inbox as
   Contributor, paste the inbox's link into the household and mark it
   shared — the app asks for all three, once, and `docs/runbook.md` §1
   "Sharing a household with a client" is the whole of it. They drop
   everything in; that's their whole job
5. `python -m tracker.filer <return_dir>` — moves each original out of the
   inbox into the client's folder for the year, untouched, files a renamed
   copy into the matching `Prepared/` folder, and records what it did in
   the return's record
6. `python -m tracker.scanner <engagement_dir>` — validates `Prepared/` in
   three deterministic tiers (existence → integrity → content
   keywords/dates) and records each row's status (`Status.ALL` in
   `tracker/manifest.py`) with plain-English notes
7. Open the Status Report (double-click it; it is a web page) to see where
   everything stands and how any given file got there. The list is edited
   in the app, not for reading the answers
8. `python -m tracker.reminder <engagement_dir>` — drafts the "still waiting
   on these" email from what the scanner found. **It only drafts it** — there
   is no SMTP anywhere in the module; a person reads it, edits it and sends it

Run steps 5 and 6 together on a schedule (Task Scheduler or cron).
`--dry-run` works on both and previews without writing or moving anything.
A `Manual Override` column (the values in `Override.ALL`) lets accountant
judgment beat the rules: `Accepted` counts the row as Received and carries
an `Override Reason` (picked from a list, or typed), `Not Applicable` takes
the request out of every count for the year, shown as "Not Applicable in
TY<year>" and kept in a folded section of the Status Report.

### Chasing what's still outstanding

```
python -m tracker.reminder "Smith Family 2025" --client "John Smith" \
    --link "https://drive.google.com/drive/folders/..." --due 2026-03-15 --write
```

The draft asks for the outstanding rows (`Status.OUTSTANDING`) and nothing
else — a received row is in, a pending-sync row is still copying down, and
an overridden row was already decided by a person. Internal validation notes
never reach the client: each one is translated into the plain instruction
`tracker/reasons.py` pairs it with.

**The letter escalates in four stages** (decision 117), measured against the
Due Date — the date the firm asks the client to send things by. More than
three weeks out it is a heads-up with no deadline sentence at all; inside
three weeks a check-in that names the target; in the last ten days a firm
request that names the target and the Filing Deadline beside it; on the day
and after it a final notice with the consequences sentence and the firm's
phone number. The stage changes the words and nothing else: who is asked is
the same at every stage, and every hold below holds at every stage. The
stage is named in the draft's header, above the fingerprint line and so
outside the text you paste, and recorded in the `drafted` event; `--stage`
writes the same rows at another stage and `--today` at another day. Both
dates are the engagement's details, editable and clearable, and the
sentences name the dates and never the arithmetic between them.

One thing is deliberately held back from the client and reported to the
accountant instead:

- A row whose only problem is that **we** haven't read it yet (an un-OCR'd
  scan), or whose working copy somebody here moved. The document may be
  perfect; asking a client to resend it is how a firm looks careless. (A
  row nobody asked for is never chased at all — decision 142. Until
  decision 168 a row with no request folder was held back as well; no
  request has a folder any more, so a request with nothing in is simply
  Missing.)

And one thing **holds the whole reminder** for a person (decision 115): a
row whose file arrived and failed the rules with no firm-side reason. A copy
the router filed cannot fail its own rules, so that row is a rule edited
after filing, a copy dragged in by hand or a copy replaced — the firm's
doing, or the client's, and not the draft's to guess. Nothing is written for
that client until somebody decides; the run's own earlier draft is removed,
an edited one is left, and the practice page and the app name the rows; the
run log counts the hold. The manual draft is held by the same question. So does a file the
client sent that the rules could not use at all — a locked PDF, an empty
upload, a file type nothing accepts — when what it looks like is a request
still outstanding (decision 117): the drop parks for a person and never
reaches a status, so the draft would otherwise ask for a document the client
knows they sent. A parked file that looks like nothing holds nothing, and
one nobody here could read is ours. Every draft that is written is one
`drafted` event on the engagement's record — what it asked for, which stage
and which file — and a regenerated draft opens with what changed since the
last one, above the line a person pastes.

And if files are still sitting in `00 - Needs Review`, the CLI says so before
you send: those are documents the client *has* already sent, so a reminder
over the top of them risks asking for something already in hand. A file a
person has marked `NOT_REQUESTED` — an agency notice, an extra statement no
row asks for — is not counted. Its copy stays where it is and nothing is
deleted; what stops is the warning, which is there for documents nobody has
decided about. One that stood for the rest of the engagement would be the
warning people learn to send past.

### Running it unattended

There is nothing to register. Point the scheduled job at the folder you keep
your clients in; every folder under it holding `_ledger.jsonl` is an
engagement, and the engagement's details (written by the wizard when you
create or roll forward an engagement, edited in the app) say who the client
is, the share link, the two dates, whether they are chased by email and
whether the engagement is still active:

| Engagement details | |
|---|---|
| Client | greeting name in the reminder |
| Engagement Name | label; the folder name if blank |
| Share Link | pasted into the reminder |
| Due Date | the date the reminder asks the client to send things by |
| Filing Deadline | the statutory filing date; named in the reminder from the third stage on; blank = not mentioned (defaults from the form, weekends shifted; holidays are yours to edit) |
| Sender | who the reminder is from |
| Firm | the sign-off line and the client README's contact (typed once at setup) |
| Reminders | `no` = this client is not chased by email |
| Active | `no` = the scheduled run skips this folder |
| Rolled From | written by the rollover; the engagement it names is no longer chased |
| Form | which catalog the request list was cut from; blank if it was never recorded |
| Household | the household this return belongs to; the folder above the year |
| Tax Year | the year the return is for; the year folder's name |
| Return | the return's folder name, form first; the same name every year |
| People | who this return is for, with the spellings documents use; a named request files only where one of these is on the page |

The app asks for that folder on first launch and writes it to
`settings.json` beside itself (`python -m tracker.settings <folder>` does the
same from a terminal). Two things about the firm rather than about a client
are kept there beside it: the firm's name, which signs the reminders, and
the firm's phone number, which only the final-notice stage says and which
is left out of the letter entirely when it is blank. Everything else reads
that one value:

```
python -m tracker.runner "G:\Shared drives\Clients"     # one pass, by hand, over the folder named
```

That single command is a whole pass. Per engagement it files the
drop folder, scans it, and **on Saturdays** drafts the chase email. The
scheduled task runs the same pass but names no clients root (decision 131):
it names the app's settings folder, and the runner reads the root from
`settings.json` there at every run, so the root has one home and changing
it in the app is all a move takes:

```
python -m tracker.runner --settings "C:\Tools\tax-tracker" --log     # what the scheduled job runs
```

`--log` alone appends the pass's counts and codes — never a client's name — to `runs.log` in the
tracker's data folder, rotated at 256 KB with three older files kept; `--log <file>` names
another, by its whole path - a person's explicit choice, written where it is named, so name a
place in the data folder. A pass that cannot have its data folder files nothing, writes the
status page with that one problem, and exits non-zero.

A root on the command line together with `--log` is the shape of the job
installed before decision 131, and it is refused - red, naming *Install
Schedule* - unless that root is the settings file's own, so an old job
never goes on sorting a tree the app has moved away from. A person's
hand-run, without `--log`, is never refused.

Creating an engagement in the app is all it takes for the next run to include it —
`python -m tracker.registry "G:\Shared drives\Clients"` lists what the run would
find and flags any manifest it cannot read.

Every real pass also writes `tracker.runner.STATUS_PAGE_FILENAME` into that
same clients folder: the whole practice on one page — every engagement with
what it still owes and what is still syncing, every file waiting for a person
across all of them (newest first, with the reason it was parked), and
everything that errored. It is one self-contained file that opens in any
browser with nothing installed and nothing fetched; the app's **Open Status**
button opens that same page, and the app's own pass rewrites it too.

Generate the job itself with:

```
.venv\Scripts\python.exe -m tracker.scheduling --working-dir "C:\Tools\tax-tracker" --install
```

Run it with the app's private Python, the one `Setup.bat` made (decision
191): the job runs whichever interpreter registered it, and the machine's
own Python holds none of the locked packages. `--settings` defaults to this checkout's own folder, whose `settings.json`
must already name a clients root; the job carries no root of its own.
`--install` registers the task as it writes the XML, and running the same
line again changes the schedule. It writes the task's file into the tracker's data folder unless
`--out` names another (a person's explicit choice, written where it is named), and refuses when the program is on a removable or network drive (decision
186). The app's **Install Schedule** button does exactly this for the
folder it is showing - from source with the Python it runs under, and in
the packaged app with its own executable, which runs the job when given
`--run` first (there is no Python on that machine). A job registered by a
version before decision 131 still carries the root it was installed with:
press **Install Schedule** once after upgrading, and never again for a
move. Every pass also re-scaffolds each engagement, so a
deleted inbox or review folder is back by the next run, and rewrites the
household's README once, after the sort (decision 130), and
an engagement that has been rolled forward is retired by its successor
without anyone opening last year's engagement.

One machine per clients root, today: the per-engagement lock
(`tracker/locking.py`) that keeps a scheduled pass and a click in the app
from working the same folder at once is a file, and a file a cloud client
syncs between two machines is not a lock. What runs on the designated
machine, and what another desk may do, is stated once, in
[docs/runbook.md](docs/runbook.md) §1, while the owner decides how several
machines may write.

One daily task is enough: the **runner** decides whether today is a drafting
day, not the scheduler. So a Saturday the machine spent switched off still
drafts on the next run instead of skipping the week, and the repeat interval
(`tracker.scheduling.DEFAULT_REPEAT_MINUTES`, or `--every`) keeps filing and
scanning running through the day without touching that.

**Reminders are weekly, on Saturday, and always just drafts.** The run writes
`reminder-draft.txt` into the engagement folder; a person opens it, edits it
and sends it. Nothing in the scheduled path sends email — and
`tests/test_layers.py` pins that no module under `tracker/` imports a mail
or network module.

The app's **Reminder** card is where that draft is read (decision 118): the
record's last word on it, the four stages as a toggle that rewrites the
letter on screen without touching the file, the letter itself in the firm's
own colours, **Copy for Outlook** (the body as HTML beside the same words as
plain text), **Approve** — which makes what is on screen this week's draft,
records it, and has the pass leave it alone for the rest of the week the way
it leaves one you edited — and **Open the draft file**. There is no send
button on it, and a held reminder shows the hold and nothing else.

How a season is actually run on the firm's one machine — the morning pass,
the draft day, what the index's reasons mean, and what to do if that machine
dies — is [docs/runbook.md](docs/runbook.md).

The schedule is a Windows Task Scheduler entry on the designated machine,
and it is a default, not a cage:

| | |
|---|---|
| draft for one client, any day | `python -m tracker.reminder <engagement_dir> --write` |
| draft the whole batch today | `python -m tracker.runner "G:\Shared drives\Clients" --reminders always` |
| file and scan, no drafts | `python -m tracker.runner "G:\Shared drives\Clients" --reminders never` |
| just one client | `python -m tracker.runner "G:\Shared drives\Clients" --only smith` |
| see what would happen | `python -m tracker.runner "G:\Shared drives\Clients" --dry-run` |
| move the drafting day | `python -m tracker.runner "G:\Shared drives\Clients" --weekday monday` |

These are a person's lines, so they name the folder they run over; left
out, the root is read from `settings.json`. The scheduled job names no
root at all (decision 131) - it names the settings folder, as above.

`Reminders: no` in an engagement's details is a standing decision that this
client isn't chased by email — neither the schedule nor `--reminders always`
overrides it, though the per-engagement CLI above still drafts one on demand.

### Returning clients: last year is the starting point

A client who filed with us last year is not a blank form, so their next
engagement is built from their own prior year rather than the generic
checklist:

```
python -m tracker.rollover "Smith Family 2025" "Smith Family 2026" --form 1040 --scaffold
```

Prior-year data takes precedence over the template, absolutely:

- Every field last year specifies is carried forward untouched — document
  names, keywords, extensions, custom rows the accountant added by hand. The
  template may only **fill a blank**, which overrides nothing.
- Periods, date rules and years inside document names all shift together, so
  `TY2025` becomes `TY2026` **and** the row that asked for the TY2024
  prior-year return now asks for the TY2025 one.
- Counts learn from what actually arrived: expected 2 W-2s, received 3 → ask
  for 3. Counts never shrink, so a client who under-delivered still owes what
  was asked.
- `Not Applicable` carries forward (it is a decision about the client), under
  its own "Previous Year Not Applicable" heading for a fresh decision: clear
  the override in the editor to ask for it this year, or leave it set aside.
  `Accepted` does not — that was a judgment about one year's particular files.
- Whether a row is **asked** carries, and so does whether it is **named**.
  A row nobody asked for that received a document this year is asked next
  year: the client sent one, so asking is the likelier need (untick Asked
  in the editor if not).
- Checklist rows this client has never had are **added as not asked**
  (decision 142): on the return, never listed as needed and never chased,
  but a document that arrives for one files there instead of parking. Set
  Asked in the app's editor to ask for one.
- Documents that arrived last year and matched no request are surfaced too —
  exactly the gap next year's list should close.

The prior engagement is opened read-only and never modified.

### How files get matched

Routing is deterministic and refuses to guess. A document is filed only
when exactly one request accepts it, judged on the manifest's own keyword
and period rules — the strongest evidence being a row's *required*
keywords ("a W-2 says W-2"). A matching file extension is never enough on
its own, and a file that matches one row's required keywords but fails that
row's other rules — last year's W-2, say — is **not** filed anywhere else.
Everything unclear lands in `00 - Needs Review` with the reason recorded in
the index, because misfiling a tax document is worse than not filing it.

A keyword is the document's own title, or a phrase only it carries — never
a word another form prints about it. Its words sit on one line, or wrap as
a heading does: two words or more from the start of a line, the rest on
the next. A keyword that is a form's
number counts in a document's text only where a form prints its own: in
the title, or as the number the document names most often — and only a
form *naming itself* counts, "Form 1040 (2025)" or "Form 1099-DIV (Rev.
January 2024)", never a form quoted in a sentence, "(Form 1040)", "attach
Form 1098", "Forms W-2", "such as Form 1099-NEC". A request whose Period
names a month (`Dec 2025`) also checks that the document prints that
month.

A scan with no text layer is read by OCR (if OCR is installed), the same
reading the scanner makes later — and OCR text routes a file only on a
request's *required* keywords; a looser match on OCR text goes to review
with the lead noted, because a misread word is how a document lands under
the wrong request.

**A file name never files anything.** The client chose that name; the form
did not. So a document nobody here can read — a scan with no text layer
the reader could not read, an image-only PDF, an empty sheet — parks for
a person with `tracker.reasons.NO_READABLE_TEXT`, which is a different
answer from "matched no request" (there the words *were* read and nothing
asked for them). What the name says is kept and handed over: the parked
file's shortlist offers the request its name points at, at the weakest
rank there is, beside a document the person then opens. The cost is
known — a scan the reader cannot read parks.

**One request can be split by who issued the document.** A person holds
Schedule K-1s from several partnerships, and one folder with all of them in
it is a folder nobody can work from. So a request list may carry one K-1 row
per issuing entity: an ordinary row, named `Schedule K-1 - Ashford Holdings
LP`, with the entity's name in **Required Keywords** and the K-1 row's own
Any Keywords. Nothing is added to the schema and no rule was needed to make
it win — a required keyword is the strongest evidence there is and the
generic K-1 row has none — so the K-1 that prints its issuer's name files on
that issuer's row, and the federal and the California K-1 from one entity
land together. What did need a rule is the K-1 whose issuer nobody listed:
with issuer rows present it parks (`tracker.reasons.ISSUER_NOT_NAMED`) with
those rows named, rather than joining everybody else's on the generic row or
being guessed onto whichever row is left over. `docs/runbook.md` §8 is how a
person adds one.

When a person files something out of `00 - Needs Review` they can type a
keyword, and it is recorded against that one engagement's request and
nowhere else — every reader lays it over the row's own Any Keywords, the
editor shows it beside the row as taught, and the rollover carries it into
next year's list as an ordinary one;
`python tools/learned_keywords.py` lists every keyword taught that way
across all your engagements, grouped by request, so the ones several clients
needed become catalog rows the test suite then defends.

#### What the routing is measured against

Blank IRS forms and reconstructed cases are paperwork nobody sent. The
firm's own documents are the measure: years of them, already sorted by
hand, sitting on the office file server. `tools/backtest.py` routes them
there against the shipped catalogs and scores how often the router lands
where the person did, with the confusions, the share still parked for a
person, and the time a real pass takes. That agreement is recorded in
`docs/backtest-baseline.json`, and no routing change may lower it. Every
document is routed under one neutral name, so the client's own file naming
never reaches the router with the document and the score is the rules' and
not the firm's filing habits'. Nothing identifying comes back: the report
carries counts, request identifiers and row numbers, never a file name, a
folder name or a word of a document — and the documents never leave the
office.

## Form-type templates

For a returning client the request list is last year's, rolled forward
(the desktop wizard's first page, or `python -m tracker.rollover`). For a
new client you choose the return type (1040, 1120, 1120-S, 1065, 1041, 990)
and every form carries its own checklist in `tracker/templates.py`,
the only place it lives. Every row of it goes on the return (decision 142);
the wizard's tick is **Ask the client**: a ticked row is asked for and
chased, an unticked one is never asked for but files a document that
arrives for it. Add custom rows (always asked) as needed. It is cut for the
tax year the calendar says, and the manifest it creates is the readable
copy.

## Setup

On the office's Windows machine, double-click `Setup.bat` once (it needs
the internet): it makes the app's own private Python in `.venv` beside it,
installs the locked packages into it, installs Electron with `npm ci`, and
never touches the machine's own Python. By hand, in an environment of your
own:

```
pip install --require-hashes -r requirements.lock
pip install --require-hashes --no-deps -r requirements-nodeps.lock
python -m pytest -q        # verify: all green
```

Every install reads a lock file and checks every file's SHA-256 (decision
191): `requirements.lock` is the whole tree of `requirements.txt`, with the
hash of every file PyPI publishes for each pinned version, so a file
replaced at a pinned version is refused, and so is any package the lock
does not name. The `requirements*.txt` files stay the human-edited list of
direct pins; to move one, change it there and in its `.lock`, run
`python tools/lockfiles.py hash` (it needs the internet) and the suite.

Two steps, in that order (decision 169): the reader, RapidOCR, is
installed without its dependencies, because its package asks for the
desktop build of OpenCV and the tracker uses the headless one;
`requirements.lock` holds what it really needs. Nothing else is installed
for reading - the models ship in the package, and nothing is downloaded
while it reads. On Windows it reads on the processor, or on an NVIDIA card
with the graphics card pack beside the packaged app (`Build GPU Pack.bat`;
[docs/runbook.md](docs/runbook.md) §6, step 5).

The suite never reads this checkout's settings file, store, scratch folder or a
client tree copied into it: every test gets a settings folder and a store of its
own, and a tripwire fails the whole run if any test, or any Python process a
test starts, reaches one of them (decision 185).

## Running the app

`Start App.bat` runs the desktop app from source (Python (the floor is `requires-python` in `pyproject.toml`) and Node
installed, and `Setup.bat` run once); it installs nothing and starts
offline, and says in one sentence when `Setup.bat` must run again because
the lock files changed. `Build App.bat` packages it as `<productName>.exe` (the name in `app/package.json`) for a
machine with neither. Both are reproducible from the commit: the Python
packages are locked by hash in `requirements.lock` and
`requirements-build.lock`, the
Electron packages in `app/package-lock.json` (installed with `npm ci`), and
the freeze is the committed `api_entry.spec`; a build-info text file in the
package records the commit and the tool versions that made it. You do not have
to run the build yourself: `build.yml` builds the same package from a `v*`
tag and from nothing else (tags are protected, so a package is the build of
reviewed code), runs the frozen executable to
prove it answers, and leaves the package to download as the run's artifact for
seven days - one zip beside its SHA-256, which the run's summary page shows
too. It builds and tests on the interpreter `[tool.office]` in
`pyproject.toml` names — the one the firm's machine runs — so the package is
proved on the interpreter it ships under. A weekly workflow (`audit.yml`)
reads the locks and asks OSV about every locked package; it builds and
installs nothing. On first launch the app asks where your clients live
and writes that to `settings.json` beside itself; everything else follows
from that one folder. Who does what, and the life of a request, is in
[docs/workflow.md](docs/workflow.md); the decision log is
[docs/ROADMAP.md](docs/ROADMAP.md).
