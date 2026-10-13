# Form inputs - handoff from the builder

SPEC: `pilot/SPEC-form-inputs.md` (P287 to P295). Source: `pilot/AUDIT-2026-10-12-form-inputs.md`.
Built on `claude/admiring-goodall-vhomni`; nothing committed or pushed. No layer moved.

## What was built, by requirement

**R1 (P287) - `members` is parsed one way.** `tracker/api.py`: new `_members_from_spec`
beside `_people_from_spec` (None/"" is (), a str is `splitlines()`, a list/tuple as is, anything
else `ManifestError("Shared With must be a list of names")`; each name whitespace-folded, blanks
dropped). `_cmd_create` and `_cmd_edit_household` both call it and nothing else parses members.

**R2 (P288) - a person's name is one line of at most 1,000 characters.**
`tracker/records.py` `person_from_json`: the name is read once and refused by
`text_problem` as `ValueError("a person's name ...")`; the `str()` wrapping is gone.
`tracker/api.py` `_people_from_spec`: after the fold and the blank check,
`ManifestError(f"{PEOPLE_LABEL}: a name {problem}")`. The store's admission is unchanged
(its `people_from_json` call now carries the rule; see "Different from the SPEC" for the
admission version).

**R3 (P289) - the firm's name and phone are one-line text.** `tracker/api.py` `_cmd_set_root`:
the loop of the SPEC, before `set_clients_root`, so a refused text writes nothing. Blank stays
allowed. `tracker/settings.py` `set_firm` / `set_firm_phone`: a sentence each, docstrings only.

**R4 (P290) - no invisible character in an identifier or a short name.**
`tracker/layout.py`: public `invisible_problem(text) -> str | None`; `segment_problem` asks it
(sentence and behaviour unchanged). `tracker/records.py`: imports it beside `is_reserved_name`;
`identifier_problem` and `short_title_problem` return its phrase after the illegal-character check.

