# Pilot 0.3 - fixes from the Windows check of the app shell - SPEC

Status: written 2026-09-29, 11:45 PM Pacific, by the Lane 3 builder, for a
separate reviewer. Decisions **P128 to P134** (`pilot/DECISIONS.md`). Source
of every item: `pilot/wintest/RESULTS-shell.md` (A1-A4, F2-F5, N1, N2) and
`pilot/handoffs/wincheck-shell.md`, "Left", job 3, with its item "Added after
the check". P117 accepted the shell's open defaults and keeps the word
"Nothing Done". These fixes ship in Pilot 0.3 (P140); no version number is
changed here.

**Not in this SPEC:** the firm view's speed (F1, P115, its own lane) and the
"Came in Email or Zip" words (P116, its own lane). Neither lane's lines are
touched here.

**Hard rule kept.** Every reproduction below used only data built by
`tests/samples.py` in a temporary folder or the renderer harness's made-up
names. No file under `%USERPROFILE%\PilotTest` was opened.

## What staff will notice (plain English)

- The Windows check's test command works as typed, and a test file that
  passes says PASS.
- Escape closes a tooltip, wherever the keyboard is.
- A Sort's answer ("Sort Failed: Folder Not Found", "Nothing Done", files not
  sorted) stays with the client it was about. It no longer shows on
  Overview, Needs Review, Reminders or Clients, and it goes away when the
  next Sort of that client ends, on F5, or when dismissed.
- After Client > Add a Return..., the new return's page opens at once.
- With the schedule off, the message says "Sort still works. Turn it on in
  Tools > Schedule."
- A Sort that did nothing says why when it can: "Nothing Done: Inactive."
  for a return switched off.
- A held reminder names the file or files still waiting in Drop files here.

---

## 1. A1 and A2: the Windows check script (P128)

**A1 root cause.** `powershell -File script.ps1 -Tests a,b` passes `a,b` to
the script as one string, so `$Tests` holds one "file" named `a,b`
(proved on this PC: `-File` gives count 1, `-Command "& ..."` gives count 2).

**A2 root cause.** In Windows PowerShell 5.1 a process started with
`Start-Process -PassThru` reports an empty `ExitCode` unless its `Handle` was
read while it ran (proved on this PC, PowerShell 5.1.26100: empty without,
set with), so `Verdict ($r.Proc.ExitCode -eq 0)` was always FAIL.

**Ruling.** Fix the script, not the command: every documented one-liner in
`PROMPT-shell.md`, `PROMPT.md`, `PROMPT-RERUN-3.md`, `run_checks.ps1`'s own
header and `CLAUDE.md` then works as written.

- `pilot/wintest/run_checks.ps1`: two helper functions, between the marker
  lines `# BEGIN test-file helpers` and `# END test-file helpers`:
  - `Split-TestList([string[]]$list)`: each value split on commas, blanks
    dropped, trimmed.
  - `Start-TestFile($python, $file, $out)`: the `Start-Process` of today,
    then `$null = $proc.Handle` at once; returns the process.
  - The `-Tests` loop uses both; the collection loop is unchanged
    (`WaitForExit()`, then `ExitCode -eq 0`).
- `pilot/wintest/PROMPT-shell.md` ("The tests"): the one-liner is unchanged
  and now works as written.

**Owning test.** `tests/test_pilot.py`:
`test_the_check_script_splits_a_comma_joined_test_list_and_reads_each_exit_code`
(Windows only; skipped elsewhere): lifts the helper block from
`run_checks.ps1`, runs it in `powershell.exe` 5.1 with a comma-joined list
and two tiny Python scripts that exit 0 and 3, and asserts the list splits in
two and the exit codes read back as 0 and 3. Fails before the fix (no helper
block).

**Doc lines made true.** `PROMPT-shell.md` "The tests" and the header of
`run_checks.ps1`, which both use `-File`.

## 2. A3 and A4: two shell tests on Windows (P129)

**A3 root cause.** `_stub_replies` (`tests/test_shell.py`, near line 2316)
runs the whole stub as `node -e <script>`, longer than Windows' 32,767-
character command line (WinError 206).

**Ruling.** Write the script to a temporary file and run `node <file>`, as
`run_shell` already does.

**A4 root cause.** `test_reveal_is_refused_when_the_file_is_no_longer_a_file_or_is_a_link`
(`tests/test_shell_menu.py`, near line 643) calls `symlink_to` with no skip,
and this PC cannot make a link without Developer Mode (WinError 1314).

**Ruling.** Check the folder half first (a folder where the file was is
refused), then try the link under the file's own skip ("this machine cannot
make a symbolic link"), as its two sibling tests do.

**Owning tests.** The two tests themselves, on Windows: A3's two tests pass
instead of failing; A4's test checks the folder half and skips the link half
on this PC.

## 3. F2: Escape and the tooltip (P130)

**Root cause.** `tooltip.js` has no key handler; the only Escape for a tip is
the last branch of `shellKey` in `shell.js`, reached only when no dialog is
open, the focus is not in the search box, and no search list or side sheet
shows - so a hover tip over the Sort icon while the search box has focus
survives Escape (reproduced in the renderer harness).

