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
