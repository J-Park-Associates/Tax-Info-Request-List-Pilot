# SPEC — Tax Document Console on a Mac

Status: **SPEC, written before the build** (2026-10-10). Rulings P238–P247
in [`DECISIONS.md`](DECISIONS.md) (Jason, 2026-10-10). Nothing here is built.
It replaces the read-only assessment of the same date, whose facts were
checked against `claude/zealous-faraday-hw5sga` (map current, 255 nodes) and
are kept below; section 8 lists what that assessment missed. Each job in
section 7 is its own session that reads this file, not this transcript.

## 1. The answer

Today the Console runs only on Windows. Its engine (the part that reads,
sorts, files and drafts) is ordinary Python that already passes its tests on
Linux, a close relative of macOS, and every package it reads with publishes
an Apple Silicon build. What is Windows-only is everything around the engine:
the schedule is a Task Scheduler job, the settings file sits beside the
program (a Mac app may not write inside itself), four safeguards silently do
nothing off Windows, and the build, installer and checks are Windows scripts.
The port adds a Mac version of each of those, so a Mac can be a practice's one
office machine. It holds the schedule, the data folder and the clients folder,
exactly as the office PC does. The engine, the routing and the standing rules
do not change. A new firm on a Mac has this first day:

- It downloads one `.dmg` file, opens it and drags the app into Applications.
  The Mac must have Apple silicon and macOS 14 or later.
- At the first open, macOS blocks the app because it is not yet signed by
  Apple. The person opens System Settings, Privacy & Security, clicks
  **Open Anyway** once and enters the Mac's password. Signing removes this
  step later.
- The app opens on the Pilot's terms screen. They sign it, then choose the
  clients folder in Google Drive. macOS asks once whether the app may use
  Google Drive's files, and they allow it.
- The schedule then sets itself up, with no button to press. macOS shows
  "Background Items Added", and the app says the Mac now runs the schedule
  every two hours from 7:00.
- The first pass starts at once, so that macOS asks for the Drive permission
  while someone is at the Mac. After that, the Mac sorts by itself every two
  hours, like the PC.

## 2. Rulings

| Row | Ruling | Decisions it touches |
|---|---|---|
| P238 | The Mac is the office machine: the schedule, the data home and the clients root. It is proved as a standalone fresh install with its own clients root and nothing carried over from the PC. It is not a second desk. | runbook §1 (one machine per root), 137 L6, 171, 209 |
| P239 | The test is unsigned: Open Anyway, and the Drive permission granted again by hand after an upgrade. The signing job (identity, entitlements, notarytool, a tag-only macOS release job) stays specified here and lands when an Apple Developer membership exists. | P4, P12, 191, 207/211 |
| P240 | Protected View on a Mac is a sentence plus an Office setting. A review copy of a macro-capable workbook, an email or a zip opens normally, and each time it is opened the app says that Protected View does not exist on a Mac and that macros must stay disabled in Office. The runbook names the setting. | 190 (part 4) |
| P241 | A Mac measures room as if the folder sat under a Windows root, against one constant. Names and parks therefore match Windows. | 125, 131, P29 |
| P242 | The after-install step excludes the Mac's data home from Time Machine. | 186, 209 |
| P243 | The floor is Apple silicon on macOS 14 or later. Anything else is refused with one sentence. Whether to use CoreML is decided after a timed season-sized pass on the CPU reader. | 169, 191 |
| P244 | The Windows root a Mac measures room against is 48 characters, fixed: a Google Drive shared drive with a 31-character name, not the firm's own 28-character root. No setting. | P241, 131, P29 |
| P245 | Windows keeps accepting a OneDrive or Dropbox clients root. Parity with the Mac's refusals is a separate decision, outside this port. | 137, 171 |
| P246 | The Mac ships as a `.dmg`, and the floor refusal runs at the app's first start, before anything is written. No `.pkg`. An Intel Mac gets macOS's own message. | P243 |
| P247 | The CoreML yardstick: the kit's season-sized pass on the CPU reader must finish well inside the two-hour schedule slot. If it does, CoreML is not built; if it does not, CoreML is its own measured job that may not lower the backtest baseline. | P243, 169 |

## 3. What a buyer experiences, step by step

This is the acceptance walk the Mac check kit (R33) runs on a Mac that has
never had the Console, with a clients folder made for the test. Each step
names what the person should see; anything else is a FAIL with a screenshot.
Before starting: Google Drive for desktop is signed in (or the walk uses a
plain folder on the Mac), and the test's clients folder holds only the
made-up sample documents (`pilot/wintest/make_samples.py`).

1. **Download.** Get `Tax-Document-Console-<version>-mac-arm64.dmg` and its
   `.sha256` file. In Terminal, `shasum -a 256 <file>` prints the same
   64 characters the `.sha256` file holds.
