# Shell S1 handoff: engine and wording (sonnet)

Branch `claude/sharp-goldberg-jmfynk` (started from `claude/admiring-lamport-bp1sse`).
Last commit: see `git log -1` on that branch. Built exactly S1's row of SPEC-shell 16.

## Done

**Section 9 (P79):**
- `api firm` (read only; in `COMMANDS`, not `WRITING_COMMANDS`; `follow=False`;
  no lock, no write, no document read). Reply as SPEC 9.2. One addition to
  note: each `returns[]` row carries no return name (the spec has none); the
  page joins to `list` by `path`. `files[].suggestion` is the first
  suggestion's request label. `draft.ready` = drafted this draft-week and
  nothing holds it. `next_sort` is the `HH:MM` at the end of
  `scheduling.next_run`'s sentence, or null.
- `api.item_group(item, placed)` (the 9.1 table) and `api.file_group(entry)`.
  `state.items[]`, `state.index[]` and `state.moved[]` carry `group`.
  `state.review[]` is left as it was: its existing `group` key is triage's
  reserved field, not this one; a parked file's group is on its `index` row
  (joined by `handle`).
- `list.paths` = `{clients_root, status}`; `PATH_KINDS["clients_root"] = "folder"`.
  Carried by `list` only, not by the writes that carry the list
  (`test_the_writes_that_change_the_list_carry_it_without_the_vocabulary`).
- `list.last_pass` gains `ok` (last pass succeeded) and `when` (its start,
  ISO), `False`/`None` when none or unreadable.

**Section 11:**
- `vocab.menu` (`api.MENU`, 44 keys, in menu order), `vocab.screen`
  (`api.SCREEN`, the 11.4 table nested by key), `vocab.reasons`
  (`reasons.SHORT_REASONS`, one per code, all 60), stage `short` (in
  `Stage`, and `vocab.reminder.stages[].short`), `tracker.SAFEGUARDS`
  (`vocab.rules[].short`), `vocab.override_labels` (parallel to
  `override_reasons`, whose stored words are unchanged; the fourth reason is
  unchanged at five words), `vocab.schedule.move_warning`.
- The approved rewording (67 reword, 5 merge, 10 error-log) applied, exactly
  as in `wording-shell.tsv`, to the constants each key reads:
  in place in `api.py`, `names.py` (NO_PEOPLE, ONE_WORD_SPELLING) and
  `reminder.py` (HELD_SUMMARY, INBOX_HELD_SUMMARY, LAST_DRAFTED_LINE,
  EDITED_BY_HAND, COPIED_NOTE, SET_ASIDE_LINE, REMINDER_NOT_YET).
- Where the status report or the console still reads a longer sentence, that
  sentence is untouched and the app says an api-owned short one beside it:
  `review.NOTHING_SUGGESTED` / `SET_ASIDE_NOTE` / the footer place word
  (`api.NOTHING_SUGGESTED_WORDS`, `SET_ASIDE_NOTE_WORDS`, `FOOTER_PLACE_WORDS`),
  `filer.ROOM_SHORT` / `ROOM_PARKS` (`api.ROOM_SHORT_WORDS`, `ROOM_PARKS_WORDS`,
  also used by `state.warnings`, `state.room_note` and the set-root reply),
  `after_install.FINDINGS_WAIT` (`api.AFTER_INSTALL_WAIT`), and the Active
  help (`api.ACTIVE_HELP`; `records.ENGAGEMENT_NOTES` stays for the README).
- Docs that quoted changed words: `docs/runbook.md` (room line, held line,
  Add issuer, room heading). The four standing rules and their docs are
  unchanged (`STANDING_RULES` keeps the full wording).
- Curated notes for `api`, `reasons`, `reminder`, `__init__` rewritten; map
  updated and current.