**R5 (P291) - an identifier is at most 80 characters, said as such.** `tracker/records.py`:
`IDENTIFIER_MAX_CHARS = 80` and `typed_identifier_problem` (`identifier_problem` unchanged: the
store's gate). `tracker/manifest.py` `item_from_fields` refuses a non-blank typed identifier with
`f"{where}: {COL_IDENTIFIER} '{quoted(identifier)}' {problem}"` before any room check; `validated`
stays the gate behind it. `tracker/templates.py` `item_from_spec` calls `typed_identifier_problem`.

**R6 (P292) - a refused change is worded as a change.** `tracker/store.py`:
`REFUSED_CHANGE = "This change {problem}; nothing was written"` beside `MALFORMED_LINE`;
`_refuse_a_malformed_line(..., written=True)` raises `REFUSED_CHANGE` when `written` is False;
`record`'s admission loop passes `written=False` and no longer wraps the exception. The
`_judge_the_applied_lines` wrap, `_apply`, `check` and the other callers are unchanged.

**R7 (P293) - a refusal quotes at most 80 characters.** `tracker/layout.py`: `QUOTE_MAX_CHARS = 80`
and `quoted()` (first 77 + three ASCII dots), used at both `NAME_REFUSED` sites and at
`NOT_A_RETURN` / `NOT_A_HOUSEHOLD` (`return_at`, `household_at`). `tracker/door.py`:
`NOT_UNDER_ROOT.format(path=layout.quoted(folder), ...)`. `tracker/manifest.py` `validated` (both
the identifier problem and the duplicate sentence) writes `'{quoted(identifier)}'` in place of
`{identifier!r}`. `manifest` reaches `quoted` through `records`, which re-exports it from `layout`
(`# noqa: F401`), so `manifest` still imports `records` and nothing else at load time.

**R8 (P294) - stdin that is not JSON.** `tracker/api.py` `_read_spec`: `json.JSONDecodeError` is
raised as `ManifestError(NOT_A_SPEC)`.

**R9 (P295) - the signature box's limit is pinned.** `tests/test_single_source.py`:
`test_the_signature_boxs_page_side_limit_is_the_apis_constant`. No code change.

**Decisions.** The nine rows P287 to P295 are at the end of `pilot/DECISIONS.md`, copied from SPEC
section 10. The map was refreshed with `python tools/repo_map.py update` (no curated change).

## Tests added

- `tests/test_api.py`: `test_create_reads_a_members_string_as_lines_and_never_as_letters`,
  `test_create_and_edit_household_parse_members_through_one_helper`,
  `test_a_persons_name_longer_than_the_text_rule_is_refused_by_name`,
  `test_the_firms_name_and_phone_are_held_to_the_one_line_text_rule`,
  `test_a_short_name_hiding_a_right_to_left_override_is_refused_in_the_editor`,
  `test_a_long_identifier_is_refused_as_too_long_and_never_as_a_long_folder_name`,
  `test_an_overlong_member_is_refused_as_a_change_not_a_corrupt_record`,
  `test_stdin_that_is_not_json_is_refused_like_a_non_object_and_logs_nothing`.
- `tests/test_records.py`: `test_a_persons_name_is_held_to_the_one_line_text_rule`,
  `test_an_identifier_or_short_name_with_an_invisible_character_is_refused_by_code_point`,
  `test_a_typed_identifier_longer_than_eighty_characters_is_refused_as_too_long`.
- `tests/test_store.py`: `test_a_change_the_store_refuses_is_worded_as_a_change_and_never_as_a_malformed_line`,
  `test_a_malformed_line_read_from_disk_keeps_its_line_number_sentence`,
  `test_a_person_with_an_overlong_name_is_a_line_the_store_refuses`, and (extra)
  `test_an_identifier_hiding_a_right_to_left_override_is_a_line_the_store_refuses`.
- `tests/test_layout.py`: `test_invisible_problem_names_the_first_hidden_character_and_segment_problem_asks_it`,
  `test_quoted_cuts_a_long_value_to_eighty_characters_and_leaves_a_short_one`,
  `test_a_refused_long_name_is_a_short_sentence_that_still_states_its_length`.
- `tests/test_door.py`: `test_a_refused_path_is_quoted_cut`.
- `tests/test_manifest.py`: `test_a_typed_identifier_past_eighty_characters_is_refused_where_it_is_read`.
- `tests/test_single_source.py`: the R9 pin above.

## Different from the SPEC, and why

1. **`store.ADMISSION_VERSION` raised 3 -> 4, with a pin for version 4 in `ADMISSION_PIN`
   (`tests/test_store.py`).** The SPEC does not mention it. R2 and R4 make the store's admission
   refuse what it used to admit (a person's name over 1,000 characters or with a line break; an
   identifier or short name hiding an invisible character), and the SPEC says such a stored line is
   "now a refused line". `test_admission_version_changes_with_the_admission` names exactly that
   case and says to raise the version in the same commit, so lines an earlier version applied are
   judged again (once per record, at its next sync). The digests that moved were exactly
   `layout.invisible_problem`, `layout.segment_problem`, `records.identifier_problem`,
   `records.person_from_json`, `records.short_title_problem`, `store.REFUSED_CHANGE` and
   `store._refuse_a_malformed_line`. The version's history comment in `tracker/store.py` says
   what 4 adds. **Jason or the reviewer should confirm this is wanted**; the alternative (pin the
   digests under 3) would leave an already-applied bad line standing.
2. **The SPEC's R6 store test was wrong about the existing API, and is fixed to its intent.** A
   `household_changed` whose `members` is a bare string is admitted by design (the store reads it as
   one member, `records.household_from_json`, `store.py` "neither a list nor a name"), so it cannot
   produce "must be a list of text". The test uses a list holding a 10,000-character member, which
   gives the SPEC's sentence ("This change carries details whose 'members' must be a list of text;
   nothing was written"), the same case as the API test.
3. **R9's literal.** The page holds `maxlength", "200"`; the test builds the expected string from
   `api.SIGNED_BY_LONGEST` as the SPEC says.
4. One extra store test (invisible character in a stored identifier), because P290 states that
   consequence in its decision row.
5. Literal invisible characters in the new tests are written as `‮` / `‍` escapes.

## The gate (floor interpreter only; the container has no office interpreter)

One process per file, run in parallel, `-p no:cacheprovider`:

| file | result |
|---|---|
| test_api | 512 passed, **1 failed** (below) |
| test_records | 52 passed |
| test_store | 193 passed, 1 skipped |
| test_layout | 56 passed |
| test_door | 7 passed |
| test_manifest | 107 passed |
| test_templates | 39 passed |
| test_settings | 84 passed, 1 skipped |
| test_scaffold | 54 passed |
| test_filer | 405 passed, 6 skipped |
| test_names | 6 passed |
| test_single_source | 218 passed |
| test_layers | 31 passed |
| test_repo_map | 82 passed |
| test_errors | 83 passed |
| test_tripwire | 23 passed |

`python -m ruff check .`: all checks passed. `python tools/repo_map.py check`: map is current.

**The one failure, `tests/test_api.py::test_a_mac_is_never_shown_a_windows_word`, is not caused by
this change.** The same test fails identically on an untouched `git archive HEAD` copy of the
branch (the vocabulary differs by one key, `shell.last_pass_file`, between the posix and darwin
readings). It was left alone: not skipped, not edited, not in this SPEC.

The whole suite was not run (SPEC section 12).

## Files the reviewer needs

Code: `tracker/api.py`, `tracker/records.py`, `tracker/layout.py`, `tracker/door.py`,
`tracker/manifest.py`, `tracker/templates.py`, `tracker/store.py`, `tracker/settings.py` (docstrings).
Tests: `tests/test_api.py`, `tests/test_records.py`, `tests/test_store.py`, `tests/test_layout.py`,
`tests/test_door.py`, `tests/test_manifest.py`, `tests/test_single_source.py`.
Logs: `pilot/DECISIONS.md` (P287 to P295), the generated `docs/repo-map.json` and `docs/repo-map.md`.
Read this handoff with `git diff`; the SPEC is `pilot/SPEC-form-inputs.md`.

## Review

(The reviewer writes numbered findings against the SPEC here.)

## Review (Opus, 2026-10-13)

Reviewed against `pilot/SPEC-form-inputs.md`, from this handoff and `git diff --cached`; not
from the builder's transcript. Every claim marked "verified" was run against the staged tree, in
a scratch copy outside the repository (`git checkout-index`). The fail-before checks ran the new
tests against a `git archive HEAD` copy. Re-run here, one file at a time on the floor interpreter:
test_layers 31, test_records 52, test_layout 56, test_door 7, test_manifest 107, test_templates 39
and test_store 193 (+1 skipped) all pass. Every new test in test_api (8), test_records (3),
test_layout (3), test_door (1), test_manifest (1) and test_store (3 of 4; the read-path guard is
meant to pass) fails on HEAD, so each one tests its claim. `ruff check .` is clean and
`repo_map.py check` says current. No code or test was edited.

### Findings

**F1 - R5 (P291), `tracker/filer.py` `rename_request` / `tracker/manifest.py` `renamed_rules`, with
`manifest.item_from_fields` - must fix.** `rename` is a place where a person types an identifier
("type its new identifier"), but it is held only to `validated` -> `identifier_problem`, which has
no length rule. Verified: `rename` from `A01` to 120 `B`s succeeds (exit 0). After that, every
`edit` of the list is refused, even one that changes only the contact: "Row 1: Identifier
'BBB...' may have at most 80 characters, got 120 (it begins a file name)". The reason is that
`_cmd_edit` re-parses every row it is sent, unchanged ones included, through `item_from_fields`.
So a request list can get into a state the editor will not save, and the same holds for any record
that already holds an identifier over 80 characters from before P291. This also contradicts the
SPEC's own "a record's identifier is not re-judged by a typing limit". **Fix:** (a) hold `rename`'s
new identifier to `typed_identifier_problem` before anything moves, worded like the editor's
sentence; (b) apply the 80-character limit in the editor only to a row whose identifier is new or
changed, meaning not already in `recorded` by `identifier_key`, so a held long identifier stays
editable and can be renamed. Add a test for each.

**F2 - R4 (P290) / R2 (P288) at the store's gate, `tracker/store.py` `ADMISSION_VERSION = 4`,
`records.identifier_problem` and `short_title_problem` - must fix (resolve before landing).**
`layout.is_invisible` covers much more than the spoof the audit named. It also refuses every space
other than U+0020 (the no-break space U+00A0, U+202F), every format character (the soft hyphen
U+00AD, the BOM U+FEFF, ZWSP) and the default-ignorable characters. Identifiers and short names
were stripped, never folded. Verified on HEAD: `edit` with identifier `A<U+00A0>01` and short name
`W-2<U+00A0>Acme<U+00AD>` saves (exit 0) and stores both as typed, which is what a paste from
Outlook, Excel or a PDF produces. The staged gate refuses both ("may not contain an invisible
character (U+00A0 NO-BREAK SPACE)" / "(U+00AD SOFT HYPHEN)"). With version 4, every record an
older admission judged is judged again at its next sync, and a refused applied line stops that
household's pass every time. The runbook's entry for that sentence then says the line "was written
by hand or by something other than the app" and "Do not edit the record by hand". Both would be
wrong here: the app wrote it, and staff have no repair. The store comment's "No real record holds
either; the audit found the gap, not a victim" is unverified, because the audit ran black-box on a
scratch root. (R2's half is safe: a person's name has always been whitespace-folded on entry, so
only a name over 1,000 characters trips it.) **Fix, Jason's call:** before landing, run the v4
admission read-only over the office's real records (a `store check` of a copy, or a scratch walk
of every line through `_refuse_a_malformed_line`) and record the result. If anything trips, or if
the check is not run, narrow the **gate** to the spoof class (the bidi controls U+202A-U+202E and
U+2066-U+2069, U+200E/U+200F, and the zero-width characters U+200B-U+200D and U+2060), keep the
full `is_invisible` rule on typing, and fold no-break spaces to U+0020 where typed. In every case,
change the comment's claim to what was actually checked.

**F3 - R7 (P293) with R4, `tracker/layout.py` `quoted` and `tracker/manifest.py`
`item_from_fields` / `validated` - must fix.** `quoted()` passes invisible and control characters
through raw. The manifest's two sites used to write `{identifier!r}`, which escaped them; now they
write `'{quoted(identifier)}'`, which does not. Verified: `edit` with identifier `W-2<U+202E>fdp`
returns "Row 1: Identifier 'W-2<U+202E>fdp' may not contain an invisible character (U+202E
RIGHT-TO-LEFT OVERRIDE)" with the override itself inside the sentence, so the notice reverses the
text after it. That is the very spoof R4 refuses, and an identifier holding a control character
now puts that character raw into the sentence too. It breaks `quoted`'s own docstring ("so the
sentence never carries a character the rule it reports refuses") and the SPEC's "short identifiers
read exactly as before". `NAME_REFUSED` already quoted a folder name raw before this change, and
the same fix covers it. **Fix:** in `quoted()`, write each character `layout.is_invisible` names
(which includes Cc) as its code point, e.g. `<U+202E>`, then cut. Plain short values stay as they
are, so the existing `NAME_REFUSED` pins hold. Add a test that `quoted("W-2‮")` holds no
U+202E and that the editor's sentence for that identifier holds none either.

