# Shell S8b (ruling 18: two-word reasons on the Folders Skipped dialog)

Builder: Sonnet 5.5, on `claude/shell-s8b-misfit-reasons` from
`claude/shell-s8a-links`. Engine, wording only. No sentence and no behaviour of
discovery changed: the order and content of `misfits` are the same (the
existing registry, runner, rollover and api tests pass unchanged).

## What

- `tracker/registry.py`: `Misfit(path, sentence, code)`. `code` is a required
  field (no default) and an empty one raises `ValueError`. All 12 constructions
  carry one: `not_a_tree`, `record_misplaced` (two places), `no_household_record`,
  `client_no_record`, `client_look_alike`, `bad_name`, `not_a_year`, `no_return`
  (two places), `unlisted`, `legacy_folder`. `TWO_CLAIM` and
  `HOUSEHOLD_RECORD_MISSING` are stopped entries, not misfits: no code, no word.
- `tracker/api.py`: `list` `misfits[]` = `{path, sentence, code, where}` (additive).
  `_vocab()["screen"]["misfits"]["reasons"]` = `{code: phrase}`.
- `pilot/wording-shell.tsv`: nine rows, `screen.misfits.reasons.<code>`.

## For S5

Draw `screen.misfits.reasons[misfit.code]` beside the folder's name. If the code
has no entry, draw the name alone.

Words: not_a_tree Unknown Folder; record_misplaced Old Layout;
no_household_record No Household; client_no_record Unowned Folder; bad_name
Name Refused; no_return No Return; unlisted Cannot List; client_look_alike
Look-Alike Folder; legacy_folder Old Workbook.

## Needs Jason: `not_a_year`

The approved "Not A Year" is three words, not two, and the existing guard
`test_every_drawn_word_the_vocabulary_carries_is_in_title_case` requires
"Not a Year". I did not invent a replacement. `not_a_year` has a code but no
reason word, is the one pinned exception in the new test, and S5 falls back to
the name alone until Jason gives a two-word phrase (add it to `_vocab()` and the
tsv, and empty `without_a_word` in the test).

No Misfit construction fit none of the ten approved entries.

## Tests

- `tests/test_registry.py`: a Misfit without a code fails (`TypeError`, and
  `ValueError` for an empty one); every `Misfit(` in the registry passes a
  literal code (AST scan, 12 calls); the reasons cover exactly the codes minus
  the pinned exception, each two words and Title Case.
- `tests/test_api.py`: `list` carries `code`, and the vocabulary words it.
- Mutation-checked on a scratch copy (8 mutations, all killed): default code,
  empty-code check removed, a construction without its code, `code` dropped
  from `list`, a three-word phrase, a lower-case phrase, a missing phrase, a
  renamed code.
- Gate, Python 3.11 then 3.13: registry, api, plus the own tests of every
  importer (after_install, households, layout, rollover, runner, scaffold,
  store, view), test_layers, test_single_source, test_repo_map; ruff.

## Files

`tracker/registry.py`, `tracker/api.py`, `tests/test_registry.py`,
`tests/test_api.py`, `pilot/wording-shell.tsv`, `pilot/handoffs/shell-S8b.md`,
and the regenerated repo map.
