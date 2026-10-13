# Handoff - the store's gate reads the Document (P301)

Builder: Claude Sonnet 5.5, 2026-10-13, branch `claude/admiring-goodall-vhomni`
from HEAD `fce8c1e`. Built against `pilot/SPEC-document-gate.md` R1-R3.
Nothing committed or pushed; the working tree holds the change beside the
other lane's half-finished files (`tracker/{rollover,api,filer,settings,errors}.py`
and their tests), which this build did not touch.

## What was built

**R1 - the store's rule (`tracker/records.py`, `tracker/store.py`).**
- `records.document_problem(document) -> str`: `layout.spoofing_problem(document) or ""`,
  beside `identifier_problem`; the whole Document is judged, not the derived cut.
- `records.rule_row_fault` names `document` after the `_RULE_TEXT` loop, so a refused
  line reads `rules_changed carries a rule whose 'document' may not contain an
  invisible character (U+202E RIGHT-TO-LEFT OVERRIDE)`.
- `store.ADMISSION_VERSION = 5`, with the comment line saying what 5 adds.

**R2 - the editor says it by row (`tracker/manifest.py`).** `item_from_fields`
applies `records.document_problem` to every row's Document, typed and held alike,
and raises `f"{where}: {COL_DOCUMENT} '{quoted(document)}' {problem}"`. It sits
after the identifier check and before the `RequestItem(...)` call, so the
derived-short-name check (`_short_title`, G2) never gets to say it of the same
character: the Document's own refusal comes first, with no "(it is also the short
name)". `_short_title` is handed the already-stripped `document`.

