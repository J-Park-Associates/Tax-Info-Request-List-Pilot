# Architecture

How the app is put together: the processes, the Python package by layer,
the tools, the tests, the files it writes, the decisions that shape all of
it, and how a package is built for each system. The README says what the
app is for; `docs/runbook.md` is the operator's side; `docs/storage.md` is
where the facts live; `docs/repo-map.md` is the module-by-module map an
agent reads. This page is the overview between them.

## The shape of it

Three programs share one codebase:

| Program | What it is | Where |
|---|---|---|
| The desktop app | An Electron window around plain HTML, CSS and JavaScript: a side panel of four pages (Overview, Needs Review, Reminders, Households), the request-list editor, the review sheet, the reminder sheet, one Sort Now button. It draws; it decides nothing. | `app/main.js`, `app/preload.js`, `app/renderer/` |
| The engine | A Python process the shell starts once per app session (`python -m tracker.api --resident`, or the frozen `tracker-api` in a package). It answers the shell's commands as JSON over its standard input and output: list, firm, household, the editor's saves, a pass. | `tracker/api.py`, `tracker/resident.py` |
| The scheduled pass | The same engine run unattended by Task Scheduler or launchd: for every return of every household under the clients root, file the inbox, scan what was filed, and on the draft day write the chase email and stop. | `tracker/runner.py`, `tracker/scheduling.py` |

One more process exists during a pass: **the reading child**. A scan or a
photo is read in a child process of the pass with a lifeline to its parent,
a memory cap and a stop clock, so a page the reader cannot cope with ends
the child and parks the document, never the pass (decision 169). Each
process has its own scratch folder under the app's data folder; nothing
temporary is ever written beside a client's file.

## The package, by layer

`tracker/` is one Python package of forty-three modules in six layers.
`tests/test_layers.py` pins the layer of every module and that no load-time
import points upward; an import inside a function is a call-time import
and may point anywhere. The scanner never imports the filer; the filer reaches
it at call time through a rescan. The three call-time cycles that remain are
named in `tests/test_layers.py`.

**Layer 0: words, files and locks.** The standard library and nothing of
the package but each other.

- `__init__.py`: the package docstring and `STANDING_RULES`, the four rules
  worded once; it imports nothing (decision 99).
- `reasons.py`: every refusal said once and known by its code: the note the
  scanner writes, the sentence the client is asked with, whether the row is
  the firm's to look at.
- `errors.py`: what an error is called where a person sees it: the class,
  and for a file error its errno's name, never a message that could carry a
  path (decision 190).
- `fsio.py`: the one way the app writes a file, whole or not at all: a temp
  beside the target, then one atomic replace.
- `locking.py`: one lock per engagement, held across a whole pass.
- `ledger.py`: the engagement's append-only record, one JSON object per line.
- `checkpoint.py`: what this machine last saw of every record, so a record
  edited elsewhere is noticed (decision 159).
- `settings.py`: the settings file beside the app (the clients root, the firm,
  its phone number), the data folder's place and its refusals, the Mac floor.
- `hold.py`: the per-reply memo: the machine's answers held for one read-only
  reply or one household of a pass and dropped after it, never an error;
  `settings.py` reads it through the module (it re-exported it until P2.13).
- `errlog.py`: the one local debug log: an unexpected error's full words and
  every warning, in a rotating file beside the database and nowhere else;
  `settings.py` neither imports nor offers it.
- `layout.py` and `door.py`: the shape of the clients root, named once
  (decision 125), and the disk half of it: a checked root, a return's folder
  from a typed path.
- `page.py`: the markup both of the firm's pages are drawn with.
- `progress.py`: the one progress-line format a running pass is watched by.
- `replies.py`: the shape of every reply the API prints, written down once
  as `TypedDict`s; the recorded replies and the screen's failure kinds are
  held to it.
- `bounds.py`: the value rule's bounds (decision 187): every limit a value in
  the record is held to, and the one phrase each refusal says, worded once for
  the editor and the store's gate; `records.py` imports the ones it reads (it
  re-exported the rest until P2.13).