**Tests changed or added (Python side):** `test_api.py` (last_pass ok/when,
schedule move_warning, stage short, the approved words, the placeholder
gone from `feed_warning`, room and triage words from the api; a helper
`_typed_as_a_string` because a short word such as `Held:` or `Spelling` is
also a substring of a comment or of `teachSpelling`, so the "renderer types
no word" checks now look for the word where a string begins; new: the six of
9.4, plus `test_firm_says_a_root_it_cannot_walk...`,
`test_a_file_falls_in_the_group_its_decision_says`, the vocabulary shape test
and the five-words test for menu, screen and reasons); `test_reasons.py`,
`test_reminder.py`, `test_single_source.py` (safeguards), `test_runner.py`
(`follow=False` is now in `runner.py` and `api.py`).

## Gate

Run under Python 3.11 and 3.13, each file its own process: `test_api`,
`test_names`, `test_reminder`, `test_reasons`, `test_review`, `test_runner`,
`test_view`, `test_layers`, `test_repo_map`, `test_tripwire`, `test_errors`
all pass on both. `python -m ruff check .` clean; `repo_map.py update` then
`check` current. `test_single_source` passes except **six tests that read
`app/main.js`'s pinned first-start words**; they fail on purpose until S2
updates `main.js` (S1 may not touch it):
`test_the_shells_default_words_are_the_apis_word_for_word`,
`test_a_pass_killed_at_its_own_limit_ends_with_the_killed_sentence`,
`test_the_shells_kill_follows_the_limit_the_pass_reported_and_says_where_it_was`,
`test_the_shell_never_puts_stderr_on_screen_and_appends_it_to_the_error_log`,
`test_with_no_error_log_the_shell_says_stderr_in_the_reply_and_writes_no_file`,
`test_a_failed_spawn_is_said_by_its_code`.
**S2 must set main.js's defaults to the API's words:** `killed` "Sort stopped:
ran too long", `noReply` "No reply from the tracker", `couldNotStart` "The
tracker could not start", `couldNotSend` "Could not send; nothing changed",
`noLog` "Tracker failed; no error log", and `not_opened` "Not opened; it has
changed" (`api.SHELL_*`). These tests then pass unchanged.

## Not done, on purpose, and for whom

- **The 78 "cut" keys are still in `_vocab()`** with today's words (the
  current `app.js` reads them; removing them now would break the shipping
  renderer). Once S4/S5 have removed the readers, S6 removes them: the list is
  every `cut` row of `wording-shell.tsv` whose source is `api._vocab`
  (`awk -F'\t' '$1=="api._vocab"&&$4=="cut"{print $2}'`). S3's
  `test_every_screen_word_is_five_words_or_fewer` will flag any that remain,
  so S6 needs the list either removed or in that test's exclusion list.
- Not S1's: `pilot-content.js` tour lines (S3), `#safeguards-modal` and
  `SAFEGUARDS` in the page (S5), docs that name toolbar buttons that move to
  the menu (`README`, runbook, Tester Guide: S6 with the join).
- `vocab.reminder.stages[].name` and `STANDING_RULES` keep their full words.

## Proposed decision rows for S6 (from P85)

- `firm` counts groups with `item_group`, the same rule `state` uses, and a
  return's draft is `ready` only when written this draft-week and unheld.
- Where another reader (status report, console) still reads a sentence, the
  app's short word is an api-owned constant beside it, not a change to that
  reader's sentence (P84 with the "cut removes from the screen" rule).
- The "renderer types no word" checks look for a word where a string begins,
  because approved words are now short enough to occur inside code.

## Files the next session needs

`tracker/api.py` (`MENU`, `SCREEN`, `_cmd_firm`, `item_group`, `_last_pass`),
`tracker/reasons.py` (`SHORT_REASONS`), `tracker/reminder.py` (`Stage.short`),
`tracker/__init__.py` (`SAFEGUARDS`), `tests/test_api.py` (end of file),
this file. S2: the six failing tests above and `api.MENU`.
