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
this closes) will show as a malformed line and stop that household until the line is
repaired by the runbook's malformed-line repair (its section 9: say which return
and which line), as a spoofed
identifier does since P290; retyping the Document in the editor is not the
way out, because the editor's `state` call refuses the same line. A no-break space or a soft hyphen in a Document is not
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

## Review (Opus, 2026-10-13)

Reviewer: Claude Opus 5.5, independent of the build. Reviewed commit
`f2c0631` ("Build SPEC-document-gate: ...") as `git diff 7137663 f2c0631`
against `pilot/SPEC-document-gate.md`, on a `git archive` copy of the commit
in the scratchpad (git-initialised so the guard tests that call `git` run).
The working tree, which holds the error-handling lane's uncommitted edits,
was not read for the review and nothing in it was touched except this
section. Every claim below was checked by running code on the archive copy
(throwaway tests and scripts in the scratchpad, none committed).

### Resolved

- **R1, the store's rule.** `records.document_problem` refuses U+202E,
  U+200B, U+200E, U+2066 (and U+061C, U+200D, U+2060) by code point in the
  `NAME_INVISIBLE` sentence, never echoing the character, and returns "" for
  a no-break space and a soft hyphen (`layout.invisible_problem`, the typed
  rule, refuses both, so the gate really is the narrow one).
  `rule_row_fault({"identifier": "A01", "document": "W-2‮fdp.exe"})` is
  `("document", "may not contain an invisible character (U+202E RIGHT-TO-LEFT OVERRIDE)")`.
- **The `isinstance` guard (done-differently 1)** is sound. A Document of
  `7`, `None`, `["x"]`, `{"a": 1}`, `1.5` or `True` is still refused, with
  the field named, by the text rule (`("document", LONG_TEXT_BOUNDS)`), and
  never reaches `spoofing_problem`, which would raise `TypeError` iterating
  an int. A text Document gets both rules, the text bound first.
- **Store.** A `rules_changed` line whose Document holds U+202E or U+200B is
  refused on `record` ("'document' may not contain ... U+202E ..."), and a
  no-break space and soft hyphen pass (the new store test). A line applied
  past the gate and left at `admitted_by = 4` is refused on `catch_up` and
  `follow_the_journal` as `line 2 of the record is malformed (...'document'
  may not contain...)`, and `admitted_by` stays 4. `python -m tracker.store
  check` judges every line of every journal against today's admission
  (`store.check`, the loop over `_refuse_a_malformed_line`, whatever
  `applied_seq` or `admitted_by` say), so the handoff's note to Jason holds:
  his read-only run now judges admission 5.
- **Pins.** `ADMISSION_PIN[5]` has 271 parts against version 4's 270.
  Exactly two differ: `records.document_problem` (new) and
  `records.rule_row_fault`. `admission_digests()` on the commit equals pin 5,
  and versions 2 to 4 are unchanged. The version bump with its `#: 5 adds
  P301's ...` comment line follows the module docstring's rule, which says a
  change that makes the admission refuse more raises the version in the same
  commit. The `>= 5` in the re-admission test is acceptable: the exact
  version is pinned by `test_admission_version_changes_with_the_admission`,
  and this test claims only "judged again under a newer admission", which
  `>=` states correctly and which survives the next bump.
- **R2, the editor.** Through `api edit`: a typed new row whose Document
  holds U+202E or U+200B, with a blank short name, is refused as
  `Row 2: Document '1099<U+202E>fdp.exe' may not contain an invisible
  character (U+202E RIGHT-TO-LEFT OVERRIDE)`, and the same with a short name
  of its own. The journal is byte-identical after each refusal. Documents
  with a no-break space save as a new row with a blank short name, as a new
  row with a short name, and as held rows sent back with an unrelated change.
  The builder's held-row API test passes, and the Document's own refusal
  comes before the derived-short-name one.
