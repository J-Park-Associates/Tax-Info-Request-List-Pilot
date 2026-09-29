# Shell S1 rebuild 3

Branch `claude/sharp-goldberg-jmfynk`. Raised by S4's review ("For S6") and
Jason's ruling of 2026-09-29 (return links read `{Return Name} ({Year})`).
Each claim was reproduced first on a scratch tracker root built by the
`tests/test_api.py` helpers (made-up names only: a return with two
requests received, one parked `setup.exe`, one moved `w2.pdf`, one set-aside
`junk.pdf`).

## The claims

1. **`files[].return` is the label, the path is in `files[].path`: TRUE.**
   Reply before: `"return": "Test Household 2025 Only file", "path": "/.../Only file"`.
   SPEC 9.2 writes `"return": str` and does not name the path; `pages.js`
   and the stub use `return` as the path. Fixed: `return` is the return's
   path (the same string as `returns[].path`); the extra `path` and the
   label are gone from `files[]` (the pages take names from `list`).
2. **`files[].handle` missing: TRUE.** Added, `handle_of(entry)`, the same
   handle `state.index[].handle` and `state.moved[].handle` carry.
3. **`counts` count requests only: TRUE.** Before: the scratch return showed
   `counts {needs_you 0, waiting 0, received 2, set_aside 0}` and
   `files 2`, while its own `state` tallied needs_you 2, set_aside 1 (index
   rows `setup.exe` needs_you, `w2.pdf` needs_you, `junk.pdf` set_aside).
   `totals.need` was right only through `or row["files"]`. Fixed: after the
   requests, every index entry whose `file_group` is not `received` is
   counted in its group (parked and moved by hand: `needs_you`; Not
   requested and marked missing: `set_aside`; filed files are the Received
   rows they answered and are not counted twice). Now
   `{needs_you 2, waiting 0, received 2, set_aside 1}`, equal to the
   tally of `state` (items' `group` + index rows' `group` except received).
   Rebuild 1's F2 (what counts as parked or moved) is untouched; the
   `totals.need` test no longer leans on `files`.
   One difference left for S4: a moved file a person marked missing is
   `set_aside` in `file_group` (and so in `state.index[].group` and in these
   counts), but `pagesTally` counts only `decision === dismissed` as
   set-aside, so that one rare case still differs. The pages should tally
   from `index[].group`.
4. **`after_install.heading`: TRUE.** Was "After installing: needs a person";
   `pilot/wording-shell.tsv` (row `api._vocab after_install.wait`) and SPEC
   E23 say "Setup needs attention". `AFTER_INSTALL_HEADING` now says that;
   the runbook line that named the old heading is changed with it. Title
   Case is S8a's job and is not done here.
5. **Year (new ruling).** `list` (`engagements[].year`, `households[].returns[].year`)
   and `state.engagement.tax_year` already carried the year. `firm`
   `returns[]` and `files[]` did not: both now have `year` (the return's
   own record, `tax_year`, else the year folder, as `list` reads it).

## The `firm` reply now

```
returns[]: path, household, year, counts{needs_you,waiting,received,set_aside},
           files, oldest, due, draft{ready,stage,held,drafted}, problem
files[]:   return (the return's path), year, name, handle, code, received, suggestion
totals:    need, waiting, complete, files, drafts
next_sort
```

Still read-only: no lock, no write, no document read, no network.

## Tests (tests/test_api.py)

New: `test_firm_counts_parked_moved_and_set_aside_files_as_the_return_page_does`,
`test_firm_reply_names_its_fields_as_the_spec_does_and_carries_year_and_handle`,
`test_list_state_and_firm_agree_on_a_returns_year`,
`test_the_after_install_heading_is_the_specs_words`. Changed: `_tally` counts
the files as the page does; two assertions read `return` instead of `path`.
Mutation-checked on a scratch copy: counting no files fails 3 firm tests;
`return` back to the label fails 3 firm tests; both restored.