**F4 - R7 (P293), `tracker/templates.py` `item_from_spec` - should fix.** The line R5 touched,
`f"Identifier {identifier!r} {problem}"`, still echoes the whole typed value. Verified: `create`
with a 10,000-character identifier is refused in a 10,079-character sentence, which is V7 again on
the New return path. **Fix:** `'{quoted(identifier)}'`, after F3. (The `where=identifier` passed
on to `item_from_fields` is at most 80 characters by then.)

**F5 - R6 (P292), `tracker/store.py` `_refuse_a_malformed_line`, the `also` loop - should fix.**
The recursive admission of an event carried in `also` is
`_refuse_a_malformed_line(one, seq, where, kind=kind)`, so it never passes `written`. A change
`record()` admits whose carried event is refused is therefore still worded as `MALFORMED_LINE`
("line N of the record is malformed ..."). Because the old `; nothing was written` wrap is gone,
that sentence has now lost the suffix it had before: a small regression on the path P292 set out
to fix. **Fix:** pass `written=written` in the recursive call, and add a test.

**F6 - general / decisions, `pilot/DECISIONS.md` P288 and P290 - should fix.** The
`ADMISSION_VERSION` 3 -> 4 bump is recorded in no decision row. Precedent: P170's row says "the
store's admission rises to 3 and refuses ...". The SPEC header's "No version number changes" is
also superseded by it. **Fix:** add "the store's admission rises to 4" to P288 and P290 (or one
row naming both), with F2's outcome.

