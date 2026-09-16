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

No AI ever reads a client document, and originals are never altered — only
moved, byte for byte, under their own names.

Works with any cloud share that syncs to a local folder: **OneDrive and
Google Drive** are both supported — online-only placeholder files are
detected on either (and never force-downloaded), Google Drive's `.tmp.drive*`
transfer temps are ignored, and Google-native documents (`.gdoc`, `.gsheet`)
are flagged with a note asking the client for an exported PDF/Excel copy.

**Full design & build status: [docs/ROADMAP.md](docs/ROADMAP.md)**

## Two ways to demo it

| | Runs on | Needs |
|---|---|---|
| [`demo/standalone/tax-document-tracker.html`](demo/standalone/tax-document-tracker.html) | any browser, any OS, offline | nothing — double-click the file |
| `Build Portable Demo.bat` → `Tax Document Tracker.exe` | Windows 10/11 | built once on a Windows PC with Python + Node |

The standalone page is a faithful port of the scanner's rules — the same
statuses and the same validation notes the Python scanner writes — so it can
be emailed to staff or opened on a prospect's laptop with nothing installed.
The portable Windows build is the full app: it writes real folders and a real
`_manifest.xlsx` you can open in Excel.

## How it works

```
{EngagementName}/
├── _manifest.xlsx        ← accountant-owned: requests, rules, statuses
├── _index.xlsx           ← every original: where it went, what it became
├── _content_cache.json   ← verdict cache (no client text is ever stored)
├── _scan.log
├── Prepared/             ← the firm's working set (the client never sees it)
│   ├── A01 - W-2 Wage Statements - All Employers/
│   │   └── A01 - W-2 Wage Statements - All Employers - TY2025.pdf
│   └── 00 - Needs Review/   ← couldn't be identified; a person decides
└── Shared/               ← the only folder the client sees
    ├── _README.txt       ← "just drop everything here"
    └── PBC/              ← their originals: same names, same bytes
        └── scan0012.pdf
```

1. Pick the tax form type — the tailored request template lives in
   `tracker/api.py` (used by the demo app's wizard) and as plain-CSV
   checklists in [templates/](templates/)
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
   keywords/dates) and stamps each row: Missing / Partial / Failed
   Validation / Received / Pending Sync, with plain-English notes
7. Open the manifest in Excel to see where everything stands, and the index
   to see how any given file got there

Run steps 5 and 6 together on a schedule (Task Scheduler or cron).
`--dry-run` works on both and previews without writing or moving anything.
A `Manual Override` column (Accepted / Waived) lets accountant judgment
beat the rules.

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

The first thing you choose for a new engagement is the return type; every
form carries its own document checklist:

| Form | Return | Template |
|---|---|---|
| 1040 | Individual / joint | [templates/form-1040.csv](templates/form-1040.csv) |
| 1120 | C corporation | [templates/form-1120.csv](templates/form-1120.csv) |
| 1120-S | S corporation | [templates/form-1120s.csv](templates/form-1120s.csv) |
| 1065 | Partnership / multi-member LLC | [templates/form-1065.csv](templates/form-1065.csv) |
| 1041 | Estate or trust | [templates/form-1041.csv](templates/form-1041.csv) |
| 990 | Tax-exempt organization | [templates/form-990.csv](templates/form-990.csv) |

The same catalog drives the demo app: **New Engagement** opens with a
form-type picker, then shows that form's tailored request list to tick,
trim, and extend before scaffolding the client folders.

## Setup

```
pip install -r requirements.txt
python -m pytest tests/        # verify: all green
```

Optional OCR for scanned PDFs: see [requirements.txt](requirements.txt).

## Try it

`demo/` contains a working sample engagement — see
[demo/demo_manifest.py](demo/demo_manifest.py) and the CLIs above. The
Electron marketing demo (`Start Demo.bat`, presenter script in
[DEMO-SCRIPT.md](DEMO-SCRIPT.md)) walks a Form 1040 engagement end to end.
