# Shell S8a review 3: rebuilds 2 and 3 (review 2's findings, ruling 15)

Reviewer: a separate agent that built neither S8a nor any of its rebuilds
(Opus 5.5). Reviewed: `claude/shell-s8a-links` at `86569b0`, only
`git diff 209e655..HEAD` (`cf0975c` rebuild 2, `1748a2d` rebuild 3,
`86569b0` map), against review 2's findings 1 and 2, `shell-rulings.md`
rulings 1-15 (branch `claude/amazing-maxwell-b4hdzo`), and the rebuild 2 and
3 handoffs. No code was changed by this review.

## Gate as run

- Each file in its own process, Python 3.11 then 3.13: test_api 404,
  test_shell 32, test_layers 29, test_single_source 171, test_repo_map 80 -
  all pass on both.
- `ruff check .` clean; `repo_map.py check` current (289 nodes) before this
  file was added.

## Review 2's findings

- **F1 is fixed.** `_shown_copy_key` returns `_review_copy_key(entry) or
  "shown_copy ..."` (`tracker/api.py:2104`), so a parked read document is
  named once, under `review_copy` (kind `file`). The new engine test asserts
  `shown_key == open_key` and that no path in `state.paths` sits under two
  keys (of any kind). The new end-to-end test feeds the real reply's `paths`,
  in its own order, with `api.PATH_KINDS`, through the real `app/main.js`:
  plain Open opens the review copy, reveal shows it, a shown-only `.docx` is
  refused on a plain open and shown on reveal. Mutation "bare `shown_copy`
  key" kills it.
- **F2 is fixed.** `wording-shell.tsv`: `feed` counts 5, notes for
  `machine`, `paused`, `feed` say approved by Jason, ruling 14 (`feed`: changed
  from the proposed Feed Return Not Found); the `api.py` comment and the
  rebuild-1 handoff table no longer say PROPOSED. Words unchanged, Title Case,
  five or fewer.

## Ruling 15 (firm Needs Review file names are links)

- **Shape.** `firm.files[].open_key` (`""` for a program, a row with no copy,
  a moved copy whose bytes are nowhere) and a top-level `firm.paths` (also
  `{}` on an empty or missing root). `firm.paths` holds only keys some file
  carries: no folder, no return path.
- **One key, one kind.** Parked rows use `_shown_copy_key`, moved rows
  `_moved_copy_key` - the builders `state` uses - so a firm file's key and
  kind equal its return's `state` ones. This matters beyond one reply:
  `main.js`'s allow-list is one `Map` for all replies, keyed by path, so a
  firm reply that disagreed with `state` on a path's kind would overwrite it;
  the parked test's `open_key == shown_key` pins the agreement (mutation
  "firm parked always `shown_copy`": caught).
- **Reveal-only where it must be; the review copy keeps `file`.** Shown,
  filed and moved copies are `reveal`; a marked review copy stays `file`
  (decision 190), so its firm link can reveal it and the card's Open still
  opens it.
- **No path drawn.** Nothing new in `files[]` carries a path (the existing
  `return` field is unchanged); keys embed a relative location and are
  never drawn.
- **Key-collision suffix.** `_firm_key` adds ` #2`, ` #3`... only when the
  key is already held by a *different* path; the same path keeps its key.
  The order is the reply's file order (registry order, then file order), so
  it is deterministic. It is safe even when a file's own key already ends in
  ` #2`: the loop compares paths, so it moves to ` #3` or ` #2 #2` and never
  overwrites a path. The kind is still the first word (`main.js` falls back
  to `key.split(" ", 1)[0]`).
- **Refusals under node (scratch test, real `main.js`, real firm `paths`
  plus a `shown_copy ... #2` and a `review_copy ... #3` key at real files):**
  plain open of a shown copy - refused ("Not Opened; It Has Changed");
  reveal - shown; review copy plain open - opened, reveal - shown; `#2`
  shown-kind key: plain open refused, reveal shown; `#3` review-kind key:
  opens (kind `file`, as its word says); a moved copy's firm key: plain
  open refused, reveal shown. Refused as not reported (7 of 7): an
  unreported file (reveal and open), `\\server\share\x.pdf`,
  `//server/share/x.pdf`, a `..` spelling of a reported copy, a key string
  given in place of a path, a `... #2` key string given in place of a path.
  `openPath` was called only for the two `file` kinds.