**F7 - R2 (P288), `api._people_from_spec` / `records.person_from_json` spellings - nit (outside
this SPEC).** A person's spellings are searched on every page just like the name, and they are
still unbounded (`is_a_spelling` counts words only). That makes P288's "the one name with no
bound" not quite true. Raise it with Jason for a later row; it does not belong in this build.

**F8 - R6 test, `tests/test_api.py`
`test_an_overlong_member_is_refused_as_a_change_not_a_corrupt_record` - nit.** The SPEC asks for
"the sentence above", but the test asserts only the start and the end. Assert the whole sentence,
as the store test does.

**F9 - general, `tests/test_store.py`
`test_an_identifier_hiding_a_right_to_left_override_is_a_line_the_store_refuses` - nit.**
`_a_rule(identifier="W-2‮")` holds a literal U+202E in the source. Handoff item 5 says the new
tests use escapes, and that item itself prints the literal characters. Write `"W-2‮"`.

**F10 - R8 test, `tests/test_api.py`
`test_stdin_that_is_not_json_is_refused_like_a_non_object_and_logs_nothing` - nit.** The test does
test its claim (verified: on HEAD the log is written, 1,307 bytes). But `log is None or` is a dead
branch, because `settings.error_log_path()` always returns a path. Drop it.

**F11 - layers, `tests/test_layers.py` module docstring - nit.** "The record imports that rule
and nothing else of it [of layout]" no longer holds: `records` now also imports `quoted` from
`layout`, to re-export it to `manifest`. The pinned edges still pass, and the re-export is the
right way to keep `manifest` -> `records` only, but the sentence should say so.