**R3 - catalog and records.** All 6 forms / 107 `FORM_TEMPLATES` rows still pass
`templates.item_from_spec`, and none holds a spoofing character in its Document
(checked directly; `test_templates` 41 passed). `pilot/SPEC-form-inputs.md`
gets section 18 appended (nothing else in that file changed). **`docs/runbook.md`:
section 4 does not apply, not edited.** Its only invisible-character list
(line ~2872) is the household-name rule, not a request's Document; no sentence
names what the request-list gate refuses. `docs/repo-map.curated.json`: no node's
text became wrong, not edited (one phrase, "ADMISSION_VERSION (2 since the merge
with decision 190's refusals)", was already historical before this build; left).

## Admission pins that moved, and how

`tests/test_store.py` `ADMISSION_PIN` is a full digest table per version. Version
5 is a new table, `admission_digests()` taken after the change (271 parts);
versions 2-4 stay. Against version 4's table exactly two parts differ:

| part | version 4 | version 5 |
|---|---|---|
| `tracker.records.document_problem` | (absent) | `7a92f22b5f2cdadc` |
| `tracker.records.rule_row_fault` | `e63ac46148a8c37f` | `40478ee286dbf2db` |

A comment above the table records that. `test_admission_version_changes_with_the_admission`
and `test_the_admission_pin_reaches_the_rules_it_calls` pass. The pin hashes
`rule_row_fault`'s source: any later edit to it, comments included, moves the pin.

## New tests, before and after

"Before" is with the tests added and no code change (record the failure), "after"
is with R1-R3.

| test | before | after |
|---|---|---|
| `test_records.py::test_a_document_with_a_spoofing_character_is_refused_by_code_point_and_a_paste_is_not` | `AttributeError: module 'tracker.records' has no attribute 'document_problem'` | passes |
| `test_records.py::test_a_stored_row_whose_document_hides_a_spoofing_character_is_a_fault_naming_the_document` | fails (same missing attribute / no fault named) | passes |
| `test_store.py::test_a_document_hiding_a_spoofing_character_is_a_line_the_store_refuses` | `Failed: DID NOT RAISE StoreError` | passes |
| `test_store.py::test_a_record_admitted_under_version_four_is_judged_again_for_its_document` | `assert 4 >= 5` (ADMISSION_VERSION was 4); the sync assertion beneath it would also not raise, as the line is admitted under 4 | passes |
| `test_manifest.py::test_a_document_hiding_a_spoofing_character_is_refused_naming_the_row_and_the_document` | `AssertionError`: said `... (U+202E RIGHT-TO-LEFT OVERRIDE) (it is also the short name)` instead of the Document's own sentence | passes |
| `test_manifest.py::test_a_document_holding_only_a_no_break_space_is_not_the_stores_gate_to_refuse` | passes (a regression guard; the gate must not start refusing a paste) | passes |
| `test_api.py::test_a_held_document_hiding_a_right_to_left_override_is_refused_by_row_and_nothing_is_written` | `AssertionError`: error ended `(it is also the short name)`, not the Document's own sentence | passes |

(Both records tests were run against a copy of HEAD's `tracker/` and fail on the
missing attribute. With the version assertion removed, the version-4 store test
fails the same way on the copy: `DID NOT RAISE StoreError` at the sync.)

## Done differently, and why

1. **`rule_row_fault` guards `isinstance(row["document"], str)`.** The SPEC's line
   appends `document_problem(row["document"])` unconditionally. `checks` is built
   eagerly, and a Document that is not text (`{"document": 7}`) would make
   `spoofing_problem` iterate an int and raise `TypeError` before the text rule's
   own `LONG_TEXT_BOUNDS` fault could be returned. With the guard, the text rule
   still names it (pinned in the records test).
2. **An existing test changed.** `test_a_derived_short_name_hiding_an_invisible_character_...`
   (test_manifest) asserted the U+202E case ends "(it is also the short name)".
   By the SPEC's own ordering that case is now the Document's refusal, so the
   case is removed there (the soft hyphen, which the gate admits, stays) and
   asserted in the new test. Nothing else in an existing test changed.
3. **The no-break-space test says more than the SPEC's sentence.** "A Document
   holding only a no-break space saves": it saves held, with a short name of its
   own, and as a new row with a blank short name, because `derived_short_title`
   folds any run of white space, a no-break space included, to an ordinary space
   (`re.sub(r"\s+", " ", ...)`), so the G2 derived check never sees it. I had
   first assumed a new blank-short-name row would be refused by G2 and the test
   failed on it; the code is right, the assumption was wrong. Soft hyphen is
   unchanged: refused as derived (the existing G2 test).
4. **The end-to-end API test writes a refused line past the gate** (the store's
   `_refuse_a_malformed_line` is patched out for the one `store.record`, then
   restored), because after R1 the store no longer admits such a line through
   `record`. The journal then holds a line a rebuild refuses, which the suite's
   autouse `the_store_agrees_with_the_record` would fail on at teardown, so the
   test removes the record in a `finally`, as the store tests' `by_hand` fixture
   does. The test also saves the row once the Document is retyped. Insertion into
   `tests/test_api.py` was an exact string insertion before
   `test_a_long_identifier_is_refused_as_too_long_...`, not a rewrite.
5. `test_a_record_admitted_under_version_four_...` asserts
   `ADMISSION_VERSION >= 5`, not `== 5`, so the next admission bump does not break
   it; it sets `admitted_by = 4` literally, which stays "older than today's".
6. **One interpreter.** CLAUDE.md asks for the floor interpreter and the office's;
   I ran the venv interpreter named in the task only.
7. `repo_map.py update` was run before the gate (not after), because
   `test_repo_map` needs a current map; it was run again after ruff and reported
   "already current". The other lane's files were already in the map by then; no
   retry was needed.

## The gate (venv Python, one process per file, in parallel, `-p no:cacheprovider`)

| file | result |
|---|---|
| test_records | 55 passed |
| test_store | 197 passed, 1 skipped |
| test_manifest | 112 passed |
| test_templates | 41 passed |
| test_row_columns | 26 passed |
| test_api | 522 passed |
| test_filer | 408 passed, 6 skipped |
| test_layers | 31 passed (unchanged) |
| test_single_source | 218 passed |
| test_repo_map | 82 passed |

`python -m ruff check .`: all checks passed (before and after). `python tools/repo_map.py
check`: current (300 nodes), exit 0. The whole suite was not run (SPEC section 7).
The `test_api` count includes whatever the other lane had added when it ran.

## For Jason, before landing

His read-only `python -m tracker.store check` on the office records now judges
admission **5** as well as 4: any office request whose Document title holds a
right-to-left override or a zero-width character (an unlikely paste, but the case
this closes) will show as a malformed line and stop that household until the
Document is retyped. A no-break space or a soft hyphen in a Document is not
flagged. Run it before landing, as P290 asked for admission 4.

## For the reviewer

- `tracker/records.py` (`document_problem`, `rule_row_fault`), `tracker/store.py`
  (`ADMISSION_VERSION` and its comment), `tracker/manifest.py` (`item_from_fields`
  and its docstring; `derived_short_title` and `_short_title` untouched).
- `tests/test_records.py`, `tests/test_store.py` (two tests after
  `test_an_identifier_hiding_a_spoofing_character_...`, and the `ADMISSION_PIN` 5 block),
  `tests/test_manifest.py` (two new tests, one existing test narrowed),
  `tests/test_api.py` (one test near the section-15 tests).
- `pilot/SPEC-form-inputs.md` section 18 (appended).
- Generated, not hand-edited: `docs/repo-map.json`, `docs/repo-map.md`.
- Not touched: `pilot/DECISIONS.md` (P301's row is the landing session's),
  `docs/runbook.md`, `docs/repo-map.curated.json`.

## Late note

The map went stale twice from the other lane's edits (`docs/runbook.md`,
`tracker/api.py`, `tests/test_api.py`) after the gate ran; `update` was run again
each time and `check` ended current (301 nodes, with this handoff). The new
handoff file had to be staged (`git add pilot/HANDOFF-document-gate.md`, that one
path, nothing committed) because the map refuses an untracked source file;
`test_repo_map` passes (82) after it. Nothing else is staged.