- `firm_cache.py`, `page_rows.py`, `firm_pages.py`: the firm view's cache,
  the practice page's kept rows and the firm lists cut into pages, so the
  app opens on hundreds of households without reading every record first.

**Layer 1: the record and the catalog.**

- `records.py`: the record types every layer above names (an index entry,
  evidence, the engagement's fields) and each one's own serialisation.
- `manifest.py`: the request list: its schema, its validation, and its
  reading from and writing to the record (decision 104: the request list
  is the record's, edited only in the app).
- `store.py`: one SQLite store per account in the data folder, a rebuildable
  view of every record; the record is the truth and the store is the index.
- `index.py`: the index as the record holds it: the words its rows carry,
  their readers (`read_index`, `ensure`, the moved and interrupted sentences
  read back) and the one proof of a row's bytes; `filer.py` imports them and
  re-exports them.
- `templates.py`: the per-form request catalog, the only source of the
  checklists.
- `households.py`, `scaffold.py`: the household's own record, and the folders
  a return's request list becomes.
- `validators.py`: tiers one and two: does the file exist, is the extension
  allowed, is the PDF readable, does the photo open, is it a cloud
  placeholder.

**Layer 2: reading a document.**

- `content_check.py`: tier three, the one reading of a document, used by the
  router and the scanner alike: text from a text layer (pdfplumber,
  openpyxl, plain text) or from the reader, tested against the row's keyword
  and date rules, with a verdict cache keyed by the file's content.
- `ocr.py`: the reader: RapidOCR on ONNX Runtime with its three models
  shipped in the app; the graphics card when the pack beside the app works
  and the processor otherwise; the preparation of a page in memory before it
  is read (drawn at 300 dots per inch, levelled, thresholded, cleared of
  specks and box lines); the download path refused outright.
- `containers.py`: an email or a zip opened in memory, each attachment handed
  back under a safe name, nothing inside ever run (decision 143).
- `names.py`: whose document this is: the matcher for the names a return's
  people put on their papers (decision 128).
- `router.py`: which single request a dropped file belongs to, judged on the
  evidence in order, refusing to guess; everything unclear parks with its
  reason and its shortlist.

**Layer 3: the stages of a pass.**

- `filer.py`: moves each original out of the household's one inbox into the
  client's folder for the year, untouched, and files a renamed working copy
  on the firm's side or parks it in `00 - Needs Review`.
- `scanner.py`: walks the working copies, runs the three tiers, resolves each
  request's status (override- and revert-aware) and records the result.
- `reminder.py`: drafts the client's chase email in four stages measured
  against the due date, or holds it for a person; there is no send.
- `review.py`: the ranked shortlist a parked file carries.
- `rollover.py`: a returning client's next-year request list from their own
  prior year.
- `registry.py`: every engagement under the clients root, by its record.
- `view.py`: the return's Status Report page.

**Layer 4: the unattended run.**

- `runner.py`: the whole scheduled task: for every engagement, file, scan,
  and on the draft day draft; the status page over the whole practice; the
  run log of counts and codes.
- `scheduling.py`: the Task Scheduler XML, or on a Mac the launchd agent.
- `after_install.py`: every one-time step after installing or upgrading, run
  by the installer, by the app at its first start after the program changed,
  and by saving the clients root, so none depends on a person remembering it
  (decision 209).

**Layer 5: the door the shell knocks on.**

- `api.py`: the JSON command layer; `COMMANDS` is the list and the module
  docstring is pinned to it. The editor's words live here.
- `resident.py`: the loop over the API that keeps one engine alive for an app
  session.

`api_entry.py` is the one script a package freezes: the API by default, the
scheduled pass when `--run` comes first, the reading child when
multiprocessing asks, the setup door, and on a Mac the floor check before
anything else.

## The tools

`tools/` holds the programs a person or a session runs on the repository,
never the app:

- `repo_map.py`: builds and incrementally updates the repository map; derives
  imports, exports, command lines, test coverage and hashes from source and
  merges the curated layer (`docs/repo-map.curated.json`) on top.
- `vocab_report.py`: which keyword in each catalog is reached by which IRS
  form in the corpus, tested the way the router reads.
- `learned_keywords.py`: what the staff taught the router across every
  engagement, grouped by request, so a keyword several clients needed
  becomes a catalog row.
- `backtest.py`: routes the firm's own already-sorted documents at the office
  and scores the router against where a person filed each one; the report
  carries counts and never a name.
- `corpus.py`: the harness the backtest and the reader bench share, and the one
  reader of the expectations file the firm's own documents are scored against;
  imported by the two tools and by `tests/test_real_corpus.py`, with no command
  line.
- `reader_bench.py`: measures which reading settings help on the firm's own
  scans and photos, one variant of a fixed grid at a time, counts only.
- `lockfiles.py`: the supply-chain lock: fills, checks, stamps and verifies
  the hash-checked lock files.
- `typecheck.py`: runs the type checker, mypy, a development tool installed
  from its own lock, and fails when any file has more type errors than
  `docs/typecheck-baseline.json` records; `update` lowers the counts after
  a fix and never raises one.
- `gpu_pack.py`: copies the NVIDIA libraries out of an environment into the
  optional graphics card pack.

`docs/tools.md` is their page.

## The tests

`tests/` has one file per module, named for it, plus the guards that cut
across the package:

- `test_layers.py` pins the layer table and the import directions.
- `test_single_source.py` holds every sentence that is typed in one place
  and quoted in others: the standing rules, the app's own refusals, the
  README's tables, the floor, the data folder's name, the one-time-step
  wording.
- `test_repo_map.py` fails when the committed map has drifted from the tree.
- `test_tripwire.py` and `conftest.py`: every test gets a settings folder
  and a store of its own, and the run fails if any test, or any process a
  test starts, reaches the checkout's real ones (decision 185).
- `samples.py` and `child_readers.py` draw the made-up documents and run the
  real reader in a child, the way a pass does. No test holds a client's
  document; the corpus under `tests/irs/` is blank IRS forms, and the walk
  over it is the `corpus` marker.
- No test file imports another. What two files need goes in a helper module,
  and `test_suite_shape.py` fails when a test file, a helper module or
  `conftest.py` imports a test file, or a helper module is imported by none:
  `samples.py` (the made-up documents; `text_pdf` has a style for each of the
  three writers it replaced), `builders.py` (a return, a document dropped
  into it, the filer's scenes), `passes.py` (whole passes over a household),
  `children.py` (waiting for the reading child), `node_harness.py` (the
  renderer's JavaScript run under node, and `js_function`, the one way to cut
  a function out of a script), `css_rules.py`, `api_driver.py` (the command
  line as `main.js` drives it), `wording.py`, `import_graph.py` and
  `routing_cases.py`. The typed cases, the workbook cases and the blank forms'
  placements are `routing_cases.py`'s (decision 70), which the suites import and
  the vocabulary report reads; the corpus readers are `tools/corpus.py`'s. No
  tool imports a test file.

The suite runs in parallel with pytest-xdist (`python -m pytest -q -n auto`),
and the gate runs each affected file as its own process under the floor
interpreter and the office's (CONTRIBUTING.md).

## What it writes, and where

Three places, kept apart on purpose (decision 186, `docs/storage.md`):

| Place | What is there |
|---|---|
| The clients root (a Shared Drive the firm owns) | The client tree: each household's folder, its one inbox, its year folders of untouched originals. The private tree: each return's record (`_ledger.jsonl`), its Status Report, its working copies and review folder, the hidden folder a container's attachments are taken out into. The practice's status page. Only what a client or the firm must see on the drive. |
| The settings folder (beside the app) | `settings.json`: the clients root, the firm and its phone number. Nothing about a client. |
| The data folder (on this machine's own disk, never synced) | The store, the record checkpoint, the run log, the last-pass note, the after-install note, the error log, the firm view's cache and the page's kept rows, the running passes' progress files, every process's scratch folder. Everything here can be rebuilt from the records or thrown away. |

The record is the truth: an append-only journal in the engagement folder
that the drive syncs. The store is an index built from it and never synced.
A checkout holds none of these; `.gitignore` names each one.

## The decisions that shape it

- **Deterministic, and no generative AI near a document.** Routing is the
  manifest's keyword and period rules in evidence order; the reader is a
  fixed model on a fixed runtime; the shortlist is ranked by rule. The unclear
  goes to a person. This is the first standing rule, and the reason a CPA
  firm can trust the app with client files.
- **Offline, local execution.** Nothing in the reminder or scheduling path
  touches a mail client or the network, and `tests/test_layers.py` pins that
  no module under `tracker/` imports one. The reader's models ship in the
  package and its download path is refused; the app starts offline; the only
  online step is the install, which reads hash-checked locks. The weekly
  dependency audit runs in CI, never in the app. There is no telemetry.
- **The standard library first, `pathlib.Path` throughout.** Each dependency
  is one more thing the firm must trust, so a library is added only where
  the standard library cannot do the job (PDFs, images, the reader, SQLite
  is in the standard library already). Every path is a `Path`, every write
  goes through `fsio`, and every file the app owns is named once, in one
  constant, that documents and tests quote.
- **Originals are never altered.** A pass moves an original byte for byte
  under its own name and works on copies; every move is a line in the record.
- **One machine runs a clients root.** The engagement lock is a file, and a
  file a cloud client syncs between two machines is not a lock; the
  designated machine is named in the private tree, and the after-install step
  registers the schedule there and nowhere else.
- **Hash-checked, reproducible installs.** Every install, on a desk and in a
  build, reads a lock that names the SHA-256 of every file (decision 191); a
  package is built from a clean commit and records which one.
- **One-time steps run themselves.** Anything that must happen after
  installing or upgrading is in `tracker/after_install.py`, run by the
  installer and by the app itself (decision 209).
- **Fail loudly, in the software's words.** A refusal is a sentence a person
  can act on, and an error log names the error's class, never a client's path.

## Packaging

The engine is frozen with PyInstaller from `api_entry.py` by the committed
`api_entry.spec`: RapidOCR's package without the engines the app does not
use, its three models, ONNX Runtime, the headless OpenCV without its video
library; on a Mac an arm64 binary signed ad hoc, on Windows the console's
icon. The shell is packaged by Electron Packager from `app/package.json` and
`app/package-lock.json`, installed with `npm ci`. Both halves are made in a
fresh environment from the locks, so a build carries what the commit names
and nothing the machine happened to have.

| Script | System | What it makes |
|---|---|---|
| `Build App.bat` | Windows | The portable folder: freezes the engine, packages the shell, copies the freeze beside it, writes a build-info text file naming the commit and the tool versions, and proves the folder holds no store or log or settings with `tools/check_package.ps1`, the check `build.yml` runs too. |
| `pilot/Build Pilot Installer.bat` | Windows | The installer, with Inno Setup (`pilot/installer/setup.iss`), from a clean commit; the version comes from `app/renderer/pilot-content.js`, its one home. |
| `Build GPU Pack.bat` | Windows | The optional graphics card pack: NVIDIA's CUDA and cuDNN libraries from `requirements-gpu.lock`, one folder to copy beside the packaged engine on a machine with a supported card. Without it the reader reads on the processor. |
| `build-mac.sh` | Mac | The disk image, in seven steps whose order is the point: freeze, package, copy the freeze into the bundle, write the build-info file, sign the bundle inside out and verify the seal, prove the bundle holds no store or log or settings, make the image and its SHA-256. Built only on an Apple silicon Mac, from a clean commit. |
| `Setup.bat`, `setup.command` | Both | Not a package: the from-source setup. The app's own private Python from the locks, Electron from its lock, then the after-install step. |
| `Start App.bat`, `start.command` | Both | Starts the app from source and installs nothing; refuses in one sentence when the locks have moved since setup. |

On GitHub, `ci.yml` runs the reusable `gate.yml` (tests, ruff, the map and
vocabulary checks, the type check on Linux, and that the shell parses) on a push to `main` and once
when a pull request is marked ready; `build.yml` builds and smoke-checks the
Windows package from a protected tag; `audit.yml` reads the locks weekly and
asks OSV about every pinned package, installing nothing. The local gate in
CONTRIBUTING.md is the one that must pass before any of them is asked.
