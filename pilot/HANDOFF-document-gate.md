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
