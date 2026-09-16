# Tax Document Tracker — Build Plan (v1.2)

A Windows-compatible system for income tax information requests: each engagement
starts by picking the return type (1040, 1120, 1120-S, 1065, 1041, 990), which
selects a tailored document request template (`FORM_TEMPLATES` in `tracker/api.py`;
CSV checklists in `templates/`). The system then scaffolds a cloud-synced folder
structure (OneDrive or Google Drive) from an Excel manifest, gives the client **one
folder** to drop everything into, then sorts what arrives: originals are preserved in
`Shared/PBC/`, renamed working copies are filed into `Prepared/{Identifier} - {Document}/`,
every move is written to `_index.xlsx`, and each request's status is validated back
into the manifest.

## Hard Constraints

- **No generative AI touches client financial documents.** Every routing and status
  decision comes from deterministic rules in the manifest.
- **Originals are never altered.** The filer *moves* each dropped file into
  `Shared/PBC/` under its own name, byte for byte, and works from a copy. Nothing is
  renamed in place, edited, or deleted, and every move and rename is recorded in
  `_index.xlsx`. The scanner never touches `Shared/` at all.
- **Nothing is guessed.** A document is filed only when exactly one request accepts
  it. Ambiguous, contested and unrecognized files go to `Prepared/00 - Needs Review/`
  for a person — misfiling a tax document is worse than not filing it.
- Python 3.11+, `pathlib.Path` throughout.
- Atomic, incremental development: one complete, verified component at a time.
- All manifest write-backs go through `openpyxl`, preserving existing content
  (write with a non-`data_only` load so formulas survive; keep the manifest free of
  charts/VBA, which openpyxl drops on re-save).

## Decision Log (2026-07-08)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Manifest placement | **Outside shared scope.** Client's edit link points at `Shared/`; `_manifest.xlsx` sits one level up, invisible to the client. |
| 2 | Manual Override column | **Yes.** `Accepted` / `Waived`; scanner never overwrites status on overridden rows. |
| 3 | Received-then-changed | **Auto-revert.** Status always reflects the current scan; original Received Date preserved with a regression note. |

## Decision Log (2026-09-16)

| # | Decision | Choice |
|---|----------|--------|
| 4 | Client-facing structure | **One folder.** The client drops everything into `Shared/`; they never sort, name or match anything. |
| 5 | Where originals live | **`Shared/PBC/`.** Moved out of the drop zone, name and bytes untouched, still visible to the client. |
| 6 | Where working copies live | **Firm side only (`Prepared/`).** The client never sees the organized tree, so they cannot edit it. |
| 7 | Unidentifiable files | **`00 - Needs Review`, never a guess.** Extension alone does not route; a contested document blocks its own filing. |
| 8 | Rename convention | **`{Identifier} - {Document} - {Period}.ext`**, with `(2)`, `(3)`… for rows expecting several files. |

## Architecture

```
OneDrive / Google Drive (synced locally on Windows)
└── Clients/
    └── {ClientName}/
        └── {EngagementName}/
            ├── _manifest.xlsx        ← accountant-only (NOT in the shared scope)
            ├── _index.xlsx           ← every original: where it went, what it became
            ├── _manifest.pending.json← sidecar written only if Excel had the file locked
            ├── scan.log              ← rotating log
            ├── Prepared/             ← firm-side working set (NOT shared)
            │   ├── A01 - W-2 Wage Statements - All Employers/
            │   │   └── A01 - W-2 Wage Statements - All Employers - TY2025.pdf
            │   ├── A02 - 1099-INT - 1099-DIV - Interest & Dividend Income/
            │   └── 00 - Needs Review/  ← could not be identified; a person decides
            └── Shared/               ← client's edit-rights link points HERE
                ├── _README.txt       ← "just drop everything here" (auto-generated)
                ├── (client drops land here, briefly)
                └── PBC/              ← their originals, untouched, still visible
                    ├── scan0012.pdf
                    └── W-2 John Smith 2025.pdf
```

