# Tax Document Console - Mac check result

- **Date:**
- **Commit tested:** (git rev-parse --short HEAD, and the branch)
- **Summary:** PASS / FAIL, and one plain-English sentence. A step nobody saw is
  NOT VERIFIED, never PASS.

## Machine

- **Mac:** model, chip (Apple silicon), macOS version and build
- **Terminal under Rosetta?** no
- **Google Drive for desktop:** version, Stream or Mirror mode, the test folder's place
  (write GoogleDrive-<account>, never the address)
- **Had the Console been on this Mac before?** no / yes, and what Jason decided
- **How the disk image was marked as downloaded:** a real download (how) / the
  quarantine mark set by hand
- **Other machines at hand:** a macOS 13 Mac (yes/no); the office PC (yes/no);
  a second network (yes/no); iCloud's Desktop & Documents Folders (on/off)

## Automated part (run_checks.sh)

| Check | Result | Evidence |
|---|---|---|
| tools | | |
| tree | | |
| environment | | |
| room_as_windows | | short_paths, limit, root length: True 259 48 |
| ruff_and_map | | |
| tests test_settings.py | | passed / failed counts; each failing test named |
| tests test_after_install.py | | |
| tests test_scheduling.py | | |
| tests test_runner.py | | |
| tests test_locking.py | | |
| tests test_fsio.py | | |
| tests test_checkpoint.py | | |
| tests test_store.py | | |
| tests test_ledger.py | | |
| tests test_layout.py | | |
| tests test_filer.py | | |
| tests test_validators.py | | |
| tests test_ocr.py | | |
| tests test_api.py | | |
| tests test_api_entry.py | | |
| tests test_build.py | | |
| tests test_shell.py | | |
| tests test_shell_menu.py | | |
| tests test_single_source.py | | |
| tests test_layers.py | | |
| tests test_repo_map.py | | |
| tests test_tripwire.py | | |
| tests test_content_check.py | | |
| tests test_pilot.py | | |
| tests test_errors.py | | |
| tests test_lockfiles.py | | |
| build | | disk image path |
| bundle | | seal, arm64, BUILD-INFO.txt, minimum macOS, folder strings, icon |
| frozen_smoke | | list answered; dry pass read the pile as the source does; reader=processor; memory readable |
| sample_folder | | |

**Disk image SHA-256:**

## Hands-on part (in the installed app, made-up documents only)

H2, the buyer's walk (SPEC-mac section 3), step by step.

| # | Step | Result | What was seen (the exact words of any dialog or notice) |
|---|---|---|---|
| 1 | Download: shasum -a 256 equals the .sha256 file | | |
| 2 | Install: window shows the app and Applications; dragged; ejected | | |
| 3 | First open: macOS's block (15+: "Not Opened"; 14: "can't be opened because Apple cannot check it"), then Open Anyway and the password | | |
| 4 | The wrong Mac: macOS 13 shows the floor sentence and writes nothing; Intel gets macOS's message | | |
| 5a | Opened from the disk image: the app's sentence, no schedule | | |
| 5b | Opened from Downloads (translocated): the app's sentence, no schedule | | |
| 6 | Terms: tick, type a name, Sign and Accept | | |
| 7a | A root in iCloud Drive is refused with its sentence | | |
| 7b | A root in Dropbox or OneDrive is refused with its sentence | | |
| 7c | The test folder is accepted; macOS's Drive prompt (words in H14) | | |
| 8 | "Background Items Added" (which name); the notice "…now runs the schedule…every day from 07:00, every 120 minutes" with no button pressed | | |
| 9 | First pass within a minute; "Last scheduled pass: <time>, succeeded."; samples filed; originals moved byte for byte | | |
| 10 | Review copy opens normally; the Protected View sentence is a page notice, each time (twice) | | |
| 11 | Next morning: a pass from that morning, not amber | | |
| 12 | Upgrade: Replace, Open Anyway, schedule set up again, notice repeats, clients folder kept; the Drive prompt came back (yes/no) | | |
| 13 | Switched off by hand: the app's next start shows the switched-off sentence | | |
| 14 | Removal: the app says it is removed; launchctl cannot find the service; plist gone; data folder, settings and clients folder remain | | |

The other steps that need a Mac.

| # | Step | Result | What was seen |
|---|---|---|---|
| H1 | The build and the frozen smoke (above); setup.command and start.command from a clean clone (H1b below) | | |
| H1b | `./setup.command` ends "Set up."; `./start.command` opens the app; /bin/bash is 3.2 | | |
| H3 | A pass started by launchd with the screen locked succeeded and filed the new document; Repair: launchctl print before and after, bootout/bootstrap words, plutil -lint, no second first pass | | |
| H4 | `python -m tracker.locking race` on the Drive folder: "one holder in every round" (counts); the full-flush line in the error log (yes/no) | | |
| H4b | Runbook section 6 L2: a line written on the PC is named by the Mac's pass | | |
| H5 | `launchctl print-disabled` before/after the Allow in the Background switch (exact output); the app's sentence appears | | |
| H6 | iCloud's signal folder exists / not; Jason's state; the empty Documents folder was refused / accepted accordingly | | |
| H7 | Machine name on two networks: scutil LocalHostName, `this_host()` and `platform.node()` each time | | |
| H8 | Stream-mode file: the pass waits on it; `ls -lO` still says dataless afterwards | | |
| H9 | `tmutil isexcluded` on both folders says [Excluded] | | |
| H10 | Season-sized pass on the CPU reader: households, scans, minutes, peak memory, any "memory limit" (PASS at 60 minutes or less) | | |
| H11 | App menu (About, Hide, Hide Others, Quit), Command-Q, Command-H, no leading "&", the app's icon, "Show in Finder", no helper left running | | |
| H12 | Accented name from the PC (or composed by hand): moved under its own name, found by its row, form on disk | | |
| H13 | Sleep and wake around a scheduled time: a pass within a minute of waking (times) | | |
| H14 | macOS's Google Drive prompt, word for word, at steps 7, 9 and 12, and the program name each gave | | |

## Failures and notes

(One entry per FAIL or NOT VERIFIED: what was expected, what happened, the
screenshot's file name.)

## Screenshots

Kept on the test Mac in ~/PilotTest/results/screens (made-up data only; not
committed). Any screenshot showing a name that is not made up is deleted.
