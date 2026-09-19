# Tax Document Tracker (Income Tax Information Requests)

Deterministic tax-document request tracking for J Park & Associates, CPA —
the tax-season sibling of the
[Audit-PBC-List](https://github.com/JPClaude99/Audit-PBC-List) tracker,
built on the same workflow principles. Pick the type of return being
prepared (1040, 1120, 1120-S, 1065, 1041, 990) and get a request list
tailored to that form. **The client gets one folder and drops everything
into it** — no sorting, no naming, no matching files to a list. A scheduled
job then files what arrives: their originals are preserved untouched in
`PBC/`, renamed working copies are sorted into per-request folders on the
firm's side, an index records every rename and move, and each request's
status is validated back into the manifest.

The standing rules, worded once in `tracker/__init__.py` and upheld by every
module:

- **No generative AI ever reads a client financial document.** Every routing
  and status decision comes from deterministic rules in the manifest.
- **Originals are never altered.** Files are moved byte for byte under their
  own names into `Shared/PBC/`; all work happens on copies, and every move is
  recorded in `_index.xlsx`.
- **Nothing is guessed.** A document is filed only when exactly one request
  accepts it. Ambiguous, contested and unrecognized files go to
  `00 - Needs Review` for a person - misfiling a tax document is worse than
  not filing it.
- **Nothing is ever sent.** The system drafts client emails and stops. There
  is no SMTP, no mail client and no network call in the reminder or scheduling
  path.

Works with any cloud share that syncs to a local folder: **OneDrive and
Google Drive** are both supported — online-only placeholder files are
detected on either (and never force-downloaded), Google Drive's `.tmp.drive*`
transfer temps are ignored, and Google-native documents (`.gdoc`, `.gsheet`)
are flagged with a note asking the client for an exported PDF/Excel copy.

**Full design & build status: [docs/ROADMAP.md](docs/ROADMAP.md)**

## How it works

```
{EngagementName}/
├── _manifest.xlsx        ← accountant-owned: requests, rules, statuses
├── _index.xlsx           ← every original: where it went, what it became
├── _index.pending.json   ← only while Excel has the index open; merged next run
├── _content_cache.json   ← verdict cache (no client text is ever stored)
├── _manifest.pending.json← statuses a locked Excel kept out of the sheet, merged next write
├── Prepared/             ← the firm's working set (the client never sees it)
│   ├── A01 - W-2 Wage Statements - All Employers/
│   │   └── A01 - W-2 Wage Statements - All Employers - TY2025.pdf
│   └── 00 - Needs Review/   ← couldn't be identified; a person decides
└── Shared/               ← the only folder the client sees
    ├── _README.txt       ← "just drop everything here"
    └── PBC/              ← their originals: same names, same bytes
        └── scan0012.pdf
```

1. Roll a returning client's list forward from last year (the default), or
   pick the tax form type for a new client — the catalog lives in
   `tracker/templates.py` and nowhere else
2. List the engagement's document requests (and validation rules) in
   `_manifest.xlsx`
3. `python -m tracker.scaffold <engagement_dir>` — builds `Shared/` and
   `Prepared/`, and writes the client's README
4. Share `Shared/` with the client. They drop everything in; that's their
   whole job
5. `python -m tracker.filer <engagement_dir>` — moves each original into
   `Shared/PBC/` untouched, files a renamed copy into the matching
   `Prepared/` folder, and appends a row to `_index.xlsx`
6. `python -m tracker.scanner <engagement_dir>` — validates `Prepared/` in
   three deterministic tiers (existence → integrity → content
   keywords/dates) and stamps each row with one of the scanner's statuses
   (`Status.ALL` in `tracker/manifest.py`), with plain-English notes
7. Open the manifest in Excel to see where everything stands, and the index
   to see how any given file got there
8. `python -m tracker.reminder <engagement_dir>` — drafts the "still waiting
   on these" email from what the scanner found. **It only drafts it** — there
   is no SMTP anywhere in the module; a person reads it, edits it and sends it

Run steps 5 and 6 together on a schedule (Task Scheduler or cron).
`--dry-run` works on both and previews without writing or moving anything.
A `Manual Override` column (the values in `Override.ALL`) lets accountant
judgment beat the rules.

### Chasing what's still outstanding

```
python -m tracker.reminder "Smith Family 2025" --client "John Smith" \
    --link "https://drive.google.com/drive/folders/..." --due 2026-03-15 --write
```

The draft asks for the outstanding rows (`Status.OUTSTANDING`) and nothing
else — a received row is in, a pending-sync row is still copying down, and
an overridden row was already decided by a person. Internal validation notes
never reach the client: each one is translated into the plain instruction
`tracker/reasons.py` pairs it with, with a safe generic ask when the cause
isn't recognized.

Two things are deliberately held back from the client and reported to the
accountant instead:

- A row whose only problem is that **we** haven't read it yet (an un-OCR'd
  scan). The document may be perfect; asking a client to resend it is how a
  firm looks careless.
