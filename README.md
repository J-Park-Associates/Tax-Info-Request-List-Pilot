# Tax Document Tracker (Income Tax Information Requests)

Deterministic tax-document request tracking for J Park & Associates, CPA —
the tax-season sibling of the
[Audit-PBC-List](https://github.com/JPClaude99/Audit-PBC-List) tracker,
built on the same workflow principles. Pick the type of return being
prepared (1040, 1120, 1120-S, 1065, 1041, 990) and get a request list
tailored to that form. The tracker scaffolds a per-engagement folder tree
from an Excel manifest, lets clients drag documents into shared folders,
and a scheduled scanner validates each file against manifest-defined rules
and writes status back into the manifest — no AI touches client documents,
no file is ever moved, renamed, or deleted.

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
├── _content_cache.json   ← verdict cache (no client text is ever stored)
├── _scan.log
└── Shared/               ← the only folder the client sees
    ├── _README.txt       ← auto-generated client instructions
    ├── A01 - W-2 Wage Statements - All Employers/
    └── ...
```

1. Pick the tax form type — the tailored request template lives in
   `tracker/api.py` (used by the demo app's wizard) and as plain-CSV
   checklists in [templates/](templates/)
2. List the engagement's document requests (and validation rules) in
   `_manifest.xlsx`
3. `python -m tracker.scaffold <engagement_dir>` — builds `Shared/`
4. Client drags files into the folders
5. `python -m tracker.scanner <engagement_dir>` — validates in three
   deterministic tiers (existence → integrity → content keywords/dates) and
   stamps each row: Missing / Partial / Failed Validation / Received /
   Pending Sync, with plain-English notes
6. Open the manifest in Excel to see where everything stands

`--dry-run` on the scanner previews without writing. A `Manual Override`
column (Accepted / Waived) lets accountant judgment beat the rules.

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
