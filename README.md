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
over the top of them risks asking for something already in hand.

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

Generate the job itself with:

```
python -m tracker.scheduling --working-dir "C:\Tools\tax-tracker" --out tax-tracker.xml --install
```

`--root` defaults to the folder in `settings.json`; `--install` registers
the task as it writes the XML, and running the same line again changes the
schedule. The app's **Install Schedule** button does exactly this for the
folder it is showing. Every pass also re-scaffolds each engagement, so a
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
machine with neither. On first launch the app asks where your clients live
and writes that to `settings.json` beside itself; everything else follows
from that one folder. Who does what, and the life of a request, is in
[docs/workflow.md](docs/workflow.md); the decision log is
[docs/ROADMAP.md](docs/ROADMAP.md).
