# Pilot 0.3 - the rename to "Tax Document Console" and the move to 0.3 - SPEC

Status: written 2026-09-30, 2:30 PM Pacific, by the SPEC author, for a
builder and a separate reviewer. It turns two decisions Jason has already made
into build detail and re-opens neither: **P155** (the rename; Q1-Q4 answered
(a), (a), (a), (a)) and **P140** (the version moves to 0.3 once; no 0.2 tag).
Branch `claude/rename-0.3` (it already holds P184). Proposed new rows are in
section 11; nothing in `pilot/DECISIONS.md` is edited by this SPEC.

**Hard rule kept.** No step here opens, reads or moves anything under
`%USERPROFILE%\PilotTest` or any Clients folder. The carry-over moves no
client file: it copies one settings file and removes one scheduled task.

**How it is built.** One builder, one worktree, two commits in this order,
because both commits edit `tests/test_single_source.py` and the gate tests
in section 7 span both (so no parallel split):

- **Commit A - the name, the version, the installer, the carry-over.**
  Sections 2, 3, 4.1-4.4, 6.1, 7.1-7.3, 8.
- **Commit B - "Tracker" on screen becomes "App" (Q3) in the engine's
  sentences and the documents' prose.** Sections 4.5-4.6, 6.2, 7.4. Kept as its
  own commit because it touches engine modules shared, by hand-merge, with the
  original repository (P17), so a later upstream merge can find these lines in
  one place.

---

## 1. What Jason and a tester will notice

- The window title, the taskbar, Alt+Tab, Help > About and the side panel's
  brand band say **Tax Document Console**. The side panel's badge and
  Help > About say **Pilot 0.3**.
- The installer file is **`Tax-Document-Console-Setup-0.3.exe`**. The Start
  menu entry, the optional desktop icon, the "Launch ..." box at the end of
  setup and the Windows **Settings > Apps** entry all say Tax Document Console.
- Task Scheduler shows a task named **Tax Document Console**; the task named
  Tax Document Tracker Pilot is gone after the app's first start.
- A PC that had the earlier name keeps its clients folder, its schedule
  choice (on or off, first run, how often), its Sort history and its column
  widths. Nothing has to be set again. The old Start menu entry and desktop
  icon are gone; the new ones replace them.
- Failure words on screen say "App", not "Tracker": **App Failed**,
  **No Reply From the App**, **The App Could Not Start**, **Folders the App
  Leaves Alone**, and the editor reason **Received Outside the App**.
  Longer sentences say "the app" where they said "the tracker".
- The Tester Guide, the pilot README, the release steps and the runbook use
  the new name.
- Unchanged, on purpose: the data folder
  `%LOCALAPPDATA%\tax-document-tracker-pilot`, and, on a PC upgraded from the
  earlier name, the program's own folder
  `%LOCALAPPDATA%\Programs\Tax Document Tracker Pilot` (rulings R2 and R3).
  A new install goes into `%LOCALAPPDATA%\Programs\Tax Document Console`.

---

## 2. Design rulings and their reasons