- **The narrowed manifest test (done-differently 2)** lost nothing pinned.
  The U+202E case (the sentence, the label, the character not echoed) is
  re-pinned in the new test, for held and new rows and for U+200B too. The
  soft-hyphen case of G2 stays where it was.
- **A pass now stops the household rather than naming files with the
  character.** Shown once with a throwaway `test_runner` test reusing
  `_a_malformed_line_is_one_folders_problem`: a synced `rules_changed` line
  whose rule's Document is `W-2<U+202E>fdp.exe` makes that engagement's
  discovery problem name the line and `'document' may not contain an
  invisible character (U+202E RIGHT-TO-LEFT OVERRIDE)`. The pass exits 1 and
  the other engagement runs. On `7137663` the same test fails with
  `{'Bad 2025': '', 'Good': ''}`: the line was admitted and the pass would
  have named working copies with it.
- **R3.** All 6 forms and 107 `FORM_TEMPLATES` rows go through
  `templates.item_from_spec`, and `document_problem` is "" for each.
  `docs/runbook.md` untouched is consistent with SPEC section 4. Its only
  sentence listing what a malformed line can say (the "line N of the record
  is malformed" bullet, about line 2738 at the commit) never named P290's
  spoofing refusal for identifiers and short names either, and its
  invisible-character list (about line 2872) is the household-name rule.
- **Layers and dead code.** No import added beyond `manifest` taking
  `document_problem` from `records` (same layers). `records` already
  imported `spoofing_problem`. `test_layers` passes and ruff is clean.
- **The API test's patch of `_refuse_a_malformed_line`, with its `finally`
  (done-differently 4)** is sound. Every autouse fixture in
  `tests/conftest.py` keeps its own `MonkeyPatch`, so `monkeypatch.undo()`
  cannot lift them. The one fixture value it does lift, `demo_root`'s
  `setenv(ENV_SETTINGS_DIR, tmp_path / "app")`, reverts to the autouse
  fixture's value, which is the same path. Four earlier `test_api` tests use
  the same pattern. It rests on that same-path coincidence; a
  `monkeypatch.context()` would not, but this is not worth a change. The
  `finally` removes the journal the suite's agreement fixture would refuse,
  as `by_hand` does.

### Findings

**F1 - should fix. A spoofing character in a K-1 issuer's name is now
refused as the Document, not as the Issuer Name.**
`tracker/manifest.py` `item_from_fields`, the new P301 refusal. SPEC-form-inputs
section 15 (G2, G5) rules that the refusal "names the field the person typed":
the issuer column's label (`COL_ISSUER`, "Issuer Name") for an issuer row.
The new Document check runs before `_short_title`, so for a spoofing
character it pre-empts that label. Verified on `7137663` against `f2c0631`
with `templates.issuer_item("F02", "Ashford‮Holdings LP", 2025)`, the
path `api` add-issuer takes, and with an editor row whose Document is
`Schedule K-1 - Ashford<U+202E>Holdings LP` and whose short name is blank:

- before: `F02: Issuer Name 'Ashford<U+202E>Holdings LP' may not contain an invisible character (U+202E RIGHT-TO-LEFT OVERRIDE) (it is also the short name)`
- after: `F02: Document 'Schedule K-1 - Ashford<U+202E>Holdings LP' may not contain an invisible character (U+202E RIGHT-TO-LEFT OVERRIDE)`

U+200B behaves the same. On the add-issuer card the person typed into one
box labelled "Issuer Name", and the card has no Document field. The builder
followed SPEC-document-gate's literal `COL_DOCUMENT` wording. The SPEC did
not consider issuer rows, and no test caught it because the existing issuer
pins (`test_manifest` about line 1523, `test_templates` about line 478) use
the soft hyphen, which the gate admits. It also makes the new section 18's
"Sections 14 to 17 otherwise stand as written" untrue for G5.

Fix: label the new refusal as `_short_title` does,
`label, source = (COL_ISSUER, entity) if (entity := _issuer_entity(document)) else (COL_DOCUMENT, document)`.
Narrowing it to "the character lies in the entity" is optional, since the
issuer prefix is fixed text. Add one test with U+202E in an issuer entity,
through `item_from_fields` or `issuer_item`, asserting the Issuer Name
sentence without "(it is also the short name)". Alternatively Jason accepts
the Document label, and section 18 and this handoff say so.

**F2 - should fix. The handoff (and the API test's docstring) give a
repair path that the upgrade case does not have.** In `## For Jason, before
landing` the handoff says a refused Document will "stop that household until
the Document is retyped". The API test's docstring says the record was
written "as a version-4 store left it" and that "retyping the Document is
the way out". A version-4 store leaves the row at `admitted_by = 4`. The
next sync then re-judges the line, and `api state` itself is refused. A
throwaway test wrote the line past the gate, set `admitted_by = 4`, and got
`state` -> exit 1 with `... line 2 of the record is malformed (rules_changed
carries a rule whose 'document' may not contain an invisible character
(U+202E RIGHT-TO-LEFT OVERRIDE)); the journal is not applied past it`,
raised from `_judge_the_applied_lines`. So the editor cannot open that list
to retype anything. The repair is the record repair the runbook's
malformed-line bullet describes (say which return and which line), as for a
P290 identifier.

The R2 held-row refusal is still right as defence in depth: it covers a row
the store admitted at 5, which is what the test builds. But it is not the
office's upgrade path. Fix: in the handoff note, say "stop that household
until the line is repaired (runbook, malformed line), as a spoofed
identifier does since P290". In the test docstring, drop "as a version-4
store left it" and "retyping the Document is the way out", or say it models
a row the store already admitted. No code change.

**F3 - should fix (landing). The committed map is stale at `f2c0631`, but
only on the other lane's files.** At the commit, `python tools/repo_map.py
check` exits 1 and `test_repo_map::test_the_committed_map_is_current` fails.
The 11 files that differ are all the error-handling lane's uncommitted
edits, which `update` hashed from the shared working tree: `docs/runbook.md`,
`tests/test_{api,errors,filer,rollover,settings}.py` and
`tracker/{api,errors,filer,rollover,settings}.py`. None of this build's own
files (`records`, `store`, `manifest`, their tests, the two pilot docs) is
named, so the map is current for this build. As committed, though, the
commit is not self-consistent. Fix: whichever commit lands second runs
`python tools/repo_map.py update` on the combined tree and `check` exits 0
before the stack goes ready. Or regenerate this commit's map at `f2c0631`
alone if it may land without the other lane.

**F4 - nit. `_short_title`'s held-row arm is now unreachable for what it
was built to catch.** `tracker/manifest.py` `_short_title`:
`(spoofing_problem if unchanged else invisible_problem)(derived)`. The
derived name holds only characters of the Document (or of the issuer entity
inside it), plus the fixed `K-1 ` and hyphens. The Document has already
passed `document_problem` by then, so `spoofing_problem(derived)` can no
longer fire. The SPEC says to keep G2 as built, and nothing is wrong, but
the docstring's "the store's when both are as held" now describes a check
that never says anything. Leave it, or note it in the docstring.

**F5 - nit, older than this build. The prose about the BOM contradicts the
code.** `layout.spoofing_problem`'s docstring, and HANDOFF-form-inputs about
line 564, say the narrow rule spares "a byte-order mark". But
`_SPOOFING_CODES` holds U+FEFF, as SPEC-form-inputs section 14 lists it
among the zero-width characters. So the gate refuses a BOM, now in a
Document too (verified: `document_problem("W-2﻿x")` refuses it, and
`str.strip()` does not remove a leading one). SPEC-document-gate's
"bidirectional controls and zero-width characters, never a no-break space
or a soft hyphen" holds as coded, and the new `document_problem` docstring
correctly names only the no-break space and the soft hyphen as admitted.
The stale sentence in `layout` should lose "or a byte-order mark" when that
file is next touched. Jason's read-only `check` will name any office
Document carrying one.

### Gate (archive copy of `f2c0631`, venv Python, one process per file, in parallel, `-p no:cacheprovider`)

| file | result |
|---|---|
| test_records | 55 passed |
| test_store | 197 passed, 1 skipped |
| test_manifest | 112 passed |
| test_templates | 41 passed |
| test_row_columns | 26 passed |
| test_api | 518 passed (the builder's 522 counted the other lane's 4 uncommitted tests) |
| test_filer | 407 passed, 6 skipped |
| test_layers | 31 passed |
| test_single_source | 218 passed |
| test_repo_map | 81 passed, 1 failed (`test_the_committed_map_is_current`, F3: only the other lane's 11 files) |

`python -m ruff check .`: all checks passed. `python tools/repo_map.py
check`: stale, the same 11 files (F3). A first run on a plain `git archive`
with no `.git` failed 7 `test_single_source` tests on "not a git
repository". That was the environment, and the table is the rerun on a
git-initialised copy.

Findings: 0 must fix, 3 should fix, 2 nits.

## Rebuild 1 (Sonnet, 2026-10-13)

Built SPEC-document-gate section 10 (F1, F2, F4, F5); F3 is the landing
session's. Edited: `tracker/manifest.py`, `tracker/layout.py` (the one
docstring sentence), `tests/test_manifest.py`, `tests/test_api.py` (one
docstring), this handoff, and the generated `docs/repo-map.json` and
`docs/repo-map.md`.

- **F1.** `item_from_fields` labels the Document refusal as `_short_title`
  labels its derived-name one: `COL_ISSUER` with `quoted(entity)` when
  `_issuer_entity(document)` is non-empty, `COL_DOCUMENT` with
  `quoted(document)` otherwise. The add-issuer card reaches it through
  `issuer_item` -> `item_from_spec` -> `item_from_fields`, so one change covers
  both. New test
  `test_a_spoofing_character_in_an_issuer_entity_is_refused_naming_the_issuer_name_box`
  (`tests/test_manifest.py`): U+202E and U+200B in `Schedule K-1 - Ashford<c>Holdings LP`,
  held and new, with and without a short name, and through `issuer_item`, each
  asserting `F02: Issuer Name 'Ashford<U+202E>Holdings LP' may not contain an
  invisible character (U+202E RIGHT-TO-LEFT OVERRIDE)` exactly (no "it is
  also the short name", the character not echoed); a non-issuer Document is
  still named as the Document. Before the change it failed with
  `F02: Document 'Schedule K-1 - Ashford<U+202E>Holdings LP' may not contain ...`;
  after, it passes.
- **F2.** The "For Jason, before landing" paragraph and the
  `test_a_held_document_hiding_a_right_to_left_override_...` docstring (in
  `tests/test_api.py`) now say a household stopped by a spoofed stored
  Document is repaired as any refused line is, by the runbook's malformed-line
  repair, not by retyping in the editor, whose `state` call refuses the line.
  The test docstring says it models a row the store already holds at the
  current admission (defence in depth), not the upgrade path. **Section
  number:** SPEC section 10 and the lead's note say "section 6"; the
  malformed-line bullet ("say which return and which line") is in the runbook's
  section 9 (`docs/runbook.md` about line 2742); section 6 is the dead-machine
  and recover section. The text says section 9.
- **F4.** `_short_title`'s derived-name check lost its held-row arm: it is
  now `if not unchanged and (hidden := invisible_problem(derived))`; the typed
  arm is kept, and the docstring says the held case is covered by the
  Document's own check (P301). `spoofing_problem` was then unused in
  `tracker/manifest.py` and its import is removed (ruff clean). Nothing
  unpinned: the existing tests all pass, including the held-row pins in
  `test_a_held_unchanged_row_is_judged_by_the_stores_rule_and_never_the_typed_one`
  (its last assertion, a held spoofing Document, is now the Document's refusal).
- **F5.** `layout.spoofing_problem`'s docstring no longer says the narrow
  rule spares "a byte-order mark" (the code refuses U+FEFF); it names the
  no-break space and the soft hyphen only. No behaviour change. The same
  sentence in HANDOFF-form-inputs (about line 564) is a historical record and
  was not touched.

Gate (venv Python, one process per file, parallel, `-p no:cacheprovider`):
`test_manifest` 113 passed (112 + the new test), `test_api` 522 passed,
`test_layout` 58 passed, `test_templates` 41 passed, `test_layers` 31 passed,
`test_single_source` 218 passed, `test_repo_map` 82 passed (it failed once,
stale, before `update`; and once more directly after it, passed on the rerun
with nothing changed); `ruff check .` all checks passed;
`tools/repo_map.py update` then `check` exit 0.

Not mine: the working tree also holds uncommitted edits to
`tracker/rollover.py` and `tests/test_rollover.py`, which `update` hashed into
the map; they appeared after this build started (the tree was clean at its
start) and were not made or touched by it.

## Review 2 (Opus, 2026-10-13)

Reviewer: Claude Opus 5.5. I did not build this. I reviewed rebuild 1, commit
`6d67fc1`, against SPEC-document-gate section 10 and re-checked sections 1-9.
The rebuild's own change is `git diff 2962ca3 6d67fc1`. `9b67afd..6d67fc1`
also carries the error-handling and client-folder commits (`6f5945f`,
`2962ca3`). `tracker/{manifest,layout,records,templates}.py` are identical at
`9b67afd` and `2962ca3`, so `9b67afd` is a faithful "before" for this build.
Everything ran on `git archive` copies of `9b67afd` and `6d67fc1` in the
scratchpad. Each copy was git-initialised and committed once. I used the venv
Python, throwaway probes and copies, and committed nothing. The checkout was
not touched except to append this section.

### Resolved

- **F1.** Probed on both archives with `item_from_fields`, for U+202E and
  U+200B in `Schedule K-1 - Ashford<c>Holdings LP`: held (`recorded` holding
  the row), new, and new with a short name of its own. At `6d67fc1` every case
  is exactly `F02: Issuer Name 'Ashford<U+202E>Holdings LP' may not contain an
  invisible character (U+202E RIGHT-TO-LEFT OVERRIDE)` (likewise for
  U+200B). At `9b67afd` each case was `F02: Document 'Schedule K-1 - ...'`.
  `templates.issuer_item("F02", "Ashford<c>Holdings LP", BASE_YEAR)` is the
  add-issuer card's path (`api` line ~5156: `issuer_row` then `issuer_item`).
  It gives the same Issuer Name sentence, with no raw character and no
  "(it is also the short name)". A non-issuer `W-2<U+202E>fdp.exe` is still
  `F02: Document 'W-2<U+202E>fdp.exe' ...`.
  - Edges:
    - A character at the start or end of the entity is quoted as
      `Issuer Name '<U+200B>Ashford'` or `'Ashford<U+200B>'`.
    - A lower-case prefix (`schedule k-1 - Ash<U+202E>ford`) gives Issuer
      Name, as `_issuer_entity` matches without case.
    - A character inside or before the prefix (`Schedule K-1<U+200B> - X`,
      `<U+202E>Schedule K-1 - X`) is not an issuer Document, so the refusal
      names the Document.
  - The entity always holds the offending character. When `_issuer_entity`
    is non-empty the fixed prefix matched exactly, and no spoofing code is
    whitespace (`\s`, `str.strip`), so neither normalisation can move or
    remove one. Narrowing the label to "the character lies in the entity" is
    therefore unnecessary.
  - The label comes from the Document's shape, the same test `_short_title`
    uses. That agrees with SPEC-form-inputs section 15 (G5): the issuer
    column's label for an issuer row. It is single-sourced:
    `assert api.ISSUER_LABEL is manifest.COL_ISSUER` (test_api ~8518) passes.
  - Mutation: with `9b67afd`'s `manifest.py` under `6d67fc1`'s tests, the new
    test fails on the `Document` label. The test discriminates.
- **F4.** Nothing that was refused before is now unrefused.
  - Why the held arm could not fire: `derived_short_title` builds the derived
    name from characters of the Document, the fixed `K-1 `, hyphens from
    `WINDOWS_ILLEGAL_CHARS.sub` and single spaces from `\s+`. No spoofing code
    is whitespace or Windows-illegal, so the derivation cannot introduce one.
    `item_from_fields` has already applied `spoofing_problem` to the whole
    Document before `_short_title` (its only caller) runs. So the removed
    `spoofing_problem(derived)` held arm could only fire when the Document
    check already had.
  - A sweep backs this up. Every code point from U+0020 to U+2FFF was
    inserted at three positions into five sample Documents, issuer and plain.
    There were zero cases where `spoofing_problem(derived)` fires while
    `spoofing_problem(document)` is clean.
  - The case you asked about: a held, unchanged row whose Document is clean
    but whose derived name holds a no-break space or a soft hyphen.
    `W-2<NBSP>Wages`, `W-2<SHY>Wages`, `Schedule K-1 - Ash<NBSP>ford LP` and
    `Schedule K-1 - Ash<SHY>ford LP` were each tried with a blank short name
    and with a short name equal to the derived one. Every one saves on both
    `9b67afd` and `6d67fc1`. Before, the held arm asked `spoofing_problem`,
    which spares both characters. Now nothing asks, and the result is the
    same. (A no-break space never survives into the derived name anyway: the
    `\s+` collapse turns it into a space.)
  - The typed arm is unchanged. A new `W-2<SHY>Wages` with a blank short name
    is refused `... (it is also the short name)` on both, and so is the
    issuer form, as Issuer Name.
  - The docstring's new paragraph states this argument correctly.
- **F5.** `layout.spoofing_problem`'s docstring now names only the no-break
  space and the soft hyphen as spared. The code refuses U+FEFF
  (`_SPOOFING_CODES`, and the comment at `layout.py:380` lists the byte-order
  mark among the refused). `test_layout` pins U+FEFF refused and NBSP, SHY,
  U+202F and U+3000 spared. It passes (58). See G1 for what this one-line
  change broke elsewhere.
- **F2.** The handoff's "For Jason, before landing" and the test_api
  docstring now say the household is repaired by the runbook's malformed-line
  repair, "its section 9: say which return and which line", not by retyping
  in the editor. At `6d67fc1`, `docs/runbook.md` section 9 is "Who to ask,
  and where the record is" (line 2703). The "line N of the record is
  malformed" bullet is at line 2742, and it ends "say which return and which
  line, and the store check ... names every such line". Section 6 is the
  dead-machine section. The builder's correction to 9 is right.
- **Dead code, layers, tests.**
  - Dead code: the removed `spoofing_problem` import had no `noqa` re-export
    and no user through `manifest` (grep over `tracker/`, `tests/`, `app/`).
    `short_title_problem` and `invisible_problem` are still used. Ruff is
    clean.
  - Layers: no import was added. `test_layers` passes (31).
  - No test weakened: the rebuild touches no existing test assertion. The
    only test edits are the new test_manifest test and the reworded test_api
    docstring. (The held-row test's last assertion became the Document's
    refusal in `f2c0631`, not here.)
  - The new test's claim matches its body: it compares the exact sentence,
    which also rules out "(it is also the short name)". It checks that the
    raw character is not echoed for held and new rows, and it covers the
    `issuer_item` path and the non-issuer Document.
- **Sections 1-9 hold.**
  - R1 and the store were unchanged by the rebuild. `test_records` passes
    (55). In `test_store` everything passes except the pin (G1).
  - R2 holds as amended by section 10.
  - R3: `test_templates` passes (41).
  - The admission is still 5. Nothing new is refused by the rebuild.

### Findings

**G1 - must fix. `tests/test_store.py::test_admission_version_changes_with_the_admission`
fails at `6d67fc1`.**
- Cause: the pin hashes the source text, docstring included, of every
  function the store's admission reaches (`admission_closure`:
  `inspect.getsource`). `layout.spoofing_problem` is one of those functions.
  F5's docstring edit moved its digest from `7a767da08a51fff8` (the
  `ADMISSION_PIN[5]` entry, test_store line 3674 in the `5: {` block that
  opens at 3607) to `972a7059c057543a`. The test fails with "The store's
  admission changed in: tracker.layout.spoofing_problem".
- Verified both ways: with `9b67afd`'s `layout.py` under `6d67fc1`, the test
  passes. On a copy of `6d67fc1` with only line 3674 re-pinned to
  `972a7059c057543a`, the whole file passes (197 passed, 1 skipped).
- Fix, in the test's own words for a rewording that refuses nothing new:
  re-pin `admission_digests()` under version **5**. Change that one entry in
  the version-5 block. Leave version 4's entry at line 3403 alone, and leave
  `ADMISSION_VERSION` at 5.
- Why it was missed: section 10's gate list (`test_manifest`, `test_api`,
  `test_layout`, `test_templates`, ...) left out `test_store`, so the rebuild
  never ran it. CLAUDE.md's affected-tests rule ("the own test file of every
  module that imports a changed one") would have included it for a
  `layout.py` change. Section 10's "No behaviour change" is true of
  behaviour, but not of the admission pin, which hashes docstrings. The
  landing session should add `test_store` (and `test_records`) to section
  10's gate line.

**G2 - nit. `pilot/SPEC-form-inputs.md` section 18 now misdescribes issuer
rows.** It says `item_from_fields` applies the rule "naming the row and the
Document". After F1 an issuer row names `Issuer Name` and its entity. Section
10 says section 18's "sections 14 to 17 otherwise stand" is true again, and
it is. Section 18's own sentence wants "(the Issuer Name and its entity for
an issuer row)". This is a docs-only change, for the SPEC's author or the
landing session.

**G3 - nit. `layout.spoofing_problem`'s docstring still says it is "what the
store's gate asks of a stored identifier or short name (P290)".** Since
P301 it also asks it of the Document. Any change to this docstring moves the
same pin, so if it is fixed it should ride G1's re-pin (one new digest, not
two commits each re-pinning).

**G4 - nit. Paperwork.**
- Commit `6d67fc1` also edits `pilot/SPEC-document-gate.md` (section 10's
  "section 6" to "its section 9; the SPEC first said 6"). The rebuild's
  "Edited:" list does not name that file, and by SPEC-form-inputs section 17
  (I4) a SPEC correction is the author's or the landing session's.
- Section 10 calls the handoff section "Reminder for Jason". It is titled
  "For Jason, before landing".

### Gate (archive copy of `6d67fc1`, venv Python, one process per file, in parallel, `-p no:cacheprovider`)

| file | result |
|---|---|
| test_manifest | 113 passed |
| test_api | 522 passed (the first review's 518 plus the error-handling lane's 4, now committed in `6f5945f`) |
| test_layout | 58 passed |
| test_templates | 41 passed |
| test_records | 55 passed |
| test_store | 196 passed, 1 skipped, 1 failed (`test_admission_version_changes_with_the_admission`, G1) |
| test_layers | 31 passed |
| test_single_source | 218 passed |
| test_repo_map | 81 passed, 1 failed (`test_the_committed_map_is_current`, see below) |

- `python -m ruff check .`: all checks passed.
- `python tools/repo_map.py check`: stale on exactly two files,
  `tracker/rollover.py` and `tests/test_rollover.py`. These are the other
  builder's working-tree edits that `update` hashed while this rebuild ran
  (the rebuild's handoff says so). This is F3 again, and it is the landing
  session's: run `update` and `check` on the combined tree. No file of this
  build is named, so the rest of the map is current for this build.

Findings: 1 must fix, 0 should fix, 3 nits.