2. **Install.** Double-click the `.dmg`. A window shows **Tax Document
   Console** and an **Applications** folder. Drag the app onto Applications,
   then eject the disk image (the eject arrow beside it in Finder's sidebar).
3. **First open.** Open the app from Applications. On macOS 15 or later the
   Mac shows "“Tax Document Console” Not Opened" and "Apple could not verify
   …"; click **Done**. On macOS 14 the message says the app "can't be opened
   because Apple cannot check it for malicious software"; click **OK**. Open
   System Settings, then **Privacy & Security**, and scroll to Security. It
   says "“Tax Document Console” was blocked…". Click **Open Anyway**, enter
   the Mac's password, then click **Open Anyway** again.
4. **The wrong Mac.** On an Intel Mac, macOS itself refuses ("not supported on
   this type of Mac"). On Apple silicon below macOS 14, the app shows R6's
   sentence and quits, and nothing is written.
5. **Opened from the wrong place.** If the app is opened straight from the
   disk image or from Downloads, the first screen shows R4's sentence ("…the
   schedule runs only the copy in Applications"), and no schedule is set up.
6. **The terms.** The app opens on "Before you start: this is a Pilot". Tick
   "I have read this and will keep my own backups", type a name, and click
   **Sign and Accept**.
7. **The clients folder.** "Choose Your Clients Folder" appears. Click
   **Choose Folder…**, pick the test folder (in Finder's sidebar, under Google
   Drive, for a Drive folder), then click **Start**. macOS may ask to let
   Tax Document Console access files in Google Drive. Click **Allow** (the
   kit records the prompt's exact words). A folder in iCloud Drive, Dropbox
   or OneDrive is refused here with R5's sentence.
8. **The schedule installs itself.** macOS shows "Background Items Added"
   (the kit records which name it gives). The app's notice says "This
   computer (<name>) now runs the schedule for this clients folder: every
   day from 07:00, every 120 minutes." No button was pressed.
9. **The first pass.** Within a minute the schedule's first pass runs (R27).
   If macOS asks again whether the schedule may use Google Drive's files,
   click **Allow**. Then the Overview's line reads "Last scheduled pass:
   <time>, succeeded." The sample documents are filed and their originals
   have moved, byte for byte, into the client's folder for the year.
10. **Open a review copy.** In Needs Review, open the sample macro workbook.
    It opens in Excel, and the app shows R8's sentence each time it is
    opened.
11. **The next morning.** Leave the Mac on and signed in overnight (asleep is
    fine). The next day, the last-pass line names a pass from that morning,
    and the line is not amber.
12. **An upgrade.** Quit the app. Install the next build as in step 2,
    choosing **Replace**, and repeat step 3's Open Anyway. At its first open
    the app sets the schedule up again by itself, and the notice repeats step
    8's sentence. The clients folder is still chosen. If the next pass
    reports "macOS did not let the schedule read the clients folder", open
    the app and allow it when asked (P239). The pass after that succeeds.
13. **Switched off by hand.** In System Settings, General, Login Items, under
    Allow in the Background, turn Tax Document Console off. The app's next
    start shows R27's sentence about switching it back on.
14. **Removal.** Choose Tools, then **Remove the Schedule From This Mac…**
    (R29). The app says the schedule is removed. Quit, then drag the app to
    the Bin. No launchd job for the Console is left
    (`launchctl print gui/$(id -u)/com.jparkassociates.taxdocumentconsole.schedule`
    answers that it cannot find the service). The data folder, the settings
    and the clients folder remain, as on Windows (P12).

## 4. Requirements

Each R names what changes, the files, the decisions it must respect, and
its acceptance. **Linux** marks what this Linux box can test: every Python
change, the POSIX lock and fsync paths (with `fcntl` stood in where Linux
lacks the Mac constant), plist generation, and the scripts' syntax
(`bash -n`). **Mac** marks what only a Mac proves: the bundle, Gatekeeper,
launchd registration, the Drive permission, Time Machine, and the reader's
Apple silicon build. "darwin" means `sys.platform == "darwin"`. Every new
platform branch reads the platform **when called**, never at import, so a
test can stand in for a Mac on Linux, as `fsio.mark_from_internet` already
does for Windows.

### A. Homes and guards

**R1. The data home.** On darwin, with no `TRACKER_DATA_HOME`, the data home
is `~/Library/Application Support/tax-document-tracker-pilot`
(`Path.home()` / `Library/Application Support` / `settings.DATA_HOME_NAME`).
`$XDG_STATE_HOME` is not read on darwin. Linux is unchanged. To make every
branch testable on any machine, `settings.resolve_data_home` takes
`system: str` (`"nt"`, `"darwin"` or `"posix"`) in place of `windows: bool`.
The F7/P193 redirect probe stays Windows-only. *Files:* `tracker/settings.py`.
*Respects:* 186 (one private local folder, never synced, never beside the
program). *Acceptance (Linux):* `tests/test_settings.py`
`test_a_mac_keeps_its_data_in_application_support`,
`test_a_mac_never_reads_xdg_state_home`; `tests/test_tripwire.py` still arms
the real place on every system.

**R2. The settings file leaves the bundle.** When packaged on darwin, the
settings folder is `~/Library/Application Support/Tax Document Console`
(the product name). `app/main.js` `SETTINGS_DIR` and `settings.settings_dir()`
(its frozen fallback, used by a frozen API started without
`TRACKER_SETTINGS_DIR`) both build it from one spelling that
`tests/test_single_source.py` pins as equal. On darwin, `settings._the_app_dir()`
for a frozen program answers the enclosing `.app` folder, not
`Contents/Resources/tracker-api`. That makes `program_folders()`,
`inside_the_app()` and `root_refusal`'s `ROOT_HOLDS_APP` judge the whole
bundle. The settings folder holds `settings.json` and nothing derived from a
client. Electron's own folder (`config.userDataName`, which holds the page's
storage, the one-instance lock and the fallback error log) is left as it is,
at `~/Library/Application Support/Tax Document Tracker Pilot`. *Files:*
`tracker/settings.py`, `app/main.js`. *Respects:* 131 (one home for the root;
on a Mac the wording "beside the app" becomes "the app's settings folder"),
186, P155 (an upgrade keeps the root: on a Mac a dragged-in replacement
cannot touch a folder outside the bundle), 185. *Acceptance:* Linux:
`test_settings.py::test_a_packaged_mac_keeps_its_settings_outside_the_bundle`,
`test_a_mac_bundle_is_the_program_folder`, and the single-source pin. Mac:
walk step 12 (the root survives a replacement).

**R3. Which disk a folder is on, on a Mac.** On darwin, `settings.drive_type`
answers from `statfs(2)` through `ctypes` (`f_flags`, `f_mntonname`):
- a mount without `MNT_LOCAL` is `DRIVE_REMOTE`;
- a mount under `/Volumes/` (an external disk, a disk image, a second
  volume) is `DRIVE_REMOVABLE`;
- the startup volume is `DRIVE_FIXED`;
- a `statfs` that fails is `DRIVE_UNKNOWN`.

Existing callers (`resolve_data_home`, `program_drive_refusal`) are
unchanged. A new `settings.synced_tree(path)` names the sync service a path
lies under: `~/Library/CloudStorage/<provider>-…` (Google Drive, OneDrive,
Dropbox and Box through File Provider, all on the local APFS volume, so
`MNT_LOCAL` alone passes them), `~/Library/Mobile Documents` (iCloud Drive),
or `~/Dropbox`. The data home, and a `TRACKER_DATA_HOME`, inside any of them
is refused with `DATA_HOME_SYNCED` ("the app's data folder {home} is inside
{service}, which copies it off this Mac; it must stay on this Mac only").
*Files:* `tracker/settings.py`. *Respects:* 186. *Acceptance (Linux, with
`statfs` stood in):* `test_settings.py::test_a_mac_volume_is_judged_by_its_mount`,
`test_a_data_home_in_a_synced_tree_is_refused`.

**R4. Where the program may run from.** On darwin, a frozen program the
schedule would run must sit directly in `/Applications` or `~/Applications`
(as `Tax Document Console.app`). `program_drive_refusal` says why not, with
one of three sentences, each naming the folder:
- `PROGRAM_TRANSLOCATED`, for a path containing `/AppTranslocation/` (a
  quarantined app opened where it was downloaded, which runs from a random
  read-only copy that is gone after a restart): "macOS is running the app
  from a temporary copy ({folder}) because it was opened where it was
  downloaded. Drag Tax Document Console into Applications and open it from
  there; the schedule runs only the copy in Applications."
- `PROGRAM_ON_DISK_IMAGE`, for anything under `/Volumes/`: "The app is
  running from {folder}, a disk image or a disk other than this Mac's own.
  Drag it into Applications and open it from there; the schedule runs only
  the copy in Applications."
- `PROGRAM_NOT_IN_APPLICATIONS`, for anywhere else: "The app is running from
  {folder}. Move it into Applications and open it from there; the schedule
  runs only the copy in Applications."

A source checkout keeps R3's disk rule and is never refused for its folder.
As on Windows, the refusal is said on the first screen and asked first by
`scheduling.schedule_decision`, and the scheduled pass never asks it.
*Files:* `tracker/settings.py`. *Respects:* 186, SPEC-186 §10, 209.
*Acceptance:* Linux:
`test_settings.py::test_a_mac_program_outside_applications_is_not_scheduled`,
with one case for each sentence. Mac: walk step 5.

**R5. The clients root on a Mac.** `settings.root_refusal` gains a `system`
argument (pure, as today). On darwin it also refuses:
- `ROOT_IN_ICLOUD`, for a root in iCloud Drive (`~/Library/Mobile Documents`),
  or in `~/Desktop` or `~/Documents` while iCloud's "Desktop & Documents
  Folders" is on. That setting is detected by
  `~/Library/Mobile Documents/com~apple~CloudDocs/Desktop` existing. If the
  kit (R33 step H6) finds that signal unreliable, the rule refuses those two
  folders outright, because nothing is guessed. The sentence: "{root} is in
  iCloud Drive, which can take a file's contents off this Mac to save space;
  choose the clients folder in Google Drive, or a folder on this Mac."
- `ROOT_IN_OTHER_SYNC`, for a root under any `~/Library/CloudStorage` folder
  whose name does not begin `GoogleDrive-`, or under `~/Dropbox`: "{root} is
  kept by {service}; the app is proved only on Google Drive for desktop and
  on this Mac's own disk. Choose the clients folder in one of those."

Accepted are a root in `~/Library/CloudStorage/GoogleDrive-*`, which is where
the lock race of R19 is measured, and a plain folder on the Mac's own disk
(the walk's test root). A root under `/Volumes` stays allowed, as another
drive letter is on Windows. *Files:* `tracker/settings.py`. *Respects:* 137,
171 (the lock was measured on Google Drive only), 188. *Acceptance:* Linux:
`test_settings.py::test_a_mac_refuses_an_icloud_root`,
`test_a_mac_refuses_a_root_another_sync_service_keeps`,
`test_a_mac_accepts_a_google_drive_root`. Mac: walk step 7.

**R6. The hardware floor (P243).** A Drag-to-Applications install has no
installer program to refuse with, so the refusal sits at the first code that
runs:
- **The shell.** `app/main.js` checks before the one-instance lock and before
  any window. If `process.arch !== "arm64"`, or the Darwin major version from
  `os.release()` is below 23 (macOS 14), it shows `MAC_FLOOR` in a
  `dialog.showMessageBoxSync` and quits. Nothing is written.
- **The API.** `api_entry.py` makes the same check
  (`platform.machine()`, `platform.mac_ver()`) and exits 1 with the same
  sentence, because the schedule runs the API directly.
- **The bundle.** Info.plist sets `LSMinimumSystemVersion` to `13.0`,
  Electron's own floor at the pinned Electron 44 (macOS 12 was dropped), so
  the app's sentence is what macOS 13 shows; macOS 12 gets macOS's own
  refusal. An Intel Mac cannot run an arm64 binary at all, and
  gets macOS's own "not supported on this type of Mac".

`MAC_FLOOR`: "Tax Document Console needs a Mac with Apple silicon running
macOS 14 or later; this Mac has {what}, so the app stops here and changes
nothing." It is spelled once in Python and once in JS, and the two are pinned
equal. *Files:* `app/main.js`, `api_entry.py`, `tracker/settings.py` (the
sentence). *Acceptance:* Linux:
`test_api_entry.py::test_a_mac_below_the_floor_is_refused_before_anything_runs`,
plus the single-source pin. Mac: walk step 4, on a macOS 13 machine if one is
at hand; otherwise NOT VERIFIED, with the reason.

**R7. Time Machine (P242).** `after_install.run()` gains one job, after the
schedule's. On darwin it marks the data home, and Electron's own folder from
R2 (its fallback log can name a client, which is the same reason), as
excluded from Time Machine. It runs `tmutil addexclusion <folder>`: the
sticky form, which needs no administrator and travels with the folder. It
makes the folder first if needed and asks `tmutil isexcluded` first, so the
job is idempotent. It says "Left the app's data folder out of Time Machine
backups." only when it newly excluded one, and nothing otherwise. A refusal
fails the step (it is tried again at the next launch) with
`TIME_MACHINE_REFUSED`: "The app's data folder ({folder}) could not be left
out of Time Machine backups ({problem}); the app tries again at its next
start." The job goes through one seam (`after_install._tmutil`) that
`tests/conftest.py` fakes for every test, as it fakes `schtasks`. *Files:*
`tracker/after_install.py`, `tests/conftest.py`. *Respects:* 209 (once at
install, never a runbook step; Repair runs it again), 186, P234's job order.
*Acceptance:* Linux:
`test_after_install.py::test_a_mac_install_leaves_the_data_home_out_of_time_machine`,
`test_a_refused_exclusion_fails_the_step_and_is_tried_again`. Mac: kit step
H9 (`tmutil isexcluded` on both folders says Excluded).

**R8. Protected View (P240).** On darwin, `fsio.mark_from_internet` still
returns False, and the copy is made unmarked, as today. The API marks each
openable path whose copy `filer._may_carry_code` would have marked on
Windows (`vocab.path_kinds` gains one flag, `carries_code`). Each time the
shell opens such a path, it shows `PROTECTED_VIEW_MAC` in the same place
Open's own result appears. It is not a confirmation, and not refused.
`PROTECTED_VIEW_MAC`: "Protected View does not exist on a Mac, so this file
opened normally. Keep macros off in Excel, Word and PowerPoint: Settings >
Security > Macro Security > Disable all macros without notification." It is
learned from the API, as `shellSays` is. The place is the page notice the
renderer shows for Open's result (`app/renderer/shell.js`), never a dialog
or a sheet with a button. *Files:* `tracker/api.py`, `app/main.js`,
`app/renderer/shell.js`. *Respects:* 190 (a Windows copy is still never made unmarked;
`NO_OPEN_CODES` is unchanged). *Acceptance:* Linux:
`test_api.py::test_a_mac_says_protected_view_does_not_exist_each_time_a_macro_copy_opens`,
and the shell pin in `test_single_source.py`. Mac: walk step 10.

**R9. Room as if under Windows (P241, P244).** One constant,
`layout.WINDOWS_ROOT_LENGTH = 48`: the length of a Google Drive for desktop
root on Windows with a 31-character shared-drive name, which covers a buying
firm's root as well as the runbook §1 root (28 characters). It is not a
setting. On darwin, every measure of room uses
`layout.measured_length(path, root)`: `WINDOWS_ROOT_LENGTH` plus the length
of `path` relative to the clients root,
counting each separator as one character. That replaces `len(str(path))` at
every site compared with `path_limit()`, `limit_for()` or `folder_need()`;
the builder lists every site in the pull request. On darwin `short_paths()`
answers True, the default Windows with long paths off, so the reserves of
P29 apply and the folder opens on any Windows desk. Refusals then quote
Windows numbers ("past the 259 Windows allows"). Off darwin,
`measured_length` is `len(str(path))`, as today. `tests/conftest.py` gains an
autouse fixture that pins the measure to the absolute length unless a test
says it is on a Mac, so the suite's root-length tests mean the same on every
machine. *Files:* `tracker/layout.py`, `tracker/filer.py` (and any other site the
builder finds), `tests/conftest.py`. *Respects:* 125, 131, P29, P244.
*Acceptance (Linux):*
`test_layout.py::test_a_mac_measures_room_as_if_under_the_windows_root`,
`test_filer.py::test_a_return_that_fits_on_windows_fits_on_a_mac_and_one_character_more_does_not`.

**R10. Files Drive has not downloaded yet.** `validators.is_cloud_placeholder`
reads Windows attributes only, so on a Mac a Stream-mode Drive file that is
not downloaded (a "dataless" file) is read like any other. Reading it forces a
download inside the reading's safety stop. On darwin it answers
`st_flags & 0x40000000` (`SF_DATALESS`, read from `os.stat` without opening
the file), so the pass treats it as `PENDING_SYNC`, exactly as Windows treats
a placeholder. *Files:* `tracker/validators.py`. *Respects:* the standing
rule that nothing is guessed, and 109. *Acceptance:* Linux:
`test_validators.py::test_a_mac_dataless_file_is_waiting_for_sync`. Mac: kit
step H8.

**R11. Words that name Windows.** Where a sentence the app shows names a
Windows program or place, darwin gets its own words from the same table
(`tracker/api.py`'s menu words and `vocab.shell`). These are proposed here
and approved when Jason approves this SPEC:

| Today | On a Mac |
|---|---|
| `show_in_explorer` "Show in File Explorer" | "Show in Finder" |
| `lock-held` "Another PC Sorting" | "Another Mac Sorting" |
| `tools/lockfiles.py` `NOT_SET_UP` "Run Setup.bat once…" | "Run setup.command once…" (pinned to `main.js` as today) |
| `SCHEDULE_UNREACHABLE` "…Task Scheduler could not be started" | "…launchd refused it" |

The `&` mnemonic in `&Tools` and its neighbours is stripped on darwin if
Electron shows it (kit step H11). *Files:* `tracker/api.py`,
`tracker/after_install.py`, `tools/lockfiles.py`, `app/main.js`.
*Acceptance (Linux):* `test_api.py::test_a_mac_is_never_shown_a_windows_word`,
and `test_single_source.py`'s existing pins with a darwin row each.

### B. Build and launch

**R12. The build lock installs on a Mac.** PyInstaller needs
`macholib; sys_platform == "darwin"`, and `requirements-build.lock` does not
name it, so `--require-hashes` refuses the install (191). Add it to
`requirements-build.txt` and re-hash with `python tools/lockfiles.py hash`.
`tests/test_build.py` gains `MAC_ENVIRONMENT = {"sys_platform": "darwin",
"python_version": "3.14"}`: every lock must resolve completely in it, and
every binary package must carry a `macosx_*_arm64` wheel hash. That covers
onnxruntime 1.30.0 (arm64 wheels only, `macosx_14_0`), opencv, numpy,
shapely, pyclipper, pillow, pillow-heif and pypdfium2. *Acceptance (Linux):*
`test_build.py::test_every_lock_resolves_for_an_apple_silicon_mac`.

**R13. The frozen API on darwin.** `api_entry.spec` gains a darwin branch:
`target_arch="arm64"` (universal2 is impossible, because onnxruntime has no
x86_64 Mac wheel), no `icon` (the API is a console binary inside the bundle),
`codesign_identity=None` (PyInstaller signs ad-hoc) and
`entitlements_file=None` until job 3. `freeze_support()` already runs in
`api_entry.py`. The frozen smoke check must prove that a reading child starts
under `spawn`. *Acceptance:* Linux: `test_build.py` pins the branch. Mac: kit
step H1 (frozen smoke: `--run` over the scratch root, one reading done).

**R14. The shell (`app/main.js`).** These changes:
- `FROZEN_API` drops the `.exe` suffix off win32.
- `SETTINGS_DIR` follows R2.
- On darwin the menu bar gains `{ role: "appMenu" }` first (About, Hide,
  Hide Others, Quit with ⌘Q), and File loses its quit item. Quit lives in the
  app menu on a Mac.
- `setAppUserModelId` runs on win32 only.
- `BrowserWindow`'s `icon` stays `.ico` (macOS ignores it). The bundle's icon
  comes from R15.
- Back gains ⌘[ on darwin beside Alt+Left (`app/renderer/pages.js`).
- The floor check of R6 and the sentence of R8.

The one-instance lock (160), the devtools refusal (176) and `spawn` are
portable. *Acceptance:* Linux: `test_shell.py`, `test_shell_menu.py`
(darwin rows) and `node --check app/main.js`. Mac: kit step H11 (the menu
bar, ⌘Q, and ⌘H).

**R15. The `.icns`.** `pilot/brand/tax-document-console/source/export.py`
writes `app/assets/icon.icns` from the same PNGs as `icon.ico`, through a
new pure-Python packer `icns.py` beside `ico.py` (types `icp4`, `icp5`,
`ic07`–`ic14`, PNG payloads), so no Mac is needed to make it. Both icons
come from one export, consistent with P232. *Acceptance (Linux):*
`test_build.py::test_the_mac_icon_is_a_byte_identical_copy_of_the_artworks`.

**R16. Three scripts for the batch files.**
- `Setup.bat` becomes `setup.command`. It checks for `python3` at the floor
  `pyproject.toml` declares and for `npm`. It runs
  `python3 -m venv --clear .venv`, the two hash-checked installs (R-11's two
  steps, 169), `npm ci`, `tools/lockfiles.py stamp .venv`, and last
  `python -m tracker.after_install --reason setup`.
- `Start App.bat` becomes `start.command`: `lockfiles.py verify .venv`, then
  `node node_modules/electron/cli.js .`. It never installs.
- `Build App.bat` and `pilot/Build Pilot Installer.bat` become
  `build-mac.sh`, which does R17.
- `Build GPU Pack.bat` has no Mac counterpart: the CPU reader is the Mac
  reader (R32).

Every script starts with `cd "$(dirname "$0")"`, finds tools with
`command -v`, never with the working folder first, and runs under the
`/bin/bash` 3.2 that macOS ships (no `mapfile`, no `${x,,}`). Git checks the
scripts out with LF line endings and mode 100755 (`.gitattributes`).
`ONE_TIME_STEP_DOCUMENTS` in `test_single_source.py` adds `setup.command`
and `start.command`. *Files:* the three scripts, `.gitattributes`,
`tests/test_build.py`, `tests/test_single_source.py`. *Respects:* 191, 209
(no "run this once" wording), 169. *Acceptance:* Linux: `bash -n` on each,
plus `test_build.py`'s existing pins (hash-checked installs, the reader's two
steps, after-install last after the stamp, the launcher never installs, own
folder ignored, product name read from `package.json`) extended to the
scripts, and `test_scripts_check_out_with_lf_and_execute`. Mac: kit step H1
(`setup.command` and `start.command` from a clean clone).

**R17. The bundle and the `.dmg`.** `build-mac.sh` builds them in seven
steps:
1. Freeze with R13 in `build-portable/venv`.
2. Run `electron-packager --platform=darwin --arch=arm64
   --icon=assets/icon.icns --app-bundle-id=com.jparkassociates.taxdocumentconsole
   --extend-info=assets/Info-mac.plist`. That plist holds
   `LSMinimumSystemVersion` (R6) and the `NSDesktopFolderUsageDescription`,
   `NSDocumentsFolderUsageDescription` and `NSDownloadsFolderUsageDescription`
   strings.
3. Copy the freeze into `Contents/Resources/tracker-api/` with `ditto`.
4. Write `BUILD-INFO.txt` into `Contents/Resources/`. That is where
   `after_install.build_info` looks from `Contents/Resources/tracker-api/tracker-api`
   (two parents up), and the file must be written before signing.
5. Ad-hoc sign from the inside out: every Mach-O in `Resources/tracker-api`,
   then the app (`codesign --force --sign -`). Then
   `codesign --verify --deep --strict`. Copying the freeze into a packaged
   app breaks Electron's seal, and on Apple silicon an app with a broken seal
   is called damaged.
6. Prove the package holds no store, log, task file or settings, as
   `test_build.py` pins for Windows.
7. Run `hdiutil create -format UDZO` from a folder holding the app and a link
   to `/Applications`, name it
   `Tax-Document-Console-<version>-mac-arm64.dmg`, and write
   `shasum -a 256` beside it.

*Acceptance:* Linux: `test_build.py` pins the order (info before signing,
signing before the image) and the names read from `package.json`. Mac: kit
steps H1 and H2.

**R18. A `macos` label, and no macOS job on push.** `ci.yml` gains a `macos`
job that is the `windows` job with `'macos'` in its condition and
`os: macos-latest`, on Python 3.14. It runs once when a draft is marked
ready with the label on, or when the label is added to a ready pull request.
**No macOS job runs on a push to `main`, on a draft, or on any other
branch.** A macOS run bills at 10× Linux (about 150 Linux-minute equivalents
for one ~15-minute gate run). The label is the explicit ask, and only for
work touching R19–R22, R23–R30 or a darwin-only test.
`test_build.py::test_ci_never_fires_per_commit` pins the `macos` condition
whole, as it pins Windows'. *Respects:* 207, 211, 137 B3 (actions pinned by
commit).

### C. Lock, host and durability on POSIX

**R19. A held lock is held on POSIX.** `acquire_lock` takes
`fcntl.flock(fd, LOCK_EX | LOCK_NB)` on the descriptor it keeps open. Before
deleting a lock judged stale, `_replace_stale` (and so `clear_stale_lock`)
opens the file and tries `flock(LOCK_EX | LOCK_NB)`. If that is refused, the
owner is alive, and the take is refused with the Windows sentence
"…looks stale ({age}s old) but is still held by a running process".

What the suite's held-lock semantics mean on POSIX:
- An unlink from outside is **not** refused on POSIX. The first half of
  `test_a_held_lock_cannot_be_deleted_from_outside` stays Windows-only.
- What is pinned on both systems is the second half, and
  `test_clearing_a_stale_lock_that_is_still_held_is_refused`: no taker and no
  clear replaces a lock its owner still holds. `flock` belongs to the open
  file, so this holds inside one process too.
- The kernel releases a `flock` when its owner dies, so a killed pass leaves
  a file that the dead-owner rule clears, as today.
- Advisory locks are local to one machine, so nothing changes between
  machines (171, 137 L6).

The two `@on_windows` tests are split into a POSIX pair. *Files:*
`tracker/locking.py`, `tests/test_locking.py`. *Respects:* 159 (A-2, the
breaker), 171 F1/F2, 189, 137 L6. *Acceptance:* Linux (real `flock`):
`test_locking.py::test_a_held_lock_that_looks_stale_is_refused_on_posix`,
`…_clearing_…_on_posix`. Mac: kit step H4, `python -m tracker.locking race`
on a folder in `~/Library/CloudStorage/GoogleDrive-*`, which repeats
decision 171's measurement on the Mac's File Provider. Its counts go in the
results.

**R20. Boot time on a Mac.** `locking.boot_time()` on darwin reads
`kern.boottime` through `sysctlbyname` (`ctypes`, a `struct timeval`), so the
boot rule (189 A-F3) works on a Mac. Today it reads `/proc/uptime` and
answers None there. *Acceptance:* Linux (with `sysctlbyname` stood in):
`test_locking.py::test_a_mac_knows_when_it_last_started`.

**R21. A stable machine name.** On darwin, `locking.this_host()` answers
`scutil --get LocalHostName` (the name in Sharing settings, which does not
change with the network), read once per process and case-folded.
`platform.node()` on a Mac can follow DHCP or Bonjour (a `-2` suffix), so the
Mac would take its own locks for another host's and its designation would
name a computer that is gone. If `scutil` fails, the answer is
`platform.node()` and the failure is kept on the error log. The name must fit
`scheduling.HOST_NAME`, or the designation refuses it with `HOST_UNNAMED` as
today. A fresh install has no older lock or ledger line naming the Mac by
another name (P238). *Respects:* 159 S1, 209, 115 (no network module).
*Acceptance:* Linux:
`test_locking.py::test_a_mac_names_itself_by_its_local_host_name`. Mac: kit
step H7 (the name is the same on two networks).

**R22. A flush reaches the disk.** On macOS, `fsync` and SQLite's
`synchronous = FULL` do not flush the drive's cache. Every flush therefore
goes through one function, `full_sync(fd)`: on darwin
`fcntl(fd, F_FULLFSYNC)`, falling back to `os.fsync` where the volume
refuses it (`ENOTSUP`/`EINVAL`), which is said once on the error log;
elsewhere `os.fsync`.

The layering forces two copies. `fsio` imports nothing of the package, and
`ledger`, `locking` and `store` may not import `fsio`. So the function lives
in `fsio` (for `fsio`, `runner`, `scheduling`) and in `locking` (for
`locking`, `ledger`, `store`), with one test holding the two identical. The
call sites are `fsio` (four, including the folder flush), `ledger` (three),
`locking` (one), `store` (two), `runner` (one) and `scheduling` (one). The
assessment named only `fsio`.

`checkpoint` and `store` also set `PRAGMA fullfsync = ON` and
`PRAGMA checkpoint_fullfsync = ON` on every connection (they do not
persist).

*Respects:* 155, 159, 189, the `test_layers` table. *Acceptance:* Linux:
`test_fsio.py::test_every_flush_goes_through_full_sync` (no other `os.fsync`
under `tracker/`), `test_fsio.py::test_a_mac_flush_asks_for_a_full_sync`
(`fcntl` stood in), and `test_checkpoint.py` / `test_store.py` pin the
pragmas.

### D. The schedule on launchd

**R23. The agent's file.** `scheduling.launch_agent_plist(...)` renders, with
`plistlib`:
- `Label` `com.jparkassociates.taxdocumentconsole.schedule`, a constant;
- `ProgramArguments`, an argv list from a new `runner_argv()`, whose
  Windows-quoted join stays `runner_arguments()`. Frozen, that is the API in
  `Contents/Resources/tracker-api/` plus `RUNNER_MODE_FLAG`, `PRODUCT_FLAG`
  and the product name, then `SETTINGS_FLAG` with the settings folder and
  `LOG_FLAG`. It names no clients root (131);
- `WorkingDirectory`, as `app_dir()`;
- `StartCalendarInterval`, one `{Hour, Minute}` entry for every time of day
  that is the start plus a whole number of intervals, 1440/every entries.
  Task Scheduler's `Duration P1D` repeats **around the clock** from the start,
  not until midnight as the assessment read it, so the Mac does the same. For
  "once a day" there is one entry;
- `ProcessType` `Standard`, and no `RunAtLoad`;
- `AssociatedBundleIdentifiers`, the app's id, so "Allow in the Background"
  names the app.

It is written atomically to `~/Library/LaunchAgents/<Label>.plist`, never
into the data home, because that is the one place launchd reads it.
launchd's own behaviour replaces three Task Scheduler settings:
- `IgnoreNew`: one label is one process at a time.
- `InteractiveToken`: the `gui/<uid>` domain runs only while the person is
  signed in.
- `StartWhenAvailable`: a time missed while asleep runs on wake. One missed
  while the Mac was off is not made up, and the draft-day logic already
  covers that.

*Acceptance (Linux):*
`test_scheduling.py::test_the_mac_agent_runs_the_times_the_windows_task_runs`
(the set of times from the plist equals the set the XML implies, for every
`EVERY_CHOICES`), `test_the_mac_agent_names_the_settings_folder_and_no_root`.

**R24. Register, ask, remove.** Every `launchctl` call goes through one seam,
`scheduling._launchctl` (like `_schtasks`, with the same 60 s limit), and
`tests/conftest.py`'s autouse fixture fakes it so no test reaches a real
launchd:
- `register_here` on darwin writes R23's file, runs
  `bootout gui/<uid>/<Label>` (where none is loaded, that answer is
  ignored), then `bootstrap gui/<uid> <file>` and `enable gui/<uid>/<Label>`.
- `task_query` runs `print gui/<uid>/<Label>`: 0 means it is loaded, and any
  other code means it is not.
- `remove_task` runs `bootout` and deletes the file.

`task_scheduler_here()` is renamed `scheduler_here()` and answers True on
win32 and darwin. `NO_TASK_SCHEDULER` / `SCHEDULE_NOT_HERE` stay for Linux.
*Respects:* 209 (one registration, every door), P198 F6, 131. *Acceptance:*
Linux: `test_scheduling.py::test_a_mac_registers_through_launchctl_bootstrap`,
`test_a_mac_removes_its_agent_and_its_file`, `test_after_install.py`'s door
tests with a darwin row. Mac: walk step 8, kit step H3.

**R25. The designation is unchanged.** The first computer to register
claims the schedule, on a Mac as on Windows, by `locking.this_host()` (R21).
`--move-schedule-here` is unchanged. *Acceptance:* existing
`test_scheduling.py` designation tests, run with `system="darwin"`.

**R26. The pass stops itself at the run limit.** launchd has no execution
time limit. The lock's stale rule assumes the scheduler killed the owner by
`RUN_TIME_LIMIT_SECONDS` (locking docstring, 137 L6). So when the scheduled
runner runs off Windows it enforces that limit itself:
- At the limit less the household budget (`HOUSEHOLD_BUDGET_SECONDS`), it
  stops as **Stop** does, after the file it is on, records the stop, and
  lets go of its locks.
- At the limit itself, a watchdog thread ends the process (`os._exit`). The
  kernel then releases its `flock` (R19), and its lock is cleared by the
  dead-owner rule.

Both are measured on the **wall clock** (`time.time`), because the lock's
age is wall time. The reading's awake clock (189 A-F9) does not advance
during sleep on a Mac. *Files:* `tracker/runner.py`. *Respects:* 159, 189,
193, 203 (Stop's contract). *Acceptance (Linux):*
`test_runner.py::test_a_scheduled_pass_off_windows_stops_itself_before_the_run_limit`,
`test_…_ends_at_the_run_limit_and_its_lock_is_cleared_as_dead`.

**R27. Switched off in the background, and the first pass.** At the launch
door, on the designated Mac, `_task_missing` also asks
`launchctl print-disabled gui/<uid>` for the label. When the person has
switched the item off under Login Items, Allow in the Background, the step
does **not** register again (macOS would refuse, and a person's switch is
theirs). The notice says `SCHEDULE_SWITCHED_OFF`: "macOS has switched the
schedule off for this app (System Settings > General > Login Items, Allow in
the Background). Switch Tax Document Console back on there; the app cannot
do it for you." Kit step H5 records whether `print-disabled` reflects that
switch. If it does not, the last-pass line's existing amber (runner
`LAST_PASS_OLD`) is the signal, and this R names that instead.

After registering on a program it has not run before, the step runs
`launchctl kickstart gui/<uid>/<Label>` once. The first pass then runs while
a person is at the Mac, and any permission macOS asks of the schedule's own
program (R30) is asked then. That is decision 209's rule: nothing waits for
someone to remember. *Acceptance:* Linux: `test_after_install.py`
`test_a_mac_whose_schedule_was_switched_off_is_told_and_not_re_registered`
and `test_a_new_program_on_a_mac_starts_its_first_pass_once`. Mac: walk
steps 9 and 13.

**R28. Repair Schedule.** Tools, **Repair Schedule** is unchanged: it runs
`after_install.run(reason="repair")`, which on a Mac is R24's bootout and
bootstrap, then R7. *Acceptance:* the existing repair-door tests with a
darwin row. Mac: kit step H3.

**R29. The uninstall gap.** Dragging an app to the Bin leaves
`~/Library/LaunchAgents/<Label>.plist`. launchd then fires a program that is
not there. That is harmless (nothing runs), but it breaks P12 and leaves a
Background item behind. Until job 3's signed build moves the agent inside the
bundle (`SMAppService`, which macOS removes with the app), darwin gains
Tools, **Remove the Schedule From This Mac…**. It is
`python -m tracker.after_install --remove-here` behind an API command in
`vocab.writing_commands`. It runs `remove_task`, forgets the after-install
record's program, and leaves the designation, data, settings and clients
folder alone (P12). It says: "The schedule is removed from this Mac. To
remove the app, quit it now and drag it from Applications to the Bin;
opening it again sets the schedule up again." A self-removing wrapper
(`/bin/sh -c` before the API) was rejected: it changes which program macOS
attributes the Drive permission to (R30). *Acceptance:* Linux:
`test_after_install.py::test_removing_the_schedule_from_a_mac_leaves_every_folder`.
Mac: walk step 14.

**R30. The Drive permission for the unattended pass.** macOS attributes file
access to the "responsible" program. For the API the shell starts, that is
the app. For the pass launchd starts, it is
`Contents/Resources/tracker-api/tracker-api` itself, and for an unsigned build
macOS keys that grant to the exact build (P239). So on darwin, a
`PermissionError` walking the clients root gets a code of its own,
`root-not-permitted`, in `runner.PASS_REASONS`: "macOS did not let the
schedule read the clients folder; open the app, and allow it when macOS asks
(runbook, 'On a Mac')". Today it falls under `root-unreadable`. R27's
kickstart raises the request at install. *Acceptance:* Linux:
`test_runner.py::test_a_mac_pass_refused_the_root_says_macos_did_not_allow_it`.
Mac: walk steps 9 and 12, kit step H3.

### E. The reader

**R31. A memory cap off Windows.** `ReadingChild.run` waits in slices of
`MEMORY_WATCH_SECONDS` (0.5 s) rather than one `poll(left)`. After each
slice it reads the child's memory:
- on darwin, `proc_pid_rusage(pid, RUSAGE_INFO_V2)` `ri_phys_footprint`
  through `ctypes` (what Activity Monitor calls Memory);
- on Linux, `/proc/<pid>/statm` resident pages.

Past `self.memory_limit` (`PROCESSOR_CHILD_MEMORY`, 2 GB), the child is ended
as a crash with today's words ("…; it had reached its memory limit (2 GB)").
The next document gets a fresh child, as the Windows job object does.
`setrlimit(RLIMIT_AS)` is rejected because it is not a reliable cap on macOS.
A footprint that cannot be read is no cap, and that is said once on the error
log (never a guess). The two skipped cap tests gain POSIX twins. *Files:*
`tracker/ocr.py`, `tests/test_ocr.py`. *Respects:* 150, 169 R-4 and §9.
*Acceptance:* Linux:
`test_ocr.py::test_a_reading_past_its_memory_on_posix_ends_as_a_crash_and_is_replaced`,
`test_the_watch_does_not_stretch_a_readings_stop`. Mac: kit step H1 (one
reading under the frozen API).

**R32. The CPU reader is the Mac reader.** Plain `onnxruntime` already
installs on a Mac (`sys_platform != "win32"`), and `gpu_pack()` finds none.
Nothing else is required. The kit times a season-sized pass on the CPU reader
(kit step H10) for the CoreML decision: the pass must finish well inside the
two-hour schedule slot (P247, section 8).

### F. Check kit and runbook

**R33. `pilot/mactest/`** mirrors `pilot/wintest/`:
- `run_checks.sh`, in bash 3.2. `--tests a,b` runs each named file as its own
  `python -m pytest` process, side by side, then builds with R17. With no
  `--tests`, it runs the whole suite. It writes PASS / FAIL / NOT VERIFIED /
  INFO with evidence to `~/PilotTest/results/checks.json`. A missing tool is
  reported with where to get it (python.org's 3.14 installer, nodejs.org LTS)
  and the script stops; it installs nothing itself.
- `PROMPT.md`, for Claude Code on the Mac, with wintest's safety block
  (generative AI reads only the made-up samples under `~/PilotTest/Clients`,
  nothing is sent, no tag).
- `RESULTS-TEMPLATE.md`.
- The sample documents come from `pilot/wintest/make_samples.py`, by path,
  not copied.

The prompt lists the exact test files: `test_settings`, `test_after_install`,
`test_scheduling`, `test_runner`, `test_locking`, `test_fsio`,
`test_checkpoint`, `test_store`, `test_ledger`, `test_layout`, `test_filer`,
`test_validators`, `test_ocr`, `test_api`, `test_api_entry`, `test_build`,
`test_shell`, `test_shell_menu`, `test_single_source`, `test_layers`,
`test_repo_map`, `test_tripwire`. These are the files this port changes,
run on the system they change for.

It lists the hands-on steps, with why each is chosen:
- H1, the build and the frozen smoke (R13, R16, R17).
- H2, section 3's walk, steps 1–14.
- H3, the launchd job running a pass with nobody at the Mac, and Repair (R24,
  R28, R30).
- H4, the lock race on the Drive folder, and runbook §6 L2 (R19).
- H5, the Allow in the Background switch (R27).
- H6, iCloud's Desktop & Documents signal (R5).
- H7, the machine name on two networks (R21).
- H8, a Stream-mode Drive file: the pass waits on it, and the Overview's
  stat-only fingerprint does not download it (R10).
- H9, `tmutil isexcluded` (R7).
- H10, a season-sized pass timed on the CPU reader, against the two-hour
  slot (R32, P247).
- H11, the menu bar and ⌘Q (R14).
- H12, an accented name written on the PC and moved on the Mac (190 (5)).
- H13, sleep and wake around a scheduled time (R23).
- H14, the Drive prompt's exact words (R30).

Steps that already passed on unchanged code are not repeated (Jason,
2026-09-29). *Acceptance:* Linux: `bash -n`, and
`test_pilot.py::test_the_mac_kit_names_the_same_safety_rules_as_the_windows_kit`.

**R34. The runbook's Mac paragraphs.** These are parallel paragraphs, not
edits to the Windows text:
- §1: which machine, the data folder
  (`~/Library/Application Support/tax-document-tracker-pilot`), the settings
  folder, the window's own folder, the program in Applications, launchd and
  Allow in the Background, the floor (P243), and Open Anyway with the Drive
  permission again after an upgrade (P239, one line).
- The Protected View setting (P240, R8).
- Time Machine (P242).
- §6, moving to or from a Mac, and removal (R29).

`test_single_source.py` accepts them. The one-machine rule is still stated
once, decision 209's one-time-step matcher covers the new text, and decision
190's tests (no one is sent to open a file themselves) read the Mac
paragraphs too. *Acceptance (Linux):* `test_single_source.py`.

**R35. The product page.** `PRODUCT.md` and `README.md` state the floor in
one sentence (P243) and name the `.dmg`. *Acceptance:* `test_single_source.py`
pins the floor sentence to R6's words.

**R36. The suite on a Mac.** Darwin-only failures are unknown today, because
no Mac has run the suite. Known ones to fix before the kit runs:
- `tests/test_content_check.py`'s process helper reads `/proc/<pid>/stat` to
  spot a zombie. On darwin it falls back to "alive" and waits out its
  15-second `eventually`. It switches to `os.waitpid(pid, WNOHANG)` where the
  test owns the child, and to `ps -o stat=` otherwise.
- The autouse fixtures of R7, R9 and R24.
- `short_root` on a Mac sits under `/private/var/folders/…`. R9's fixture
  keeps the room tests independent of it.

*Acceptance:* the H1 run of section 7's files is all PASS on the Mac.

**R37 (job 3; lands when P239's membership exists). Signing.** These parts:
- a Developer ID Application identity;
- the hardened runtime on every Mach-O, inside out;
- entitlements settled by one signed test build. Electron needs
  `com.apple.security.cs.allow-jit`; whether the frozen Python or onnxruntime
  needs `allow-unsigned-executable-memory` or `disable-library-validation`
  is what that build shows;
- `xcrun notarytool submit --wait` and `xcrun stapler staple` on the `.dmg`;
- the agent moved inside the bundle (`Contents/Library/LaunchAgents`) and
  registered through `SMAppService`, which closes R29's gap and keeps the
  Drive grant across upgrades;
- a `build.yml` `macos-latest` job on `v*` tags only, with actions pinned by
  commit and the signing secrets. At about 300–400 Linux-minute equivalents
  per tag, it is never run per commit.

Until then the Mac package is built and checked on the Mac by the kit.

## 5. What does not change

- **The engine and the routing**: router, catalog, matcher, scanner, filer
  decisions, manifest, reminder. No catalog word or typed case changes, so
  `docs/vocab-coverage.md` is untouched and the backtest baseline cannot
  move. R9 and R10 change what a measure and a placeholder answer on a Mac
  only.
- **The record format**: ledger lines, store schema (`SCHEMA_VERSION`),
  checkpoint, designation file, layout and names. A Mac writes exactly what a
  PC writes.
- **The standing rules**, worded once in `STANDING_RULES`: no generative AI
  reads a client document, originals are never altered, nothing is guessed,
  nothing is sent. No SMTP, network call or mail client enters any path
  (`test_layers`' network-module guard holds; `scutil`, `launchctl` and
  `tmutil` are local).
- **The Windows product and its tests**: every Windows branch, sentence,
  installer (`setup.iss`), batch file, `pilot/wintest/` and the Windows CI
  job. Every darwin branch is added beside the Windows one. A Windows test
  that changes is only one that gains a darwin row.
- **The one-machine rule** (runbook §1). A Mac is a practice's one machine,
  never a second desk (P238). There is no carry-over or migration from a PC
  (P238; runbook §6's move stays the documented way).

## 6. Rules for every job below

- Behaviour on Windows and Linux does not change, except R19 (a held lock is
  now held on Linux too), R26 (the self-limit applies to any scheduled pass
  off Windows) and R31 (the cap applies on Linux too). Each is named in its
  job's pull request.
- The standing rules, the layering table in `tests/test_layers.py` and the
  single-source tests hold. No new load-time import crosses a layer. R22's
  two copies are the layering's price, and a test holds them identical.
- Every job edits `docs/repo-map.curated.json` where a module's purpose,
  artifact or cross-language hop changes. New artifacts: the launchd plist,
  the Time Machine exclusion, the `.icns`, the Mac scripts and the kit. It
  then runs `python tools/repo_map.py update` and commits the map in the same
  commit.
- Decision rows: each job that changes behaviour a row protects appends its
  row to `pilot/DECISIONS.md`, citing this SPEC's R-numbers.
- The gate before push, per decision 207. Dead code in the changed files
  goes first. Then the job's tests (section 7) under the floor interpreter
  (3.11) and the office's (3.14), each file its own process. Then
  `python -m ruff check .`, `python tools/repo_map.py check` and, for job 5,
  `python tools/vocab_report.py check`. The whole suite runs only for job 5,
  which reaches the engine (Jason, 2026-09-29). After review fixes, only the
  tests the fix touches run again.
- Build on Sonnet, and review on Opus at high effort in a session that did
  not build the job. Findings are numbered against this SPEC. A rebuild fixes
  findings and nothing more.
- Everything lands in one draft pull request, in the order below, each job
  its own commits, marked ready once when the stack is final (decision 211).
  The `windows` label goes on it (R19 and R22 touch the held lock and the
  atomic replace). The `macos` label goes on it only after job 2 lands
  R18, and costs one run.
- Each job ends with its handoff in the pull request's description, not a
  file. A job that needs the Mac ends its Linux half with the kit's
  `--tests` list and hands-on steps named.

## 7. The jobs

Lanes: jobs **1**, **5** and **7** touch different files and run at once.
Job **2** follows job 1 (they share `app/main.js` and `tracker/api.py`). Job
**6** follows jobs 2 and 5 (it edits `runner`, `scheduling`, `main.js` and
`tests/conftest.py` after them); R7 sits in job 6 because it is an
after-install job and job 6 already fakes its seam. Job **8** runs last.
Job 4 (a read-only viewer for a second desk) is dropped: P238 makes the Mac
the one machine. The table is in landing order.

| # | Job | Files | Tests to run | R | Where it finishes |
|---|---|---|---|---|---|
| 1 | **Mac homes and guards**: the data home, settings out of the bundle, disks, program location, the clients-root guard, the floor (Python and shell), the Protected View sentence | `settings`, `api`, `api_entry.py`, `app/main.js` (`SETTINGS_DIR`, floor, R8), `app/renderer/shell.js` (R8's notice) | `test_settings`, `test_after_install`, `test_api`, `test_api_entry`, `test_scheduling`, `test_tripwire`, `test_errors`, `test_single_source`, `test_layers`, `test_repo_map` | R1–R6, R8 | **Linux alone**; walk steps 4–7 and 10 in job 8's kit run |
| 5 | **Lock, host, durability, room and placeholders on POSIX** | `locking`, `ledger`, `store`, `checkpoint`, `fsio`, `runner` and `scheduling` (the flush sites only), `layout`, `filer`, `validators`, `tests/conftest.py` (the room fixture) | the whole suite (it reaches the engine), then `vocab_report.py check` | R9, R10, R19–R22 | **Linux alone**; H4, H7 and H8 in the kit |
| 7 | **The reader on the Mac**: the POSIX memory watch | `ocr` | `test_ocr`, `test_content_check`, `test_filer`, `test_runner`, `test_single_source`, `test_layers`, `test_repo_map` | R31, R32 | **Linux alone**; H1 and H10 in the kit |
| 2 | **Build, launch and words**: build lock, spec branch, shell changes, `.icns`, the three scripts, the bundle and `.dmg`, the `macos` label, the Mac words | `requirements-build.txt/.lock`, `api_entry.spec`, `app/main.js`, `app/renderer/pages.js`, `app/assets/icon.icns`, `pilot/brand/tax-document-console/source/export.py` and a new `icns.py` beside it, `setup.command`, `start.command`, `build-mac.sh`, `app/assets/Info-mac.plist`, `.gitattributes`, `.github/workflows/ci.yml`, `tracker/api.py` and `tools/lockfiles.py` (words) | `test_build`, `test_lockfiles`, `test_shell`, `test_shell_menu`, `test_api`, `test_pilot`, `test_single_source`, `test_layers`, `test_repo_map`; `bash -n` on each script | R11–R18 | **Needs the Mac kit**: H1, H2 steps 1–3, H11 |
| 6 | **The schedule on launchd and Time Machine**: plist, launchctl seam, self-limit, switched-off check, first-pass kick, repair, removal, the permission sentence, the Time Machine job | `scheduling`, `after_install`, `runner`, `api` (the removal command), `app/main.js` (its menu item), `tests/conftest.py` (the `launchctl` and `tmutil` fakes) | `test_scheduling`, `test_after_install`, `test_runner`, `test_api`, `test_shell_menu`, `test_tripwire`, `test_errors`, `test_single_source`, `test_layers`, `test_repo_map` | R7, R23–R30 | **Needs the Mac kit**: H3, H5, H9, H13, H14, walk steps 8, 9, 12–14 |
| 8 | **Mac check kit, runbook and product page**, plus the suite's darwin fixes | `pilot/mactest/{run_checks.sh,PROMPT.md,RESULTS-TEMPLATE.md}`, `docs/runbook.md`, `PRODUCT.md`, `README.md`, `tests/test_content_check.py`, `tests/test_pilot.py` | `test_single_source`, `test_pilot`, `test_content_check`, `test_repo_map`; `bash -n pilot/mactest/run_checks.sh` | R33–R36 | **Needs the Mac**: the kit's full run (section 3's walk, H1–H14) is the port's acceptance |
| 3 | **Signing and notarization** — *lands when P239's membership exists* | `build-mac.sh`, `app/assets/entitlements.plist`, `scheduling` (`SMAppService` route), `.github/workflows/build.yml`, `tests/test_build.py` | `test_build`, `test_scheduling`, `test_after_install`, `test_single_source`, `test_repo_map` | R37 | Mac, and one tagged build |

Rough size, from the assessment: about 1,150 lines of code and scripts, 1,000
of tests and 250 of runbook for jobs 1, 2 and 5–8, and about 160 more for
job 3.

## 8. Open items

The four questions the SPEC first left open were ruled by Jason on
2026-10-10 (P244–P247) and are folded into the requirements above:

1. **CoreML (P243, P247).** Kit step H10 times a season-sized pass on the
   CPU reader on the office Mac. If it finishes well inside the two-hour
   schedule slot, CoreML is not built. If it does not, CoreML is a measured
   job of its own: rapidocr 3.9.2 accepts
   `EngineConfig.onnxruntime.use_coreml`, the macOS onnxruntime wheel carries
   `CoreMLExecutionProvider`, and the job would need decision 169's "really
   got the provider" check and self-test, and may not lower the backtest
   baseline.
2. **The Windows root constant (R9, P244).** 48 characters, fixed, no
   setting. Raising it later re-measures every return, so it is not changed
   lightly.
3. **Windows parity for R5 (P245).** Windows keeps accepting a OneDrive or
   Dropbox root. Parity is a separate decision, outside this port.
4. **The package (R6, P246).** A `.dmg`, with the floor refusal at the app's
   first start; an Intel Mac gets macOS's own message. No `.pkg`.

Nothing else is open. **What the assessment missed**, all now in an R above:

5. The Mac placeholder check (R10). `is_cloud_placeholder` reads only Windows
   attributes, so a Stream-mode Drive file is read (a download inside the
   safety stop) instead of waiting.
6. Eight flush sites outside `fsio`, and the layering that forces two
   copies of `full_sync` (R22).
7. Task Scheduler's repetition runs around the clock (`P1D`), not "from 07:00"
   until midnight (R23).
8. `BUILD-INFO.txt` must sit in `Contents/Resources` to be found. Copying the
   freeze into a packaged app breaks the ad-hoc seal, so the bundle is signed
   again after assembly (R17).
9. `program_identity()` hashes the executable's path, so a translocated copy
   would be a new program at every launch. R4's refusal makes that moot.
10. The launchd pass is its own "responsible process" for the Drive
    permission, apart from the app (R27, R30). The self-limit must use wall
    time, not the awake clock (R26).
11. With P241, the suite's root-length tests would mean something else on a
    Mac, and `test_content_check` reads `/proc` (R9, R36).
12. Windows words a Mac person would see (R11). macOS's `/bin/bash` is 3.2
    (R16). Electron's own folder keeps the pilot's earlier name on a Mac, and
    may hold a client's name in its fallback log (R2, R7).
13. Outside the port: the runbook names the data folder
    `%LOCALAPPDATA%\tax-document-tracker` (§1, §6), but
    `settings.DATA_HOME_NAME` is `tax-document-tracker-pilot`. Job 8 corrects
    the Windows line while it writes the Mac one.
