# Pilot handoff

## Done (Job 0, 2026-09-28)

- Branch `pilot/first-edition` cut from `origin/main` at `a2d6af4` (merge of
  PR #139, decision 209), in its own worktree `../Tax-Tracker-Pilot`.
- `pilot/README.md` (purpose and branch rules), `pilot/DECISIONS.md` (P1-P7),
  this file. Repo map refreshed for the new files.

## Next: Job 1 - SPEC (opus, high effort) -> `pilot/SPEC.md`

Read, in this order: `pilot/README.md`, `pilot/DECISIONS.md`, then the plan
below. Use `python tools/repo_map.py show <file>` for single nodes; do not read
`docs/repo-map.md` whole.

The SPEC must fix:

1. **`pilot/edition.json`** - edition name, version (e.g. `0.1-pilot`), the
   `main` commit it was built from, terms version. The app shows a "Pilot
   edition" badge and version in the header.
2. **Terms screen** - shown at first launch and again when the terms version
   changes; wording in `pilot/terms.md` (Opus drafts, Jason approves);
   acceptance stored in the tracker's data folder.
3. **Guided tour** - overlay on the real UI, replayable from a Tour button,
   all text in `pilot/tour-content.json`. Steps: choose clients root; create
   household and request list; open "Drop files here" and drop documents;
   Scan; originals moved to the year folder; organized working copies in
   `Prepared/`; resolve a Needs Review item; Status page; drafted reminder
   (never sent). Each step: "What it does", "Why it's safe / strength",
   "Current limit".
4. **Pros and cons copy** (first draft, Jason edits):
   - Strengths: no AI reads a client document; originals moved byte for byte,
     never altered; nothing guessed, doubt goes to a person; nothing sent,
     drafts only; every move recorded; organized names follow the request
     list; offline on your own PC.
   - Limits: Windows only; about 74 document kinds across 6 return types,
     unfamiliar layouts go to Needs Review; scans read slowly on the processor
     without the optional graphics pack; one PC should run the schedule;
     unsigned installer (SmartScreen); no email sending, by design; pilot,
     expect rough edges.
5. **Installer** - Inno Setup (`pilot/installer/pilot.iss`) wrapping
   `Build App.bat`'s portable folder; per-user, no admin, Start-menu
   shortcut, uninstaller that never touches the clients root or the data
   folder. `pilot/Build Pilot Installer.bat` runs `Build App.bat`, stamps
   `edition.json`, compiles. Office PC only, never Actions.
6. **Tester guide** - `pilot/Tester Guide.md`.
7. **Tests** - pin the `edition.json` shape; every element id in
   `tour-content.json` exists in `app/renderer/index.html`; tour and terms text
   carry no wording `tests/test_single_source.py` forbids.

Open items to confirm with Jason in the SPEC session: final terms wording,
final pros/cons wording, product name and version string on the badge.

## After the SPEC

- Jobs 2A (installer + edition badge) and 2B (tour + terms + content) run in
  parallel as sonnet builds; they touch disjoint files and share only the
  `edition.json` shape.
- Job 3: opus review in a session that built nothing; rebuild/review loop.
- Job 4: Jason builds and installs on a clean Windows account, runs the tour,
  uninstalls and confirms client folders and data folder are untouched.
- Job 5: tag `pilot-0.1` (never `v*`), send installer and Tester Guide.

## Useful references (from the engine, unchanged here)

- One pass: `tracker/runner.py` `run_engagement`; Scan button ->
  `tracker/api.py` `_cmd_run_now`.
- Working-copy names: `tracker/filer.py` `prepared_name_for`.
- New household: `tracker/api.py` `_cmd_create` -> `households.create_household`
  -> `scaffold.scaffold_engagement`; catalogs in `tracker/templates.py`.
- Local test documents: `tests/samples.py` `build_scratch_root` (local checks
  only, never shipped).
- Build: `Build App.bat`, `api_entry.spec`; `build.yml` fires on `v*` tags only.