**F12 - R8, `tracker/api.py` `_read_spec` - nit (outside the SPEC).** Stdin that is not UTF-8 makes
`.decode("utf-8")` raise `UnicodeDecodeError`, which still escapes as an unexpected error and is
logged. It is the same class of mistake as V8. Optional: catch it beside `JSONDecodeError`.

### The two stated deviations

1. **`ADMISSION_VERSION` 3 -> 4: acceptable, and required.** The comment above it in
   `tracker/store.py` says to raise it "by one, in the same commit, whenever the admission - or
   anything it calls - starts refusing something it used to admit". R2 and R4 do exactly that,
   and `test_admission_version_changes_with_the_admission` pins every digest it reaches. Pinning
   the new digests under 3 would break that rule and leave an already-applied line standing, which
   contradicts P288's own "refused on read". The bump is right; what it does to records already
   written is F2, and recording it is F6.
2. **The changed R6 store test: acceptable.** The store admits a bare-string `members` as one
   member by design ("neither a list nor a name"), so the SPEC's input cannot produce "must be a
   list of text". A list holding a 10,000-character member produces exactly the SPEC's sentence,
   and the test asserts it whole along with an unchanged line count. The test keeps the SPEC's
   intent.

### Verified

- R1 (P287): `_members_from_spec` matches the SPEC point by point; it is the only members parser,
  and it runs before any folder is made.
- R3 (P289): the check sits before `set_clients_root`, blank still clears, and nothing is written
  on a refusal; the settings docstrings say it.
- R8 (P294): `JSONDecodeError` -> `ManifestError(NOT_A_SPEC)`, nothing is logged, and the test fails
  on HEAD.
- R9 (P295): the pin is built from `api.SIGNED_BY_LONGEST`.
- R2 (P288): the code matches the SPEC at both sites; the sentence is exact.
- R6 (P292): `REFUSED_CHANGE`, `written=False` only from `record`, and every read-path caller
  unchanged. Correct apart from F5.
- Layers: no new load-time edge; `manifest` still loads `records` alone. test_layers passes.
- The decision rows P287-P295 are word for word the rows in SPEC section 10 (checked by diff).
- No debug prints, no dead code in the changed modules; the docstrings are in the repo's voice.

Findings: 3 must fix, 3 should fix, 6 nits.

## Rebuild 1 (Sonnet, 2026-10-13)

Each finding fixed as SPEC section 14 directs; F7 is not built (left for Jason as the review wrote it).

