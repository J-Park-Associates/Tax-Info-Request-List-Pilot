# Tax Document Tracker — Build Plan

A Windows-compatible system for income tax information requests: each engagement
starts by picking the return type (1040, 1120, 1120-S, 1065, 1041, 990), which
selects a tailored document request template (`FORM_TEMPLATES` in
`tracker/templates.py`, the one source of truth). A returning client's list is
rolled forward from last year instead. The system then scaffolds a cloud-synced folder
structure (OneDrive or Google Drive) from an Excel manifest, gives the client **one
folder** to drop everything into, then sorts what arrives: originals are preserved in
`Shared/PBC/`, renamed working copies are filed into `Prepared/{Identifier} - {Document}/`,
every move is written to `_index.xlsx`, and each request's status is validated back
into the manifest.

## Hard Constraints

The standing rules are worded once, in `tracker/__init__.py`, and quoted here:

- **No generative AI ever reads a client financial document.** Every routing
  and status decision comes from deterministic rules in the manifest.
- **Originals are never altered.** Files are moved byte for byte under their
  own names into `Shared/PBC/`; all work happens on copies, and every move is
  recorded in `_index.xlsx`. The scanner never touches `Shared/` at all.
- **Nothing is guessed.** A document is filed only when exactly one request
  accepts it. Ambiguous, contested and unrecognized files go to
  `00 - Needs Review` for a person - misfiling a tax document is worse than
  not filing it.
- **Nothing is ever sent.** The system drafts client emails and stops. There
  is no SMTP, no mail client and no network call in the reminder or scheduling
  path.
- Python at the floor `pyproject.toml` declares, `pathlib.Path` throughout.
- Atomic, incremental development: one complete, verified component at a time.
- All manifest write-backs go through `openpyxl`, preserving existing content
  (write with a non-`data_only` load so formulas survive; keep the manifest free of
  charts/VBA, which openpyxl drops on re-save).

## Decision Log (2026-07-08)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Manifest placement | **Outside shared scope.** Client's edit link points at `Shared/`; `_manifest.xlsx` sits one level up, invisible to the client. |
| 2 | Manual Override column | **Yes.** `Accepted` / `Waived`. `Accepted` is written as Received (decision 33); `Waived` keeps its facts and is outside every count. |
| 3 | Received-then-changed | **Auto-revert.** Status always reflects the current scan; original Received Date preserved with a regression note. |

## Decision Log (2026-09-16)

| # | Decision | Choice |
|---|----------|--------|
| 4 | Client-facing structure | **One folder.** The client drops everything into `Shared/`; they never sort, name or match anything. |
| 5 | Where originals live | **`Shared/PBC/`.** Moved out of the drop zone, name and bytes untouched, still visible to the client. |
| 6 | Where working copies live | **Firm side only (`Prepared/`).** The client never sees the organized tree, so they cannot edit it. |
| 7 | Unidentifiable files | **`00 - Needs Review`, never a guess.** Extension alone does not route; a contested document blocks its own filing. |
| 8 | Rename convention | **`{Identifier} - {Document} - {Period}.ext`**, with `(2)`, `(3)`… for rows expecting several files. |
| 9 | Returning clients | **Prior year takes absolute precedence.** The template may fill a blank but never overwrite one; rows the client has never had are offered, not added. |
| 10 | Rolling `Accepted` forward | **No.** `Waived` is a decision about the client and persists; `Accepted` judged one year's files and must not pre-approve the next. |

## Decision Log (2026-09-16, scheduling)

| # | Decision | Choice |
|---|----------|--------|
| 11 | Reminder cadence | **Weekly, Saturday.** A nightly reminder is noise that gets ignored; one a week, waiting over the weekend for a start-of-week send, gets read. Filing and scanning still run on whatever cadence the task is set to. |
| 12 | Who decides the day | **The runner, not the scheduler.** One daily task, with `DRAFT_WEEKDAY` as the only place the day is written down. A run the scheduler misses still drafts when it next runs, instead of skipping the week. |
| 13 | Manual drafting | **Always available.** `python -m tracker.reminder <dir>` is unconditional, and `--reminders always` forces the batch on any day. The schedule is a default, not a cage. |
| 14 | `Reminders: no` | **A standing decision, not a flag.** It means this client is not chased by email; neither the schedule nor `--reminders always` overrides it. The manual CLI still drafts one on demand. |
| 15 | Regenerating a draft | **Never overwrite an edit.** The header carries a fingerprint of the generated text; anything that no longer matches is somebody's work, so the new draft goes to `reminder-draft.NEW.txt` beside it. |
| 16 | One engagement fails | **Record it and carry on.** A mistyped path must not be why nine other clients went unprocessed. The run exits non-zero so the scheduler still shows a failure. |

