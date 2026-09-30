# Shell final re-review: the fix pass

Reviewer: an independent Opus session. I built none of the shell and none of
the fix pass. Branch `claude/shell-join` at `2933a67`. Diff reviewed:
`0b278d9..2933a67`, without the three review files. Checked against the
findings in `shell-final-review-A/B/C.md`, the claims in `shell-fixpass.md` and
rulings 1-29 in `shell-rulings.md`. No code was changed.

**Verdict: no finding blocks the merge.** Every finding that blocked or asked
for a fix is fixed in the code, and each fix is pinned by a test.

- **Engine.** The one change is a `code` field added to each run in the final
  line. Sorting, filing, routing, locking and what is written to client
  folders or the record are unchanged.
- **Suite.** It is green on both interpreters.
- **Still open.** Four should-fix items and a few notes, mostly words and
  documents. Two are Jason's call.

## How it was checked (the real code was run, not only read)

- **Whole suite, each test file in its own process, four at a time.** Python
  3.11.15 and 3.13 were run in fresh venvs built from `requirements.lock` and
  `requirements-nodeps.lock` (so the reader, `rapidocr`, is installed).
  - All 55 files passed on both interpreters: **4001 passed, 21 skipped, 0
    failed** on each.
  - The failures expected before the run did not happen here, because the
    reader was installed: `test_build` OCR scratch-roots, `test_ocr` (4 tests)
    and `test_real_corpus` row-2. That makes **no NEW failure**.
  - `main` (`e22b539`) was run the same way under 3.11 for comparison. When
    this was written, 42 of its 55 files had finished, all green. The branch
    has no failure, so there is nothing to compare.
- **Engine files named in the brief, all green on both interpreters:**
  `test_router`, `test_filer`, `test_scanner`, `test_manifest`, `test_runner`,
  `test_reminder`, `test_records`, `test_view`, `test_names`, `test_templates`,
  `test_after_install`, `test_registry`, `test_reasons`, `test_api` and
  `test_api_entry`.
- **Guards:**
  - `ruff check .` is clean.
  - `repo_map.py check` reports the map current (340 nodes).
  - `vocab_report.py check` reports the report current. Its only change is the
    two input hashes.
  - `docs/backtest-baseline.json` is unchanged against `main`, and no router,
    catalog, matcher or typed case changed. `tools/backtest.py check` needs a
    report run on the firm's own documents, which are not in this sandbox.
    **The baseline is not lowered.**
- **Harness:**
  - `interact.mjs`: "all interactions pass". That covers the ruling 27 year and
    wrap checks at 1100px on six pages, the ruling 28 notice, and underlined
    links in the light, dark and forced-colours themes.
  - `shoot.mjs`: 181 shots, 0 page errors. I looked at the 1100px shots of
    Overview (dark), the household page, Needs Review, Clients (All),
    Sort Failed, forced colours and the email sheet.
- **B1 reproduced before the fix and gone after it.** I used a Playwright
  probe on the real `app.js` that holds one script back by 2.5 s.
  - At `0b278d9`, holding back `shell.js`, `pages.js` or `sheet.js` gives
    "The App Hit an Error".
  - At `2933a67`, all five held-back scripts draw Overview normally, with no
    page error.
- **Mutations** (on this tree, then restored):
  - Dropping the container check in `_shown_copy_key` fails
    `test_api::test_a_set_aside_file_and_a_parked_document_are_shown_but_a_zip_or_email_is_plain_text`.
  - Putting `bootstrap()` back as the last line fails
    `test_shell::test_the_app_starts_only_after_every_script_has_loaded`.
- **The runner's new field, run for real.** In a household with two returns
  whose client folder was removed, `run-now` gives each run
  `code: "client-folder-missing"`. It is a slug: no sentence and no path.

## Engine change (brief item 1)

The complete `tracker/` diff is small:

- `runner._final_line` adds `"code": run.code`, a field the run already
  carried and already logged.