**R1. One home for each name.** The new name has one home,
`app/package.json` `"productName": "Tax Document Console"`. Everything else
reads it: the window title (`app/main.js:687`), the scheduled task
(`tracker/scheduling.py:110`, `TASK_NAME = product_name()`), Help > About
(`tracker/api.py:1560`, `:5351`), the packaged program's name
(`Build App.bat:31`), and the fallback error log's folder (`app/main.js:141`).
`tracker/api.py:1353` types "Tax Document Console" today for the side panel
(the 0.3 lanes wrote it, P155's "new text names the app"); it becomes
`product_name()`, so there is no second copy. The earlier name gets one home
too: `tracker/settings.py` gains
`EARLIER_PRODUCT_NAME = "Tax Document Tracker Pilot"` (the pilot's name
before P155). The places that cannot import Python (the installer script, the
two Windows check scripts, `app/package.json`'s `config.userDataName`) type
it, and a test holds each copy equal to the constant.
*Reason:* the repo's single-source rule (`test_the_product_name_has_one_home`);
a second copy is how a rename goes half-done.

**R2. An upgrade installs over the earlier copy, in its own folder.**
`pilot/installer/setup.iss` keeps its `AppId` (the line says never change it)
and keeps Inno Setup's default `UsePreviousAppDir=yes`, so a PC that has the
earlier name is upgraded in place, in
`%LOCALAPPDATA%\Programs\Tax Document Tracker Pilot`. A new install uses
`DefaultDirName={localappdata}\Programs\Tax Document Console`.
*Reason:* `settings.json` lives beside the program (`tracker/settings.py:175-190`),
and decision 186's left-behind move reads the program's folder. Installing an
upgrade into a new folder would leave the earlier program runnable in the old
one, where it would register its old task again at its next start. Installing
over the earlier copy is also Windows' standard upgrade behaviour (Jason's
2026-09-28 rule: Windows behaviour follows Microsoft's guidance). The folder's
name is seen only by someone browsing AppData, and Q2 says the install keeps
what it has.

**R3. The data folder keeps its name.** `%LOCALAPPDATA%\tax-document-tracker-pilot`
(`tracker/settings.py:120` `DATA_HOME_NAME`, equal by test to
`app/package.json:2` `"name"`) is not renamed, and nothing moves it.
*Reason:* it is `package.json`'s internal `name`, the same class as Q4's
internal names; it holds the store, the checkpoint and the run log; and the
scheduled pass can start at any minute between the upgrade and the app's
first launch, so a moved folder would race a pass that builds a new, empty
store beside the old one. Keeping it is the most literal reading of Q2's
"keeps its data folder". Documents that name it (Tester Guide line 76,
`pilot/RELEASE.md` line 14, the runbook) keep naming it; section 11 proposes a
row recording this ruling.

**R4. Electron's own folder keeps its earlier name.** Electron keeps the
page's local storage (the column widths, `app/renderer/pages.js:85`, and the
cached terms and tour answers, `app/renderer/pilot.js:25-26`) in its
`userData` folder, which it names after `productName`
(`%APPDATA%\Tax Document Tracker Pilot`). Renaming `productName` would
silently start a new, empty folder. So `app/main.js` sets
`app.setPath("userData", path.join(app.getPath("appData"), PKG.config.userDataName))`
before `app.requestSingleInstanceLock()` (`app/main.js:723`) and before
anything else asks for a path, with `app/package.json` `config.userDataName`
= "Tax Document Tracker Pilot" (equal by test to
`settings.EARLIER_PRODUCT_NAME`). *Reason:* Q2 (the install keeps its
settings) with nothing to copy or move; the single-instance lock, which
Electron keys on this folder, stays the same across the upgrade.

**R5. The settings file carries over only when it is missing.** New
after-install job, section 3.1. It runs only from the packaged program, never
from source (from source, `settings.json` is the checkout's own, and the
office PC may also have the pilot installed). *Reason:* R2 already keeps the
file on an upgrade; the job covers the one other case, a PC where the earlier
copy was uninstalled (the uninstaller deliberately leaves `settings.json`,
`setup.iss` lines 49-53) and the new name then installed fresh.

**R6. The scheduled task is replaced by the after-install step, not the
installer.** New job, section 3.2: after the schedule job has registered
**Tax Document Console**, the step removes **Tax Document Tracker Pilot**.
*Reason:* P155 names `tracker/after_install.py` (decision 209: one-time steps
run themselves); the step already owns registering and removing this
computer's task, knows whether this computer runs the schedule, and records a
failure so the next launch tries again. The installer cannot know the
schedule choice.

**R7. The installer replaces the old shortcuts and program file.**
`setup.iss` gains `UsePreviousGroup=no` and an `[InstallDelete]` section
(section 6.1) that deletes exactly the earlier Start menu shortcut, its
now-empty folder, the earlier desktop icon and `{app}\Tax Document Tracker Pilot.exe`.
The uninstaller removes the task under either name. *Reason:* Q2 says the old
shortcut is replaced; shortcuts are the installer's own files, so the
installer removes them; exact paths only, never a wildcard, so nothing else
in the Start menu or on the desktop can match.

**R8. The firm's production product is never touched.** The earlier name is
"Tax Document Tracker **Pilot**". The production tracker's name
("Tax Document Tracker"), task and data folder (`tax-document-tracker`,
`UPSTREAM_DATA_HOME_NAME` in the tests) are never passed to a removal, a copy
or a deny rule change, and tests prove it (section 7). `STANDING_RULES` in
`tracker/__init__.py` contains no product name and no "tracker", so neither it
nor its quoted copies (README, roadmap, knowledge map, app) change, and
`tests/test_single_source.py`'s standing-rule checks are untouched.

**R9. Q3 applies to every sentence a person can see, and a test enforces
it.** Title-case screen words: "Tracker" becomes "App". Sentences: "the
tracker" becomes "the app", "the tracker's" becomes "the app's". Internal
names stay (Q4): the `tracker` package and `tracker/...` paths,
`python -m tracker...`, `tracker-api.exe`, every `TRACKER_*` variable,
`tracker-errors.log`, `tax-tracker.xml`, `window.tracker`,
`tax-document-tracker-pilot`, the repository's name. Code comments and
docstrings are not screen text and are not changed. The override *label*
changes; the stored reason (`tracker/manifest.py:329`) is record data and is
never rewritten. Two gate tests (section 7.4) fail on any person-visible
"tracker" that is not an internal name, so a sentence this SPEC's grep missed
(a string split over lines, say) is still caught. *Reason:* Jason: "apply it
everywhere"; Q3 (a).

**R10. History is never rewritten.** Decision rows (`pilot/DECISIONS.md`,
`docs/ROADMAP.md`), earlier SPECs, handoffs, reviews, audits, prompts and
results of the 0.2 checks keep the old name. `docs/ROADMAP.md`'s *title line*
is not a row: it carries the product name by test
(`tests/test_single_source.py:47-49`) and is renamed.

**R11. The version moves once (P140).** `app/renderer/pilot-content.js:9`
`"version": "0.3"`. The badge, Help > About (`tracker/api.py:1514`
`"Pilot {version}"`), the installer's `AppVersion` and file name
(`pilot/Build Pilot Installer.bat` reads the badge) follow. `pilot/RELEASE.md`
becomes the 0.3 release steps; its tag line becomes `pilot-0.3`. No 0.2 tag.
`app/package.json` `"version": "1.1.0"` is the program's own version (in the
program identity) and does not change.