## Decision Log (2026-09-16, hardening)

| # | Decision | Choice |
|---|----------|--------|
| 17 | One drop fails | **Isolate it, record it, keep sorting.** Originals are moved into `PBC/` before anything else, so a failure after the move (disk full, a copy error) is indexed as *Needs Review* with the error and the rest of the pile is still sorted. A file the sync client still holds open is left in place for the next run. The index is written in a `finally`, and if Excel has it open the rows wait in `_index.pending.json` — nothing moved into `PBC/` is ever unrecorded. The engagement still counts as failed so the scheduler shows it. |
| 18 | Workbook saves | **Atomic.** Every `_manifest.xlsx` / `_index.xlsx` save lands beside the file and is swapped in with `os.replace`. A killed task mid-save used to leave a workbook Excel could not open; now it leaves the previous one. |
| 19 | Identifiers | **Must survive as a folder-name prefix.** `A:01` or `A01.` scaffolds a folder the scanner can never match back (permanent "folder not found"), so the loader refuses them, and `A01`/`a01` are one identifier because Windows folders are case-insensitive. |
| 20 | Why a file was not filed | **The most useful reason available.** A document whose content fits a request that refused the file (below the size floor, wrong type, unreadable) is parked with `CONTESTED_PREFIX` and the request; a file every request refused for one reason carries that reason. `UNMATCHED` is the last resort, not the default. |
| 21 | Partial rows we have not read | **Ours, not the client's.** If the file that would complete a `Partial` row is an un-OCR'd scan, "1 of 2 received" is not something we know yet; the row goes to the accountant with the other firm-side flags. |
| 22 | Overlapping runs | **One engagement lock for sort and scan.** `tracker/locking.py`; the filer holds it too. A second run that started mid-sort used to move the remaining originals and overwrite the first run's index rows. |
| 23 | Files dropped into `PBC/` | **They count.** The client can see `PBC/` and was told to drop things anywhere, so a file that lands there is filed and indexed in place instead of ignored for ever. |
| 24 | Re-sent document, working copy gone | **Re-file it.** A re-send is the client answering *Missing*; calling it a duplicate of a copy somebody deleted would keep the row Missing for good. The original was always safe in `PBC/`. |
| 25 | Document renamed in Excel | **Same folder.** New files go into the folder that already holds the request's earlier files (prefix rule), not a second folder built from the new name. |
| 26 | Excel open during the Saturday scan | **The draft still knows.** Deferred statuses in `_manifest.pending.json` are overlaid before triage, so the reminder never asks for a document the last scan saw arrive; the draft's footer says how many are waiting. |
| 27 | The registry | **Gone. An engagement is a folder with a manifest in it.** `engagements.yaml` was a second list a person kept in step with the folders on disk; a mistyped path was a client silently skipped. The run walks the clients root, and each manifest's Engagement sheet (client, link, due, sender, firm, reminders, active) carries what the registry used to. The wizard writes the sheet, so creating an engagement is the only step. |
| 28 | Needs Review triage | **A click, not a file move.** The person picks the request; the filer moves the parked copy under the canonical name, rewrites the index row as Filed with the `ASSIGNED_BY_PERSON` reason, optionally learns a keyword onto the request, and re-scans. Dragging a copy into a folder by hand can land it under the wrong name or in the wrong folder, and the index never learned the decision. |
| 29 | Manifest typos | **Named with their row before anything moves.** `check_manifest()` runs behind the app's **Check Manifest** button and at the top of every scheduled pass; a bad regex or a non-number typed in Excel fails that engagement's run immediately with the row, and rows the rules cannot act on (no keyword, `*` types, statuses waiting in the sidecar) are warnings in the report instead of surprises at a deadline. |
| 30 | Blank Allowed Extensions | **The safe default, not "anything".** Blank means `DEFAULT_EXTENSIONS`; accepting any file type has to be written as `ANY_EXTENSION`. A blank left by accident used to let an `.exe` count as a document. Items built in code with no extensions are written as `*` so a round trip keeps their meaning. |
| 31 | Long PDFs | **The first `MAX_PAGES` only, text and OCR alike.** The words that identify a document are on its first pages; a 500-page ledger was being read cover to cover on every route and scan, and that is what stalled a run. A keyword deep in a long document is not evidence the router should act on. |
| 32 | The lock, and the name | **Shown, not left as a mystery file.** The app shows a running lock with its start time, and offers to clear one older than `STALE_LOCK_SECONDS`; a fresh lock is refused with how long to wait, because clearing a live one is the race the lock exists to prevent. A new-client engagement is named from the client, the template's tax year and the form unless a name is typed. |
| 33 | `Accepted` | **Is Received.** Status, date and every count that reads the status column agree; a row a person signed off on no longer reads Missing in the sheet or in the run. `Waived` rows keep their facts but are left out of the outstanding count. |
| 34 | Scaffold | **Every pass.** A row added or un-waived in Excel has its folder and its README line by the next scheduled run; nobody re-runs scaffold. The README is rewritten only when its text changes, so the sync client is not pushed a "new" file each pass. |
| 35 | After a rollover | **The prior retires itself.** The new engagement's sheet records *Rolled From*; discovery marks that prior inactive with its successor named, and the run skips it. The prior's manifest is never written to (decision 9 still holds); nobody opens last year's file to type "no". |
| 36 | The tax year | **From the calendar.** A new engagement is for the most recently ended year (`default_tax_year`); the catalog is written for one base year and shifted to it, relative periods included. Nobody edits `TY2025` to `TY2026` across six checklists every January, or forgets to. |
| 37 | Installing the schedule | **One step.** `python -m tracker.scheduling --root ... --out ... --install` generates the XML and registers it (`schtasks /create /f`), and re-running is how the schedule is changed. |
| 38 | One pass, one count, one record | **The app's scan button is the runner's pass** (`run_engagement`), so the button and the job do the same thing to the same folder; `sort` and `scaffold` commands are gone. **`summarize()` is the only count** of where an engagement stands - runner log, reminder, scanner CLI and app all read it. **The index is the only record of parked files**; the scanner's Unfiled sheet is no longer written (old ones are left alone), and what it alone knew - loose files and unrecognised folders in `Prepared/` - are warnings on the pass. |
| 39 | One name, one firm, one root | **The folder is the engagement's name**; the wizard no longer copies it onto the sheet (a copy drifts the first time the folder is renamed; the cell is still read if present). **The sheet's Firm is the sign-off and the README contact**; the reminder and scaffold read the sheet themselves, and the wizard reads the firm from `settings.firm()` so it is typed once. **The clients root is in `settings.json` beside the app**, set on first launch (or `python -m tracker.settings <folder>`); the app, the priors list, `tracker.scheduling` and the Install Schedule button all read that one value. |
| 40 | The year, once | **Period implies the year check.** The year was typed twice (Period for people, Date Pattern for the rules) and, on 73 of 78 catalog rows, only once - so a 2024 form satisfied a TY2025 request. A blank Date Pattern on a row whose Period names a year now checks for that year; `*` says no check; a typed regex wins. A derived year is a *check* on a document a keyword already matched, never evidence on its own, so a row with only a Period can still never claim a document. Rollover leaves derived checks blank; the shifted Period derives them again. |
| 41 | The demo, and the second copies | **Gone.** The presenter guide in the app, the demo buttons, the demo folder and batch file, the demo script and portable readme, and the sample builder in the API module (now `tests/samples.py`, which the suite still needs). The template CSVs and their check: the manifest is the readable copy. The scanner's per-engagement log: `runs.log` is the log. The README is setup; `docs/workflow.md` is how the work is done. |
| 42 | Every fact, one home | **`tracker/reasons.py` is every refusal** - the note the scanner writes, the marker the reminder looks for, the client's ask and whose side it is; producers and the reminder both read it, so rewording one cannot silently change what a client is asked. **The renderer's vocabulary comes from the API** (`_vocab()`: statuses, decisions, reasons, product name, firm), so the app never retypes a Python string. **`settings.json` is the firm and the clients root; `app/package.json` is the product name and the API name** - Python, the Electron shell and the build script all read them, and the guard tests in `tests/test_single_source.py` pin the literals that have to cross the language line (env names, chip classes, the README's Engagement table, this file's schema table). **`filer.INDEX_LAYOUT` is the index**: the columns, their headers and widths, read back by header. **`Engagement` wraps `EngagementInfo`** instead of copying its fields. **The four standing rules are worded once** (`STANDING_RULES`); the app renders them and the documents are pinned to them. **The manifest owns the outstanding set, the sidecar suffixes, the lock-retry policy, the yes/no spellings and the year range** its pattern is built from; the Carried Forward sheet, like the index, is one layout. Documents name a constant rather than quoting its value, and `tests/test_single_source.py` pins every literal that has to cross the language line - the version, the IPC channels, the Python floor, the form list, the status vocabulary, the button label. Constants are rendered on the knowledge map so a second copy is visible. |