**Ruling.** SPEC-shell 8.5 gives `tooltip.js` its own Esc logic. A keydown
listener in `tooltip.js`, on the document in the capture phase, hides a
showing tip on Escape and **does not consume the key**: the same Escape
still clears the search box, closes the side sheet or asks the dialog to
close. (Consuming it was rejected: the keyboard puts a tip on every focused
control at once, so every dialog would need two Escapes.)

- `app/renderer/tooltip.js`: `tipKey(e)` and its registration; `tipShowing()`
  goes (no caller is left).
- `app/renderer/shell.js` `shellKey`: the `if (tipShowing()) { hideTip(); return true; }`
  branch goes (dead: the tip is already hidden when it runs).

**Owning tests.** `tests/test_shell.py`:
`test_escape_hides_a_showing_tip_first_and_leaves_the_key_to_the_page`
(node: `tipKey` lifted with a fake tip; Escape hides it and neither
`preventDefault` nor `stopPropagation` is called; another key leaves it) and
`test_the_tooltip_listens_for_escape_in_the_capture_phase` (the listener is
registered with `true`, and `shellKey` no longer names the tip). Both fail
before the fix.

**Staff notice.** Escape closes a tip everywhere.

## 4. F3: a Sort's answer belongs to its return (P131)

**Root cause.** `passEnded` (`app/renderer/app.js`) said a Sort's answer
through `outcome()`, which makes plain window-wide notices that nothing but
the dismiss icon removes (decision 193), so "Sort Failed: {reason}" stayed
after a later good Sort, after F5, and on every page, the firm pages included.

**Ruling (rulings 20, 28; SPEC-shell 3.5, 8.4).**

- `app.js` keeps `sortAnswers`: return path -> the lines of its last Sort's
  answer (sentence, kind, and Retry for a pass that failed as a whole).
- When a pass ends: every return the pass ran loses its old answer, then the
  asked return's answer (if it has anything to say) is kept. What was a
  toast-free "ok" says nothing, as today.
- The answer is shown as keyed notices (`syncNotices("sort", ...)`) only
  while a page of the same household is on screen (household, year or
  return). Firm pages and Setup show none. It is re-shown on every route
  change (`appRouteChanged`) and after each pass.
- A dismissed line is forgotten (it does not come back on the next visit).
- F5 (`shellRefresh`) forgets every answer: the page is re-read from the
  record, which the app's own Sort does not write.
- The answer said while another return was shown keeps its label prefix
  ("{label}: ..."), as today.
- Unchanged: the scheduled sort's "Sort Failed" (keyed `last-sort`, every
  page), the pass's machine warnings, and every other notice.

Files: `app/renderer/app.js` (`passEnded`, new `keepSortAnswer`,
`showSortAnswers`, `forgetSortAnswers`, the notices' click handler,
`appRouteChanged`); `app/renderer/shell.js` `shellRefresh` (one call to
`forgetSortAnswers()`); `pilot/harness/app-stub.js` (the double names
`forgetSortAnswers`).

**Owning tests.** `tests/test_shell.py`:
`test_a_sorts_answer_shows_only_on_its_own_clients_pages` and
`test_a_later_sort_or_f5_takes_a_sorts_answer_away` (node: the functions
lifted from `app.js` with fakes for `syncNotices`, `shellRoute` and
`shellReturn`). Both fail before the fix.

**Staff notice.** See the list at the top.

## 5. F4: the page after Create Return (P132)

