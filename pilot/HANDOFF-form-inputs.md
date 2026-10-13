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

## Review 2 (Opus, 2026-10-13)

A second, separate review of the final state (`bd139f2`) against `pilot/SPEC-form-inputs.md` as
section 14 amends it. I read the SPEC, this handoff, `git diff 6f6410b HEAD` file by file and the
rebuild alone (`git diff 5469d30 HEAD`). I did not read any agent transcript and did not edit any
code or test. Every behaviour claim marked "verified" was run on the floor interpreter, either
through the named test file or through a throwaway test kept in the scratchpad, never in the
repository.

### Resolved

- **F1 - resolved for the cap, not in effect for the rule beside it (see G1).** `rename_request`
  holds the new identifier to `typed_identifier_problem` before the lock, using the SPEC's
  `Row`-less sentence. `item_from_fields(recorded=...)` skips the cap only, and `_cmd_edit` passes
  the held keys. The api, filer and manifest tests pass, and a held 120-character identifier stays
  editable.
- **F2 - resolved as section 14 directs.** `spoofing_problem` and `_SPOOFING_CODES` are exactly
  the listed code points. The gate (`identifier_problem`, `short_title_problem`) asks
  `spoofing_problem`. The typed checks (`typed_identifier_problem`, the new
  `typed_short_title_problem` through `manifest._short_title`) ask `invisible_problem`.
  `ADMISSION_VERSION` stays 4. The store admits `A<NBSP>01` / `W<SHY>X` and refuses U+202E and
  U+200D (tests pass). The store comment no longer claims an unchecked fact. The read-only run over
  the real records is still Jason's to make.
- **F3 - resolved.** `quoted` writes every `is_invisible` character (Cc included) as `<U+XXXX>`
  and then cuts, and its docstring says why. Verified: `quoted("W-2‮fdp") == "W-2<U+202E>fdp"`,
  and the editor's sentence carries no U+202E. Two existing api pins now expect
  `layout.quoted(name)`. That is the intended change, not a weakened test.
- **F4 - resolved.** `templates.item_from_spec` words `Identifier '{quoted(identifier)}'`. Its test
  checks a sentence under 300 characters and `<U+202E>` with no raw character.
- **F5 - resolved.** The `also` recursion passes `written=written`. The new store test checks both
  wordings.
- **F6 - resolved.** P288 and P290 each end "The store's admission rises to 4." P290 is reworded to
  the two rules, and that wording matches the code (but see G4).
- **F7 - not built, as section 14 directs** (left for Jason as a later row).
- **F8 - resolved.** The whole sentence is asserted.
- **F9 - resolved.** `‮` / `‍` escapes only. No literal bidi character is in the new
  tests.
- **F10 - resolved.** The dead `log is None or` is gone.
- **F11 - resolved.** The test_layers docstring states the `quoted` re-export and why.
  test_layers passes, and `manifest` still loads `records` alone.
- **F12 - resolved.** `UnicodeDecodeError` is caught beside `JSONDecodeError`, with the decode
  inside the `try`. Verified by hand: stdin `\xff\xfe{` to `set-schedule` exits 1 with
  `NOT_A_SPEC`. No test pins it (G3).
- **F13 - resolved, not a weakened test.** `shell.last_pass_file` is `str(runner.last_pass_path())`,
  a machine path like `shell.error_log`. It is excluded only from the mac/windows equality
  comparison and is still searched for Windows words. test_api is whole: 515 passed.

### Findings