## Decision Log (2026-09-17, hardening II)

| # | Decision | Choice |
|---|----------|--------|
| 43 | Sidecars, the cache and the settings file | **Written whole or not at all, under a name no other writer can share.** Every JSON beside a workbook (`PENDING_SUFFIX` sidecars, the content cache, `settings.json`) and every Task Scheduler XML goes through `atomic_replacement()` in `tracker/manifest.py`: a temp file that carries the process id and a random tag, still ending in `TEMP_SUFFIX` so the validators ignore it, swapped in with `os.replace`. A fixed temp name let two writers swap each other's half-written file into place. **Readers never move a file.** `quarantine_sidecar()` moves an unreadable sidecar aside only for the write that would otherwise retry it for ever; the app's state, the reminder and every dry run pass `quarantine=False` and leave the disk as they found it. A second unreadable sidecar gets its own name (`.2`, `.3` ...) - the first is evidence, never overwritten. |
| 44 | The index sidecar | **A snapshot, not a tail.** When Excel holds `_index.xlsx`, `write_index()` saves the whole index as it should now read (`INDEX_SIDECAR_VERSION`), and `read_index()` returns that snapshot in the workbook's place until the next write lands it. Saving only the rows past the workbook's end lost the one row a person had just rewritten - the parked file they filed from Needs Review - while the working copy had already moved, so the index said the file was still parked in a folder it was no longer in. A bare-list sidecar written before the version key still appends, once. A waiting sidecar is landed on every real run, not only one that also sorted something. |
| 45 | The lock | **Held, owned, taken first, and older than the job's kill time.** The lock's descriptor stays open while a run holds it, so on Windows a lock that merely looks stale but belongs to a run still going cannot be deleted under it; release removes the file only if it still carries the run's own line. It is taken *before* the manifest, the index or the drop folder is read - reading first and locking afterwards let a run that finished in between be invisible, and its rows were rewritten from a stale picture; `assign_review_file()` writes the learned keyword under the lock too. `RUN_TIME_LIMIT_SECONDS` in `tracker/locking.py` is the one number for how long a scheduled pass may run: the task's ExecutionTimeLimit is that number rendered, and `STALE_LOCK_SECONDS` is derived above it, so a lock is presumed dead only after Task Scheduler must have killed its owner (the two were typed apart, 3600 s against a two-hour limit, and the repeat fired exactly at the boundary). Accepted cost: the repeat that fires as a run is killed still respects the lock and the one after proceeds. **One machine per clients root** - a lock file a cloud client syncs between machines is not a lock. |

