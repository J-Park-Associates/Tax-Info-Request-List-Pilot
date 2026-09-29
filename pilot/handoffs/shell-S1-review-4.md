# Shell S1 review 4 (of rebuild 3)

Branch `claude/sharp-goldberg-jmfynk`, reviewed at `2795778` (code commit
`a9569fd`, diff `ff0fef0...HEAD`). The reviewer did not build S1 or any of
its rebuilds. Read: CLAUDE.md, `shell-S1.md`, every S1 review and rebuild,
`shell-S4-review-1.md` ("For S6", on `claude/shell-s4-pages`),
`shell-rulings.md` row 13 (on `claude/amazing-maxwell-b4hdzo`), SPEC-shell
9.1-9.4 (on `claude/admiring-lamport-bp1sse`) and `app/renderer/pages.js`
(on `claude/shell-s4-pages`). No code changed.

## The rebuild's five claims, checked

1. **`files[].return` is the return's path: true.** `tracker/api.py:5259`
   and `5263` send `row["path"]`, the same string as `returns[].path`; the
   label and the extra `path` are gone. SPEC 9.2 writes only
   `"return": str`. Path is the right reading: `pages.js` groups the Needs
   review page by `file.return` (`pagesReviewGroups`, 351-352), looks the
   return up by it in `firm.returns` by `path` (`pagesFirmReturn`, 78-81),
   names it through `list`'s `return_name` by path (`pagesReturnName`,
   84-87) and hands it to the Check step as `ret` (369). The pages and the
   reply now agree; with a label nothing on that page would resolve. No
   finding.
2. **`files[].handle`: true.** `handle_of(entry)` on both the parked and the
   moved rows (5260, 5264), the same function `state.index[].handle` and
   `state.moved[].handle` use. Checked on a scratch root: every file's
   handle is found among its return's `state` index/moved handles. (The
   moved rows' handle is not pinned by a test: F1.)
3. **Counts: true.** `5255-5257` add every index entry whose `file_group`
   is not Received. Compared `firm` with the same return's `state` on a
   scratch root built with the `tests/test_api.py` helpers (made-up names;
   one return, A01 received, B01 outstanding) for each mix:

   | Mix | `firm` counts (ny/w/r/sa) | `state` tally (items + index `group`, not received) | `files` | totals |
   |---|---|---|---|---|
   | parked only | 1/1/1/0 | 1/1/1/0 | 1 | need 1 |
   | moved only | 1/1/1/0 | 1/1/1/0 | 1 | need 1 |
   | Not requested | 0/1/1/1 | 0/1/1/1 | 0 | waiting 1 |
   | moved, marked missing | 0/1/1/1 | 0/1/1/1 | 0 | waiting 1 |
   | all four | 2/1/1/2 | 2/1/1/2 | 2 | need 1 |
   | record unreadable | 0/0/0/0, `problem` "Could not be read", `year` 2025 | - | 0 | need 1 |

   Equal in every mix, and `files == len(files[]) ==` the files' share of
   `needs_you`. `totals.need` dropping `or row["files"]` (5312) is safe:
   every file counted in `files` is now in `counts.needs_you`.
4. **`AFTER_INSTALL_HEADING` is "Setup needs attention": true** (5005),
   matching SPEC E23 and `pilot/wording-shell.tsv`; the runbook line moved
   with it (`docs/runbook.md:103`). The old words survive only in
   `docs/ROADMAP.md` decision 209, which is history and stays.
5. **`year`: true.** `firm` `returns[].year` (5226) and `files[].year`
   (5259, 5263) read the record's `tax_year`, else the year folder - the
   same expression `list` uses for `engagements[]` (3375),
   `households[].returns[]` (3366) and `state`'s `household.returns[]`
   (2582); `state.engagement.tax_year` carries the record's. So every row a
   return link is drawn from (ruling 13) has the year. An unreadable return
   still carries it (from the folder).

**Field names against SPEC 9.2.** `returns[]`: `path, household, counts
{needs_you, waiting, received, set_aside}, files, oldest, due, draft {ready,
stage, held, drafted}, problem` - exactly 9.2, plus `year` (ruling 13).
`files[]`: `return, name, code, received, suggestion` - exactly 9.2, plus
`year` (ruling 13) and `handle` (S4 review, For S6 item 2). `totals`:
`need, waiting, complete, files, drafts`; `next_sort`. No other extras.

**Read-only.** Beyond `test_firm_is_read_only` (bytes of the root, store and
data home identical; no lock file), a scratch test wrapped `open`,
`Path.open/read_bytes/write_*/touch/mkdir/unlink/rename/replace`, every
callable in `tracker.locking`, and `socket.socket`/`create_connection`
around one `firm` on a return with a parked `setup.exe` and a moved
`w2.pdf`: reads only of the two `_ledger.jsonl` records, the inbox's own
`_README.txt` and `settings.json`, one `mkdir` of the already existing
settings folder (a no-op); no write, no lock call, no socket, and neither
client file opened.