**G1 - R4/R5 as amended (P290, P291), `tracker/manifest.py` `item_from_fields` with
`tracker/records.py` `typed_identifier_problem(capped=False)` and `manifest._short_title` - must
fix (Jason's call, because it needs a section 14 amendment).** Section 14 exempts a held
identifier from the cap only: "the invisible rule still applies to every row". In effect, that
recreates F1's trap for exactly the values F2 says an ordinary paste leaves in a real record.
`_cmd_edit` re-parses every row it is sent, and `_as_recorded` refills the held short name even
for a row that leaves it out. So a list that holds an identifier with a no-break space, or a short
name with a soft hyphen, can no longer be saved at all. That includes an edit to another column
and an older window's row that sends only `identifier` and `document`. The first review verified
that HEAD saves both values as typed, and the store keeps admitting them by design. Verified here
by writing each value straight into a record and then editing only the Document:
`Row 1: Identifier 'A<U+00A0>01' may not contain an invisible character (U+00A0 NO-BREAK SPACE)`
and `Row 1: Short name may not contain an invisible character (U+00AD SOFT HYPHEN)`, exit 1 both
times. There is a way out (Rename for the identifier, retyping the cell for the short name), but
the sentence names neither, and the person did not touch that row. Jason's pre-landing
`python -m tracker.store check` cannot size this either, because it runs the narrow gate, which
admits these values. **Fix:** a row the list already holds is asked only the gate's rule for what
it sends back unchanged. For the identifier, `capped=False` (better named `held=True`) skips
`invisible_problem` as well as the cap, so the typed check is `identifier_problem` alone. For the
short name, when the row's short name equals the held rule's, ask `short_title_problem` rather than
`typed_short_title_problem`. This needs the held short name, so pass the held rules (a key-to-rule
mapping) instead of the bare key set. A new or changed value stays held to the full rule. Add an
api test: a list holding `A 01` with short name `W­X`, written straight into the record,
saves an edit to its Document, and a new row holding U+00A0 is refused. Reword P290/P291 to match.
If Jason prefers the SPEC as written, record that decision in P290 and add a read-only scan of
identifiers and short names for `is_invisible` to the pre-landing check, because `store check`
will not show them.

**G2 - R4 (P290), `tracker/manifest.py` `item_from_fields` / `derived_short_title`, a path the
rule still misses - should fix (it predates the rebuild; the first review did not raise it).** R4
refuses the spoof because "both values become part of every working copy's file name". A row
whose short name is left blank, which is the usual case for a row typed in the editor, takes
`derived_short_title(document)` at use. The Document is held only to `text_problem`, which does
not refuse format characters. Verified: `item_from_fields({"identifier": "A01", "document":
"W-2‮fdp.exe"})` passes `validated`, and `prepared_name_for` gives
`'A01 - W-2‮fdp.exe.pdf'`, the exact spoof P290 names. **Fix:** in `item_from_fields`, when
the short name is blank, hold `derived_short_title(document)` to `typed_short_title_problem`'s
invisible half and refuse as `{where}: {COL_DOCUMENT} ...` (or hold the Document itself to
`spoofing_problem` where typed). Whether the store's gate should judge the Document too is
Jason's call, because it widens what admission 4 refuses. Add a manifest or api test, and mention
the Document in P290.

**G3 - R8 as amended (F12), `tests/test_api.py` - nit.** The `UnicodeDecodeError` branch is
untested. A two-line sibling of
`test_stdin_that_is_not_json_is_refused_like_a_non_object_and_logs_nothing` that feeds non-UTF-8
bytes would pin it.

**G4 - decisions, `pilot/DECISIONS.md` P290 / P291 - nit.** P290 says "A stored identifier holding
a spoofing character is a refused line", but the gate refuses a stored short name holding one too
(`short_title_problem`). P291 does not say that an identifier the list already holds is exempt
from the cap, or that Rename is held to it (F1). Both rows should say what the code does.
Re-settle them after G1.

**G5 - R4 typed rule, `tracker/templates.py` `issuer_item` / `manifest.issuer_short_title` - nit.**
A K-1 issuer name typed with a soft hyphen, which `entity_keyword` does not fold away, is now
refused as `F02: Short name may not contain an invisible character (U+00AD SOFT HYPHEN)`. The
person never typed a short name, because it is derived from the issuer. Verified with
`issuer_item("F02", "Ashford­Holdings", 2025)`. Before this change it was accepted. Either
fold or drop `is_invisible` characters in `entity_keyword`, or word the refusal on the issuer's
name.

### Verified

- Test files run one process each, in parallel, on the floor interpreter: test_api 515 passed,
  test_records 53, test_layout 58, test_manifest 108, test_templates 40, test_store 195 (+1
  skipped), test_filer 406 (+6 skipped), test_door 7, test_layers 31, test_single_source 218,
  test_errors 83, test_tripwire 23. `ruff check .` passes, `repo_map.py check` says current, and
  the tree is clean.
- **`capped=False`** has the right shape for what section 14 says (it skips the cap and only the
  cap). It is used at exactly one call site, `item_from_fields`, for a key in `recorded`, which
  only `_cmd_edit` passes. `create`, `templates.item_from_spec` and `rename_request` all use the
  capped default. It is tested in test_records (`"A"*200` passes; with U+00A0 it is refused) and
  in test_manifest (a held key passes, case-folded too; a new key, or no `recorded`, is refused).
  Whether it should also skip the invisible rule is G1.
- **The store gate, end to end.** `person_from_json` holds the name to `text_problem` (only
  `api._people_from_spec` builds a `Person`, and it whitespace-folds, so only a name over 1,000
  characters or one holding a non-space control character can trip it). `identifier_problem` and
  `short_title_problem` ask `spoofing_problem`, and `store.check` re-judges every line through
  `_refuse_a_malformed_line`. `rollover` uses `validated` (the gate rule), so Roll Forward is not
  touched by the typed rule. An ordinary existing record is refused on read only if it holds a
  person's name over 1,000 characters or a control character, or a bidi or zero-width character in
  an identifier or short name. That is the narrow set section 14 accepted, pending Jason's run.
- **The admission pin is honest.** Pin 3 is byte-identical to `6f6410b`. Pin 4 is a full
  dictionary that differs from pin 3 in exactly `_SPOOFING_CODES`, `invisible_problem`,
  `segment_problem`, `spoofing_problem`, `identifier_problem`, `person_from_json`,
  `short_title_problem`, `REFUSED_CHANGE` and `_refuse_a_malformed_line`.
  `test_admission_version_changes_with_the_admission` still compares every digest exactly against
  the current version's pin, so any further change to the admission fails it again.
- **Layers.** `filer` takes `COL_IDENTIFIER`, `quoted` and `typed_identifier_problem` from
  `records`. `templates` takes `quoted` and `typed_identifier_problem` from `manifest`. `records`
  imports `invisible_problem`, `spoofing_problem` and `quoted` from `layout`. The
  `short_title_problem` re-export in `manifest` is still used (test_templates, the same-object
  test). No new load-time edge; test_layers passes.
- **SPEC-named tests.** Every one in sections 1-9 and section 14 is present and named as its
  claim. The records R4 test is renamed to "spoofing character", which matches the amended claim.
  The amended R5 api test uses a 120-character new row where section 14 said 81, and the
  81-character boundary is pinned in test_manifest. Each test asserts its claim, including
  nothing written on refusal where the SPEC asks for it.
- **The rebuild's diff** touches only what F1-F6 and F8-F13 name: no stray behaviour change, no
  debug output and no dead code (ruff is clean). The admission comment and the docstrings are in
  the repo's voice.

Findings: 1 must fix, 1 should fix, 3 nits.

## Rebuild 2 (Opus, 2026-10-13)

Each finding fixed as SPEC section 15 directs; nothing else touched.

- **G1** - `tracker/manifest.py` `item_from_fields(..., recorded=None)`: `recorded` is now a mapping of `identifier_key` to the held `RequestItem`. An identifier spelt exactly as held is asked `records.identifier_problem` alone; any other spelling (a case-only respelling included) gets `typed_identifier_problem`. `_short_title` asks `short_title_problem` of a short name equal to the held one and `typed_short_title_problem` otherwise. `tracker/api.py` `_cmd_edit` passes `{key: item_from_record(rule)}` for the held rows. `tracker/records.py` `typed_identifier_problem` loses `capped`; its docstring says who asks the gate's rule instead. Tests: `test_a_list_holding_what_an_older_paste_left_stays_editable_and_a_changed_spelling_is_typed` (api: a record holding `A<NBSP>01` / `W<SHY>X` saves a Document edit and an older window's two-key row; `a<NBSP>01` is refused with the typed sentence, nothing written). `test_a_held_identifier_past_eighty_characters_is_not_refused_but_a_new_one_is` (manifest) is rewritten to the mapping: a held NBSP identifier passes, and a case respelling is now a change. The `capped=False` lines in test_records are gone.
- **G2** - `tracker/manifest.py` `_short_title(value, document, where, held)`: a blank short name, or one equal to `derived_short_title(document)`, has that derived name judged for invisible characters. That is `invisible_problem` when the Document or short name is new or changed, and `spoofing_problem` (the store's half) when both are as held. The refusal is `{where}: {label} '{quoted(source)}' {problem} (it is also the short name)`. Only the invisible half is asked of the derived name: the derivation already cuts the length and strips a trailing separator, and `filer._parts_of` sanitises an illegal character. The full short-name rule would have started refusing a Document such as `Form 1099: Interest`, which no finding asks for. Tests (manifest): `test_a_derived_short_name_hiding_an_invisible_character_is_refused_naming_the_document` and `test_a_held_unchanged_row_is_judged_by_the_stores_rule_and_never_the_typed_one`. The second test shows soft hyphens on held rows passing, the same values changed refused, and a held U+202E Document still refused by the store's half.
- **G3** - `tests/test_api.py` `test_stdin_that_is_not_utf8_is_refused_like_a_non_object_and_logs_nothing` (stdin `\xff\xfe{`). No code change.
- **G4** - `pilot/DECISIONS.md` P290 now says a stored identifier *or short name* holding a spoofing character is a refused line, and that the derived short name is judged when the list is saved, naming the Document or Issuer Name (the store's gate does not read the Document). P291 says the cap and the typed rules apply to a new or changed value only, never to one the list already holds, and that Rename is held to them.
- **G5** - `tracker/manifest.py` adds `COL_ISSUER = "Issuer Name"`, and `api.ISSUER_LABEL` is now `COL_ISSUER`, so the wording lives in one place: no existing `COL_*` named the issuer, and `manifest` cannot import `api`. A new `_issuer_entity(document)` is shared by `derived_short_title` and the refusal's label. An issuer row's derived short name is refused on the issuer: `F02: Issuer Name 'Ashford<U+00AD>Holdings' ... (it is also the short name)`. Test (templates): `test_an_issuer_name_hiding_a_soft_hyphen_is_refused_naming_the_issuer_never_a_short_name`.

Each new test was run against the pre-fix code (HEAD's `manifest`/`records`/`api`, with `_read_spec`'s `UnicodeDecodeError` catch removed for G3), and all six failed. The gate (floor interpreter, one process per file in parallel, `-p no:cacheprovider`):

| file | result |
|---|---|
| test_api | 517 passed |
| test_manifest | 110 passed |
| test_records | 53 passed |
| test_templates | 41 passed |
| test_filer | 406 passed, 6 skipped |
| test_layers | 31 passed |
| test_single_source | 218 passed |
| test_repo_map | 82 passed (first run: 1 failed, `repo-map.md` out of step while the other lane committed `bfe9fea`; `update` then said current, and the retry passed) |

`python -m ruff check .`: all checks passed. `python tools/repo_map.py check`: map is current (298 nodes). The other lane's commit `bfe9fea` carried a `docs/repo-map.json` already hashed from this rebuild's code; `update` after this handoff refreshed only this file's hash, and `docs/repo-map.json` is staged with it. The whole suite was not run.

## Review 3 (Opus, 2026-10-13)

A third review, by an agent that built neither rebuild. It covers the rebuild alone
(`git diff e7c3c3e de34594`) and the build since the base where a trace needed it, against
`pilot/SPEC-form-inputs.md` with sections 14 and 15 overriding. I read the SPEC, this handoff and
the diffs, and no agent transcript. I edited no code or test. Each behaviour claim below was run on
the floor interpreter, either through the named test file or through a throwaway test in the
scratchpad that drives `edit` and `rename` end to end on records written straight into the store.

### Resolved

- **G1 - resolved in effect, for every value the list holds as it holds it.** `_cmd_edit` passes
  `{identifier_key: item_from_record(rule)}`, and `item_from_fields` looks the row up by the typed
  identifier's key. An identifier spelt exactly as held is asked `identifier_problem` only. A short
  name equal to the held one is asked `short_title_problem` only. These were traced end to end:
  - A held `A<NBSP>01` / `W<SHY>X` row saves an edit to its Document.
  - An older window's row that sends only the identifier and the Document also saves, because
    `_as_recorded` refills the held short name, which then equals it.
  - The same list saves with a new clean row added beside the held one.
  - A new row whose short name holds a soft hyphen is refused by the typed rule:
    `Row 3: Short name may not contain an invisible character (U+00AD SOFT HYPHEN)`.

  `capped` is gone from `typed_identifier_problem`, and no caller still passes it. A respelling by
  case alone is treated as a change. That is the SPEC's letter, but see H1.
- **G2 - resolved.** A blank short name, or one equal to the derived name, has
  `derived_short_title(document)` judged for invisible characters: the typed half when the row is
  new or changed, the store's half when it is held unchanged. The refusal names the Document.
  `W-2<U+202E>fdp.exe` and `W-2<U+00AD>Wages` are refused naming the Document, and neither raw
  character is in the sentence. A character past the twenty that the derived name keeps is not
  refused, and that is correct: it reaches no file name.
- **G3 - resolved.** `test_stdin_that_is_not_utf8_...` feeds `\xff\xfe{` and checks `NOT_A_SPEC`
  and an empty error log.
- **G4 - resolved.** P290 now names the stored short name, the derived name, and the store's gate
  not reading the Document. P291 says the typed rules apply to a new or changed value only, and that
  Rename is held to them. Both rows match the code.
- **G5 - resolved.** An issuer row's derived name is refused on the issuer. Through `issuer_item`
  the result is `F02: Issuer Name 'Ashford<U+00AD>Holdings' ... (it is also the short name)`.
  Through the editor, a new row `Schedule K-1 - Ashford<SHY>Holdings` gets
  `Row 3: Issuer Name 'Ashford<U+00AD>Holdings' ...`. `_issuer_entity` is the one reading shared by
  `derived_short_title` and the label.

### The held Document with a right-to-left override

A held row whose Document is `W-2<U+202E>fdp.exe` with a blank short name passes the store: the
gate does not read the Document, and `load_manifest` returns it. Every save of that list is then
refused, including one that only adds an unrelated row:
`Row 1: Document 'W-2<U+202E>fdp.exe' may not contain an invisible character (U+202E RIGHT-TO-LEFT OVERRIDE) (it is also the short name)`.

This is the right outcome, and it is consistent with how F2 treated held identifiers. F2 exempted
only the characters an ordinary paste leaves (no-break space, soft hyphen, byte-order mark). A
spoofing character stays refused even when it is held, and a held identifier holding one is a
refused line that stops the household on every pass. Refusing the save is milder than that. The
sentence names the row, the field, the code point and why, and the way out is in the same save:
retype that Document or give the row a short name. The pass still names the working copies with
the override, because it never calls `item_from_fields`. That is G2's open question, whether the
store's gate should read the Document, and P290 now records that it does not. It stays Jason's
call. It is not a finding against this build.

### The builder's reading on the derived short name - accepted; amend the SPEC

Section 15 says the derived short name "is judged as a short name is". Read literally, that means
the whole `short_title_problem`, and it would refuse ordinary Documents. Verified:
`derived_short_title("Form 1099: Interest")` is `Form 1099: Interest`, and `short_title_problem`
refuses it for the colon. The rest of the rule has no work to do on a derived name:
- `_cut_short` already cuts the length and strips a trailing dot or space (`Misc.` derives `Misc`).
- `filer._parts_of` turns an illegal character into a hyphen where the name is used.
- A device name cannot occur, because the identifier always comes first (`A01 - CON.pdf`).

The invisible character is the one part that would reach a file name unchanged. That is what G2
asked for. **Section 15 should be amended rather than the code**, to say: "judged for invisible
characters as a short name is (the derivation already cuts the length and the trailing
separators, and the filer turns an illegal character into a hyphen, so the rest of the short-name
rule does not apply to it)".

### Findings

**H1 - R4/R5 as amended in section 15 (P290, P291): `tracker/manifest.py` `item_from_fields` (the
`identifier == held.identifier` test), with `tracker/filer.py` `rename_request` (`RENAME_CASE_ONLY`)
- should fix (Jason's call, because it needs one word added to section 15).**

Section 15 says an identifier "spelt exactly as recorded" is judged by the store's rule, and the
builder counts a respelling by case alone as new. Elsewhere this repo treats a change of case as
the same request:
- `identifier_key` folds case.
- Decision 160: "a change of case only reads the same everywhere".
- `_refuse_taking_away_documents` keeps a request respelt by case.
- `rename_request` refuses a case-only rename with "change it in the list and save - a change of
  case needs no rename".

Neither typed rule can see a case change. Invisible characters have no case, and the length is
unchanged (barring a handful of exotic letters). So the typed rule on a case respelling re-judges
only what the list already held. The two sentences then contradict each other. Verified end to
end on a held 120-character identifier:
- The editor's case respelling is refused with
  `Row 1: Identifier 'lll...' may have at most 80 characters, got 120 (it begins a file name)`.
- Rename's case respelling is refused with
  `... differ only in case; change it in the list and save - a change of case needs no rename`.

So the case cannot be changed anywhere. The same holds, with a way out the sentence does not name,
for a held `A<NBSP>01` respelt `a<NBSP>01`. Rebuild 1 let a case respelling through, case-folded,
and Review 2 verified that. Rebuild 2 reversed it, and the test claim was reversed with it.

**Fix:** in `item_from_fields`, judge an identifier whose key is held by `identifier_problem`
whenever `held is not None`, so "spelt as recorded, case aside". In
`test_a_held_identifier_past_eighty_characters_is_not_refused_but_a_new_one_is`, put back the
case-folded pass. In `test_a_list_holding_what_an_older_paste_left_stays_editable_...`, change the
refused respelling from `a<NBSP>01` to a different key, such as `B<NBSP>01`. Amend section 15 and
P291 with "case aside". If Jason prefers the letter as built, change `RENAME_CASE_ONLY`'s
instruction instead, so that it does not send a person to a save that will refuse them.

**H2 - R7 (P293): `tracker/filer.py` `RENAME_CASE_ONLY` and `tracker/manifest.py`
`RENAME_NOT_ON_THE_LIST` - nit (it predates this SPEC, and R7 did not list these sites).**
P293 says a refusal quotes at most 80 characters of what was typed. Both rename sentences format
`{old}` / `{new}` whole. Verified: two 120-character identifiers that differ only in case come back
as 240 characters of echo. The case check runs before the typed check, so a 10,000-character `to`
is echoed whole too. **Fix:** `quoted(old)` / `quoted(new)` at the two format sites (`filer`
already imports `quoted`).

**H3 - G5's single source: `tracker/api.py` `ISSUER_LABEL = COL_ISSUER` - nit.** The wording is
single-source by construction. `tests/test_api.py` still pins the page's word as the literal
`"Issuer Name"` (`labels["issuer_label"]`), so the card is unchanged. No test ties the card's word
to the refusal's, though. A later edit that gives `ISSUER_LABEL` its own literal would pass every
test. **Fix:** one line, `assert api.ISSUER_LABEL is manifest.COL_ISSUER`, beside that pin.

### Verified

- Test files run one process each, in parallel, on the floor interpreter, `-p no:cacheprovider`:

  | file | result |
  |---|---|
  | test_api | 517 passed |
  | test_manifest | 110 passed |
  | test_records | 53 passed |
  | test_templates | 41 passed |
  | test_row_columns | 26 passed |
  | test_scaffold | 55 passed |
  | test_filer | 406 passed, 6 skipped |
  | test_layout | 58 passed |
  | test_store | 195 passed, 1 skipped |
  | test_layers | 31 passed |
  | test_single_source | 218 passed |
  | test_repo_map | 82 passed |
  | test_tripwire | 23 passed |
  | test_errors | 82 passed, 1 failed (see below) |

  `test_row_columns` imports `item_from_fields` and was not in section 15's gate. It passes.
- **`test_errors` fails outside this SPEC.** `test_the_error_class_list_is_spelled_once` names
  `registry.py:940`, `runner.py:1368` and `scaffold.py:384`, all from `bfe9fea`
  (SPEC-client-folder-unreadable). This rebuild touches none of them, but the other lane's gate
  must fix it before landing.
- **The map.** `ruff check .` passes. `repo_map.py check` was current at `de34594`, since
  test_repo_map passed against it. While this review ran, the other lane committed `2680406`
  (pilot files only), and `check` now says stale for `pilot/HANDOFF-client-folder.md` and
  `pilot/SPEC-client-folder-unreadable.md`. That is that lane's to refresh.
- **Catalogs.** All 107 `FORM_TEMPLATES` rows still pass `item_from_spec` under the new derived
  check, and none holds an invisible character.
- **Tests not weakened.** The `capped=False` lines left with the parameter. The manifest held-row
  test is rewritten to the mapping, and its case-respelling claim is reversed, deliberately (H1).
  Every new test asserts its whole sentence or its prefix, the absence of the raw character, and
  "nothing written" where it matters. The builder reports each new test failing on the pre-fix
  code.
- **Layers and dead code.** `manifest` takes `invisible_problem` and `spoofing_problem` from
  `records` only, and both are used. No new load-time edge, and test_layers passes. `COL_ISSUER`
  lives in `manifest` because `manifest` cannot import `api`. Ruff finds nothing unused.
- **SPEC sentences.** The refusal is
  `{where}: {label} '{quoted(source)}' {problem} (it is also the short name)`, with
  `label` = `COL_DOCUMENT` or `COL_ISSUER`, as section 15 words it. `source` is the typed field
  (the Document, or the issuer's entity), which is what "the field the person typed" means.
- **Record.** The commit `de34594` carries `Co-Authored-By: Claude Fable 5.1`, while this handoff
  and CLAUDE.md say the rebuild is Opus's. It does not affect the code, but the history says
  otherwise from here on.

Findings: 0 must fix, 1 should fix, 2 nits.

## Rebuild 3 (Sonnet, 2026-10-13)

Built from SPEC section 16 for findings H1-H3. Edited: `tracker/manifest.py`, `tracker/filer.py`,
`tests/test_api.py`, `tests/test_manifest.py`, `tests/test_filer.py`, `pilot/DECISIONS.md`, and this
file. `docs/repo-map.json` regenerated by `repo_map.py update` (no curated change: no behaviour
the curated layer describes moved). No commit made.

### What was built

- **H1.** `manifest.item_from_fields`: `rule = identifier_problem if held is not None else
  typed_identifier_problem`, where `held` is `recorded.get(identifier_key(identifier))`. A held key
  is the store's rule alone whatever its case; only a key the list does not hold gets the typed rule.
  The short name's rule is unchanged. Docstring now says "spelt as the held row spells it, a change
  of case aside" and "a key the list does not hold" (was "spelt exactly as"). Tests:
  `test_manifest.py::test_a_held_identifier_past_eighty_characters_is_not_refused_but_a_new_one_is`
  now passes the case respelling of the held 120-character identifier (and of the held `L...NBSP...L`
  one) and refuses `M*120` and a different-key respelling of the NBSP one;
  `test_api.py::test_a_list_holding_what_an_older_paste_left_stays_editable_and_a_changed_spelling_is_typed`
  refuses `B<NBSP>01` with the typed sentence (nothing written) and saves `a<NBSP>01` (case aside).
  P291 in `pilot/DECISIONS.md` reworded: "sent back as the list holds it, a change of case aside",
  with H1 and decision 160 named.
- **H2.** `filer.RENAME_CASE_ONLY.format(old=quoted(old), new=quoted(new))` and
  `manifest.RENAME_NOT_ON_THE_LIST.format(old=quoted(old))`. New test
  `test_filer.py::test_a_rename_refusal_quotes_at_most_eighty_characters_of_what_was_typed` (both
  sentences, a 10,000-character `old` for the not-on-the-list one, nothing written). No existing
  rename test pinned a sentence that `quoted` changes.
- **H3.** `assert api.ISSUER_LABEL is manifest.COL_ISSUER` beside the `"Issuer Name"` pin in
  `test_api.py` (`manifest` added to its `from tracker import` line). This one passes on the
  pre-fix code too: it is a guard against a future edit, not a behaviour change.
- Section 15's rewording: no code change, as section 16 says.

### Failing before the fix

Run before the code edit: the H1 manifest test (`Row 1: Identifier 'lll...' may have at most 80
characters, got 120`), the H1 api test, and the H2 test each failed; the H3 assertion passed (above).

### Done differently

- Section 16 asks that the H2 sentence be "shorter than 240 characters". Two `quoted` echoes are 80
  characters each and the fixed words add 92, so `RENAME_CASE_ONLY` comes to 252. The test asserts
  `< 260` and that the sentence holds exactly two `...` cuts and never 80 unbroken `L`s (the old
  332-character sentence fails both). Section 16 also says the sentence "ends with the ellipsis":
  it ends with the fixed words, the ellipsis closes each quoted name. The SPEC wording is loose on
  both points; the reviewer may want it tightened.
- SPEC section 15 (lines ~450, ~504) still says "spelt exactly as recorded"; section 16 amends it
  and I did not edit the SPEC.

### Gate (floor interpreter, one process per file, `-p no:cacheprovider`)

| file | result |
|---|---|
| test_api | 517 passed |
| test_manifest | 110 passed |
| test_filer | 407 passed, 6 skipped |
| test_records | 53 passed |
| test_row_columns | 26 passed |
| test_layers | 31 passed |
| test_single_source | 218 passed |
| test_repo_map | 82 passed (after the final `update`) |
| test_errors | 83 passed (the other lane's registry/runner/scaffold fix had landed in the checkout) |

`ruff check .` passes; `repo_map.py update` then `check` says current (298 nodes). Only the office
interpreter's run is not done (one interpreter available in this session).

### For the reviewer

`tracker/manifest.py` (`item_from_fields`, `renamed_rules`), `tracker/filer.py` (`RENAME_CASE_ONLY`
use in `rename_request`), the three test files, P291 in `pilot/DECISIONS.md`.

## Review 4 (Opus, 2026-10-13)

A fourth review, by an agent that built none of the rebuilds. It covers rebuild 3 (`git diff 07e0fda
8da6fe9 -- tracker/ tests/ pilot/DECISIONS.md`; the `households`/`registry`/`runner`/`scaffold`
lines in that range are the client-folder lane's 7df8b93, not this SPEC's) against section 16 as
corrected in 8da6fe9. It also checks that the whole change still meets sections 1-15, with 14-16
overriding. I edited no code or test. Each behaviour claim was run on the floor interpreter
(Python 3.13 venv; `requires-python >=3.11`), either through the named test file or through a
throwaway test in the scratchpad (`r4/test_review4.py`). That test drives `edit` and `rename` end to
end on records written straight into the store.

### Resolved

- **H1 - resolved in effect.** `item_from_fields` now asks `identifier_problem` whenever
  `recorded.get(identifier_key(identifier))` is not `None`. These were traced end to end through
  `edit`:
  - A held `"L" * 120` respelt `"l" * 120` saves, and the list holds one row, `l*120`. An older
    window's row sending only `{"identifier": "L"*120, "document": ...}` saves back to `L*120`.
  - `rename` from `L*120` to `l*120` is still refused with `RENAME_CASE_ONLY`. Its instruction
    ("change it in the list and save") now leads to a save that works, so the contradiction H1
    named is gone.
  - A held `A<NBSP>01` respelt `a<NBSP>01` saves.
  - `B<NBSP>01` is refused with
    `Row 1: Identifier 'B<U+00A0>01' may not contain an invisible character (U+00A0 NO-BREAK SPACE)`,
    and the journal is byte-identical. The same holds as a new row 2 beside the held row
    (`Row 2: ...`).
  - A held identifier with U+202E is still refused by the store's rule. The store will not write
    it: `StoreError: This change carries a rule whose 'identifier' may not contain an invisible
    character (U+202E RIGHT-TO-LEFT OVERRIDE); nothing was written`. Through `item_from_fields`
    with that key held, it is refused in either case as `Row 1: Identifier 'A0<U+202E>1' ...` /
    `'a0<U+202E>1' ...`, and no raw U+202E is in the sentence.

  **The key lookups stay consistent with the fold:**
  - In `_cmd_edit`, `_as_recorded` uses `exact.get(...) or folded.get(key)`, `held_items` is keyed
    by `identifier_key`, and `_short_title` receives the same `held`.
  - `_refuse_taking_away_documents` compares `identifier_key`s.
  - On `_filed_documents`' return, respelling `A01` as `a01` saves. The row count is unchanged,
    `A01` is gone, there is no duplicate key, and `documents_by_request` gives `{'a01': 2, 'c01': 1}`.
  - Sending both `L*120` and `l*120` in one save is refused by `validated` as
    `Duplicate identifier 'lll...' (rows 1 and 2)`, with nothing written.

  The one lookup that does not fold is I2's, and it is harmless here.
- **H2 - resolved.** Both format sites now pass `quoted(...)`:
  - `filer.rename_request`: `RENAME_CASE_ONLY.format(old=quoted(old), new=quoted(new))`.
  - `manifest.renamed_rules`: `RENAME_NOT_ON_THE_LIST.format(old=quoted(old))`.

  Through the API, the 120/120 case sentence is 252 characters, with two `...` cuts.

  The new `test_a_rename_refusal_quotes_at_most_eighty_characters_of_what_was_typed` asserts what
  corrected section 16 says:
  - The whole sentence equals the `quoted` format, and it is `< 260`.
  - It has exactly two `...` cuts, `L*77 + "..."` is present, and `L*80` is absent.
  - A 10,000-character `old` through `RENAME_NOT_ON_THE_LIST` equals its `quoted` format and is
    `< 240`.
  - Nothing is written: neither files nor journal lines change.

  Mutation checks were run on a scratch copy of the tree at 8da6fe9:
  - With 07e0fda's `filer.py`/`manifest.py`, all three new or changed claims fail: this test, the
    manifest H1 test and the api H1 test.
  - With only the `RENAME_NOT_ON_THE_LIST` site reverted, this test still fails, so both sites are
    load-bearing.

  No existing rename test was edited, and every rename test in `test_filer` and `test_api` passes
  unchanged.
- **H3 - resolved.** `assert api.ISSUER_LABEL is manifest.COL_ISSUER` is the line directly after
  `assert labels["issuer_label"] == "Issuer Name"` (`tests/test_api.py:8460`). It is a guard, and it
  passes on the pre-fix code too, as the handoff says.
- **The test changes follow the SPEC.**
  - In `test_manifest`, the case-respelling claim is reversed back, as section 16 directs. The
    lowered NBSP identifier now passes, and a different-key NBSP identifier (`hidden.replace("L",
    "M")`) is refused, so the refusal claim survives on a new key.
  - In `test_api`, the refused respelling is `B<NBSP>01`, as directed, and a passing `a<NBSP>01`
    was added.
  - No other claim was weakened.
- **Sections 14-16 elsewhere: still built.**
  - `layout.spoofing_problem` and `invisible_problem` exist.
  - `records.typed_short_title_problem` exists, and `typed_identifier_problem` has no `capped`.
  - `templates` quotes its identifier with `quoted`.
  - `_read_spec` catches `UnicodeDecodeError`.
  - `ADMISSION_VERSION = 4`.
  - The derived short name is judged for invisible characters only, which is section 16's rewording.

  The other rename sentences that format `old` raw (`RENAME_COPY_MOVED`, `_MISSING`, `_CHANGED`,
  `RENAME_UNFINISHED`) echo the identifier the list holds, not what was typed. By then `new` has
  passed the 80-character cap. So P293 ("what was typed") does not reach them, and R7 is not built
  differently there.
- **Dead code and layers.** No new import in `tracker/`: `filer` and `manifest` already imported
  `quoted`. `tests/test_api.py` adds `manifest` to its `from tracker import` line, and it is used.
  Ruff is clean, and `test_layers` passes.

### Findings

**I1 - `pilot/DECISIONS.md` P291 - should fix (wording only).** P291 now reads "an identifier or
short name sent back as the list holds it, a change of case aside, is judged by the store's rule
alone". Grammatically, "a change of case aside" covers the short name too. The code does not apply
it to the short name, and neither does section 16 ("The short name's rule is unchanged (equal to the
held one, or new)"). `_short_title` compares `text == held.short_title`, which is case-sensitive.
Verified end to end: a held row `A<NBSP>01` / `W<SHY>X` whose short name is respelt `w<SHY>x` (with
or without the identifier's case changed too) is refused with
`Row 1: Short name may not contain an invisible character (U+00AD SOFT HYPHEN)`.

**Fix:** reword P291 so that the case clause attaches to the identifier alone. For example: "an
identifier sent back as the list holds it (a change of case aside), or a short name sent back
exactly as held, is judged by the store's rule alone". No code change is needed.

**I2 - `tracker/api.py` `_refuse_a_changed_row_past_the_limit` - nit (read from the code).**
`stored` is keyed by the exact identifier, so a case-only respelling is measured as a changed row,
while the same row sent back as held is not measured. This predates this SPEC (decision 131), and a
clean `A01` to `a01` was always measured. H1 only lets a held long or NBSP identifier reach the check
now. It is harmless while the row has room: the respelling is the same length, and the scratch
`l*120` edit saved. A held row already past what Windows opens, though, would be refused a change of
case with the "shorten the folder" sentence, which is V5's complaint.

**Fix (if wanted):** key `stored` by `identifier_key`, so that a case-only change is measured only
when another path field moved. Otherwise, leave it as it is and record that it is deliberate.

**I3 - tests - nit.** No committed test pins H1's two sentences together. The H1 contradiction was
"rename says go to the editor, the editor refuses". The manifest test covers `item_from_fields`
alone, and the api test covers the NBSP identifier only.

**Fix:** add two steps to `test_a_list_holding_a_long_identifier_stays_editable_and_renames_it_away`:
- `rename` from `L*120` to `l*120` is refused with
  `RENAME_CASE_ONLY.format(old=quoted(...), new=quoted(...))`.
- `edit` with `l*120` saves, and the list holds `["l"*120]`.

The scratch test does exactly this, and it passes.

**I4 - the record - nit.** Rebuild 3's "Done differently" presents section 16's "240" and "ends with
the ellipsis" as still open ("the reviewer may want it tightened"), and it says "I did not edit the
SPEC". The same commit, 8da6fe9, carries section 16 already corrected to "260", with "the builder's
reading is the right one". So the build's own commit amended the SPEC that judges it, and the handoff
does not say so or say who did. Also, the `Co-Authored-By: Claude Fable 5.1` trailer that Review 3
flagged is on 8da6fe9 (and 7df8b93), while this handoff says "Rebuild 3 (Sonnet ...)" and CLAUDE.md
names Opus 5.5.

### Gate (floor interpreter, one process per file, in parallel, `-p no:cacheprovider`, at 8da6fe9)

| file | result |
|---|---|
| test_api | 517 passed |
| test_manifest | 110 passed |
| test_filer | 407 passed, 6 skipped |
| test_records | 53 passed |
| test_row_columns | 26 passed |
| test_templates | 41 passed |
| test_errors | 83 passed |
| test_tripwire | 23 passed |
| test_layers | 31 passed |
| test_single_source | 218 passed |
| test_repo_map | 82 passed |

- `python -m ruff check .`: all checks passed.
- `python tools/repo_map.py check`: **stale**, on exactly `pilot/HANDOFF-client-folder.md` and
  `pilot/SPEC-client-folder-unreadable.md`. Both come from the client-folder lane's b558c94
  ("Review 3 of SPEC-client-folder-unreadable"), which landed while this review ran. It touches
  pilot files only, and `tracker/`, `tests/`, `docs/` and `tools/` are unchanged since 8da6fe9. That
  is the other lane's to refresh, not this change's.
- This append makes the map stale on `pilot/HANDOFF-form-inputs.md` too, until whoever commits it
  runs `update`.
- Only the office interpreter's run is not done (one interpreter in this container).

Findings: 0 must fix, 1 should fix, 3 nits.

## Rebuild 4 (Sonnet, 2026-10-13)

Built SPEC section 17: I1 (the P291 wording) and I3 (the test steps). I2 and I4
are not built, as section 17 says. No code under `tracker/` changed.

**I1 - `pilot/DECISIONS.md` P291.** One line, same columns, no other row touched.
The clause that changed:

- Before: "an identifier or short name sent back as the list holds it, a change of
  case aside, is judged by the store's rule alone (the reviews' F1, G1, H1: a
  change of case is the same request, decision 160)."
- After: "an identifier sent back as the list holds it, a change of case aside, and
  a short name sent back as the list holds it, are judged by the store's rule
  alone (the reviews' F1, G1, H1, I1: a change of case is the same request for an
  identifier, decision 160, which a short name has no key for)."

**I3 - `tests/test_api.py`
`test_a_list_holding_a_long_identifier_stays_editable_and_renames_it_away`.**
Two steps, placed after the cap's rename refusal and before the rename to `B01`:

1. `rename` of the held `"L" * 120` to `"l" * 120` is refused, and the error is
   exactly `RENAME_CASE_ONLY.format(old=layout.quoted(...), new=layout.quoted(...))`
   (imported inside the test from `tracker.filer`). The ledger file is
   byte-identical before and after, so nothing was written.
2. The editor's case-only respelling (`edit` with the row's identifier lowered)
   saves with code 0, and the list reads back as `["l" * 120]`. The held name is
   then the lowercase one, so the existing rename-away to `B01` that follows now
   renames `l*120`.

Before/after: the test passed before the edit (1 passed) and passes after it
(1 passed). That is expected: the steps pin behaviour that already held (Review 4
ran the same two steps in a scratch test). I did not mutate the code to see them
fail.

**Gate** (floor interpreter, each file its own process, in parallel,
`-p no:cacheprovider`): `test_api` 517 passed; `test_single_source` 218 passed;
`test_repo_map` 82 passed on the second run. The first run failed
`test_the_committed_map_is_current` only because the map was stale against my two
edits; after `tools/repo_map.py update` (changed: `pilot/DECISIONS.md`,
`tests/test_api.py`; `docs/repo-map.json` regenerated) it passes. It did not fail
on `HANDOFF-client-folder.md`. `python -m ruff check .` clean;
`tools/repo_map.py check` reports the map current (298 nodes).

## Review 5 (Opus, 2026-10-13)

A fifth review, by an agent that built none of the rebuilds. It is narrow: rebuild 4 (5aead97,
`git diff ed109f1 5aead97 -- pilot/DECISIONS.md tests/test_api.py`) against section 17. I edited no
code or test. The P296 row in the same commit belongs to the client-folder lane. I checked only that
it is one well-formed row: one line, six `|` fields like its neighbours.

### Resolved

- **I1 - resolved.** P291 now reads "an identifier sent back as the list holds it, a change of case
  aside, and a short name sent back as the list holds it, are judged by the store's rule alone".
  This is what `manifest.item_from_fields` does:
  - The identifier's rule is chosen by `recorded.get(identifier_key(identifier))`. A held key gets
    `identifier_problem`, whatever its case.
  - `_short_title` takes the store's rule only when `text == held.short_title`, a case-sensitive
    comparison.
  - The row is still one line with the table's six fields, and no other row changed.
  - No test pins decision-row text. `grep -rn P291 tests/` finds docstrings only, and no test reads
    `pilot/DECISIONS.md` (the only mention of it is a docstring in `test_pilot_installer.py`).
  - The `item_from_fields` and `_short_title` docstrings already say the same thing as the row.
- **I3 - resolved.** The two steps sit between the cap's rename refusal and the rename to `B01`:
  - Step 1: `rename` from `L*120` to `l*120` returns code 1. The error is exactly
    `RENAME_CASE_ONLY.format(old=layout.quoted(...), new=layout.quoted(...))`, and the journal is
    byte-identical.
  - Step 2: `edit` with the row's identifier lowered returns code 0. The list reads back as
    `["l"*120]`.
  - The later rename-away now starts from `l*120`. That is the same claim (a held long identifier
    can be renamed away), so it is not weakened.
- **I2 and I4:** not built, as section 17 records. Nothing further to check.
- **Scope:** 5aead97 touches only `pilot/DECISIONS.md`, `tests/test_api.py`,
  `pilot/HANDOFF-form-inputs.md` and `docs/repo-map.json`. The map change is three hash and
  line-count updates plus `reused`. Nothing under `tracker/` changed, and no existing assertion was
  removed or loosened.

### Verified, and how

All runs used the floor interpreter (scratchpad venv) on `git archive` copies of 5aead97 in
`scratchpad/r5/`.

- **Throwaway test (`r5/base/tests/test_review5.py`, 2 passed).** It drives `edit` end to end on
  records written straight into the store.
  - Held `A<NBSP>01` / `W<SHY>X`, short name respelt `w<SHY>x`, with the identifier as held and with
    it respelt `a<NBSP>01`: each is refused with exactly
    `Row 1: Short name may not contain an invisible character (U+00AD SOFT HYPHEN)`, and the journal
    is byte-identical.
  - The same row with only the identifier respelt `a<NBSP>01` saves. The list holds
    `(a<NBSP>01, W<SHY>X)`.
  - Held `L*120` respelt `l*120` saves.
- **Mutation, step 1 (`r5/m1`).** In `filer.rename_request`, the case-only test was changed from
  `identifier_key(old) == identifier_key(new)` to `old == new`.
  - The test fails at the step-1 sentence assertion: the 80-character cap refuses instead.
  - `code == 1` alone would still have passed. The exact-sentence assertion is what makes the step
    load-bearing.
- **Mutation, step 2 (`r5/m2`).** In `item_from_fields`, the store's rule was given only when
  `held.identifier == identifier`, so a held key is judged again by case. The test fails at step 2's
  `assert code == 0`: `Row 1: Identifier 'lll...' may have at most 80 characters, got 120`.

### Gate (floor interpreter, one process per file, in parallel, `-p no:cacheprovider`)

The gate ran on a local clone checked out at 5aead97 (`scratchpad/r5/clone`). The shared checkout
moved during the review: the client-folder lane committed 6a4ac16 and has uncommitted edits to
`tracker/households.py` and `tests/test_registry.py`.

| file | result |
|---|---|
| test_api | 517 passed |
| test_single_source | 218 passed |
| test_repo_map | 82 passed |

- `python -m ruff check .`: all checks passed.
- `python tools/repo_map.py check`: current (298 nodes).
- In the shared checkout, the first run's `test_the_committed_map_is_current` failed on exactly
  `pilot/HANDOFF-client-folder.md`, which that lane was appending to at the time.
- Afterwards, `check` there is stale on `tests/test_registry.py`, from that lane's uncommitted
  edits. Both belong to that lane, not this change. Nothing was fixed.
- This append makes the map stale on `pilot/HANDOFF-form-inputs.md` until whoever commits it runs
  `update`.
- The office interpreter's run was not done (there is one interpreter in this container).

No findings.

## Closed (2026-10-13)

The loop closed at commit `567d5b2` (Review 5: no findings). Code for
SPEC-form-inputs sections 1-17 is on `claude/admiring-goodall-vhomni`; decision
rows P287-P295 are in `pilot/DECISIONS.md`. The converged gate ran on `5aead97`
(the last code change of either lane): nineteen test files one process each,
ruff, the map, all clean - on the Python 3.13 venv only; the 3.11 floor was
not run in this container (no pytest for it), so the office gate before the
merge covers it.

**Jason's open calls, collected from the SPEC sections and reviews:**
- Section 16's "case aside" ruling: an identifier the list already holds may
  have its case changed in the editor without the typed rules (decision 160).
  Reverse it if the stricter reading is wanted.
- A held Document holding a right-to-left override (U+202E) with a blank
  short name still passes the store's gate, which does not read the Document,
  so the pass writes that character into working-copy names until a save of
  that list is attempted (P290; Review 3). Decide whether the gate should read
  the Document.
- I2 (section 17): `api._refuse_a_changed_row_past_the_limit` counts a
  case-only change as a changed row (decision 131), so a held row already
  past what Windows opens is refused a change of case with the "shorten the
  folder" sentence. Needs a row of its own.
- F7 (Review 1): a person's alternative spellings are unbounded. Not built.
- Before landing on office records: `python -m tracker.store check` (read
  only) against the firm's records, since the store's admission rose to 4 and
  now refuses spoofing characters in a stored identifier or short name; a
  record holding one is a refused line that stops its household.

**Landing:** CLAUDE.md's bulk-landing rule: the tracker lane opens the pull
request as a draft at its turn and marks it ready once.

**Decided by Jason, 2026-10-13:** the store's gate reads the Document. Built
under `pilot/SPEC-document-gate.md` (P301), which amends P290.

## Rebuild 5 (Sonnet, 2026-10-13)

Built SPEC-form-inputs section 19 (F7; decision P304, whose row the landing
session adds). Files: `tracker/api.py`, `tests/test_api.py`, this handoff.

**Built.** In `api._people_from_spec`, after the `is_a_spelling` check and
before the duplicate test, each whitespace-collapsed spelling is held to
`records.text_problem`: `raise ManifestError(f"{PEOPLE_LABEL}: a spelling
{problem}")`. One check serves `create` and `edit-household`'s people (and
the editor's people block). The store's gate is unchanged.

**Tests** (`tests/test_api.py`, beside the P288 name test), each run before
the code change and after:

| test | before | after |
|---|---|---|
| `test_a_typed_spelling_of_1001_characters_is_refused_by_name_and_nothing_is_written` | fails (value saves) | passes |
| `test_a_typed_spelling_with_a_control_character_is_refused_and_nothing_is_written` (a bell, `\x07`: not whitespace, so `split()` leaves it) | fails (value saves) | passes |
| `test_a_typed_spelling_of_exactly_the_text_rule_saves` (two words, 1,000 characters) | passes | passes |
| `test_a_one_word_spelling_is_refused_before_the_text_rule_is_asked` (1,001 x's and `Smith\x07`: `ONE_WORD_SPELLING` first) | passes | passes |

The refusals assert the exact sentence and that the list head and the ledger
bytes are unchanged.

**Gate** (Python 3.13 venv only; each file its own process, in parallel):
`test_api` 526 passed, `test_single_source` 218, `test_layers` 31,
`test_repo_map` 82 (re-run after the final `update`: see below); `ruff check .`
clean. The first `check` failed only on another lane's handoff file
(`pilot/HANDOFF-error-handling-small.md`, appended mid-gate); `update` was run
again and `check` then reported the map current (302 nodes).

## Rebuild 6 (Sonnet, 2026-10-13)

Section 20 (I2, decision P305): the editor's path-room check matches a sent
row to the stored one by the identifier's key. Built together with
SPEC-error-handling-small section 13 (both edit `tests/test_api.py`).

**Built.** In `api._refuse_a_changed_row_past_the_limit`, `stored` is keyed by
`identifier_key(item.identifier)` and each sent item is looked up by the same
key; a row is `changed` when the lookup finds nothing, when its document,
period or file types differ, or when it is newly Asked. `_PATH_FIELDS` loses
`"identifier"` (three fields now, comment says why): the identifier is what the
rows are matched by, so its spelling cannot also be the difference measured
(left in, a case-only respelling would still read as changed). The docstring
says a change of case is the same row (decision 160). Section 19's
`_people_from_spec` check (f55605a) is untouched.

**Tests** (`tests/test_api.py`, after the decision-131 save test, over a shared
helper `_a_held_row_past_the_limit` built on `_a_long_row_return`; each run
before the code change and after, under both `path_setting` parametrizations):

| test | before | after |
|---|---|---|
| `test_a_change_of_case_alone_on_a_held_row_past_the_limit_is_the_same_row_and_is_not_measured` (B01 sent as `b01`) | fails, both settings (`PATH_TOO_LONG`) | passes |
| `test_a_respelt_held_row_past_the_limit_with_its_document_lengthened_is_still_refused` | passes | passes |
| `test_a_new_row_past_the_limit_is_still_refused_beside_a_held_one` | passes | passes |

The two refusals assert creation's sentence and that the ledger bytes are
unchanged. The existing decision-131 save test still passes.

**Gate** (Python 3.13 venv only; each file its own process, in parallel,
`-p no:cacheprovider`):

| Step | Result |
|---|---|
| test_api | 533 passed |
| test_single_source | 218 passed |
| test_layers | 31 passed |
| test_repo_map | 82 passed (an earlier run in the same gate failed `test_the_committed_map_is_current` while the tree held the other lane's uncommitted files; after they were committed and the map was current, it passed) |
| `ruff check .` | all checks passed |
| `repo_map.py update` / `check` | "already current" / current (302 nodes), exit 0 |

**Could not do.** The Python 3.11 floor was not run (one interpreter in the
venv). Process note: one insertion in `tests/test_api.py` (the guard-test
constant, section 13) was made with a read-modify-write script rather than the
Edit tool; the other builder's test was not yet in the file and the diff shows
only my hunks, but the orchestrator should confirm that the other lane's test
is present.

## Review 7 (Opus, 2026-10-13)

Review of SPEC-form-inputs section 19 (f55605a, P304) and sections 20 and 21
(ccdf943, P305), judged against section 21 where it differs from 20. Read on
a fresh `git archive ccdf943` copy (git-initialised), Python 3.13 venv. The
reviewer did not build either change.

**Verdicts.** Section 19: lands; one should fix for Jason's ruling (1), one
nit (2). Sections 20/21: land; one should fix (3), one nit (4). Both builds
do what their SPECs named on every case the SPECs named; the findings are
cases the SPECs did not name. Finding 5 is outside the sections, seen while
tracing, and is not this build's defect.

**What was checked, with evidence.**

- *Section 19 placement and sentence.* `tracker/api.py` `_people_from_spec`:
  `if not is_a_spelling(spelling): raise ManifestError(ONE_WORD_SPELLING)`,
  then `if problem := records.text_problem(spelling): raise
  ManifestError(f"{PEOPLE_LABEL}: a spelling {problem}")`, then `if spelling
  not in spellings` - after the two-word check, before the duplicate test,
  the SPEC's sentence exactly. Its one caller is `_info_from_spec`, reached by
  `edit` (line 3580, the editor's people block), `create` (4213) and
  `rollover` (4605). The store does not re-judge: `records.person_from_json`
  checks the kind, `text_problem(name)` and `is_a_spelling` only, unchanged.
- *Section 19 tests.* Each refusal asserts the exact sentence and
  `(list_head(engagement), ledger.path_for(engagement).read_bytes()) ==
  before`. The 1,001 value is `"J " + "x" * 999` (two words, 1,001); the
  saving value `"J " + "x" * 998` with `assert len(longest) == 1000` and
  `saved.spellings == (longest,)`; the ordering test drives
  `api._people_from_spec` with `"x" * 1001` and `"Smith\x07"` and asserts
  `ONE_WORD_SPELLING`. Mutations on throwaway copies: removing the check
  fails exactly the 1,001 and control-character tests; moving the text rule
  above the one-word check fails exactly the ordering test.
- *`\x07` is the right choice.* `[ch.isspace() for ch in "\x1c\x1d\x1e\x1f"]`
  is `[True, True, True, True]`, `"\x07".isspace()` is `False`, and
  `"Jane\x07 Smith".split()` is `['Jane\x07', 'Smith']`: the builder is right
  that `\x1c`-`\x1f` would be split away before the rule sees them.
- *Section 20/21 code.* `stored = {identifier_key(item.identifier): item ...}`
  and `held = stored.get(identifier_key(item.identifier))`; changed is `held
  is None`, or any of `_PATH_FIELDS` differs, or `item.asked and not
  held.asked` - the old three conditions, rewritten as a loop. `_PATH_FIELDS =
  ("document", "period", "allowed_extensions")` with the comment "bar the
  identifier, which rows are matched by (its key) and whose case is not a
  change (P305)". No new import (`identifier_key` was already imported).
- *A respelling that changes the key cannot escape.* A key the list does not
  hold gives `held is None` and is measured. Matching a renamed row onto
  another stored row's key compares that row's document, period and types,
  and two sent rows of one key are refused by the manifest's duplicate rule.
- *Section 20 tests and mutations.* The three tests pin the SPEC's three
  cases under both `path_setting` parametrizations. Restoring exact keying
  (`stored = {item.identifier: ...}`, `stored.get(item.identifier)`) fails
  exactly
  `test_a_change_of_case_alone_on_a_held_row_past_the_limit_is_the_same_row_and_is_not_measured`
  in both parametrizations; the other two and the decision-131 save test
  `test_saving_a_list_refuses_a_changed_row_whose_path_would_pass_the_limit_and...`
  pass ("2 failed, 6 passed"). Putting `"identifier"` back into
  `_PATH_FIELDS` with key matching kept fails the same two, so section 21's
  change was needed.

**Findings.**

1. **Should fix (Jason's ruling): a spelling the record already holds is
   judged again on every editor save.** The comment says "a stored one is
   not re-judged", which is true of the store's gate only. The editor sends
   the people block with every save (`app/renderer/app.js`
   `engagementFromFields`: `details.people = editorPeople.filter((p) =>
   p.name.trim()).map(personSpec);`), and `person_from_json` admits a
   spelling of any length or with a control character. So a record written
   before P304 keeps such a spelling, and on that return every save,
   row-only edits included, is refused until a person finds and unticks it.
   Probe: a 2,001-character spelling saved with the rule patched out (as the
   old build saved it), then the rows and stored people sent back as the
   editor sends them gave `1 People: a spelling must be one line of text of
   at most 1000 characters, with no control character`. The sentence names
   neither the person nor the spelling, and a `\x07` cannot be seen in the
   box. P290/P291 solved the same case for identifiers: a value sent back as
   it is held gets the store's rule, and only a new or changed one gets the
   typed rule. Options: (a) skip `text_problem` for a spelling the stored
   person already holds; (b) keep the refusal but name the person; (c) accept
   it as is (incidence is near nil) and reword the comment. P288's name check
   has the same shape but cannot meet this case, because the store does
   re-judge names.
2. **Nit: "edit-household's people" (SPEC section 19, Rebuild 5).**
   `_cmd_edit_household` takes no people. Its `members` go through
   `_members_from_spec`, which returns bare names with no spellings. The check
   reaches `create`, the editor's `edit` and `rollover`, which are all the
   paths that take spellings, so coverage is complete. Only the wording is
   wrong.
3. **Should fix (small): one key-preserving respelling changes the path's
   length.** Section 21 and the docstring rest on "`records.identifier_key`,
   which strips and lowers and so cannot change a path's length". The strip
   changes nothing by this point (`text()` and `_cmd_edit` strip, and
   `identifier_problem` refuses a trailing space). The lowering does, for
   exactly one pair: `"İ".lower()` is `"i̇"`, one code point
   becoming two. A scan of every code point grouped by `.lower()` finds that
   pair and no other, counted in code points or UTF-16 units. Both `"İ01"`
   and `"i̇01"` pass `identifier_problem` and `typed_identifier_problem`,
   and `sanitize_component` keeps them at 3 and 4 characters. Probe: a held
   row `İ01` past the limit, respelt `i̇01`, saves at ccdf943 with room need
   going 270 to 271 (limit 260). At 21b9d38 the same save is refused ("would
   be 271 characters, past the 260 Windows allows"). So P305 opened a
   one-character, unmeasured growth for this one letter. It is contrived
   (Turkish dotted capital I retyped with a combining dot), but it makes
   section 21's sentence false. Fix: also count a row as changed when
   `len(item.identifier) != len(held.identifier)`, so a respelling that keeps
   both key and length is a pure case change. The deeper cause is older:
   Python's `.lower()` is wider than the Windows case rule here, so
   `identifier_key` treats two names as one that NTFS would treat as two.
4. **Nit: the case-only test asserts only `code == 0`.** Both mutations make
   it fail, so it does test the mechanism. It would read stronger if it also
   checked that the respelling took (`b01` recorded) and that the ledger
   otherwise holds what was sent.
5. **Outside the sections, seen while tracing (should fix, separate SPEC;
   pre-existing, not this build's defect).** The rewritten `_PATH_FIELDS`
   comment says these are "the things a working copy's path is made of, bar
   the identifier". That is not so. Since decision 144 the copy is named by
   `item.short_name` (`short_title or derived_short_title(document)`,
   `filer._parts_of`), and `short_title` is not compared. The old comment
   ("the four things") had the same error. Two probes give the same result
   at 21b9d38 and at ccdf943:
   - Lengthening a held row's short title to 20 characters takes A01's need
     from 253 to 270 (limit 260), and the save succeeds unmeasured.
   - Setting A01 Not Applicable with a 20-character short title, then
     clearing Not Applicable in a second save, succeeds; A01's need ends at
     270 against 260. Decision 142's reason for measuring a newly Asked row
     ("it is now a request creation would have measured") applies just as
     much to a row taken off Not Applicable.

**Gate** (on the ccdf943 copy; each file its own process, in parallel,
`-p no:cacheprovider -q`; Python 3.13.16 venv):

| Step | Result |
|---|---|
| tests/test_api.py | 533 passed |
| tests/test_errors.py | 85 passed |
| tests/test_single_source.py | 218 passed |
| tests/test_layers.py | 31 passed |
| tests/test_repo_map.py | 82 passed |
| tests/test_tripwire.py | 23 passed |
| `ruff check .` | All checks passed |
| `tools/repo_map.py check` | Map is current (302 nodes), exit 0 |
| Python 3.11 floor | not run (no pytest for it here) |

**Hygiene.** No new import or layer change. No print, and no `str(exc)` in
`tracker/`; the one new `str(raised.value)` is a test asserting the
sentence, and `test_errors` passes. ruff is clean, so no dead code. Under
`tracker/` the two commits touch `api.py` only. f55605a also carries
`pilot/SPEC-client-folder-unreadable.md` section 18, which its commit
message attributes to the landing session. ccdf943 carries this SPEC's
section 21. The other lane's
`test_rollover_refuses_a_legacy_return_with_the_legacy_sentence_and_writes_nothing`
is byte-identical at 4dca3fb and ccdf943 (AST source segment compared), and
`git diff 4dca3fb ccdf943 -- tests/test_api.py` shows 71 insertions and 2
deletions: the two replaced lines of the guard test.

## Rebuild 7 (Sonnet, 2026-10-13)

Sections 22 (F3 and nits), 23 (P306) and 24 (P307), built on 19c6a92 together
with SPEC-error-handling-small section 14 (all edit `tracker/api.py` and
`tests/test_api.py`). Every edit was made with the Edit tool; no script
rewrote a file. No import added: `Override` and `PERSON_KIND_LABELS` were
already imported at load time.

**Built** (`tracker/api.py`).
- Section 22: in `_refuse_a_changed_row_past_the_limit` a matched row also
  counts as changed when `len(item.identifier) != len(held.identifier)`, with
  a comment naming the one pair (`"İ".lower()` is two code points); the
  docstring says so.
- Section 23: the name's refusal is `f"{PEOPLE_LABEL}: the
  {PERSON_KIND_LABELS[kind]}'s name {problem}"` and the spelling's `f"{PEOPLE_LABEL}:
  a spelling of {name} {problem}"`. The comment "a stored one is not
  re-judged" is replaced: the check runs on every save, stored values
  included, so the refusal names the person (P306). `ONE_WORD_SPELLING` is
  untouched.
- Section 24: `_PATH_FIELDS` is `("document", "short_title", "period",
  "allowed_extensions")` (comment: the short name a copy is named by is the
  short title or the Document's derivation); a matched row also counts as
  changed when `held.manual_override == Override.NOT_APPLICABLE and
  item.manual_override != Override.NOT_APPLICABLE`; the docstring names the
  short title and the cleared Not Applicable.

**Tests** (`tests/test_api.py`). Each was run before the code change and
after. `_a_long_row_return` and `_a_held_row_past_the_limit` gained an
optional `second` identifier (default `"B01"`, so every existing caller is
unchanged) for the `İ01` fixture. Path tests run under both `path_setting`
parametrizations.

| test | before | after |
|---|---|---|
| `test_a_change_of_case_alone_on_a_held_row_past_the_limit_is_the_same_row_and_is_not_measured` (nit 4: also asserts the record holds `["A01", "b01"]`) | passes, both settings | passes |
| `test_a_respelling_that_keeps_the_key_but_changes_the_length_is_measured_and_refused` (new; held `İ01` sent as `i` + U+0307 + `01`) | fails, both settings (saved: `removed İ01, changed i̇01`) | passes |
| `test_lengthening_a_held_rows_short_title_is_measured_and_refused` (new; A01's short title to 20 characters, as long as B01's copy) | fails, both settings (saved) | passes |
| `test_a_row_set_not_applicable_saves_unmeasured_and_is_measured_when_cleared` (new; B01 set Not Applicable saves and the record holds it, then cleared is refused with nothing written) | fails, both settings (the clearing save succeeded) | passes |
| `test_a_held_row_past_the_limit_whose_short_title_is_sent_back_unchanged_saves` (new; B01 sent back as held, A01's Document shortened) | passes, both settings | passes |
| `test_a_persons_name_longer_than_the_text_rule_is_refused_by_name` (asserts "People: the Taxpayer's name must be ...") | fails (old sentence) | passes |
| `test_a_typed_spelling_of_1001_characters_...` and `test_a_typed_spelling_with_a_control_character_...` (via `_SPELLING_REFUSED`, now "People: a spelling of Jane Smith must be ...") | fail (old sentence) | pass |
| `test_a_stored_spelling_past_the_rule_refuses_a_row_only_save_and_names_the_person` (new; a 2,001-character spelling stored through `make_engagement` / `create_engagement`, which does not judge it; a row-only edit sending the people block back as stored) | fails (sentence names no person) | passes; asserts the exact sentence and that `list_head` and the ledger bytes are unchanged |

The unchanged-short-title test passes before the change by design: it pins
that the new comparison does not trap an untouched row (the editor sends the
stored `""` back).

**Mutations** (each on a throwaway copy of the tree in the scratchpad, never
the checkout; the listed tests are all that failed among the 22 selected
path, people and guard tests):

| mutation | failed |
|---|---|
| drop `"short_title"` from `_PATH_FIELDS` | the lengthened-short-title test, both settings |
| drop the Not Applicable clause | the set-then-cleared Not Applicable test, both settings |
| drop the identifier-length clause | the `İ01` respelling test, both settings |
| name refusal back to "a name {problem}" | the name test |
| spelling refusal back to "a spelling {problem}" | the 1,001-character, control-character and stored-spelling tests |

**Gate** (Python 3.13 venv only; each file its own process, in parallel,
`-p no:cacheprovider -q`, on the working tree at 19c6a92 plus this change;
the tree also holds the reviewer's uncommitted append to
`pilot/HANDOFF-client-folder.md`):

| Step | Result |
|---|---|
| tests/test_api.py | 542 passed (533 + 9: four new tests twice under `path_setting`, one new people test) |
| tests/test_errors.py | 85 passed |
| tests/test_tripwire.py | 23 passed |
| tests/test_single_source.py | 218 passed |
| tests/test_layers.py | 31 passed |
| tests/test_repo_map.py | 82 passed after `update` (81 passed and `test_the_committed_map_is_current` failed in the parallel run, which began before the map was refreshed, as the stale map predicted) |
| `ruff check .` | All checks passed |
| `repo_map.py update` / `check` | updated (`docs/repo-map.json` only; it also took up the already-committed `pilot/DECISIONS.md` rows) / "Map is current (302 nodes)", exit 0 |

**Could not do.** The Python 3.11 floor was not run (one interpreter in the
venv).