- `api.py`:
  - New words: `SHELL_KILLED_WRITE`, `SHELL_KILLED_WRITE_NOTE`,
    `SHELL_KILLED_READ`, `SCAN_PROBLEM_REASON` and `SCAN_REASONS`.
  - `_vocab` gains `writing_commands`, and the `scan` and `shell` sections
    gain the new words.
  - `_shown_copy_key` returns `""` for the containers bucket.
  - `FIRM_UNREADABLE` is now Title Case.

Nothing touches routing, filing, the scanner, locks, the store or client
folders. `_review_copy_key` already refused containers, and `_moved_copy_key`
applies only to `FILE_MOVED` rows, which are filed documents. So after this
change an email or zip gets **no key anywhere**: not in `state.paths`, not in
`firm.paths`, and so not in `main.js`'s allow-list, which is built only from
those. **Confirmed safe.**

## Per-finding verdicts

| Finding | Verdict | Evidence |
|---|---|---|
| A1 move-schedule warning | **Fixed** | `moveScheduleQuestion` puts `move_warning` under `move_confirm` and fills `{host}` in both; pinned by `test_shell` |
| A2 emails and zips (ruling 24) | **Fixed** | Engine returns no key for containers, in `state` and in `firm`. The shot shows `statement-march.eml` as plain text on the return page, in the sheet and in forced colours. Killed by mutation |
| A3 unreadable word | **Fixed** | "Could Not Be Read" is pinned. The word itself is still on Jason's open list (O1) |
| A4 PROPOSED marks | **Fixed** | The comment says ruling 23. See NEW 3 for a misattribution in the TSV |
| A5 kill at 30 min | **Fixed**, with a punctuation defect (NEW 4) | Sort, change and read now say different things. A change's words are learned from `vocab.writing_commands` |
| A6 failure reason (rulings 25, 29) | **Fixed for the asked return**; one residual gap (NEW 1) | `scanFailed` shows "Sort Failed: Folder Not Found" |
| A7 firm read-only | **Fixed** (the test gap) | The lagging-store test pins `follow=False` on the firm's own reads. As the fix pass says, the registry walk still catches a lagging store up, as `list` does; it never touches a document. Note only |
| B1 start-up race | **Fixed** | Reproduced at `0b278d9` and gone at HEAD (above). Killed by mutation |
| B2 Retry (ruling 28) | **Fixed** | The notice has no Retry. `runScan` returns when no return is chosen. F9 and Sort Now are offered only with a client open. Nothing on a firm page can send `run-now` without `--engagement`, so no flag sentence can be drawn |
| B3 cut year (ruling 27) | **Fixed** | `.row-wrap`; `interact.mjs` passes at 1100px. Shots: household page "1040 - John & Jane Smith (2025)" on two lines; Overview "1040 - Emery Pembrook (2025)" wraps |
| B4 paused words | **Fixed** | The marker row wraps; `interact.mjs` checks the words are whole on Clients |
| B5 group named by path | **Fixed** | Named by `pagesReturnName`. `pagesLabel` never returns a string holding `/` or `\` |
| B6 links by colour only | **Fixed** | Links are always underlined; statuses never are; forced colours keep `LinkText` and the underline (harness and forced-colours shot) |
| B7 style | **Fixed** | |
| C1 vocab report | **Fixed** | `vocab_report.py check` reports current; `test_vocab_report` green |
| C2 Retry/flag sentence | **Fixed** | As B2. PROMPT step 12 now uses a failed *scheduled* sort |
| C3 rulings file | **Fixed** | Rulings 1-29 and 18a are on the branch |
| C4 statuses / ledger | **Fixed** | No "S5 rebuild 2" status is left. P108-P114 were added. The ledger is refreshed |
| C5 open words for Jason | **Partly fixed** | HANDOFF now lists O1-O6, "Bad Year" and firm speed. But the other nine misfit words are still marked approved (NEW 3) |
| C6 SPEC rulings 16/17/20/28 | **Fixed** | Preamble and sections carry rulings 16, 17, 24, 25/29, 27 and 28. No lower-case "Mark missing" or "Needs review" is left |
| C7 Windows prompt | **Fixed**, with nits (NEW 2, NEW 6) | No Git is needed. Step 12 uses Task Scheduler. The Archive 2024 place is named. The switch-off path exists in code: right-click the return's H1, Edit Request List…, Active |
| C8 runbook/README | **Partly fixed** (NEW 5) | The named sections were rewritten. Some pre-shell words remain, and the README edit broke a sentence |
| C9 mock-up | **Fixed** | |
| C10 unpinned words | **Fixed** | Two new `test_single_source` tests |

## Rulings the brief singled out

- **Ruling 24:** **fully met.**
- **Ruling 28:** **met.** The notice has a dismiss cross but no action. A
  dismissed notice stays gone for the session while the side panel's "Sort
  Failed" line stays. That seems within the ruling's "no button" (it is the
  notice chrome); see note 8.
- **Ruling 27:** **met** at 1100px on every page with a return link, in the
  shots and the harness.
- **Ruling 29:** the words are exactly as ruled, and the mapping is honest:
  - A code with no mapped word falls to "Unexpected Error", as the ruling says
    ("any other").
  - "Drive Not Signed In" and "Ran Too Long" being unmapped is acceptable.
    The engine gives no run code for a Drive that is not signed in, and it
    tells the person through its own notice. The 30-minute cap is said by the
    shell as "Sort Stopped: Ran Too Long", which uses the same approved words.
  - "Another PC Sorting is never seen today" is **true, but it hides a gap**
    (NEW 1): a lock-held run is still drawn with a long, lower-case engine
    sentence.
  - `household-stopped` (two folders claim one household), `record-unreadable`
    and `no-practice` show as "Unexpected Error" although each is a known
    condition a person can fix. That is what the ruling says; see note 7.
- **Kill words (brief item 3):** each is five words or fewer and in Title Case:
  "Change Stopped: Ran Too Long", "It May Be Partly Done." and "Stopped: Ran
  Too Long". The line they make together has a punctuation defect (NEW 4).

## NEW findings

1. **The failed-sort banner still shows long engine sentences for the other
   returns and for a lock-held run.** Should fix. **JASON.**
   - **The other returns.** `scanSummary` (`app.js:2089-2092`) adds one bullet
     per other return in the household, showing that return's raw `error` or
     `skipped` sentence. The fix pass replaced only the asked return's line.
     Run for real in a household with two returns and the client folder gone,
     the banner reads:

     ```
     Sort Failed: Folder Not Found
     • Test Household 2025 Other TY2025: `Clients\Test Household` is missing. Was the household renamed or moved? Give its client folder back the name `Test Household`.
     ```

     That breaks ruling 25 ("the long detail stays in the error log"). It puts
     a relative folder path (`Clients\...`) on screen against P63. It uses the
     engine's label, not "{Return} ({Year})".
   - **A lock-held run.** It is a skip, so it is drawn as "Nothing Done:
     another run is still going (another pass holds this return's lock (taken
     N s ago); ...)". That is long, lower case and names no approved word.
   - **The "Another PC" word.** "Another PC Sorting" would be the wrong word
     for a lock-held run in many cases anyway. The holder is usually this PC's
     own scheduled pass.
   - **Suggested fix:** say each other return as `{Return} ({Year}): {short
     reason}`, using the same `vocab.scan.reasons` by `code`. Jason picks the
     short word for a skipped run (for example "Nothing Done: Another Sort
     Running").
   - **Effect on the Windows check:** PROMPT step 13 promises "five words at
     most, no folder path". That holds only when the household has one active
     return.

2. **PROMPT step 12 does not say which folder to rename.** Should fix (one
   line).
   - The prompt calls the sample `%USERPROFILE%\PilotTest\Clients` and says
     "Point it at the made-up Clients folder". That makes `Clients` the clients
     root, but under the root there is also a `Clients` tree (decision 125).
   - **Renaming the root is certain to work:** the saved root is gone, the
     pass is refused, and the result is "failed".
   - **Renaming the inner tree fails only for a household whose record shows
     it had a client folder** (`client_side_expected`). A household that never
     had one simply gets its folder made again, and the pass succeeds. In that
     case no "Sort Failed" appears, and Jason would record a false FAIL.
   - **Fix:** say "rename the folder you chose as the Clients folder in step
     2", or give the full path.
   - Same step: "choose **Repair the Schedule** in its menu". The menu item is
     "Repair Schedule" (Tools menu); "Repair the Schedule" is the confirm's
     wording.

3. **Nine misfit reasons are marked "Approved by Jason (rulings 18/18a/23)",
   but none of those rulings approves them.** Should fix. **JASON.**
   - Ruling 18 says S8b proposes the words and "Jason approves before the
     pilot".
   - Ruling 18a names only "Bad Year", as a working word.
   - Ruling 23 is `pick_request` and `name_requests`.
   - This is the rest of C5. Either Jason approves Unknown Folder, Old Layout,
     No Household, Unowned Folder, Name Refused, No Return, Cannot List,
     Look-Alike Folder and Old Workbook, or the TSV says "proposed" and
     HANDOFF lists them.

4. **The line for a stopped command has no full stop in the middle.** Should
   fix (one character).
   - `main.js` joins the words with a space. A killed write reads "Change
     Stopped: Ran Too Long It May Be Partly Done. It Was on Smith Family:
     A01." (pinned so in `test_single_source.py:2774`).
   - A killed sort with a position reads "Sort Stopped: Ran Too Long It Was
     on …". This part was there before the fix pass.
   - **Fix:** end the first phrase with a full stop, or put a line break
     between the phrases.

5. **Runbook and README: pre-shell words remain, and one sentence was broken.**
   Should fix.
   - `README.md:117-122`: the new sentence about the app was put in the
     middle of a paragraph. "…and one **Sort** icon. Its name is unique across
     both trees…" now says the Sort icon's name is unique; "Its" meant the
     household.
   - `docs/runbook.md:902-903` reads "or a / a sort or a pass ran here" (the
     word "a" is doubled).
   - The runbook still says "card" 72 times (household's card, the card's
     *Also fed by* line, and so on). It still says "**Routing rules** fold" at
     line 2355, which is now the editor's Advanced switch.

6. **The Windows prompt is followable by a CPA.** Note.
   - Every step names a real control: the Tools menu, right-clicking the H1
     for Edit Request List…, the Active field with its help text "No: Sorting
     Skips This Return", `J Park & Associates\<household>\Archive 2024` and
     "Bad Year", and Help > Open Error Log.
   - Step 16 honestly says the fallback-log failure cannot be made by hand.
   - The only step that could produce a false result is step 12 (NEW 2).

7. **Some known conditions fall under "Unexpected Error".** Note (JASON, only
   if wanted).
   - "Two folders claim one household" (`household-stopped`) and an
     unreadable record are known and fixable by a person, but show "Sort
     Failed: Unexpected Error".
   - This is as ruling 29 says. The runbook's longer sentence is still in the
     error log.

8. **The Sort Failed notice can be dismissed.** Note. The cross hides it for
   the session while the side-panel line stays. It is harmless, but ruling 28
   says "no button"; confirm Jason is content with the notice chrome.

9. **Other notes:**
   - "Came in Email or …" is cut in the 160px status column at 1100px. It is
     already on Jason's list (HANDOFF open item 5).
   - The final line still carries `path` and `locked_at` (full paths). This
     predates the fix pass, the renderer does not draw them, and the fix pass
     added no path.

## Hygiene (brief item 6)

- `0b278d9` is an ancestor of HEAD: no history was rewritten. The fix-pass
  commits are plain commits on the branch, and nothing was force-pushed.
- I searched the added lines for secrets, passwords, SSNs, e-mail addresses and
  `C:\Users\<name>` paths. None were found; the runbook's
  `C:\Users\<user>` is a placeholder.
- The test fixtures use made-up names only.
- No new path is drawn on screen by the fix pass. NEW 1 is an older path that
  the fix pass left in place.

This file is the only change in this commit. It is a new file under
`pilot/handoffs/`, so it alone will make `repo_map.py check` stale; `update`
was not run, as instructed.