**Nothing else changed.** The code diff is `tracker/api.py` (heading, `year`,
the file counting, the `files[]` shape, the `totals.need` condition),
`docs/runbook.md` (the heading), `tests/test_api.py` (four new tests, `_tally`
counting files, two assertions reading `return`) and the regenerated map.

**Earlier fixes still hold.** Rebuild 1's F2: moved files are listed in
`files[]` and counted in `files`/`totals.files`, and a return whose only work
is a file is Need a person (rows 1-2 above). Rebuild 2's `draft.ready`
(drafted this week and not approved; a hold does not unmake it,
`_firm_draft`, 5206) is untouched by the diff.

## Gate

Each file its own process, Python 3.11 then 3.13, identical results:
test_api 384 passed; test_names 6; test_reminder 204 (1 skipped);
test_reasons 57; test_review 67; test_runner 193; test_view 34; test_layers
29; test_repo_map 80; test_tripwire 19; test_errors 83; test_single_source
162 passed, 6 failed - exactly the six expected `main.js` ones (the killed
sentence x2, stderr to the log, no error log, failed spawn, the shell's
default words). `ruff check .` clean; `repo_map.py check` current.

Mutations on a scratch copy (`git archive HEAD`), `-k firm`:
- files counted only when Needs you (set-aside files dropped): fails
  `test_firm_counts_parked_moved_and_set_aside_files_as_the_return_page_does`.
- a parked file's `handle` set to its name: fails
  `test_firm_reply_names_its_fields_as_the_spec_does_and_carries_year_and_handle`.
- `returns[].year` set to `None`: fails that test and
  `test_list_state_and_firm_agree_on_a_returns_year`.
- a moved file's `handle` set to `""` and its `year` to `None`: **all 14
  firm tests pass** (F1).

## Findings

**F1. A moved file's `handle` and `year` on `firm` are not pinned by any
test.** `tracker/api.py:5263-5264`; `tests/test_api.py:8212-8240`. The
rebuild claims `files[].handle` and `files[].year` on every file (claims 2
and 5; S4 review For S6 item 2; ruling 13), and the code does send them on
the moved rows, but the only test that reads `handle`/`year` has one parked
file and no moved one, so the mutation above (moved `handle` `""`, `year`
`None`) survives the whole firm set. The Check step reads `file.handle` for
moved rows on the Needs review page as for parked ones (`pages.js:369`).
Smallest fix: in
`test_firm_lists_every_file_it_counts_and_buckets_a_return_with_only_a_file`,
assert for each file `f["year"] == 2025` and `f["handle"]` equal to the
handle of the same name in that return's `state` (`index` for `setup.exe`,
`moved` for `w2.pdf`).

One finding.

## Notes for S4/S6

- **The marked-missing edge is an S4 note, not an engine finding.** The
  engine is consistent with itself: `file_group` (`api.py:2650-2659`, from
  the first S1 build) puts a moved row a person marked missing in Set aside,
  `state.index[].group` says `set_aside`, and `firm` counts it there (mix 4
  above). SPEC 9.1 names "set aside by a person (Not requested)" and not
  marked missing, but a person's Mark missing is a setting-aside and no other
  of the four groups fits a row that "counts for nothing". The pages differ:
  `pagesTally` (`pages.js:634-644`) counts only `decision === dismissed` as
  set aside and `pagesReturnGroups` (573) draws only dismissed rows there, so
  on such a return the tally is one lower than `firm`'s, the return page
  never shows the row, and `shellStateArrived` re-reads the whole firm every
  time the return is opened. Fix in the pages: tally and draw files by
  `state.index[].group` (the S4 review's For S6 item 5 already suggests it).
  If Jason would rather a marked-missing row count nowhere, that is a SPEC
  9.1 ruling, then one line in `file_group`.
- `files[]` carries no `seq`; the S4 review suggested one "for the write".
  Nothing in `pages.js`/`shell.js` reads it, and SPEC 7.1 draws the Check
  sheet from `reviewRow()`/`movedRow()` over the return's `state`, which
  carries `seq`. S5 should load the return's `state` for the Check step
  (it has `ret` and `handle`) rather than write from the `firm` row.
- SPEC 9.2's `files[]` block should gain `year` and `handle` and say
  `return` is the return's path, so the SPEC and the reply read the same.
- Return link text `{Return Name} ({Year})` (ruling 13) is S5's: `year` is on
  `firm` `returns[]`/`files[]` and `list`; `pagesReturnName` does not add it
  yet.
