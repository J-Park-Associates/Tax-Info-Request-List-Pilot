# Shell final review A: engine and window safety

Independent Opus reviewer (built none of it). Branch `origin/claude/shell-join` at
`0b278d9`, compared with `origin/main`. Area: `tracker/api.py` (firm, state, list,
open keys, `paths` allow-list, shown/filed/moved kinds, one key one kind, misfit
codes, paused flag, vocabulary), `tracker/registry.py`, `tracker/reasons.py`,
`app/main.js`, `app/preload.js`, `.claude/settings.json` deny list.

**Verdict: nothing in this area blocks the merge.** No new code reads, moves or
alters a client document. `firm` is read-only (no lock, `follow=False`, no document
read; `test_firm_is_read_only` snapshots the tree and the store). Sorting and filing
behave as before: the engine diffs are words only (labels in `manifest`, `records`,
`runner`, `names`, `view`, `templates`) plus `Misfit.code`, and the engine's own
tests all pass. A reveal-only copy cannot be plain-opened, an unreported path or a
link is refused, and no stderr or path reaches the screen. The findings below are
about warnings and words.

## Findings

1. **The move-schedule warning is in the vocabulary but never shown.** Should fix.
   `tracker/api.py:1373` adds `SCHEDULE_MOVE_WARNING` ("Only If {host} Is
   Retired"), and SPEC-shell 11.2 says the move "gains" it (P77: a risky act keeps
   its warning). At the same time `SCHEDULE_MOVE_CONFIRM` (`api.py:5094`) was cut to
   "Move Schedule Here From {host}?", dropping "do this only when {host} has stopped
   running it for good". The only confirm, `app/renderer/app.js:1949`, still shows
   `move_confirm` alone, and no renderer file reads `move_warning`.
   Scenario: someone on a second PC presses Repair Schedule and answers yes to a
   bare question. Both computers run the pass until the old one next starts, which
   is the hazard decision 209 closes. Fix: add `move_warning` to that confirm.

2. **The "do not open" warnings on emails, zips and non-documents are gone, while
   their file names became reveal links.** Should fix. JASON.
   `api.py:749-753`: `BUCKET_HEADINGS` went from "Emails and zips - opened, if at
   all, on another machine, never this one" and "Not documents - do not open; ask
   the client what they meant to send" to "Emails and Zips" and "Not Documents".
   Meanwhile `_shown_copy_key` (`api.py:2116`) gives an email or zip working copy a
   `shown_copy` key (for example, `letters.zip` in `test_api.py:8686`), so its name
   now selects it in File Explorer on the Drive-signed-in machine. One more click
   opens it, which decision 190 says never happens on that machine.
   Programs are safe: they have no working copy, so they get no key
   (`test_filer.py:9452`). Jason's call: keep a short warning on the two headings
   (for example "Emails and Zips: Open Elsewhere"), or make containers plain text
   rather than links, as an exception to ruling 15.

3. **The firm row's problem word is not Title Case.** Should fix (one line).
   `FIRM_UNREADABLE = "Could not be read"` (`api.py:5320`) is drawn as the row's
   status by `pagesCounts` (`app/renderer/pages.js:195`) and by the Overview
   (`pages.js:558`). This breaks ruling 10, and ruling 14 retired "Could Not Be
   Read" as a general word. `test_api.py:8426` pins the lower-case spelling. The
   Title Case test does not see this word because it is not in `_vocab()`.
   Suggested fix: "Record Not Readable", or Jason's word.

4. **A stale "PROPOSED" marker.** Note. `api.py:1338` still says `pick_request` and
   `name_requests` are "PROPOSED for Jason: not yet ruled on". Ruling 23 approved
   both, so S6's fix pass should remove the comment. The words themselves are
   correct.

5. **Commands that are not a sort are reported as a stopped sort when they time
   out.** Note. `SHELL_KILLED` is "Sort Stopped: Ran Too Long" (`api.py:434`;
   `main.js:93`), and `main.js:311-317` uses it for every command killed at the
   30-minute cap. Examples are an `edit` or `rename` moving many copies on a
   streamed Drive, or `roll-household`. The screen says a sort stopped, and nothing
   says that part of the write may have happened. This is rare, and the old
   sentence ("The pass ran past its limit") was just as sort-specific. A neutral
   word such as "Stopped: Ran Too Long" would fit both.

