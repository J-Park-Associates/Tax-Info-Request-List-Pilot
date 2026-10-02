# Security review - Pilot 0.1 - 2026-09-29

Two independent reviewers (Opus, built nothing), each on half of the system: **S1** the shell, its boundaries, the tester's PC and the build (findings S-1 to S-14); **S2** the engine's handling of a hostile or careless file and everything it writes for a person to read (S-101 to S-107). The orchestrating session merged the halves without changing a finding, and verified every blocking finding and three others per half against the cited code.

**Findings:** 2 blocking (S-1, S-101), 7 should-fix (S-2, S-3, S-4, S-5, S-6, S-102, S-103), 12 nit (S-7, S-8, S-9, S-10, S-11, S-12, S-13, S-14, S-104, S-105, S-106, S-107).

**Labels.** *blocking*: fix before 0.1 reaches an outside firm - it could show a client's document to the wrong party, alter an original, run code from a dropped file, send anything, lose the record, stop a tester finishing Tester Guide sections 3-6, or make the way to report a problem carry client data. *should-fix*: the next build round. *nit*: minor. Items that are by design are answered in the table near the end, with the decision that covers them. Every finding cites `path:line`, says how it was established (**Evidence**), what it means for a firm or who hits it and when, a **Fix** concrete enough to specify, and whether it reopens a logged **Decision**. Nothing here was fixed by the reviewers; fixes are separate jobs.

## Scope and method

### S1 - the shell, the PC and the build

**Read.** Briefs 00 and 01. pilot/README.md, DECISIONS.md, SPEC sections 2, 3, 3a, 5, 10, 12.5-12.6, Tester Guide, RELEASE.md and reviews 1-2. All of app/main.js and app/preload.js, the index.html CSP, the DOM writes in app.js, pilot.js, tour.js and pilot-content.js. The api.py envelope, `_read_spec`, `paths` and vocab, and the handlers for set-root, unlock, cancel-pass, set-/install-schedule, move-schedule-here and after-install. errors.py, progress.py, settings.py (settings, error log, data home, root and program-drive refusals), scheduling.py (XML, schtasks), after_install.py (run, launch, move), ocr.py's GPU-pack loader, api_entry.py/.spec, package.json and its lock, setup.iss, the three build .bat files, Setup.bat, the four locks, the workflows, CODEOWNERS and .claude/settings.json.