Two jobs run against the local synced path on a schedule (Windows Task Scheduler or
n8n cron), in order:

1. `python -m tracker.filer <engagement_dir>` — sort the drop folder: preserve each
   original in `PBC/`, file a renamed copy into `Prepared/`, append to `_index.xlsx`.
2. `python -m tracker.scanner <engagement_dir>` — validate `Prepared/` and write
   statuses into `_manifest.xlsx`.

A per-engagement lock file prevents overlapping runs when an OCR-heavy scan exceeds
the interval. Cloud-only placeholders are left in the drop folder until the sync
client has actually downloaded them, so a stub is never filed as if it were the
document.

## Manifest Schema (`_manifest.xlsx`, sheet "Requests")

| Column | Type | Owner | Purpose |
|---|---|---|---|
| Identifier | str, unique (e.g., A01) | accountant | Join key; folder name prefix; matched by *prefix against known identifiers* (no hardcoded format regex — A100, BS01 all work) |
| Document | str | accountant | Human-readable name |
| Period | str | accountant | e.g., "Dec 2025" |
| Expected Count | int, default 1 | accountant | For multi-file items; counted over content-hash-distinct valid files (duplicates like "statement (1).pdf" don't inflate the count) |
| Allowed Extensions | csv str | accountant | Tier-2 whitelist |
| Min Size KB | int, default 5 | accountant | Rejects 0-byte / placeholder files |
| Required Keywords | csv str, optional | accountant | Tier-3: ALL must appear in extracted text |
| Any Keywords | csv str, optional | accountant | Tier-3: at least ONE must appear |
| Date Pattern | regex str, optional | accountant | Tier-3 date check |
| Manual Override | enum, optional | accountant | `Accepted` (treat as Received despite rules) / `Waived` (no longer needed). Scanner skips status writes on these rows. |
| Status | enum | scanner | Missing / Partial / Failed Validation / Received / **Pending Sync** |
| Received Date | date | scanner | First date all validations passed; preserved on regression |
| File Count | int | scanner | Distinct valid files currently in folder |
| Validation Notes | str | scanner | Which tier failed and why; regression notes |

Unmatched files dropped in `Shared/` root go on a separate **"Unfiled" sheet**
(path, size, first seen) — never ignored, never moved.

## Validation Tiers (deterministic, gate status)

1. **Existence** — folder contains ≥1 file (ignore `desktop.ini`, `Thumbs.db`, `~$*`).
2. **Integrity** — extension whitelisted; size ≥ Min Size KB; PDFs open without error
   (`pypdf` load test).
3. **Content** — extract text (`pdfplumber`; `openpyxl`/`csv` for spreadsheets;
   `pytesseract` OCR fallback for image-only PDFs); apply keyword/date-pattern rules
   from the manifest row. **Extraction results are cached** in a sidecar JSON keyed by
   `(path, size, mtime)` — unchanged files are never re-extracted, so steady-state
   scans stay fast at a 15-minute cadence.

Status resolution:
- 0 valid files → **Missing**
- valid files < Expected Count → **Partial**
- files present but a tier fails → **Failed Validation** (+ note)
- all checks pass → **Received** (+ date stamp on first pass)
- cloud-only placeholders — OneDrive Files On-Demand or Google Drive streaming
  (detected via `st_file_attributes` /
  `FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS`, never force-hydrated) → **Pending Sync**
- previously Received, files changed/removed → auto-revert to current truth,
  Received Date kept, regression note added

*(Optional future tier: local LLM as read-only advisory classifier — suggestion
column only, never gates status. Deferred; requires explicitly relaxing the
no-genAI-on-financial-docs rule.)*

## Components — Build Order

| # | Component | Status |
|---|-----------|--------|
| 1 | `tracker/manifest.py` — schema, `RequestItem`, `load_manifest()`, `write_statuses()` with lock-retry + pending-sidecar merge, `create_template()` | ✅ built + tested |
| 2 | `tracker/scaffold.py` — manifest → `Shared/` drop folder + `Shared/PBC/`, and `Prepared/{Identifier} - {Document}` + `00 - Needs Review` (sanitize `\ / : * ? " < > \|`), `_README.txt`. Idempotent via prefix matching; never touches existing files. CLI: `python -m tracker.scaffold <engagement_dir>` | ✅ built + tested |
| 3 | `tracker/validators.py` — Tiers 1–2, pure read-only functions; passive cloud-placeholder detection (OneDrive / Google Drive) (plain local files just report False — no cloud dependency). Dry-run CLI: `python -m tracker.validators <engagement_dir>` | ✅ built + tested |
| 4 | `tracker/content_check.py` — Tier 3 extraction (pdfplumber / openpyxl / text; optional OCR fallback that degrades to a "review manually" note when Tesseract is absent) + rules + verdict cache. Cache stores pass/fail only — extracted client text is never persisted | ✅ built + tested |
| 5 | `tracker/scanner.py` — orchestrator: walk `Prepared/`, prefix-match folders, run tiers, resolve status (override- and revert-aware), hash-dedupe counts (skipped for 0/1-file rows), Unfiled sheet, write-back, console summary, stale-aware run-lock. CLI: `python -m tracker.scanner <engagement_dir> [--dry-run]` | ✅ built + tested |
| 6 | `tracker/router.py` — deterministic routing of a dropped file to one manifest row. Evidence order: required keywords → any-keywords/period → filename (text-less scans only). Extension alone never routes; a document matching one row's required keywords but failing its other rules is contested and blocks its own filing | ✅ built + tested |
| 7 | `tracker/filer.py` — sort the drop folder: move each original into `Shared/PBC/` untouched, copy a renamed working file into `Prepared/…` or `00 - Needs Review`, append `_index.xlsx`. Content-hash de-duplication makes re-runs no-ops; cloud-only files are left to finish syncing. CLI: `python -m tracker.filer <engagement_dir> [--dry-run]` | ✅ built + tested |
| 8 | `tracker/reminder.py` — draft client email per engagement from Missing/Partial/Failed rows (draft only — no sending) | pending |
| 9 | Scheduling — Task Scheduler XML / n8n cron; `engagements.yaml` registry | pending |

## Edge Cases (designed in)

- Cloud-only files (OneDrive Files On-Demand, Google Drive streaming) → detect
  placeholder attributes; mark **Pending Sync**;
  never force-hydrate (a cloud-only 500 MB file must not be silently downloaded every scan).
- Client drops a whole folder → recursed into and flattened; the folder itself is left behind.
- Same document sent twice under different names → both originals preserved in `PBC/`,
  filed once (content-hash match), the second recorded in the index as a duplicate.
- Two files that would take the same prepared name → `(2)`, `(3)`… never an overwrite.
- A name already used in `PBC/` → the newcomer becomes `name (2).ext`; nothing is replaced.
- Google-native documents (`.gdoc`, `.gsheet`, ...) → tier-2 fail with a note asking the
  client to upload an exported PDF/Excel copy; Google Drive `.tmp.drive*` transfer temps
  are ignored as junk.
- Folder renamed but prefix kept → still matched (prefix match on known identifiers).
- Folder deleted → scaffold re-run recreates; status reverts to Missing with note.
- Duplicate/versioned uploads → content-hash dedupe before counting.
- Manifest locked by Excel during write-back → retry with backoff; final failure
  writes `_manifest.pending.json`; merged automatically on next write.
- Multi-engagement concurrency → one manifest per engagement; no shared state;
  per-engagement run-lock prevents overlapping scans.

## Stack

Python 3.11+ · openpyxl · pdfplumber · pypdf · pytesseract (+ Tesseract Windows
install) · PyYAML · pathlib · logging (rotating file log per engagement).
No database — the manifest is the source of truth.
