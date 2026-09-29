# Shell S8a rebuild 1 (after review 1, F1-F10)

Branch `claude/shell-s8a-links` (built on local `rebuild-s8a`, pushed with a
plain push). Last commit: the one that adds this file's final form; its sha is
in the final message. Made-up names only; nothing reads a client document.

## Findings

- **F1 (safety). Filed and moved working copies are reveal-only.**
  `PATH_KINDS["filed_copy"]` and `["moved_copy"]` are the new kind `"reveal"`
  (in `vocab.path_kinds` too). `app/main.js` `openChecked` treats `"reveal"` as
  a file for the `lstat` test and refuses a plain open of it with `notOpened`;
  `open(path, "reveal")` shows it in File Explorer. `review_copy` stays
  `"file"`: only a marked review copy opens in the default program (decision
  190). Tests (real `main.js` under node): a moved `.xlsm` opened without reveal
  is refused and with reveal is shown; a filed copy and a shown copy are refused
  plain; a review copy still opens.
- **F2. Every file name can be a link.** New key `shown_copy <ledger key>`,
  kind `"reveal"`, in `state.paths`, carried as `state.index[i].shown_key` on
  every Needs Review / Not Requested row that has a working copy
  (`prepared_location`): a set-aside file, a parked email or zip, a parked
  document. The existing `open_key` is unchanged (still only for a marked review
  copy). A parked program has no copy, so `shown_key` is `""`. Filed rows keep
  `open_keys`; moved rows keep `moved[i].open_key`. Reveal only, never open.
- **F3.** `test_a_moved_copy_whose_bytes_are_nowhere_has_no_key` builds a real
  moved row with `a_moved_row`, deletes the file, scans again, and asserts the
  `moved` row has `now None`, `open_key == ""` and no `moved_copy` key in `paths`.
- **F4.** `test_reveal_of_a_path_the_api_did_not_report_is_refused` asserts the
  exact sentence ("That path is not one the tracker reported; nothing was
  opened.") five times, and once before any report. A separate test pins the
  kind check's fail-closed default on its own (a reported path whose word has
  no kind gets the other sentence). Two locks, each tested.
- **F5.** `title_case` in the test lower-cases a small word that is neither
  first nor last; `title_case("Waiting On Clients") == "Waiting on Clients"`.
  Re-run over all vocab: no vocabulary string changed.
- **F6.** A page filed under two requests (decision 94): keys end in `0`, `1`,
  their names equal `filed_names`, their paths equal `filed_locations`.
- **F7.** `FOOTER_PLACE_WORDS = "in the page {page} footer"` again, and the TSV
  proposed cell. The fragments spliced into longer lines (the four `places`, the
  `Pass complete` line and its Filed / Review / Syncing pieces) are in the test's
  `_TITLE_EXEMPT_STRINGS`, each with a reason.
- **F8.** The `columns` and `editor.engagement_fields` and `triage.places`
  and `scan.complete` branch skips are gone. `_TITLE_EXEMPT_STRINGS` exempts exact
  `(path, text)` pairs, each with a reason ("Short name" is a record column
  name shown as record data; three help lines SPEC 7 cuts). `ACTIVE_HELP` is
  "No: Sorting Skips This Return" (pin updated). A test proves each exception is
  really drawn and the Active warning is not exempt.
- **F9.** `app/preload.js` comment: reveal shows a file in File Explorer, or, for
  a reported folder, opens it.
- **F10.** `shell-S8a.md`'s literals list now has the review's full list.

## New key names and kinds

| key | kind | row |
|---|---|---|
| `filed_copy <ledger key> <n>` | reveal | `state.index[i].open_keys[n]` |
| `moved_copy <ledger key>` | reveal | `state.moved[i].open_key` |
| `shown_copy <ledger key>` | reveal | `state.index[i].shown_key` (Needs Review, Not Requested) |
| `review_copy <ledger key>` | file | `state.index[i].open_key` (unchanged) |

Call: `window.tracker.open(state.paths[key], "reveal")` for a file name. A plain
open of a reveal-only path is refused with `vocab.shell.not_opened`.

## Mutation checks (scratch, restored)

- `!openable.has(p)` -> `false`: a test fails. Reveal-only refusal removed: fails.
  Kind check `"reveal"` -> file removed: fails.
- Moved row always keyed: F3's test fails. `open_keys` reversed: F6's fails.
  `_shown_copy_key` returns `""`: F2's fails. `title_case` not lower-casing: fails.

## For Jason

- Ledger default 5 (fragments spliced into longer lines stay lower case, listed
  as exceptions) is applied: footer place words, and the pieces of the `Pass
  complete` line. `SCAN_FILED`, `SCAN_REVIEW`, `SCAN_SYNCING` are in fact
  Title Case already ("Filed {n}", "{n} to Review", "{n} Still Syncing"); they
  are listed as fragments too.
- SPEC 5.7 / 9.3 should name the reveal-only kind and `shown_key`.
