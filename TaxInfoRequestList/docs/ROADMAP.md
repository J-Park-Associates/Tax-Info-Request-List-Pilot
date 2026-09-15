# Tax Document Tracker — Build Plan (v1.1)

A Windows-compatible system for income tax information requests: each engagement
starts by picking the return type (1040, 1120, 1120-S, 1065, 1041, 990), which
selects a tailored document request template (`FORM_TEMPLATES` in `tracker/api.py`;
CSV checklists in `templates/`). The system then scaffolds a OneDrive folder
structure from an Excel manifest, lets clients drag documents into shared folders,
and automatically validates and tags document status back into the manifest.

## Hard Constraints

- **No generative AI touches client financial documents and no automated file moves.**
  All status decisions are made by deterministic rules. The scanner is strictly
  read-only against client files: it reads, validates, and reports — it never moves,
  renames, or deletes.
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

## Architecture

```
OneDrive (synced locally on Windows)
└── Clients/
    └── {ClientName}/
        └── {EngagementName}/
            ├── _manifest.xlsx        ← accountant-only (NOT in the shared scope)
            ├── _manifest.pending.json← sidecar written only if Excel had the file locked
            ├── scan.log              ← rotating log
            └── Shared/               ← client's edit-rights link points HERE
                ├── _README.txt       ← client instructions (auto-generated)
                ├── A01 - W-2 Wage Statements - All Employers/
                ├── A02 - 1099-INT - 1099-DIV - Interest & Dividend Income/
                └── ...
```

The scanner runs against the local synced path on a schedule (Windows Task Scheduler
or n8n cron). A per-engagement lock file prevents overlapping runs when an OCR-heavy
scan exceeds the interval.

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
- cloud-only OneDrive placeholders (detected via `st_file_attributes` /
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
| 2 | `tracker/scaffold.py` — manifest → `Shared/{Identifier} - {Document}` folders (sanitize `\ / : * ? " < > \|`), `_README.txt`. Idempotent via prefix matching; never touches existing files. CLI: `python -m tracker.scaffold <engagement_dir>` | ✅ built + tested |
| 3 | `tracker/validators.py` — Tiers 1–2, pure read-only functions; passive OneDrive placeholder detection (plain local files just report False — no cloud dependency). Dry-run CLI: `python -m tracker.validators <engagement_dir>` | ✅ built + tested |
| 4 | `tracker/content_check.py` — Tier 3 extraction (pdfplumber / openpyxl / text; optional OCR fallback that degrades to a "review manually" note when Tesseract is absent) + rules + verdict cache. Cache stores pass/fail only — extracted client text is never persisted | ✅ built + tested |
| 5 | `tracker/scanner.py` — orchestrator: walk `Shared/`, prefix-match folders, run tiers, resolve status (override- and revert-aware), hash-dedupe counts (skipped for 0/1-file rows), Unfiled sheet, write-back, console summary, stale-aware run-lock. CLI: `python -m tracker.scanner <engagement_dir> [--dry-run]` | ✅ built + tested |
| 6 | `tracker/reminder.py` — draft client email per engagement from Missing/Partial/Failed rows (draft only — no sending) | pending |
| 7 | Scheduling — Task Scheduler XML / n8n cron; `engagements.yaml` registry | pending |

## Edge Cases (designed in)

- OneDrive files-on-demand → detect placeholder attributes; mark **Pending Sync**;
  never force-hydrate (a cloud-only 500 MB file must not be silently downloaded every scan).
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