**R12. What the step prints and records.** Every carry-over job says one
plain sentence every time it runs, including "nothing to do" (fail loudly,
never skip silently). The sentences lead the step's printed lines (as the
left-behind move's does today) and are kept in a new `"carried"` list in
`after-install.json`. A job that could not finish adds its sentence to
`failed`, so the program identity is not recorded and the next launch runs
the step again (`tracker/after_install.py:941-1000`). A carry-over note that
is not a failure does not raise the app's notice (the notice is for findings
and failures only).

---

## 3. The carry-over, in `tracker/after_install.py`

Both jobs run inside `_run()` (`tracker/after_install.py:955`), under the
step's existing lock (pilot P47), so two starts never carry over at once.

### 3.1 `_carry_over_settings() -> _Step`

Runs **first** in `_run()`, before `_save_choice()` (line 971) and before
`_saved_preference()` / `_saved_root()` read the file, so the schedule and the
record check use the carried-over choice in the same run.

| Case | What it does | Sentence (new constant) | Failure? |
|---|---|---|---|
| Not frozen (from source) | Nothing | `SETTINGS_FROM_SOURCE` "Run from source: the settings file is the checkout's own, so nothing is carried over from the earlier name." | No |
| The earlier path is this program's own settings file (R2's in-place upgrade; compared resolved) | Nothing | `SETTINGS_IN_PLACE` "The program was upgraded in its own folder, so its settings file stayed where it was." | No |
| `settings_path()` exists and the earlier file exists elsewhere | Nothing; the current file wins | `SETTINGS_BOTH` "This program already has its settings file ({new}), so the one left by the earlier name ({old}) was not used; it was left where it was." | No |
| `settings_path()` missing, earlier file missing | Nothing | `SETTINGS_NO_EARLIER` "There was no settings file from the earlier name to carry over." | No |
| `settings_path()` missing, earlier file present | Copy its bytes to `settings_path()` with the existing atomic writer (`fsio`), read back, compare SHA-256; the earlier file is left in place | `SETTINGS_CARRIED` "Copied the settings file left by the earlier name ({old}) to {new}, so the clients folder and the schedule choice carry over; the earlier file was left where it was." | No |
| The copy or the comparison fails | The partial copy (if this job made one) is removed; the earlier file is untouched | `SETTINGS_CARRY_FAILED` "The settings file left by the earlier name ({old}) could not be copied to {new} ({problem}); nothing was changed. Start the app: it tries again at launch." | Yes |

- The earlier path is `settings.earlier_settings_path()`, a new function:
  `Path(LOCALAPPDATA) / "Programs" / EARLIER_PRODUCT_NAME / SETTINGS_FILENAME`,
  or `None` when `LOCALAPPDATA` is unset (said as `SETTINGS_NO_EARLIER`).
- The file is copied as bytes and never parsed or rewritten here: whether its
  contents are usable is `_saved_root()` and `_saved_preference()`'s job,
  which already say so loudly.
- `{problem}` is said by `errors.said` (its class), never a traceback; the
  whole error goes to the local debug log with `errors.keep`, as the other
  jobs do.
- Idempotent: after one copy the second run meets `SETTINGS_BOTH` and changes
  nothing.

### 3.2 `_replace_earlier_task(schedule: _Step) -> _Step`

Runs right after `_schedule()` (line 985). The task name it removes is
`settings.EARLIER_PRODUCT_NAME` and nothing else; it calls the existing
`scheduling.remove_task(task_name=...)` (`tracker/scheduling.py:477`), which
queries first, deletes with `/f`, and raises `RuntimeError` on a failed
delete.