- A row with no request folder. We can't tell a client we never received
  something we never made a place to put — that's a scaffold problem.

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
your clients in; every folder under it holding `_manifest.xlsx` is an
engagement, and the manifest's **Engagement** sheet (written by the wizard
when you create or roll forward an engagement) says who the client is, the
share link, the due date, whether they are chased by email and whether the
engagement is still active:

| Engagement sheet | |
|---|---|
| Client | greeting name in the reminder |
| Engagement Name | label; the folder name if blank |
| Share Link | pasted into the reminder |
| Due Date | the date the reminder asks the client to send things by |
| Sender | who the reminder is from |
| Firm | the sign-off line and the client README's contact (typed once at setup) |
| Reminders | `no` = this client is not chased by email |
| Active | `no` = the scheduled run skips this folder |
| Rolled From | written by the rollover; the engagement it names is no longer chased |
| Form | which catalog the request list was cut from; blank if it was never recorded |

The app asks for that folder on first launch and writes it to
`settings.json` beside itself (`python -m tracker.settings <folder>` does the
same from a terminal). Everything else reads that one value:

```
python -m tracker.runner "D:\OneDrive\Clients" --log     # or the app's Install Schedule button
```

That single command is the whole scheduled task. Per engagement it files the
drop folder, scans it, and **on Saturdays** drafts the chase email. Creating
an engagement in the app is all it takes for the next run to include it —
`python -m tracker.registry "D:\OneDrive\Clients"` lists what the run would
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
python -m tracker.scheduling --working-dir "C:\Tools\tax-tracker" --out tax-tracker.xml --install
```

`--root` defaults to the folder in `settings.json`; `--install` registers
the task as it writes the XML, and running the same line again changes the
schedule. The app's **Install Schedule** button does exactly this for the
folder it is showing - from source with the Python it runs under, and in
the packaged app with its own executable, which runs the job when given
`--run` first (there is no Python on that machine). Every pass also re-scaffolds each engagement, so a
row added in Excel has its folder and its README line by the next run, and
an engagement that has been rolled forward is retired by its successor
without anyone opening last year's manifest.

One machine per clients root: the per-engagement lock (`tracker/locking.py`)
that keeps a scheduled pass and a click in the app from working the same
folder at once is a file, and a file a cloud client syncs between two
machines is not a lock. Schedule the job, and press Scan, on one machine.

One daily task is enough: the **runner** decides whether today is a drafting
day, not the scheduler. So a Saturday the machine spent switched off still
drafts on the next run instead of skipping the week, and the repeat interval
(`tracker.scheduling.DEFAULT_REPEAT_MINUTES`, or `--every`) keeps filing and
scanning running through the day without touching that.

**Reminders are weekly, on Saturday, and always just drafts.** The run writes
`reminder-draft.txt` into the engagement folder; a person opens it, edits it
and sends it. Nothing in the scheduled path sends email.

How a season is actually run on the firm's one machine — the morning pass,
the draft day, what the index's reasons mean, and what to do if that machine
dies — is [docs/runbook.md](docs/runbook.md).

`automation.manifest.json` registers the tracker with the firm's Command
Center, so a preview pass, a real pass, the engagement list and the learned
keywords are all a button there, on demand, under the dated exception the
Center's contract requires of anything that schedules itself. The schedule
itself is not moved there and never will be: it stays a Windows Task
Scheduler entry on the designated machine, and the Command Center runs
nothing on a timer.

The schedule is a default, not a cage:

| | |
|---|---|
| draft for one client, any day | `python -m tracker.reminder <engagement_dir> --write` |
| draft the whole batch today | `python -m tracker.runner "D:\OneDrive\Clients" --reminders always` |
| file and scan, no drafts | `python -m tracker.runner "D:\OneDrive\Clients" --reminders never` |
| just one client | `python -m tracker.runner "D:\OneDrive\Clients" --only smith` |
| see what would happen | `python -m tracker.runner "D:\OneDrive\Clients" --dry-run` |
| move the drafting day | `python -m tracker.runner "D:\OneDrive\Clients" --weekday monday` |

`Reminders: no` on an engagement's sheet is a standing decision that this
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
- `Waived` carries forward (it is a decision about the client). `Accepted`
  does not — that was a judgment about one year's particular files.
- Checklist rows this client has never had are **offered, not added**. They
  are listed in the output and on the manifest's `Carried Forward` sheet;
  `--include-new` adds them.
- Documents that arrived last year and matched no request are surfaced too —
  exactly the gap next year's list should close.

The new manifest carries a `Carried Forward` sheet explaining why every row
is there. The prior engagement is opened read-only and never modified.

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
and no OCR on this machine, an image-only PDF, an empty sheet — parks for
a person with `tracker.reasons.NO_READABLE_TEXT`, which is a different
answer from "matched no request" (there the words *were* read and nothing
asked for them). What the name says is kept and handed over: the parked
file's shortlist offers the request its name points at, at the weakest
rank there is, beside a document the person then opens. The cost is
known — until Tesseract is installed, every scanned PDF parks.

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
keyword, and it is learned by that one engagement's manifest and nowhere
else; `python tools/learned_keywords.py` lists every keyword taught that way
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
the only place it lives. The wizard shows it to tick, trim and extend, for
the tax year the calendar says, and the manifest it creates is the readable
copy.

## Setup

```
pip install -r requirements.txt
python -m pytest -q        # verify: all green
```

Optional OCR for scanned PDFs: see [requirements.txt](requirements.txt).

## Running the app

`Start App.bat` runs the desktop app from source (Python (the floor is `requires-python` in `pyproject.toml`) and Node
installed); `Build App.bat` packages it as `<productName>.exe` (the name in `app/package.json`) for a
machine with neither. Both are reproducible from the commit: the Python
packages are pinned in `requirements.txt` and `requirements-build.txt`, the
Electron packages in `app/package-lock.json` (installed with `npm ci`), and
the freeze is the committed `api_entry.spec`; a build-info text file in the
package records the commit and the tool versions that made it. You do not have
to run the build yourself: `build.yml` builds the same package on demand (the
Actions tab, *Run workflow*, or a `v*` tag), runs the frozen executable to
prove it answers, and leaves the package to download as the run's artifact for
seven days. It builds and tests on the interpreter `[tool.office]` in
`pyproject.toml` names — the one the firm's machine runs — so the package is
proved on the interpreter it ships under. On first launch the app asks where your clients live
and writes that to `settings.json` beside itself; everything else follows
from that one folder. Who does what, and the life of a request, is in
[docs/workflow.md](docs/workflow.md); the decision log is
[docs/ROADMAP.md](docs/ROADMAP.md).