## Architecture

```
OneDrive / Google Drive (synced locally on Windows)
└── Clients/
    └── {ClientName}/
        └── {EngagementName}/
            ├── _manifest.xlsx        ← accountant-only (NOT in the shared scope)
            ├── _index.xlsx           ← every original: where it went, what it became
            ├── _manifest.pending.json← sidecar written only if Excel had the file locked
            ├── _content_cache.json   ← tier-3 verdict cache (never client text)
            ├── _index.pending.json   ← same, for index rows while Excel has _index.xlsx open
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

One scheduled job runs against the local synced path (Windows Task Scheduler or n8n
cron) and walks the clients folder for every engagement (any folder holding
`_manifest.xlsx`; the manifest's Engagement sheet carries the client's details):

```
python -m tracker.runner "D:\OneDrive\Clients" --log
```

Per engagement it does, in order:

1. `tracker.filer` — sort the drop folder: preserve each original in `PBC/`, file a
   renamed copy into `Prepared/`, append to `_index.xlsx`.
2. `tracker.scanner` — validate `Prepared/` and write statuses into `_manifest.xlsx`.
3. `tracker.reminder` — **on Saturdays only**, draft the client chase email into
   `reminder-draft.txt`. Never sends it; never overwrites a draft somebody edited.

Each step is still its own module with its own CLI, so any one of them can be run by
hand against a single engagement. The runner is the unattended path, not the only one.

A per-engagement lock file prevents overlapping runs when an OCR-heavy scan exceeds
the interval. Cloud-only placeholders are left in the drop folder until the sync
client has actually downloaded them, so a stub is never filed as if it were the
document.

## Manifest Schema (`_manifest.xlsx`, sheet `SHEET_NAME`)

| Column | Type | Owner | Purpose |
|---|---|---|---|
| Identifier | str, unique (e.g., A01) | accountant | Join key; folder name prefix; matched by *prefix against known identifiers* (no hardcoded format regex — A100, BS01 all work) |
| Document | str | accountant | Human-readable name |
| Period | str | accountant | e.g., "Dec 2025" |
| Expected Count | int, default `DEFAULT_EXPECTED_COUNT` | accountant | For multi-file items; counted over content-hash-distinct valid files (duplicates like "statement (1).pdf" don't inflate the count) |
| Allowed Extensions | csv str | accountant | Tier-2 whitelist. Blank = `DEFAULT_EXTENSIONS`; `*` = any type (say it out loud) |
| Min Size KB | int, default `DEFAULT_MIN_SIZE_KB` | accountant | Rejects 0-byte / placeholder files |
| Required Keywords | csv str, optional | accountant | Tier-3: ALL must appear in extracted text |
| Any Keywords | csv str, optional | accountant | Tier-3: at least ONE must appear |
| Date Pattern | regex str, optional | accountant | Tier-3 date check. Blank + a year in Period = that year, case-insensitive, whole-token; `*` = no year check; a typed regex wins. A derived year is a check on a matched document, never a reason to route |
| Manual Override | enum, optional | accountant | `Accepted` (written as Received) / `Waived` (no longer needed; outside every count). |
| Status | enum | scanner | Missing / Partial / Failed Validation / Received / Pending Sync |
| Received Date | date | scanner | First date all validations passed; preserved on regression |
| File Count | int | scanner | Distinct valid files currently in folder |
| Validation Notes | str | scanner | Which tier failed and why; regression notes |

Unmatched files are parked in `00 - Needs Review` and recorded in `_index.xlsx`
with the reason — never ignored, never guessed.

## Validation Tiers (deterministic, gate status)

1. **Existence** — folder contains ≥1 file (ignoring the junk `tracker/validators.py` lists).
2. **Integrity** — extension whitelisted; size ≥ Min Size KB; PDFs open without error
   (`pypdf` load test).
3. **Content** — extract text (`pdfplumber`; `openpyxl`/`csv` for spreadsheets;
   `pytesseract` OCR fallback for image-only PDFs); apply keyword/date-pattern rules
   from the manifest row. **Extraction results are cached** in a sidecar JSON keyed by
   `(path, size, mtime)` — unchanged files are never re-extracted, so steady-state
   scans stay fast at the scheduled cadence.

Status resolution:
- 0 valid files → **Missing**
- valid files < Expected Count → **Partial**
- files present but a tier fails → **Failed Validation** (+ note)
- all checks pass → **Received** (+ date stamp on first pass)
- cloud-only placeholders — OneDrive Files On-Demand or Google Drive streaming
  (detected via the Windows cloud-placeholder attribute flags in
  `tracker/validators.py`, never force-hydrated) → **Pending Sync**
- previously Received, files changed or removed → auto-revert to current truth,
  Received Date kept, regression note added

*(Optional future tier: local LLM as read-only advisory classifier — suggestion
column only, never gates status. Deferred; requires explicitly relaxing the
no-genAI-on-financial-docs rule.)*

## Components — Build Order

| # | Component | Status |
|---|-----------|--------|
| 1 | `tracker/manifest.py` — schema, `RequestItem`, `load_manifest()`, `write_statuses()` with lock-retry + pending-sidecar merge, `create_template()` | ✅ built + tested |
| 2 | `tracker/scaffold.py` — manifest → `Shared/` drop folder + `Shared/PBC/`, and `Prepared/{Identifier} - {Document}` + `00 - Needs Review` (sanitize `WINDOWS_ILLEGAL_CHARS`), `_README.txt`. Idempotent via prefix matching; never touches existing files. CLI: `python -m tracker.scaffold <engagement_dir>` | ✅ built + tested |
| 3 | `tracker/validators.py` — Tiers 1–2, pure read-only functions; passive cloud-placeholder detection (OneDrive / Google Drive) (plain local files just report False — no cloud dependency). Dry-run CLI: `python -m tracker.validators <engagement_dir>` | ✅ built + tested |
| 4 | `tracker/content_check.py` — Tier 3 extraction (pdfplumber / openpyxl / text; optional OCR fallback that degrades to a "review manually" note when Tesseract is absent) + rules + verdict cache. Cache stores pass/fail only — extracted client text is never persisted | ✅ built + tested |
| 5 | `tracker/scanner.py` — orchestrator: walk `Prepared/`, prefix-match folders, run tiers, resolve status (override- and revert-aware), hash-dedupe counts (skipped for 0/1-file rows), write-back, console summary, stale-aware run-lock. CLI: `python -m tracker.scanner <engagement_dir> [--dry-run]` | ✅ built + tested |
| 6 | `tracker/router.py` — deterministic routing of a dropped file to one manifest row. Evidence order: required keywords → any-keywords/period → filename (text-less scans only). Extension alone never routes; a document matching one row's required keywords but failing its other rules is contested and blocks its own filing | ✅ built + tested |
| 7 | `tracker/filer.py` — sort the drop folder: move each original into `Shared/PBC/` untouched, copy a renamed working file into `Prepared/…` or `00 - Needs Review`, append `_index.xlsx`. Content-hash de-duplication makes re-runs no-ops; cloud-only files are left to finish syncing. CLI: `python -m tracker.filer <engagement_dir> [--dry-run]` | ✅ built + tested |
| 8 | `tracker/rollover.py` — build a returning client's next-year list from their prior engagement. Prior-year fields always win; the template only fills blanks and its unknown rows are offered rather than added. Years shift as a set (so relative periods stay right), counts learn from what arrived and never shrink, `Waived` carries and `Accepted` does not. Writes a `Carried Forward` sheet explaining every row. CLI: `python -m tracker.rollover <prior_dir> <new_dir> [--form] [--year] [--include-new] [--scaffold]` | ✅ built + tested |
| 9 | `tracker/reminder.py` — draft client email per engagement from Missing/Partial/Failed rows (draft only — no sending; no SMTP anywhere in the module). Validation notes are translated into plain client instructions, never quoted. Rows we simply have not read yet, and rows with no request folder, are held back for a person instead of being asked for; untriaged `00 - Needs Review` files raise a warning so a reminder never asks for something already in hand. CLI: `python -m tracker.reminder <engagement_dir> [--client] [--link] [--due] [--from-name] [--firm] [--write]` | ✅ built + tested |
| 10 | Scheduling — `tracker/registry.py` (discovery: every folder under the clients root holding `_manifest.xlsx` is an engagement; its Engagement sheet supplies client, link, due, reminders and active; an unreadable manifest is listed with its error, never dropped), `tracker/runner.py` (one unattended pass: file → scan → draft, with per-engagement failure isolation and a non-zero exit so the scheduler shows a red run), and `tracker/scheduling.py` (generates the Task Scheduler XML / n8n workflow). **Reminders are drafted weekly, on Saturday** — the runner owns the day, so one daily task covers it and a missed Saturday still drafts on the next run. CLI: `python -m tracker.runner <clients root> [--only] [--dry-run] [--reminders auto\|always\|never] [--weekday] [--date] [--log]` | ✅ built + tested |
| 11 | `tracker/templates.py` — the per-form request catalog (`FORM_TYPES`, `FORM_TEMPLATES`) and `item_from_spec()`; the one source of truth for the checklists, read directly by the wizard and the rollover. A request with no rule gets its own document name as the required keyword; the year check is implied by each row's Period; `default_tax_year()` follows the calendar. | ✅ built + tested |
| 12 | `tracker/locking.py` — the per-engagement lock (`_scan.lock`), taken by the filer while sorting and the scanner while scanning, before either reads anything, held open until released, stale after `STALE_LOCK_SECONDS` (derived from `RUN_TIME_LIMIT_SECONDS`, the scheduled task's time limit). One lock, because a sort and a scan overlapping is how an original ends up in `PBC/` with no index row. | ✅ built + tested |

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

Python at the floor `pyproject.toml` declares · the packages `requirements.txt`
pins · pathlib · logging to the one `runs.log` in the clients root.
No database — the manifest is the source of truth.