**Ran** (venv, repo root). `test_single_source -k "shell or ipc or openable or deny or csp or html or channel or renderer or log"`: 36 passed. test_scheduling, test_pilot, test_errors, test_tour, test_pilot_installer, test_build and test_progress: 264 passed, 1 skipped, and 1 failed (test_build's scan needs onnxruntime; this is the P27 no-OCR gap). test_layers, test_after_install, test_settings and test_tripwire: 167 passed, 2 skipped. I ran `node --check` on all six app scripts (clean) and `tools/lockfiles.py check` (clean). I drove the API with malformed payloads against a synthetic root at `$S/roots/s1/r`. I also drove the **real main.js** under a stubbed Electron (a scratch copy of the shell layout) through `list`, `set-root`, `state` and `open-path`.

**Could not.** No Windows, installer, Task Scheduler, packaged window or OCR engines. `tools/lockfiles.py audit` was refused by this environment's proxy (403 to api.osv.dev). Package versions were read from the npm and PyPI registries instead. I read no file on the deny list: generated content was judged from API replies and file metadata only. The pytest runs left git-ignored `__pycache__/` folders in the checkout. Nothing tracked changed (`git status` is clean).

### S2 - the engine and its outputs

**Read:** briefs 00 and 01 (sections 3-7, 9, 11); `pilot/README.md`, `pilot/DECISIONS.md`; `pilot/README.md` 1-60; `docs/runbook.md` *Sharing a household with a client* (790-822), the reason table (1574-1627) and §2. Code, verified against the inventory: `tracker/containers.py` (whole), `tracker/door.py` (whole), `tracker/fsio.py` (whole), `tracker/validators.py` 60-560, `tracker/layout.py` 667-1011, `tracker/filer.py` (marking 940-1060, moves 1080-1110, walks 2210-2345, README 1340-1510, step checks 1890-1990, `_take_out` 4600-4650, program park 5033-5118), `tracker/store.py` admission 1780-1870, `tracker/records.py` link and value rules, `tracker/locking.py` 1-470, `tracker/content_check.py` limits/extractors/child, `tracker/ocr.py` child and download refusal, `tracker/runner.py` practice page 2280-2530, `tracker/view.py` page assembly, `tracker/reminder.py` HTML renderers, `tracker/scaffold.py` README, `tracker/households.py` link checks. Each guardrail test brief 0 lists for my modules was read.

**Ran the engine** (Linux, synthetic "Smith Family" roots only, deny list obeyed: names listed and `sha256sum` computed, no contents printed; generated pages judged from their generator functions rendered in memory, never from the written files):

- **r2 (awkward pile):** `run-now`, `list`, `state`. Reply: filed 10, review 15, waiting 1 (the `.tmp.driveupload`), 0 file errors. 28 of 28 regular inbox files re-hashed byte-identical in `Clients/Smith Family/2025/`; both symlinks left in the inbox untouched; `/etc/hostname` unchanged; nothing written outside `/tmp/r2` and `/tmp/r2-data` (other reviewers' concurrent pytest folders aside).
- **r3 (clean pile):** filed 7, review 5, waiting 1, statuses Received 4 / Partial 1.
- **r2x (mine):** D01's file types widened to `xlsm`; dropped a macro workbook, a zip holding a macro workbook and a `.docm`, and a W-2 named `<img src=x onerror=alert(1)> W-2.pdf`. `filer.mark_from_internet` patched to record what it is handed (the suite's own technique, `tests/test_filer.py:9466`).
- **r2y (mine):** dropped `.rdp`, `.msc`, `.one`, `.svg`, `.html`, `.rtf`, `.pub`.
- In-memory renders of the practice page, the per-return view, the letter (text and clipboard HTML) and the client README for r2 and r2x.

**Tests:** `test_containers.py test_door.py test_layout.py` 109 passed; `test_fsio.py test_page.py test_filer.py -k "mark or program or junction or link or macro or fsio or page"` 120 passed, 4 skipped (Windows-only junction tests); `test_view.py test_reminder.py -k "markup or link or esc or html or clipboard"` 4 passed; `test_ocr.py::test_a_full_read_opens_no_socket...` fails here (`No module named 'rapidocr'`, P27). My first pytest run wrote pytest's bytecode into `tests/__pycache__` (gitignored; `git status` clean); later runs used `PYTHONDONTWRITEBYTECODE=1 -p no:cacheprovider`.

**Linux differences:** no OCR engines (the photo and the scan park "nothing in this file could be read", a Windows tester never sees that); `.msg` opened fine here; `mark_from_internet` is a no-op off Windows, so review copies exist unmarked here; no job-object memory cap on the reading child; no junctions, no placeholders, no 260-character limit.

## Threat model

### From the shell's side (S1)

**Assets.** The client originals in the shared Drive `Clients` tree. The private tree (journals, Prepared copies, Needs Review, status page). settings.json (root, firm, phone). The drafts. The data home: store, error log, run log, after-install note, progress files, scratch.

**Actors.**
- The **client** is the one untrusted actor with write access, through Contributor rights on their own inbox.
- A **hostile file** dropped by that client.
- The **tester firm's staff**, who see every client of their own firm and may run the pilot on several PCs.
- A **second computer** over the same root.
- **J Park** as the receiver of bug reports. For a tester firm, J Park is a third party.
- Malware or another program running as the same Windows account is **out of scope**. So is anyone with admin rights.

**Trust boundaries.**
1. Inbox -> engine (S2).
2. Renderer -> main: preload's six functions, the allow-list, `openable`.
3. Main -> Python child: argv, one JSON on stdin, lines on stdout.
4. App -> Task Scheduler: the XML, schtasks, the designation file in the synced private tree.
5. Installer -> PC: per-user, unsigned, `[UninstallRun]`.
6. Repo -> build -> tester: locks, npm ci, packager, PyInstaller, ISCC, delivery.
7. **Tester -> J Park: the problem report.** This is a new boundary the pilot creates, and the only one where client data is designed to leave the firm.

**Out of scope.** The engine's handling of accepted files (S2). Drive's own sharing and sync. Clipboard history sync, which is an OS setting.

### From the engine's side (S2)

The one untrusted actor with write access is **the client**, a Contributor on their household's inbox: they, or whoever has taken over their mailbox, can put any bytes under any name into it and edit files there until the pass moves them (they cannot move or delete them). Their files reach every parser the engine has (zip, email, Outlook, PDF, workbook, image), every page and letter that quotes a name, and every folder staff browse. **A careless file** matters as much: someone else's W-2, last year's form, an empty upload, a 200-character name. **A second household fed by the same inbox** must never see, or have filed into it, what it should not. **The firm's own staff** are trusted but fallible: they type request lists (file types, keywords, Date Patterns), inbox links and people lists, and they double-click what the tracker puts in front of them. **The synced folder** can change under a pass: Drive for desktop delivers, renames, and carries lock files and journals from other machines. What the engine must uphold: nothing it writes runs a client's code or makes one easier to run; nothing reaches a party who should not see it; originals move byte for byte; a failure is said, not swallowed. Out of scope: Windows, Drive and physical security of the PC, and the shell/API parsing (S1).

## Verified: the guardrails that hold as stated

### S1 - the shell, the PC and the build

- **Window and preload.** preload exposes exactly six functions and never exposes `ipcRenderer`. contextIsolation, sandbox and webSecurity are on and nodeIntegration is off. DevTools and the menu are off when packaged. window.open is denied. `will-navigate` is prevented, which also covers a file dropped on the window.
- **The shell's gate, reproduced with the real main.js.** Before vocab, only `list` runs. `rm` gets "Unknown command". An extra argument gets "Malformed command arguments". An unreported `/etc` is refused. A reported folder opens.
- **Spawning.** The child starts from an argument array with no shell, and the payload is serialised before spawn.
- **The API is the wall, reproduced.** A non-object payload gets NOT_A_SPEC. Bad JSON and 200,000-deep nesting are said by class only. A 50 MB payload is parsed and ignored. Bad set-schedule values, `cancel-pass {"pass":1|true}` and `after-install {"reason":"setup"}` are all refused in firm sentences. So main.js not validating payloads, and stdin/stdout having no cap, are **not a risk**: only the app's own page and its own child produce them.
- **Page building.** The CSP is present with no inline script or style. There are no HTML sinks in the four renderer scripts. `el()` keeps an attribute allow-list, and data-driven classes come only from vocab.
- **No network.** test_layers holds for app/ and tracker/.
- **The scheduled task.** The XML is escaped and schtasks gets an argument list. The task uses InteractiveToken + LeastPrivilege with no stored password. Its arguments are fixed flags plus the quoted settings folder, never the root. Its working directory is the program folder.
- **The 30-minute kill re-arm is not a risk.** Every progress key is fixed in code (filer.py:4262, scanner.py:859, runner.py:1136, 2931) and strings are capped at 200 characters, so no file name can set `limit_seconds`.
- **Single instance.** The single-instance lock is per user session, and per-user installs keep separate settings.
- **Folder permissions are not a risk.** settings.json, the program folder and the data home inherit the profile's ACL, so only same-account processes, which are out of scope, can write them. program_drive_refusal refuses removable, network and unknown drives for both the program and the settings folder.
- **Decision 176's DevTools-off holds as coded but is not a wall.** tracker-api.exe takes the same stdin from any command prompt. The API's own checks are the wall, and they hold.
- **log-error has no rate limit** and main.js appends outside Python's rotation. Only the page's own errors and failed children write there, and Python rotates at its next write, so this is **not a risk**.
- **pick-folder has no defaultPath.** Its answer only fills the text box, and set-root checks the folder again, so this is **not a risk**.
- **The after-install launch door** takes only `{"reason":"launch"}`. It returns at once when program identity, designation and choice all match. It never creates a store, and it moves only decision 186's group, refusing links.
- **With no error log yet**, a crashed first command puts about 4 KB of traceback on screen (reproduced). It holds code paths and the program folder, not client data.
- **Supply chain.** All four locks are fully hash-pinned. The workflows are read-only, SHA-pinned, set persist-credentials false, use no secrets and have no pull_request_target.
- **P19 holds:** the deny list names both data folders.

### S2 - the engine and its outputs

Held as stated, by code, test and (where marked) run. **Containers** (`containers.py:96-117, 425-463`): depth 2, 200 attachments counted from the directory before any unpacking, 250 MB counted from bytes produced, ratio 100 per member through a 64 KB counting loop, 200 skipped parts, stored/deflated only, encrypted or AES = locked; each with an edge test (`test_containers.py:390-463, 1018`). Run: `nested.zip` opened two deep and parked `inner.zip` "nested more than 2 deep"; `../../escape.txt` landed as `_Opened/documents/escape.txt`; `sub/dir/1099-INT.pdf` was flattened and filed; `stored.zip`, the `.eml` and the `.msg` opened. "Never extracted to disk" means never via `extract()` and a member name is never a path: the bytes are written by the filer into the private `_Opened` folder under `safe_name` (decision 143). **Programs** park before any reading (`tracker/filer.py:5116-5117`, and `4806` for attachments): `setup.exe` inside the zip was never written anywhere; `helper.exe` got no copy. **Protected View mark** on review copies of macro types, emails and zips, on the temp before the swap, fail closed (`filer.py:983-998, 1971`; `test_filer.py:9466-9507, 9605`) - within the review folder only (S-102). **Reading limits**: 10 pages, 40 M pixels, 20 M characters, one reading child stopped at 600 s a document and 60 s a photo; "60 s a page" is a between-pages check (`tracker/content_check.py:1759-1773`) with the document's 600 s as the hard stop; the child has a 2 GB job-object cap on Windows (`tracker/ocr.py:918-920`), none if the job cannot be made (`tracker/ocr.py:911-915`). **Downloads refused** (`tracker/ocr.py:211-222`), by code only here. **Escaping**: every value on the practice page, the per-return view, the letter HTML and the client README goes through `page.esc`; reproduced with `<img src=x onerror=alert(1)> W-2.pdf` - escaped in the page and the view, absent from the letter and README; the practice page's CSP is `default-src 'none'` with a hashed style and no script; the view's sort script uses `textContent` only. **Inbox link**: `javascript:` refused, 1,000-character cap, `quote=True` in the `href` (`tracker/reminder.py:1664`). **Containment**: `door._placed` resolves then asks `layout.parts_below`, which compares part by part with `normcase`, never by string prefix, and treats a surviving `..` as outside; `place_problem` refuses absolute, drive and UNC locations (`tracker/layout.py:932`) and any removal in the client tree; no client-controlled value reaches an `open()` as a UNC path (attachment names are basenames, record locations refuse absolute), so no UNC rule is needed engine-side. **Typed Date Patterns** are held to a shape rule (`tracker/records.py:1806`) and run only in the stoppable child; keywords are `re.escape`d. **Locks** (`_scan.lock`, `_readme.lock`) live in the private tree, which a client cannot write. **The client README** carries request labels, return names, received days and a count under review - never a client file name (render checked) - and speaks only for the household's own returns (`tracker/scaffold.py:443-455`). **Byte identity** held for every moved original (28/28, above), and links were never followed, moved or copied through.

## Findings

### Blocking

#### S-1 **blocking** `pilot/Tester Guide.md:80-82` - The only reporting guidance says "never attach client documents", while the app's own failure sentences send the tester to tracker-errors.log, which keeps client data by design.
- **Evidence:** read from code.
  - Failure sentences name the log: api.py:388-389 ("the details are in tracker-errors.log beside the tracker's database"), 433 and 443.
  - The log keeps an error's full message and trace. errors.py:3-8 and 41-47 say a parser's message can quote the file's bytes ("a damaged W-2 could carry its employee's number"), and an OS error spells out the full path.
  - Other entries carry file names (content_check keeps with `name=path.name`), engagement labels (api.py:4686-4687), page errors with stacks (app.js:250-254 -> main.js:348-350), and up to 64 KB of each failed child's stderr (main.js:305-308, 125-132).
  - Screenshots are the other channel. The household card shows the client's share link (app.js:1526) and so does the reminder letter (app.js:616), alongside household names, file names and progress lines.
  - The terms bullet (pilot-content.js:63-67) says the same as the guide and nothing more.
- **Impact for a firm:** a tester whose scan fails does the helpful thing and emails J Park the log file, or a screenshot with only the names covered. That sends clients' names, folder paths, file names, possibly fragments of a W-2, and a working link to a client's Drive folder to a third party. For a tax preparer, that is a disclosure of taxpayer information without consent, and the pilot's own report path caused it.
- **Fix:**
  - Tester Guide §10 and the terms bullet: "Never send tracker-errors.log, runs.log or anything from `%LOCALAPPDATA%\tax-document-tracker-pilot`: they name your clients and can quote their documents. In a screenshot, cover client and household names, file names and any link."
  - J Park's intake rule (RELEASE.md): never ask a tester for a log. Ask for the error class shown on screen, such as "(JSONDecodeError)".
  - A later build may add a class-and-code-only report; that is new work.
- **Decision:** reopens P20 (terms wording). The guide edit needs none.

#### S-101 **blocking** `tracker/validators.py:138-149` - PROGRAM_EXTENSIONS misses file types Windows runs or follows (`.msc`, `.rdp`, `.msu`, `.wsb`, `.jnlp`, `.xbap`, `.theme`/`.themepack`, `.py`/`.pyz`/`.pyc`, `.pl`, `.vsmacros`) and types a browser runs script from (`.html`, `.htm`, `.mht`, `.mhtml`, `.xhtml`, `.svg`); each is treated as a document and gets a copy in `00 - Needs Review` with no Protected View mark - and, out of a zip or email, an unmarked file in `_Opened` too.
- **Evidence:** reproduced by running the engine (r2y): `connect.rdp`, `snap.msc`, `invoice.svg`, `statement.html`, `notes.one`, `report.pub`, `letter.rtf` all got review copies; `mark_from_internet` was handed none of them. r2x shows the same path out of a zip (`_Opened/forwarded/Macro notes.docm`). The list is decision 190's own definition ("programs, and the files Windows runs, mounts or follows as if they were one"); Outlook's blocked-attachment list names `.msc`, `.msu`, `.jnlp`, `.wsb`, `.xbap`, `.theme`, `.py`, `.pl`.
- **Impact for a firm:** a client whose email has been taken over forwards a zip holding a console file or a remote-desktop file. The tracker unpacks it and places it, unmarked, in the folder staff work from each morning. The app offers no **Open** for it, but one double-click in Explorer runs it, or connects this PC - which holds every client's folder through Drive - to a stranger's computer. Decision 190 removed exactly this for `.exe`; these types slip past it.
- **Fix:** add the types above to `PROGRAM_EXTENSIONS` (and keep it aligned with Outlook's Level-1 list plus `.rdp`, `.one`, `.svg`, `.html`), with a test that fails when a Level-1 type is missing; the guard test that no other file spells these extensions stays.
- **Decision:** reopens decision 190 (the list).

### Should-fix

#### S-2 **should-fix** `tracker/api.py:1146-1149` - PATH_KINDS has no `review_copy …` key, so main.js stores kind=null and refuses every review copy the API reports, and the card's Open says nothing.
- **Evidence:** reproduced.
  - I scanned the synthetic root, then called `state` through the real main.js: one `review_copy …` key pointed at an existing file.
  - `open-path` on it answered "That is no longer the folder or file the tracker reported" (main.js:160, 332).
  - app.js:1365-1368 ignores the answer, so the click does nothing.
  - test_single_source.py:2104-2120 never checks that every reported key has a kind.
- **Impact for a firm:** staff cannot open a parked document from Needs Review and must browse to it by hand. The fault fails closed, but the fix must not fail open. The path comes from the record through `layout.locate` (api.py:2588-2592), and the store admits it only with `place_problem(writes=False)` (store.py:1864). That also allows any household's inbox or year folder.
- **Fix:**
  - `_path_kind(key)` answers "file" for the `review_copy ` prefix, and main.js asks it by prefix.
  - The API reports a review copy only when it lies lexically under this return's Needs Review folder and `is_program` is false. The first check is stricter than the store's admission.
  - `openReviewCopy` shows the refusal.
  - Test: every key in a state reply's `paths`, review copies included, has a kind.
- **Decision:** none.

#### S-3 **should-fix** `pilot/Build Pilot Installer.bat:30-36` - The clean-tree check is blind to git-ignored files, which are exactly the client-data names, and the only "package holds no data" check lives in build.yml, which never runs for a `pilot-*` tag with Actions off.
- **Evidence:** read from code.
  - `git status --porcelain` omits ignored files. .gitignore lists status.html, drafts, `_ledger.jsonl`, `Clients/`, `J Park & Associates/`, tracker.db and settings.json *anywhere*.
  - electron-packager copies `app/` whole (Build App.bat:66). It does not honour .gitignore.
  - The name scan is at build.yml:204-210 (`on: tags v*`).
- **Impact for a firm:** a debugging copy of a client folder, a status page or a draft left under `app/` on J Park's office PC would be compiled into the installer and handed to every tester firm, even though the build reports a "clean" tree.
- **Fix:**
  - The .bat refuses when `git status --porcelain --ignored app` lists anything but `app/node_modules/`.
  - Before ISCC, it runs build.yml's name list (plus `_README.txt` and `after-install.json`) over the packaged folder. It runs locally and turns no Actions on.
- **Decision:** none. This extends P13.

#### S-4 **should-fix** `.github/workflows/audit.yml:17-20` - With Actions off (pilot/README rule 4), nothing checks dependency advisories before or during the pilot.
- **Evidence:** read from code.
  - `lockfiles.py audit` runs only in audit.yml. No step in RELEASE.md or the local gate runs it. I could not run it here (proxy).
  - Seen on the npm registry: app/package.json:16 pins electron 43.7.1, which is four patch releases behind 43.7.5 (2026-09-23).
  - Python parser pins are current, except pypdfium2 at 5.11.0 against 5.13.0.
- **Impact for a firm:** a published flaw in a library that opens client files (pypdf, Pillow, pypdfium2, olefile, onnxruntime) or in Electron would ship to testers, and stay on their PCs for the whole pilot, with no one told.
- **Fix:**
  - RELEASE.md gains a step before each build, on the office PC: `python tools/lockfiles.py audit`, with the build stopping on red.
  - The same on a calendar reminder during the pilot. Also turn on GitHub's Dependabot *alerts* (repository settings; no Actions minutes).
  - Bump electron to the current 43.7.x.
- **Decision:** none. It keeps decisions 207 and 211 and pilot README rule 4.

#### S-5 **should-fix** `pilot/Tester Guide.md:25` - The guide trains click-through ("It does not mean anything is wrong ... Run anyway") and gives the tester no way to tell the real installer from a substitute.
- **Evidence:** read from code; Windows-only, inferred.
  - RELEASE.md:57-59 sends the SHA-256 with the installer, over the same channel. The guide never asks anyone to compare it.
  - The build prints the hash (Build Pilot Installer.bat:72).
- **Impact for a firm:** staff at a CPA firm, a steady phishing target in season, learn that a SmartScreen warning on a J Park program is expected. A swapped download, or a later "pilot update" email, gets the same click. Firm IT or antivirus may also quarantine an unsigned program that registers a scheduled task from `%LOCALAPPDATA%`, which would stop §4-6.
- **Fix:**
  - Send the hash by a second channel: the phone, or a J Park web page.
  - Add a guide step: `Get-FileHash <file>` must match, and "Run anyway" only when it does. If the file came any other way, stop and call.
  - A short note for the firm's IT: a per-user install; two programs; one task named "Tax Document Tracker Pilot" running `tracker-api.exe --run` at the chosen interval; no network use.
- **Decision:** none. It complements P4.

#### S-6 **should-fix** `tracker/ocr.py:195-201` - The graphics pack's DLLs are loaded from `gpu-runtime` beside tracker-api.exe with no integrity check, and the pilot has no defined way to deliver them, yet the guide and tour advertise the pack.
- **Evidence:** read from code.
  - `gpu_pack()` and `preload_dlls(directory=…)` are at ocr.py:299.
  - tools/gpu_pack.py writes no hash manifest.
  - The pack is advertised at Tester Guide:68 and pilot-content.js:222.
  - The pack is 1.6 GB outside the installer (Build GPU Pack.bat:3-6).
- **Impact for a firm:** the first tester who asks gets a zip of unsigned DLLs by whatever channel is handy. Whatever that zip holds then runs inside the process that reads every client document.
- **Fix:**
  - For 0.1, the guide says the pack is not offered in the pilot.
  - Later, gpu_pack.py writes SHA-256s, and `gpu_pack()` refuses a folder with any file that does not match before loading.
- **Decision:** none.

#### S-102 **should-fix** `tracker/filer.py:983` - The Protected View mark is applied only inside `00 - Needs Review`: a macro workbook filed as a working copy, and every macro-capable file the tracker takes out of a zip or email into `_Opened`, is written unmarked (`tracker/filer.py:4619-4645` writes with no mark).
- **Evidence:** reproduced by running the engine (r2x): with D01 accepting `xlsm`, `Prepared/D01 - Charity Receipts - TY2025.xlsm` and `... (2).xlsm` (both holding `vbaProject.bin`) and `_Opened/forwarded/Receipts 2025.xlsm`, `_Opened/forwarded/Macro notes.docm` were written; only the review copy of the `.docm` was marked. `tracker/content_check.py:192` reads `.xlsm`, so a request a person widened to `xlsm` or `*` files one automatically; `tracker/manifest.py:1929-1932` only warns about `*`. Review copies of `.one`, `.pub`, `.rtf` are unmarked too (`_may_carry_code`, `tracker/filer.py:1023-1032`).
- **Impact for a firm:** a business client's macro workbook is filed into `Prepared` where staff open working copies every day; Office then shows an "Enable content" bar instead of blocking the macros outright. Windows would have marked the same file had staff saved it from Outlook or unzipped it themselves; the tracker's copy loses that.
- **Fix:** mark every file the tracker writes from a client's bytes whose type Office opens - working copies in `Prepared` of any macro-capable type and everything written into `_Opened` - failing closed as the review copy does; and mark every review copy whatever its type (the code's own note: "marking a harmless file costs nothing"). Consider refusing macro types in a request's file types.
- **Decision:** reopens decision 190 (where the mark applies).

#### S-103 **should-fix** `tracker/households.py:116-117` - The inbox link is checked only for an `http://`/`https://` prefix (`tracker/records.py:854-866`, also `tracker/households.py:183`); any host is accepted, and the same link can be recorded on two households, so a paste slip puts client A's inbox link in client B's letter.
- **Evidence:** read from code (no comparison across households anywhere in `tracker/households.py`, `tracker/records.py`, `tracker/api.py`'s create/edit-household); `link_problem` returns clean for `http://drive.google.com.example.net/x` and `https://user:pw@evil.example/login`.
- **Impact for a firm:** the letter is the firm's; a staff member copying links between households can invite one client to another client's drop folder. If that folder was shared "anyone with the link", or someone approves the access request, client B can see client A's documents waiting there and drop into A's return.
- **Fix:** refuse a link another household already records, naming that household; since the product supports Google Drive only, require `https://drive.google.com/` (or show a warning for any other host); show the household's name beside the link on **Mark as shared**.
- **Decision:** reopens decision 137 (L5).

### Nit

#### S-7 **nit** `app/renderer/pilot.js:77-78` - No test ever parses or runs pilot.js or tour.js with Actions off, and the terms screen fails open when pilot.js throws.
- **Evidence:** read from code.
  - gate.yml:98-100 checks three files, and only on GitHub.
  - test_pilot reads text. test_pilot_installer.py:140-147 executes only pilot-content.js.
  - `node --check` passes today (run).
- **Impact for a firm:** a typo in pilot.js would ship an app that opens straight to work with no terms shown, and every test would pass.
- **Fix:** a pytest that runs `node --check` on every `app/**/*.js` (skipped without node), so the local gate covers it. A static overlay in index.html that pilot.js removes would fail closed, but would reopen P10.
- **Decision:** none.

#### S-8 **nit** `pilot/Build Pilot Installer.bat:40` - The version is read by *executing* pilot-content.js in Node, while the tests read the JSON between the markers.
- **Evidence:** read from code.
  - No test pins the text outside the markers.
  - test_pilot_installer.py:140-147 checks the version's shape, not that it equals `content()["edition"]["version"]`.
  - `/DAppVersion=%VER%` is unquoted (line 65).
- **Impact for a firm:** a stray statement in "the one file Jason edits" runs on the build PC with full rights, and could make the installer name and the badge disagree.
- **Fix:**
  - Read the region as JSON: `node -e` that reads the file as text and `JSON.parse`s the region.
  - Test that the text outside the markers is exactly the fixed prologue and epilogue, and that the build's value equals the badge's.
- **Decision:** none. This keeps P13's one home for the version.

#### S-9 **nit** `app/main.js:381-396` - Electron hardening is left at its defaults.
- **Evidence:** read from code.
  - No fuses: RunAsNode, NODE_OPTIONS and `--inspect` stay enabled.
  - No asar and no asar integrity (Build App.bat:66).
  - No `setPermissionRequestHandler`.
  - The CSP has no `base-uri` or `form-action` (index.html:8-9).
  - The IPC handlers do not check the sender frame.
- **Impact for a firm:** none today. There is no injection path, and anyone who can pass a flag can already run tracker-api.exe. Each is defence in depth for a future mistake.
- **Fix:**
  - Flip the three fuses with `@electron/fuses` in Build App.bat (a new pinned dev dependency).
  - Add `base-uri 'none'; form-action 'none'` to the CSP.
  - Add `session.defaultSession.setPermissionRequestHandler((…, cb) => cb(false))`.
  - Upstream first, per pilot/README rule 1.
- **Decision:** none.

#### S-10 **nit** `app/main.js:208` - The packaged shell passes its whole environment to the API, so P18's "the pilot can never touch the real product's data" holds only while TRACKER_DATA_HOME and TRACKER_STORE are unset.
- **Evidence:** read from code; the harness run used inherited overrides.
- **Impact for a firm:** at J Park, where both products may share an account, one leftover variable points the pilot at the real store.
- **Fix:** when `app.isPackaged`, drop `TRACKER_*` from the environment the shell passes, keeping only the two variables it sets.
- **Decision:** none.

#### S-11 **nit** `tracker/scheduling.py:428-444` - `schtasks` is run by bare name.
- **Evidence:** read from code. Windows finds a bare name in the program's own folder and the working folder before System32. The .bat files (E-10) and setup.iss:54 use full paths.
- **Impact for a firm:** none within scope, since those folders are writable only by the same account. It is an inconsistency with the house rule.
- **Fix:** `os.path.join(os.environ["SystemRoot"], "System32", "schtasks.exe")` on Windows.
- **Decision:** none.

#### S-12 **nit** `.github/CODEOWNERS:6-14` - CODEOWNERS covers root `*.bat` but not `pilot/installer/`, `pilot/*.bat`, app/main.js, app/preload.js or app/renderer/index.html (the CSP).
- **Evidence:** read from code. Branch protection could not be seen.
- **Impact for a firm:** a change to the installer or the shell's boundary needs no named owner's review.
- **Fix:** add those five paths.
- **Decision:** none.

#### S-13 **nit** `.claude/settings.json:3-68` - The deny list does not name the client README `_README.txt`, which lists what a client sent.
- **Evidence:** read from code. Nor does it name after-install.json or `passes/*.json` when the data home is overridden. Those name client folders and files.
- **Impact for a firm:** an AI agent in a checkout could read client-describing text there.
- **Fix:** add those three names, and extend the P19 test.
- **Decision:** none.

#### S-14 **nit** `app/renderer/pilot-content.js:192` - The tour says the status page is "A file on this computer". It is written into the clients root, which syncs wherever that folder syncs, and it names every client.
- **Evidence:** read from code.
- **Impact for a firm:** a tester may leave it somewhere shared that they would not, had they known.
- **Fix:** "A page in your clients folder, naming every client; not a client portal."
- **Decision:** reopens P22.

#### S-104 **nit** `tracker/filer.py:2233-2238` - A symlink or junction in an inbox is skipped silently: it is never followed or moved (verified), but `unreachable_drops` excludes links (`tracker/filer.py:2296`), so it is named nowhere - not in the reply, the index, the practice page or the letter; and on Python 3.11 `rglob` still walks through a junction before the filter drops what is behind it (`tracker/door.py:132` says so).
- **Evidence:** reproduced by running the engine: `link-to-outside.txt` and `link-to-private-tree` stayed in the inbox with `warnings: []` and no row; walk behaviour read from code, Windows-only, inferred.
- **Impact for a firm:** low - a client cannot make a link through Drive. Something a local user or a sync tool leaves in an inbox waits for ever unseen, and a junction to a large folder slows every pass.
- **Fix:** name links in the inbox in the pass warnings as unreachable drops, and walk the inbox with `os.walk`/`scandir` that never enters a link.
- **Decision:** none.

#### S-105 **nit** `tracker/store.py:1862-1864` - A row's `prepared_location` is admitted for reading anywhere in any household's inbox or year folder (`writes=False`, `tracker/layout.py:955-958`), though a working copy only ever lives under its own return.
- **Evidence:** read from code; not run.
- **Impact for a firm:** only a hand-edited or corrupted record reaches it: the app's **Open** or the scanner's proof would point at another household's original, shown to staff only.
- **Fix:** admit `prepared_location` and `also_filed` only as `IN_RETURN` of the row's own return.
- **Decision:** none (narrows decision 187's read rule for one field).

#### S-106 **nit** `docs/runbook.md:1622` - A document that names none of the return's people (a wrong-client drop) has its original moved into this household's client-visible year folder before a person sees it, and the runbook's step for `reasons.NAME_NOT_ON_PAGE` says to file it where it belongs but not to take the original out of the folder this household can see.
- **Evidence:** reproduced by running the engine: `Jane Doe W-2 2025.pdf` now rests in `Clients/Smith Family/2025/` and parks with `name-absent`.
- **Impact for a firm:** if staff misdrop another client's document into a household's inbox, that household keeps seeing it in its year folder until someone moves it by hand.
- **Fix:** one runbook line under `NAME_NOT_ON_PAGE`: when it is somebody else's, move the original out of this household's year folder too; consider saying so on the card.
- **Decision:** none.

#### S-107 **nit** `tracker/runner.py:2283-2287` - The practice page, written into the synced clients root, prints this machine's full store path (the Windows user name) and other machines' host names, with a `python -m tracker.checkpoint` command a frozen pilot install cannot run (`tracker/runner.py:2520-2521`).
- **Evidence:** read from code; not triggered in the run.
- **Impact for a firm:** small: account and machine names reach every staff member's copy of the Shared Drive, and the tester cannot follow the step.
- **Fix:** name the data folder by its `%LOCALAPPDATA%` form and give the app's own action instead of a command line.
- **Decision:** none.

## By design: answers for testers

| Item | Why | Decision row |
|---|---|---|
| Unsigned installer; Windows shows SmartScreen | A certificate can come later | P4 |
| Terms acceptance lives in the window's local storage, can be cleared or edited on the PC, and is no evidence J Park holds | No new channel. If the no-warranty term matters, get a signed pilot letter by email | P9 |
| Uninstall leaves `%LOCALAPPDATA%\tax-document-tracker-pilot` (index of every client's documents, logs) and settings.json | Client data is never the installer's to delete. Tell testers to delete that folder when the pilot ends; originals and copies are in the clients folder | P12 |
| Reinstalling reads the old settings.json and registers the schedule at first launch, before the terms show | One-time steps run themselves | P12, decision 209 |
| Uninstalling the computer that runs the schedule leaves no computer running it until another presses Move schedule here | The designation lives in the private tree | decision 209 |
| Any staff PC on the same clients folder can move the schedule to itself | One firm, one schedule | decision 209 |
| The error log keeps full error text, which can quote a document, on this PC | A programmer needs it; the screen never shows it | decisions 190, 193 |
| The data folder is not encrypted; the account and admins can read it | Not a wall | decision 186 |
| Program folder, settings.json and gpu-runtime are writable by the same Windows account | Per-user, no-admin install | P4, proposed accepted |
| A copied reminder sits on the Windows clipboard (and its history or sync, if the firm turned that on) | It is pasted into the firm's own email | proposed accepted |
| Choose-folder opens at Windows' default place | The typed box is checked either way | proposed accepted |
| The practice page `status.html` names every client and every parked file name, in the clients root, synced to Drive | The root is the firm's own and never shared with a client; its audience is the private tree's audience | decision 91; runbook §2 |
| An email or zip, and a card with no **Open**, is opened only on a machine with no Drive sign-in | The app offers **Open** only for documents it read; everything else is procedure | decision 184, 190 |
| Container detection by extension only | An `.xlsx` or `.docx` is a zip and is a document | decision 143 |
| Attachment bytes are written to `_Opened` in the private tree | The container stays the client's original; each attachment is sorted like a drop | decision 143 |
| A program's original rests in the client's year folder; a `.url`, `.lnk` or `.scf` there can make Explorer reach out when the folder is merely listed | Originals are never altered or removed; that is Windows's behaviour on any folder holding client files | proposed accepted (decision 190 covers the no-copy half) |
| Originals are numbered `W2 (2).pdf` when two share a name in the flat year folder | The year folder is flat; the first keeps its name | decision 147 |
| The move out of the inbox is not written down before it happens | A crash leaves the file in the year folder; the next pass files or parks it | decision 119 |
| Every write is whole or absent; a killed write's temp is swept next pass | Atomic replace; copies proved against the recorded digest | decision 155 |
| A lock from another computer waits out 2 h 5 min; a lock's pid and host are trusted | Locks live in the private tree; only one machine may run a root | decision 137 (L6), 171 |
| A typed Date Pattern can cost one document its 600 s stop | Shape rule bounds it; the stop parks the file and is kept | decision 189 |
| A `.tmp.driveupload` or placeholder is left alone as waiting | Never read, never force-downloaded | README; runbook |
| The link check is a prefix check | A letter only ever opens a web address | decision 137 (L5) (see S-103) |
| No memory cap on the reading child off Windows | Development only; Windows has the job object | decision 169 |

## Cross-references between the halves

- S1 asked S2 to confirm that a review copy's recorded location can only be its own return's Needs Review folder. S2's answer (S-105): the store admits a `prepared_location` anywhere in any household's inbox or year folder for reading. So S-2's fix must add the stricter check it already names - the API reports a review copy only when it lies lexically under this return's Needs Review folder - and not rely on the store.
- S1 asked S2 which parsers' messages can carry document text (for S-1's wording). S2's Verified section: pypdf quotes the bytes it choked on, Pillow names the chunk, the email parser repeats the header; all are kept whole in `tracker-errors.log` (`tracker/errors.py:3-8`). S-1's wording stands.
- S2 asked S1 to confirm the shell offers no way to open one of S-101's file types from the app. S-2: today the shell refuses every review copy (no kind), so there is none; S-2's fix adds `is_program` to the refusal so that stays true once review copies open.
- S2's note that the practice page's acknowledge step names a `python -m` command a frozen install cannot run is S-107, and is also a UX matter for `ux-review.md`.
- `tests/test_ocr.py:116`, the proof that a full read opens no socket, cannot run in the cloud (no reading engine). It runs in Jason's Windows step (RELEASE.md step 3).

## Not reviewed

### S1 - the shell, the PC and the build

- **Windows-only behaviour, inferred and not observed:** installer run, SmartScreen, antivirus reaction, the packaged window, schtasks registration, drive types and junctions.
- **The OSV audit:** blocked by the proxy.
- **The Electron zip's download chain:** @electron/get and the packager's checksum source; node_modules is not installed here.
- **Local crash dumps:** whether Electron 43 writes Crashpad minidumps under `%APPDATA%\Tax Document Tracker Pilot` without `crashReporter.start`. They would hold renderer memory, including client names.
- **The designation file's race:** two PCs claiming within Drive's sync lag (scheduling.claim). This needs two Windows PCs on one Drive.
- **Engine internals behind the door** (S2).

### S2 - the engine and its outputs

- Windows-only behaviour, inferred from code only: writing `:Zone.Identifier` on NTFS and on Drive's `G:`; junctions in an inbox or swapped for a year folder; the 260-character limit on moving a 200-character original (it moved uncut here); placeholder attributes; the job-object memory cap against a workbook shared-strings bomb.
- OCR paths (no engines here) and `pypdfium2` rendering limits beyond code reading.
- A fed-household pass end to end (read from code and decision 204 only: parks stay home; the README and letter speak only for their own returns).
- Recovery after a pass killed half-way (checkpoint, intents) - read, not provoked.
- Drive's own semantics (same-name files, Contributor edit rights on files in the inbox) - from Drive's documented roles, not tested.
- The whole suite (policy: affected tests only).