| Case | What it does | Sentence | Failure? |
|---|---|---|---|
| The schedule job failed this run (`schedule.failed`) | Keeps the earlier task, so the pass still runs on a schedule | `EARLIER_TASK_KEPT` "The scheduled task under the earlier name, {old}, was kept because the new one could not be registered (above); the app tries again at its next start." | No (the schedule's own failure already stops the identity being recorded) |
| Otherwise (registered here, off, or this computer not the one named to run it) and the earlier task exists | Removes it | `EARLIER_TASK_REMOVED` "Removed the scheduled task under the earlier name, {old}; the schedule now runs as {new} where it is on." | No |
| The earlier task is not there (or no Task Scheduler, off Windows) | Nothing | `EARLIER_TASK_NONE` "There was no scheduled task under the earlier name, {old}, on this computer." | No |
| The delete fails | The earlier task stays | `EARLIER_TASK_FAILED` "The scheduled task under the earlier name, {old}, could not be removed ({problem}); until it is, both tasks start the pass, and the second finds the first's lock and moves nothing. Start the app: it tries again at launch, and Repair the Schedule tries at once." | Yes |

- `{old}` is `EARLIER_PRODUCT_NAME`, `{new}` is `scheduling.TASK_NAME`; no
  sentence types either name.
- Every removal is noted on the debug log with why, as P47's task removals
  already are.
- Idempotent: after one removal the second run meets `EARLIER_TASK_NONE`.

### 3.3 Record and output

- `after-install.json` gains `"carried": [settings sentence, task sentence]`.
  `read_record()` treats a missing `"carried"` (a record written by 0.2) as
  an empty list.
- `main()` prints the two sentences first, then the lines it prints today.
- `failed` gains `SETTINGS_CARRY_FAILED` / `EARLIER_TASK_FAILED` when they
  happen, de-duplicated as today (line 988).

---

## 4. Inventory (found by targeted grep, 2026-09-30, on `claude/rename-0.3` at 8d9effa)

Reproduce with:
`git ls-files -z | xargs -0 grep -n -I -i 'Tax Document Tracker\|Tax-Document-Tracker\|Pilot 0\.2\|"0\.2"'`
and, for screen words, `grep -n 'Tracker' app/main.js tracker/*.py` and
`grep -n -i "the tracker\|tracker's" tracker/*.py`.

### 4.1 RENAME - the program's name (Commit A)

| File:line | Today | Becomes |
|---|---|---|
| `app/package.json:3` | `"productName": "Tax Document Tracker Pilot"` | `"Tax Document Console"`; also add `config.userDataName` (R4) |
| `tracker/api.py:1349-1353` | side panel `"product": "Tax Document Console"` typed | `product_name()` (R1); the comment says so |
| `app/main.js:112` | comment names `%LOCALAPPDATA%\Tax Document Tracker Pilot\error.log` | names the folder as `%LOCALAPPDATA%\<productName>` and says the earlier folder may still hold an earlier log |
| `pilot/installer/setup.iss:1, 9` | header comment, build example | new name, `Tax Document Console-win32-x64` |
| `pilot/installer/setup.iss:21` | `AppName=` | `AppName=Tax Document Console` |
| `pilot/installer/setup.iss:25` | `DefaultDirName=` | `{localappdata}\Programs\Tax Document Console` |
| `pilot/installer/setup.iss:26` | `DefaultGroupName=` | `Tax Document Console`; add `UsePreviousGroup=no` below it |
| `pilot/installer/setup.iss:29` | `OutputBaseFilename=Tax-Document-Tracker-Pilot-Setup-{#AppVersion}` | `Tax-Document-Console-Setup-{#AppVersion}` |
| `pilot/installer/setup.iss:30` | `UninstallDisplayName=` | `Tax Document Console {#AppVersion}` |
| `pilot/installer/setup.iss:42, 43` | Start menu and desktop shortcuts | `Tax Document Console` -> `{app}\Tax Document Console.exe` |
| `pilot/installer/setup.iss:46` | `[Run]` launch box | `Launch Tax Document Console` |
| `pilot/installer/setup.iss:54` | `/Delete /TN ""Tax Document Tracker Pilot""` | the new name; plus a second line for the earlier name (6.1) |
| `pilot/Build Pilot Installer.bat:2, 3, 68` | comments and `INSTALLER=...Tax-Document-Tracker-Pilot-Setup-%VER%.exe` | `Tax-Document-Console-Setup-%VER%.exe` |
| `pilot/Tester Guide.md:1, 5, 24, 74` | title, first sentence, installer file, Settings > Apps entry | new name and file |
| `pilot/README.md:4` | "copy of the Tax Document Tracker" | "copy of Tax Document Console" (and the common noun, 4.6) |
| `README.md:1` | `# Tax Document Tracker Pilot (...)` | `# Tax Document Console (Income Tax Information Requests)` |
| `docs/ROADMAP.md:1` | title line | `# Tax Document Console — Build Plan` (R10; rows unchanged) |
| `docs/runbook.md:586, 590, 591` | fallback log folder | `%LOCALAPPDATA%\Tax Document Console\error.log`, plus one sentence that a PC upgraded from the earlier name may still hold an earlier log in `%LOCALAPPDATA%\Tax Document Tracker Pilot\`, which a person may delete |
| `pilot/wintest/run_checks.ps1:27, 178, 197, 198, 200` | program folder, installer glob, exe, shortcut, uninstall entry | new names; line 27 looks for the new folder first, then the earlier one (R2) |
| `pilot/wintest/uninstall_checks.ps1:10, 11, 27, 35` | task, folder, process, exe | new names; the task check asserts **both** names are gone |
| `pilot/wintest/PROMPT-shell.md:95, 134, 139, 140` | task name, "the tracker", fallback log folder | new names, "the app" |
| `pilot/wintest/RESULTS-TEMPLATE.md:1, 45` | "Pilot 0.2", task name | "Pilot 0.3", new task name |
| `pilot/harness/interact.mjs:597` | About must include "Pilot 0.2" | reads the version from `pilot-content.js` and checks "Pilot " + it |
| `.claude/settings.json:71-78` | deny rules for the fallback log under the earlier folder | **add** the same eight rules for `Tax Document Console`; **keep** the eight earlier ones (an earlier log can name a client). Tightening only. |
| `docs/repo-map.curated.json:190, 191, 433` | notes naming the earlier fallback folder | the new folder; `after_install`, `settings`, `api` and `app/main.js` notes gain the carry-over and R4 |

### 4.2 RENAME - the version (Commit A)

| File:line | Today | Becomes |
|---|---|---|
| `app/renderer/pilot-content.js:9` | `"version": "0.2"` | `"0.3"` |
| `pilot/RELEASE.md:1, 7-8, 11, 59, 77` | 0.2 title, text, installer path, tag `pilot-0.2` | 0.3; tag `pilot-0.3`; add one line: no 0.2 tag (P140) |
| `pilot/RELEASE.md:13, 15, 73` | program and task names | new names (line 14's data folder stays, R3) |

### 4.3 RENAME - the terms bullet (owner question Q1, section 10)

| File:line | Today | Becomes (recommendation) |
|---|---|---|
| `app/renderer/pilot-content.js:21` | "A test edition of Tax Document Tracker, built by J Park & Associates." | "A test edition of Tax Document Console, built by J Park & Associates."; `terms.version` stays 1 |

### 4.4 RENAME - title-case screen words (Q3, Commit A)

| File:line | Today | Becomes |
|---|---|---|
| `app/main.js:99` and `tracker/api.py:445` | No Reply From the Tracker | No Reply From the App |
| `app/main.js:100` and `tracker/api.py:446` | The Tracker Could Not Start | The App Could Not Start |
| `app/main.js:102` and `tracker/api.py:453` | Tracker Failed | App Failed |
| `tracker/api.py:704` and `tracker/runner.py:2270` | Folders the Tracker Leaves Alone | Folders the App Leaves Alone |
| `tracker/api.py:3834` | "...listed under Folders the Tracker Leaves Alone..." | "...Folders the App Leaves Alone..." |
| `tracker/api.py:1208` | override label "Received Outside the Tracker" | "Received Outside the App" (label only) |
| `tracker/ocr.py:168` and `pilot/harness/stub.js:33` and `docs/runbook.md:2085` | example folder `C:\JPA Tracker` | `C:\JPA App` |

### 4.5 RENAME - "the tracker" in sentences a person sees (Q3, Commit B)

Every module-level sentence constant that calls the program "the tracker":

- `tracker/api.py:396-397` (FAILED), `:608` (MEMBERS_HELP), `:724`
  (SHARING_NOTE), `:977` (ROUTING_HELP), `:1078` (HOUSEHOLD_NOT_OURS)
- `tracker/after_install.py:188` (FINDINGS_WAIT)
- `tracker/settings.py:127, 131, 134, 136, 809, 818, 820`
- `tracker/checkpoint.py:99-100, 159`
- `tracker/door.py:209`
- `tracker/errors.py:87` (WHERE_KEPT: "beside the app's database"; the file
  name `tracker-errors.log` stays)
- `tracker/layout.py:142, 730`
- `tracker/ledger.py:527, 528`
- `tracker/reasons.py:234, 564`
- `tracker/registry.py:85, 107, 123, 129, 972`
- `tracker/runner.py:289, 2282, 2644`
- `tracker/store.py:247, 252, 2551, 2641, 3947`
- `tracker/scheduling.py:756, 778` (command-line help; `:764` "the tracker
  package" is internal and stays)

The grep that found these reads one line at a time; the gate test in 7.4
finds any sentence split over lines that it missed, and the builder fixes
those too.

### 4.6 RENAME - "the tracker" in documents a person reads (Commit B)

The common noun becomes "the app" in: `docs/runbook.md` (87 uses),
`README.md` (9), `docs/workflow.md` (3), `PRODUCT.md:19` (1),
`pilot/Tester Guide.md` (3, beyond 4.1), `pilot/RELEASE.md` (3),
`pilot/README.md` (1). Counts are words that are not an internal name, from
`grep -o -i '[^ ]*tracker[^ ]*' <file>` less the internal-name patterns of
R9. Where one of these documents quotes a constant from 4.5 exactly,
`tests/test_single_source.py` already fails until the quote matches, so the
constant and its quote change in the same commit.

### 4.7 KEEP - internal names (Q4) and on-disk folders (R2-R4)

| File:line | What | Why kept |
|---|---|---|
| `tracker/` package, every `tracker/...` path, `python -m tracker...` | code | Q4 |
| `app/package.json:9` `apiName: "tracker-api"` | `tracker-api.exe` | Q4 |
| `tracker/settings.py:105, 108, 111, 118`; `app/main.js:292`; `pilot/Build Pilot Installer.bat:12, 19, 44, 47` | `TRACKER_*` variables | Q4 |
| `app/package.json:2` `"name"` and `tracker/settings.py:120` `DATA_HOME_NAME` | data folder `tax-document-tracker-pilot` | R3 |
| `pilot/Tester Guide.md:76`, `pilot/RELEASE.md:14`, `pilot/RELEASE.md:75`, runbook mentions of the data folder | name the data folder | R3 |
| `%APPDATA%\Tax Document Tracker Pilot` (Electron `userData`) | page storage | R4 |
| `%LOCALAPPDATA%\Programs\Tax Document Tracker Pilot` on an upgraded PC | program folder | R2 |
| `tracker/settings.py:203` `tracker-errors.log`; `tracker/scheduling.py:116` `tax-tracker.xml`; `after-install.json`, `after-install.lock` | file names | Q4 |
| `tracker/scheduling.py:764` "the folder holding the tracker package" | command-line help about the package | Q4 |
| `app/renderer/app.js:153, 173` `TrackerError`; `app/main.js:270-278, 451, 737` `runTracker`/`spawnTracker`; `window.tracker` | code names | Q4 |
| `tracker/manifest.py:329` stored override reason | record data | never rewritten |
| `tests/test_pilot_installer.py:21`, `tests/test_single_source.py:379` `UPSTREAM_DATA_HOME_NAME = "tax-document-tracker"` | the production product's folder | R8 |
| `CLAUDE.md:1`, `docs/tools.md`, `docs/repo-map.json`/`.md` (generated) | agent-facing | not read by a person as the app; the map regenerates |
| `J-Park-Associates/Tax-Info-Request-List-Pilot` | the repository | Q4 |

### 4.8 KEEP - history (R10), every line in these files

`pilot/DECISIONS.md` rows; `docs/ROADMAP.md` rows (all but line 1);
`pilot/SPEC.md`, `SPEC-glass.md`, `SPEC-ui.md`, `SPEC-shell.md`,
`SPEC-lists.md`, `SPEC-wincheck-fixes.md`, `SPEC-firm-cache.md`,
`SPEC-email-zip-tag.md`; `pilot/HANDOFF.md`, `PROMPTS.md`, `AUDIT-shell.md`,
`BRIEF-shell.md`, `PLAN-ui.md`, `mockup-shell.html`, `shell-test-pins.md`;
`pilot/handoffs/*`; `pilot/reviews/*`; `pilot/review/wording-table.md`;
`pilot/wording-shell.tsv` and `pilot/wording-inventory.tsv` (records of the
finished wording pass: "today" and "proposed" columns, read by no test);
`pilot/wintest/PROMPT.md`, `PROMPT-RERUN-3.md`, `PROMPT-shell-local.md`,
`RESULTS-shell.md`.

**Totals.** RENAME: 118 line sites (4.1: 54, 4.2: 10, 4.3: 1, 4.4: 13,
4.5: 40) plus 107 common-noun words in seven documents (4.6). KEEP: 30
internal line sites (4.7) plus 26 history files or folders (4.8, the
`handoffs` and `reviews` folders counted once each).

---

## 5. What stays exactly as it is

- `tracker/__init__.py` `STANDING_RULES` and every quoted copy (R8).
- The catalog, the matcher and routing: no catalog text changes, so
  `tools/vocab_report.py build` is not needed and the backtest baseline is
  not touched.
- The layer table in `tests/test_layers.py`: no import is added.
  `after_install` already imports `settings` and `scheduling`.

---

## 6. Files, functions and line ranges to touch

### 6.1 Commit A

| File | Where | Change |
|---|---|---|
| `app/package.json` | `productName`, `config` | R1, R4 |
| `app/main.js` | 99-102, 112, top of file before 723 | Q3 defaults; comment; `app.setPath("userData", ...)` from `PKG.config.userDataName` (R4) |
| `app/renderer/pilot-content.js` | 9, 21 | 0.3; the terms bullet (4.3) |
| `tracker/settings.py` | beside `DATA_HOME_NAME` (120) and `settings_path()` (193) | `EARLIER_PRODUCT_NAME`; `earlier_settings_path()` |
| `tracker/after_install.py` | new constants beside the others (about 75-230); `_carry_over_settings()`, `_replace_earlier_task()` beside `_move_what_186_lists()` (878); `_run()` 955-1000; `read_record()`; `main()` 1159 | section 3 |
| `tracker/api.py` | 445, 446, 453, 704, 1208, 1353, 3834 | 4.4, R1 |
| `tracker/runner.py` | 2270 | 4.4 |
| `tracker/ocr.py` | 168 | 4.4 |
| `pilot/installer/setup.iss` | whole `[Setup]`, `[Icons]`, `[Run]`, `[UninstallRun]`; new `[InstallDelete]` | below |
| `pilot/Build Pilot Installer.bat` | 2, 3, 68 | 4.1 |
| `pilot/wintest/run_checks.ps1`, `uninstall_checks.ps1`, `PROMPT-shell.md`, `RESULTS-TEMPLATE.md` | 4.1 lines | 4.1; section 9 steps added to `PROMPT-shell.md` |
| `pilot/harness/interact.mjs:597`, `pilot/harness/stub.js:33` | | 4.1, 4.4 |
| `.claude/settings.json` | 71-78 | add eight rules (4.1) |
| Documents | section 8 | |

The new `setup.iss` lines, exactly:

```
UsePreviousGroup=no

[InstallDelete]
; The earlier name's own files (P155): exact paths, never a wildcard.
Type: files; Name: "{app}\Tax Document Tracker Pilot.exe"
Type: files; Name: "{userprograms}\Tax Document Tracker Pilot\Tax Document Tracker Pilot.lnk"
Type: dirifempty; Name: "{userprograms}\Tax Document Tracker Pilot"
Type: files; Name: "{userdesktop}\Tax Document Tracker Pilot.lnk"

[UninstallRun]
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN ""Tax Document Console"" /F"; Flags: runhidden; RunOnceId: "RemoveSchedule"
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN ""Tax Document Tracker Pilot"" /F"; Flags: runhidden; RunOnceId: "RemoveEarlierSchedule"
```

A comment above `DefaultDirName` states R2 (why `UsePreviousAppDir` is left at
its default). The installer closes a running earlier copy because it uses
files the installer replaces (Inno Setup's default `CloseApplications`);
the Tester Guide's upgrade line still says to close the app first.

### 6.2 Commit B

The constants of 4.5 in their modules, their quotes in the documents, and the
documents' prose of 4.6. No function changes.

---

## 7. Tests

Run under Python 3.14 and 3.11, each file as its own process
(`pilot\wintest\run_checks.ps1 -Tests <files>` on Windows). Only these files;
never the whole suite (the orchestrator runs it once a day).

### 7.1 Owning test files

- Commit A: `tests/test_after_install.py`, `tests/test_settings.py`,
  `tests/test_scheduling.py`, `tests/test_api.py`, `tests/test_runner.py`,
  `tests/test_ocr.py`, `tests/test_shell.py`, `tests/test_shell_menu.py`,
  `tests/test_pilot.py`, `tests/test_pilot_installer.py`,
  `tests/test_pilot_ui.py`, plus the guard files `tests/test_single_source.py`,
  `tests/test_layers.py`, `tests/test_repo_map.py`, `tests/test_errors.py`,
  `tests/test_tripwire.py` (error wording changes).
- Commit B adds: `tests/test_checkpoint.py`, `tests/test_door.py`,
  `tests/test_layout.py`, `tests/test_ledger.py`, `tests/test_reasons.py`,
  `tests/test_registry.py`, `tests/test_store.py`.
- The pilot's renderer harness `pilot/harness/interact.mjs` (the About check).

### 7.2 Existing tests that change with the words

- `tests/test_single_source.py:2518` (comment), `:2832-2856` ("App Failed"),
  `:2912-2925` (`product == "Tax Document Console"`), `:4080` (the runbook's
  new fallback-log path), `_fallback_log_rules()` at `:423-431` (both the
  current and the earlier folder).
- `tests/test_pilot_installer.py:57-66` (both task names), `:86-97` (the new
  file name), `:131-138` (guide names the new product; the data folder line
  unchanged).
- `tests/test_pilot.py:103-109` (the approved terms phrase becomes the new
  bullet; the exception is no longer needed, since the bullet now names the
  product - the test then asserts the terms name the product exactly once).
- `tests/test_shell.py:1335, 2301-2318` (the stub's version and product),
  `:3592` unchanged in value; `tests/test_shell_menu.py:470-473`;
  `tests/test_ocr.py:678`.

### 7.3 New tests (Commit A)

`tests/test_after_install.py`:
- `test_a_fresh_install_copies_the_earlier_settings_file_byte_for_byte_and_leaves_it`
- `test_the_carried_settings_are_used_by_the_same_run`
- `test_settings_already_beside_the_program_win_and_the_earlier_file_is_named_and_left`
- `test_an_upgrade_in_place_has_no_settings_to_carry_and_says_so`
- `test_with_no_earlier_settings_file_nothing_is_copied_and_it_says_so`
- `test_from_source_the_settings_are_never_carried_over`
- `test_a_settings_copy_that_fails_leaves_nothing_behind_and_is_a_failure`
- `test_the_earlier_task_is_removed_after_the_new_one_is_registered`
- `test_the_earlier_task_is_removed_when_the_schedule_is_off_or_elsewhere`
- `test_the_earlier_task_is_kept_when_the_new_one_could_not_be_registered`
- `test_with_no_earlier_task_nothing_is_removed_and_it_says_so`
- `test_a_failed_removal_of_the_earlier_task_is_a_failure_and_runs_again_at_launch`
- `test_only_the_earlier_pilot_name_is_ever_removed_never_the_production_task`
- `test_running_the_step_twice_changes_nothing_the_second_time`
- `test_a_record_from_before_the_rename_reads_as_nothing_carried`
- `test_the_carry_over_sentences_lead_the_printed_lines`

`tests/test_settings.py`:
- `test_the_earlier_product_name_is_the_pilots_old_name_not_the_current_or_production_one`
- `test_the_earlier_settings_path_is_under_local_app_data_programs`
- `test_the_data_folder_keeps_its_name_through_the_rename`

`tests/test_pilot_installer.py`:
- `test_an_upgrade_installs_over_the_earlier_copy_in_its_own_folder` (AppId
  value pinned; no `UsePreviousAppDir=no`)
- `test_the_start_menu_takes_the_new_name_on_an_upgrade` (`UsePreviousGroup=no`)
- `test_an_upgrade_removes_exactly_the_earlier_shortcuts_and_program_file`
- `test_uninstalling_removes_the_task_under_either_name`
- `test_every_copy_of_the_earlier_name_matches_the_one_in_settings` (setup.iss,
  both .ps1 scripts, `package.json` `config.userDataName`)
- `test_the_pilot_build_names_the_installer_as_setup_iss_does`

`tests/test_single_source.py`:
- `test_the_side_panel_names_the_product_from_its_one_home`
- `test_the_electron_user_data_folder_keeps_its_earlier_name`
- `test_the_fallback_log_rules_deny_the_current_and_the_earlier_folder`
- `test_the_version_is_0_3_in_the_badge_and_the_release_steps`

### 7.4 The gate tests (Commit B)

In `tests/test_single_source.py`:
- `test_no_sentence_the_app_shows_calls_it_the_tracker`: every string in
  `api._vocab()` (walked recursively), every module-level UPPER_CASE `str`
  constant in `tracker/*.py`, the JSON between `pilot-content.js`'s markers,
  and `app/main.js`'s three default `let` sentences - none contains the word
  "tracker" (any case) once the R9 internal names are removed. A short,
  commented allowlist names any constant whose value is an internal name
  (for example a `TRACKER_*` variable name), each with its reason.
- `test_no_person_facing_document_calls_the_program_the_tracker`: the same
  over `README.md`, `PRODUCT.md`, `docs/runbook.md`, `docs/workflow.md`,
  `pilot/README.md`, `pilot/Tester Guide.md`, `pilot/RELEASE.md`. A line may
  name the earlier product only if it also says "earlier", and the production
  product only if it also says "production".

### 7.5 Quick checks

Dead code first (unused imports, locals, commented-out code, names nothing
uses) in the changed files; then `python -m ruff check .`,
`python tools/repo_map.py check`, `python tools/vocab_report.py check` (it
must stay current; no rebuild expected).

---

## 8. Documents that ship in the same commit

- Commit A: `pilot/Tester Guide.md` (4.1, plus one line in the install
  section: installing over the earlier name keeps your settings and schedule;
  close the app first), `pilot/RELEASE.md` (4.2), `pilot/README.md`,
  `README.md` line 1, `docs/ROADMAP.md` line 1, `docs/runbook.md` 586-591 and
  a short new paragraph "After the rename (P155)" in the section on moving or
  upgrading the program: what the first start after the upgrade does (task
  replaced, settings kept or copied, data folder unchanged, where an earlier
  fallback log may remain), each sentence of section 3 quoted exactly (the
  single-source tests hold the quotes), `pilot/wintest/*` (4.1),
  `docs/repo-map.curated.json` (4.1), then `python tools/repo_map.py update`.
- Commit B: the prose of 4.6 and every runbook quote of a 4.5 constant, then
  `python tools/repo_map.py update` again if a curated note quotes one.
- Not needed: `tools/vocab_report.py build` (no catalog text changes).
  `pilot/wording-shell.tsv` is history (4.8) and is not edited.

---

## 9. The 0.3 Windows check gains these hands-on steps

Only where the rename could change behaviour (the rest already passed):

1. On a PC with the earlier name installed and a schedule on: install
   `Tax-Document-Console-Setup-0.3.exe` over it without uninstalling. Start
   menu and desktop show only Tax Document Console; Settings > Apps shows
   one entry, "Tax Document Console 0.3".
2. Start the app once. `schtasks /Query /TN "Tax Document Console"` finds the
   task; `schtasks /Query /TN "Tax Document Tracker Pilot"` finds none. The
   clients folder, schedule choice and column widths are as they were.
3. Uninstall 0.3, then install 0.3 fresh: it goes to
   `%LOCALAPPDATA%\Programs\Tax Document Console`, and the settings left by
   the earlier name are copied (the after-install line says so).
4. Uninstall: `uninstall_checks.ps1` shows both task names gone, and the data
   folder and `settings.json` left.
5. The window title, side panel, About and badge read Tax Document Console /
   Pilot 0.3; a forced failure reads "App Failed".

`pilot/wintest/run_checks.ps1` and `uninstall_checks.ps1` must pass on
Windows before merge (the installer, paths and Task Scheduler are
operating-system behaviour); label the pull request `windows` only if Jason
asks for a GitHub run.

---

## 10. Owner questions

**Q1 - The terms a tester accepts (wording that speaks for the firm).** The
first terms bullet says "A test edition of Tax Document Tracker, built by
J Park & Associates." After the rename a tester sees Tax Document Console
everywhere else.
- **(a) Recommended:** change it to "A test edition of Tax Document Console,
  built by J Park & Associates." and keep the terms version at 1, so testers
  who already accepted are not asked again (only the name changed, not what
  they agreed to).
- (b) The same new wording, and raise the terms version to 2, so every tester
  sees and accepts the terms again.
- (c) Keep the sentence as it is (it names the product the pilot tests).

The build proceeds on (a). The answer is recorded in this SPEC and the log.

No other owner question: everything else follows P155's four answers and
P140.

---

## 11. Proposed decision rows (for the orchestrator to write; next free is P185)

| No. | Date | Decision | Source / status |
|---|---|---|---|
| P185 | 2026-09-30 | **How the rename carries an install over (P155 Q2, build detail).** An upgrade installs over the earlier copy in its own folder (same AppId, Inno Setup's default); a new install goes to `Programs\Tax Document Console`. The data folder `tax-document-tracker-pilot` and Electron's own folder keep their earlier names (internal, as Q4), so nothing holding client data moves. The installer removes the earlier shortcuts and program file by exact path and the uninstaller removes the task under either name; the after-install step copies `settings.json` from the earlier program folder only when the program has none, and removes the task "Tax Document Tracker Pilot" after registering "Tax Document Console" (kept if the new one failed). Each job says one sentence every run; a failure is retried at the next launch. Never the production product's task or folder. `pilot/SPEC-rename.md`. | SPEC author, from P155 and decision 209. Status: Open until the rename lands. |
| P186 | 2026-09-30 | **"Tracker" on screen becomes "App" in every sentence, enforced by test (P155 Q3, build detail).** Title-case screen words and "the tracker" in every sentence a person sees, the app's and the engine's, and in the person-facing documents; internal names (Q4), comments, stored record values and history are kept. Two gate tests fail on any other "tracker" a person could see. The engine sentences are their own commit, since the original repository is merged in by hand (P17). | SPEC author, from P155 Q3. Status: Open until the rename lands. |
| P187 | 2026-09-30 | **The terms bullet names Tax Document Console** - Q1 of `pilot/SPEC-rename.md`: (a) new name, terms version stays 1 (recommended); (b) new name, version 2; (c) unchanged. | Awaiting Jason; built on (a) meanwhile. |