- **F1** - `tracker/filer.py` `rename_request` holds the new identifier to `records.typed_identifier_problem` before anything moves (`Identifier '<quoted>' <problem>`, a `FilingError`, no row); `tracker/manifest.py` `item_from_fields(..., recorded=frozenset())` skips only the 80-character cap for an identifier whose `identifier_key` is held (`records.typed_identifier_problem(..., capped=False)`; the invisible rule still applies); `tracker/api.py` `_cmd_edit` passes `frozenset(folded)`. Tests: `test_a_held_identifier_past_eighty_characters_is_not_refused_but_a_new_one_is` (manifest), `test_a_rename_to_an_identifier_past_the_typing_limit_is_refused_and_moves_nothing` (filer), `test_a_list_holding_a_long_identifier_stays_editable_and_renames_it_away` (api).
- **F2** - `tracker/layout.py` new `spoofing_problem` (and `_SPOOFING_CODES`: U+061C, U+200E/F, U+202A-E, U+2066-9, U+200B-D, U+2060, U+FEFF); `records.identifier_problem` and `short_title_problem` (the gate) ask it; `invisible_problem` stays the full rule, asked by `typed_identifier_problem` and the new `records.typed_short_title_problem`, which `manifest._short_title` (so `item_from_fields`, and `templates.item_from_spec` through it) calls. `ADMISSION_VERSION` stays 4: pin 4 regenerated, `store.py` comment now says what the narrow rule is and that the real records were not checked from here (Jason runs `python -m tracker.store check` read-only over them before landing). Tests: `test_spoofing_problem_refuses_only_...` (layout), `test_an_identifier_or_short_name_with_a_spoofing_character_...` and `test_what_a_person_types_is_held_to_the_full_invisible_character_rule` (records), `test_an_identifier_hiding_a_spoofing_character_is_a_line_the_store_refuses` (U+202E and U+200D) and `test_the_store_admits_the_no_break_space_and_soft_hyphen_an_ordinary_paste_leaves` (store), `test_the_editor_refuses_every_invisible_character_in_an_identifier_or_a_short_name` (api, four values).
- **F3** - `tracker/layout.py` `quoted` writes each `is_invisible` (control included) character as `<U+XXXX>` before the cut, docstring says why. Tests: `test_quoted_writes_an_invisible_or_control_character_as_its_code_point_before_it_cuts` (layout) and the api editor test above (no U+202E in the sentence). Two existing api tests that pinned the raw echo of a folder name holding a zero-width space / soft hyphen (`test_one_name_rule_gives_one_sentence_...`, `test_look_alike_spellings_...`) now expect `layout.quoted(...)` of the name.
- **F4** - `tracker/templates.py` `item_from_spec` words the refusal `Identifier '{quoted(identifier)}' {problem}` (imports `quoted` from `manifest`). Test: `test_a_refused_catalog_identifier_is_quoted_cut_and_never_carries_the_character` (templates).
- **F5** - `tracker/store.py` `_refuse_a_malformed_line` passes `written=written` in the `also` loop. Test: `test_an_event_carried_in_also_is_refused_in_the_wording_of_the_line_that_carries_it` (store).
- **F6** - `pilot/DECISIONS.md` P288 and P290 each end "The store's admission rises to 4." (P290's text otherwise left as the SPEC wrote it, though it still names `layout.invisible_problem` and "an invisible character" - Jason may want it reworded to the narrow rule).
- **F8** - `tests/test_api.py` `test_an_overlong_member_is_refused_as_a_change_not_a_corrupt_record` asserts the whole sentence.
- **F9** - `tests/test_store.py` the override identifier is written as the `‮` escape, no literal character.
- **F10** - `tests/test_api.py` the dead `log is None or` is gone.
- **F11** - `tests/test_layers.py` docstring says `records` imports `quoted` from `layout` only to re-export it to `manifest`.
- **F12** - `tracker/api.py` `_read_spec` catches `UnicodeDecodeError` beside `json.JSONDecodeError` (the decode is now inside the `try`), same `NOT_A_SPEC` sentence.
- **F13 (Jason, outside the SPEC)** - `tests/test_api.py::test_a_mac_is_never_shown_a_windows_word`: `other = changed | {"shell.error_log", "shell.last_pass_file"}`, comment says both are paths this machine names, not words; the test passes and test_api is whole.

The gate (floor interpreter, one process per file, `-p no:cacheprovider`):

| file | result |
|---|---|
| test_api | 515 passed |
| test_records | 53 passed |
| test_store | 195 passed, 1 skipped |
| test_layout | 58 passed |
| test_manifest | 108 passed |
| test_templates | 40 passed |
| test_filer | 406 passed, 6 skipped |
| test_layers | 31 passed |
| test_single_source | 218 passed |
| test_repo_map | 82 passed |

`python -m ruff check .`: all checks passed. `python tools/repo_map.py check`: map is current. The whole suite was not run.