**Root cause.** `createEngagement` (`app.js`) selected the new return and
drew its state, but left the page's route on the return it was opened from,
so the return page (drawn only when the state is the route's return) drew
nothing until F5 re-read it.

**Ruling.** After a successful create the window goes to the new return's
page (`shellGo(pagesRoute(path))`), whichever page the wizard was opened
from; its notices ("return created", a dropped link) are said after it.

**Owning test.** `tests/test_shell.py`
`test_create_return_goes_to_the_new_returns_page` (static: `createEngagement`
calls `shellGo(pagesRoute(` with the new path after `adoptList`). Fails
before the fix.

## 6. F5: the schedule-off words (P133)

**Root cause.** The sentences were written before the shell renamed Scan to
Sort and moved Schedule into the Tools menu (SPEC-shell sections 5 and 11).

**Ruling.** Staff-facing words (no owner question):

| Constant | Now |
|---|---|
| `tracker/scheduling.py` `SCHEDULE_OFF` | The schedule is off on this computer. Sort still works. Turn it on in Tools > Schedule. |
| `tracker/after_install.py` `SCHEDULE_OFF_HERE` | The schedule is off on this computer; turn it on in Tools > Schedule before moving it here. |
| `tracker/after_install.py` `PREFERENCE_UNUSABLE` (last sentence) | Choose it again in Tools > Schedule. |

Left as they are, and why: `runner.LAST_PASS_OFF` ("... Scan still works.")
is not drawn by the shell (the last-sort line uses its own words) and is the
runner's, whose tests are the sorting engine's; `api.SCHEDULE_NOTE` is cut
from the screen (SPEC-shell E87). The runbook's many "Schedule button" lines
describe the full product and are pinned by `test_single_source`; only its
"Scan still works by hand" line changes to "Sort still works by hand".

**Owning tests.** `tests/test_after_install.py` (its pin of "Schedule
button" becomes "Tools > Schedule"); `tests/test_api.py` pins
`scheduling.SCHEDULE_OFF` by name and is unchanged.

## 7. "Nothing Done" and "Held" (P134)

**Reproduced** (a temporary probe on `tests/samples.py` data, not
committed): a household with a 2025 return and a 2024 return set inactive.

- The list gives the household's returns oldest year first, and a household
  or year page Sorts through `own.find(active) || own[0]` - the inactive 2024
  return. The runner skips it with code `inactive`; `scanSummary` has a word
  only for `lock-held`, so the banner read a bare "Nothing Done", although
  the 2025 return was sorted in the same pass. A Sort asked for the 2025
  return itself did not skip.
- The skip kinds that reach the bare word are `inactive`, `rolled-forward`
  and `no-room` (`runner.why_skipped`, `runner._no_room`). A skip is not an
  error, so nothing in `tracker-errors.log` is right.
- "Held: 1 Files Not Sorted" came from the sample pile's half-uploaded
  `W-2 Jane Smith 2025.pdf.tmp.driveupload`, a transfer still in progress,
  which stays in Drop files here and holds every draft (decision 133) until
  it finishes or a person removes it. The stages are greyed because a held
  reminder has no letter to re-stage (by design).

**Ruling.**

- `tracker/api.py` `SCAN_REASONS` gains `inactive: "Inactive"` and
  `rolled-forward: "Rolled Forward"` (the screen's approved words,
  `screen.inactive` and `screen.rolled`) and `no-room: "Names Too Long"`
  (new: Q1). `app.js` `scanSummary` says "Nothing Done: {why}." whenever the
  skip's code has a word (not `other`), else "Nothing Done" (P117).
- `tracker/reminder.py`: `unsorted_files_in_inbox(engagement_dir)` gives the
  name of each waiting file (or unreadable folder), sorted; the count
  `unsorted_in_inbox` is its length, so the two can never disagree.
- `tracker/api.py` reminder card: `unsorted_files` beside `unsorted`.
- `app.js` `drawReminder`: the names are listed under the hold line, after
  the held requests. A file's name only, never its folder path.
- `pilot/harness/stub.js`: its reminder card carries `unsorted_files: []`.
- Considered and left: making a household page pick the newest or an active
  return. The list carries no active flag; the reason word now says what
  happened, and the return's own Sort sorts the same household.

**Owning tests.** `tests/test_shell.py`
`test_a_sort_asked_for_an_inactive_return_says_why_nothing_was_done` (the
real engine through `run-now`, then `scanSummary`: "Nothing Done:
Inactive."); `tests/test_reminder.py`
`test_the_waiting_files_are_named_and_counted_from_one_walk`;
`tests/test_api.py` `test_the_card_shows_the_inbox_hold_in_the_apis_words_and_offers_no_approve`
(extended: `unsorted_files` names the waiting file). All fail before the fix.

**Words.** `pilot/wording-shell.tsv` gains `scan.reasons.inactive`,
`scan.reasons.rolled-forward`, `scan.reasons.no-room`; the vocabulary report
is rebuilt.

## 8. N2: the prompt's step 14 (P133)

`pilot/wintest/PROMPT-shell.md` step 14: "untick **Active — No: Sorting Skips
This Return**" in place of "set **Active** to *No: Sorting Skips This
Return*".

## 9. N1: the "Close" tip over the Sort icon (P133)

Investigated only. The app's window has the standard Windows frame (no
`frame: false`, no `titleBarOverlay`, no drag region); the renderer sets no
`title` attribute anywhere (`tests/test_shell.py` pins that every tip is
`#tip`); the Sort icon sits below the menu bar, away from the caption
buttons. A plain Windows "Close" tip is the caption button's own, drawn by
Windows (or by Windhawk, installed on that PC). **Not the app's doing; left.**
Worth one look on a PC without Windhawk at the next Windows check.

## Open for Jason

- **Q1. The reason word when a household's folder names leave no room**
  (runner code `no-room`, rare: a path too long for Windows). (a) "Nothing
  Done: Names Too Long." **(recommended; built)** (b) "Nothing Done: No Room
  for Name." (the Needs Review word, but six words, over the five-word rule)
  (c) keep the bare "Nothing Done".

## Tests this SPEC runs (both interpreters)

`tests/test_shell.py`, `tests/test_shell_menu.py`, `tests/test_pilot.py`,
`tests/test_after_install.py`, `tests/test_reminder.py`, `tests/test_api.py`,
and the guards `tests/test_layers.py`, `tests/test_single_source.py`,
`tests/test_repo_map.py`, `tests/test_tripwire.py`, `tests/test_errors.py`,
`tests/test_vocab_report.py`; then `ruff`, `repo_map.py check`,
`vocab_report.py check`. On Windows, `run_checks.ps1 -Tests` with the same
files re-proves A1 and A2 at the next Windows check.