6. **A failed sort no longer says why on the return's own banner.** Note.
   `SCAN_PROBLEM` lost `{error}` (`api.py:451`), so `app.js:2082` shows only "Sort
   Failed" when the pass held the asked return back. Examples are "the client folder
   is missing" and "an old clients root in the job". The household's other returns
   still show theirs (`also`), and the run log keeps it. This fits the five-word
   rule, but the preparer has no next step on screen. JASON, only if he wants the
   short reason code shown beside it.

7. **The firm view is fast enough on local disk; Drive is not measured.** Note.
   On local disk (Python 3.11, this container), 100 returns in 100 households with
   24 requests each took `firm` 1.33 s and `list` 0.42 s. That is about 10 s for
   750 returns. `_firm_draft` (`api.py:5312`) lists the household inbox once per
   return (`unsorted_in_inbox`), not once per household, and each return reads its
   record, index and ledger. On a streamed Drive this could be several times
   slower. It is not a blocker: the page runs `firm` in the background and keeps
   what it last had (`shell.js:175-197`). If the office finds it slow, count each
   household's inbox once.

No findings on: preload (one `menu` channel, the `open` second argument only); the
menu channel (sender check, unknown ids and popups dropped, token of 64 characters
or fewer); the fallback log (lstat, no link or folder, 256 KiB cap with one `.1`
copy, never shown); the deny list (both fallback paths and `.1` are in `deny`, and
the data home `tax-document-tracker-pilot` was already there); first paint;
`Misfit.code` (every construction site carries one, and `test_shell.py:2396`
checks every code has a word); the paused flag (the same `open_years` rule as
`runner.py:1173`); `_firm_key` suffixing; one key one kind in `state`.

## Tests run (each file its own process; Python 3.11, then 3.13)

`test_api test_api_entry test_registry test_reasons test_shell test_shell_menu
test_layers test_single_source test_repo_map test_router test_filer test_scanner
test_manifest test_runner test_reminder test_names test_records test_view
test_templates test_after_install`: every file passed on both interpreters.
`ruff check .` is clean and `repo_map.py check` reports the map current.
The engine's regression files (router, filer, scanner, manifest, runner) are
included because `api.py` changed.

## Mutation checks (scratch copy, one at a time)

| # | Mutation | Test file | Result |
|---|---|---|---|
| M1 | `main.js`: a reveal-only kind may be plain-opened | test_shell_menu | killed |
| M2 | `main.js`: the `isSymbolicLink()` check removed | test_shell_menu | survived; equivalent (on lstat a link is neither a file nor a folder, so `same` refuses it anyway) |
| M3 | `PATH_KINDS["filed_copy"]` set to `"file"` (openable) | test_api | killed |
| M4 | `_shown_copy_key` ignores the review key (one path, two kinds) | test_api | killed |
| M5 | `_firm_key` never adds its suffix | test_api | killed |
| M6 | An unreadable firm row is totalled as complete | test_api | killed |
| M7 | A moved file marked missing is counted as Needs You | test_api | killed |
| M8 | The `paused` flag is always false | test_api | killed |
| M9 | A registry misfit gets the wrong code | test_registry | killed |
| M10 | The menu channel accepts any sender | test_shell_menu | killed |
| M11 | `withNoLog` appends a field the reply does not have | test_shell_menu | survived; equivalent (no such field) |
| M11b | The no-log reply carries the stderr on screen | test_single_source | killed |
| M12 | One `SHORT_REASONS` entry removed | test_reasons | killed |
| M13 | `firm` includes inactive returns | test_api | killed |
| M14 | `firm` reads with `follow=True` | test_api | **survived** |
| M15 | A moved key is reported for a row that is nowhere | test_api | killed |
| M16 | Open Error Log skips the lstat check | test_shell_menu | killed |

About M14: `test_firm_is_read_only` snapshots only a practice whose store already
matches its record, so a `firm` that catches up a lagging store would pass it. This
does not harm any document: the walk already catches the store up, as `list`
does. It is a test gap only, worth pinning if "firm writes nothing" is to hold
when a journal is behind.

This file is the only change in this commit. It is a new file under
`pilot/handoffs/`, so it may make the repository map stale; `repo_map.py update`
was not run, as instructed.