- **No client document read.** `firm` run under a spy (`builtins.open`,
  `io.open`, `os.open`, `os.stat`, `os.lstat` recorded; `socket.socket`,
  `create_connection`, `locking.acquire_lock` raising) after a real scan: 0
  writes, 0 sockets, 0 locks, no open and no stat of any working copy in
  `firm.paths`. The only file under an inbox or `Prepared` opened is the
  tracker's own `Drop files here/_README.txt` (read by `_firm_draft`, as
  review 2 found before this change).

## Size and cost

A real measurement was possible on Linux, not on the office PC: a scanned
return (4 files needing a person, all 4 keyed) copied to 750 households, both
trees, then `firm` run three times, old `api.py` (`209e655`) against new.

| | reply | `paths` | warm time |
|---|---|---|---|
| before (`209e655`) | 1.21 MB | - | 6.67-6.77 s |
| after (`86569b0`) | 2.14 MB | 0.65 MB | 6.87-7.05 s |

750 returns, 3000 files, 3000 keys. The change adds about 0.93 MB (+77%;
about 310 bytes per keyed file: the key twice, once as `open_key` and once
in `paths`, plus the path) and 0.2-0.3 s (3-5%). Four waiting files in every
return is a heavy season; at one per return the cost is a quarter. Sane.
The budget itself (SPEC 9.2: 750 returns under 3 s on the office PC) is
already over on this sandbox before the change (6.7 s); that is `firm` as S1
built it, not this rebuild, and the Windows check is where it is measured.

## Words

Nothing new is drawn: rebuild 3 adds keys and paths only. Ruling 14's words
are checked above.

## Minimal change

Rebuild 2 touched only `_shown_copy_key`, the notices comment, its tests,
the TSV, the rebuild-1 handoff; rebuild 3 only `_firm_row`, `_firm_key`,
`_cmd_firm`, tests, its handoff; then the map. No `main.js` change (none was
needed: `learn()` already reads a reply's top-level `paths`). Nothing
beyond the handoffs.

## Findings

No findings.

## Notes for S5/S6

- SPEC 9.2's `firm` shape does not yet name `files[].open_key` or `paths`;
  S6 adds them (ruling 15 names S6 for the stub check).
- `main.js` keeps one path-keyed allow-list across every reply and never
  forgets a path. Firm and `state` now report the same copies, so any future
  change to one key builder must change both replies together; the
  `open_key == shown_key` assertion is the test that says so.
- Ruling 15's row names "S8a rebuild 2"; the work landed as rebuild 3.

## Mutation checks (scratch copy of the tree, bytecode off, the new tests only)

| Mutation | Test that fails | Result |
|---|---|---|
| no suffix: the later return overwrites | `test_two_returns_spelling_one_key_..._suffix` | caught |
| suffix even for the same path | same | caught |
| suffix spelled `key#2` | same | caught |
| firm parked rows use `_review_copy_key` only | `test_a_parked_files_open_key_is_the_states_shown_key_...` | caught |
| firm parked rows always `shown_copy` (kind clash with `state`) | same | caught |
| moved key's path is its home, not where it is | `test_a_moved_files_open_key_is_where_it_is_now_...` | caught |
| `firm.paths` also gets each return folder | `test_firm_reply_names_its_fields_...` | caught |
| `_cmd_firm` skips the merge into `paths` | `test_a_parked_files_open_key_...` | caught |
| `main.js`: kind by full key only, unknown falls to `file` | `test_a_real_firm_replys_paths_reveal_...` | caught |
| `_shown_copy_key` back to bare `shown_copy` | `test_a_parked_pdfs_shown_key_is_its_open_key_...` | caught |
| an empty key written to `paths` | `test_a_moved_files_open_key_..._nowhere` | caught |

11 of 11 caught. One more mutant, a return folder added to `_firm_row`'s own
`paths` dict, survived because `_cmd_firm` merges only keys a file carries,
so it never reaches the reply (an equivalent mutant; the version that reaches
`firm.paths` is the row above, caught). Unmutated: all 8 of those tests pass.
