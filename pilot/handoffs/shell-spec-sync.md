# Shell SPEC sync (documentation only)

Branch `claude/shell-spec-sync`, from `0776ea6` (the SPEC's last clean commit,
"Shell handoff: prompts for every build, review, rebuild and the Windows
check"). Last commit: the one that adds this file; its sha is in the final
report (a file cannot name the commit that holds it). Earlier commits:
`63b9d9b` (wording table), `583ac3c` (SPEC), `3ff3e9a` (test-pin survey).
No code and no test changed.

## Sources read

`shell-rulings.md` and `shell-ledger.md` (rows 1-13; later rows win) and
`DECISIONS.md` P50-P66 on `claude/amazing-maxwell-b4hdzo`; the handoffs and
rebuild/review files of S1 (`claude/sharp-goldberg-jmfynk`, up to rebuild 3's
commit `a9569fd`, whose handoff is not written yet), S2
(`claude/shell-s2-menus`, rebuilds 3 and 4), S3
(`claude/friendly-archimedes-33y9uk`), S4 (`claude/shell-s4-pages`) and S7
(`claude/shell-s7-tooltips`, rebuilds 1 and 2). `claude/shell-s8a-links` has
no `shell-S8a.md` yet; only its work in progress (`1e34e78`, "unfinished,
ungated") was looked at, and nothing from it is stated as final.

## What changed, per section of `pilot/SPEC-shell.md`

A note at the top, "Amended by rulings 1-13 (2026-09-29)", lists these.

- **1** - the vendored Floating UI row (`@floating-ui/dom` 1.8.0 and core
  1.8.0, which holds utils 0.2.12; two unedited UMD files, licences,
  README, SHA-256 pinned); the deny-list row for the fallback log; the load
  order with the two vendor scripts directly above `app.js` (ruling 5, S7).
- **3.9 (new) Links** - file names show that exact working copy in File
  Explorer ("Show in File Explorer"); household names navigate ("Navigate
  to Client"); return names navigate ("Navigate to Return"); the only link
  that opens File Explorer is a file name; return links read
  "{Return Name} ({Year})" with the year from the API; no path ever shown
  (rulings 8, 9, 11, 12, 13).
- **4.3** - menu bar hidden until Alt (ruling 3); the terms' and the tour's
  own keydown listeners are an accepted exception (ruling 1); the page acts
  on a menu accelerator's `{id}`, not on the raw key (S2's note).
- **5.1, 5.2** - item words in Title Case.
- **5.5** - Open Error Log opens the API's log, else the fallback; the
  fallback log in `%LOCALAPPDATA%\Tax Document Tracker Pilot\error.log`
  (userData off Windows), 256 KB rotation to one `.1`, links and folders
  refused, writes never throw, never roaming/data home/upstream, in the
  deny list (ruling 4); the failure's on-screen text is its own sentence, a
  blank line, "Tracker Failed" (ruling 6).
- **5.7 (new)** - `open(path, "reveal")` on the existing `open-path` channel
  (`shell.showItemInFolder`), same allow-list and `lstat`, file only; the
  openable keys of working copies under `state.paths`; no household or
  return open key (rulings 8, 12). S8a's key names are quoted as work in
  progress.
- **6** - the link kinds on every page; return links with the year; the
  6.1 and 6.7 diagrams in Title Case with "Could Not Sort".
- **8.5** - rewritten: 300 ms hover (ruling 7); focus shows the tip at once
  on every control except the search box (ruling 2); Floating UI places it
  (offset 4, flip, shift 8, strategy fixed, only through `FloatingUIDOM`);
  it follows its element and is hidden when its element scrolls out of
  view, returning only on the next hover or focus (S7).
- **9.2, 9.3** - `year` on `firm`'s `returns[]` and `files[]`; `files[]`
  carries `handle`, `return` is the path, moved-by-hand files are listed;
  the Need a person rule; `draft.ready`/`held` as S1 built them; "Could Not
  Be Read"; `paths` on `list` only; `state.paths` working-copy keys.
- **11.1** - the Title Case rule (ruling 10), its exceptions, examples, and
  that 11.3-11.6 win over sentence-case quotes elsewhere in the SPEC.
- **11.2** - the table's two new columns; the no-error-log bullet (rulings
  4, 6).
- **11.3-11.6** - every word in Title Case; `unmatched` is "Could Not Sort";
  the three link tooltips and "Could Not Be Read" added to 11.4; stage
  shorts and safeguards in Title Case.
- **12** - tour step titles in Title Case ("Needs Review"); tour lines per
  the table's `title_case` column.
- **14** - survey counts 113/35; 14.1: the keydown exception, the six
  tooltip tests by name, a Title Case test and the link claims; 14.2: the
  fallback-log tests and the deny-list pin.
- **16** - S7 and S8a rows; S5 builds the links; S6 does the tour and the
  rulings' decision rows; the Windows check's added hands-on steps.
- **17** - the vendored files are the one allowed package.
- **19 (new)** - open for Jason (below).

`pilot/wording-shell.tsv`: two columns added to every row, `title_case`
(ruling 10 applied to the proposed words; empty for the 113 cut rows; the
17 terms rows unchanged) and `changed` (`case` 76, `no` 22, `-` 113,
`word` 1). The one word change: `shell.no_log` is "Tracker failed" (rulings
4 and 6), as S2 rebuild 3 set it. `triage.places.footer` is flagged.

`pilot/shell-test-pins.md`: the no-data-home page-error row (S1 rebuild 1)
and the no-error-log shell test row (KEEP to CHANGE, renamed by S2), with
the counts and a note.

No decision row number was touched (S6 numbers them).

## Open for Jason (SPEC section 19)

1. Approve "Could Not Be Read" (`api.FIRM_UNREADABLE`).
2. A cut name's tooltip (its full name) against a link's tooltip: which
   wins on one element.
3. How a keyboard user acts on a name link inside a listbox row.
4. Whether a file row's right-click menu gains "Show in File Explorer"
   (S8a's work in progress hints at one; no ruling adds it).
5. `triage.places.footer`, a fragment inside a reason line: Title Case or
   not.
6. Confirm "Tracker Failed" (ruling 6's words in ruling 10's casing).

## Pending other jobs

S8a's key names, fields and Title Case test name (SPEC 5.7, 9.3, 11.4, 14.1)
become final with its review; `year` and `handle` on `firm` rows with S1
rebuild 3's review. When either lands with different names, this SPEC's
lines naming them change with it.

## Checks run

`python tools/repo_map.py update` then `check` (current) after each file;
`tests/test_repo_map.py` (80 passed) and `tests/test_single_source.py`
(167 passed), each in its own process, Python 3.11 (`/tmp/v`).
