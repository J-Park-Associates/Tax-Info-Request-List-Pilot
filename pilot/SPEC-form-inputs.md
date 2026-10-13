# Form inputs - the nine findings of the 2026-10-12 audit - SPEC

Status: written 2026-10-12 for a separate builder and a separate reviewer.
Decisions **P287 to P295** (`pilot/DECISIONS.md`; the builder adds the rows
in section 6). Source of every item: `pilot/AUDIT-2026-10-12-form-inputs.md`
(findings V1 to V9), black-box against commit `60cba18` on
`claude/admiring-goodall-vhomni`. No version number changes.

**Not in this SPEC:** the silent sanitising of a client name into a return
folder's name (the audit's "also seen"), the `exe` extension a request may
accept, and the client README's wording. Those are design questions for
Jason, not errors.

**Hard rules kept.** No generative AI reads a client document. Every value a
person types is still checked in the Python API and the store, never only in
the page; this SPEC adds rules there and changes nothing in the renderer but
one test pin. No layer moves: `records` keeps importing only `layout`'s one
name rule, `settings` keeps importing only `layout` and `fsio`, the API does
the firm-text check itself (section 3, R3).

## What staff will notice (plain English)

- A person's name, the firm's name and the firm's phone are refused when
  they are blank lines, longer than 1,000 characters or hold a control
  character, with the same sentence every other one-line field uses.
- A request identifier or short name that hides an invisible character (a
  right-to-left override, a zero-width joiner) is refused and the character
  is named by its code point, exactly as a household or return name already
  is. An identifier longer than 80 characters is refused as too long, instead
  of being told to shorten the household.
- A change the record will not take is refused as a change ("This change
  carries details whose 'members' must be a list of text; nothing was
  written"), not as a corrupt record on disk.
- A refusal that quotes what was typed quotes at most 80 characters of it.
- In the New household dialog, a members value the page could only ever send
  as a list is read the same way Edit household reads it.

---

## 1. R1 - `members` is parsed one way (P287)

**Root cause.** `tracker/api.py` `_cmd_create` builds
`HouseholdInfo.members` as
`tuple(" ".join(str(m).split()) for m in (spec.get("members") or []) if str(m).strip())`.
A string is iterable, so `"Jane"` becomes four members. `_cmd_edit_household`
splits a string into lines first (`typed.splitlines()`).

**Change.** One helper in `tracker/api.py`, beside `_people_from_spec`:

```python
def _members_from_spec(sent: object) -> tuple[str, ...]:
    """The household's members as the dialog and the editor send them:
    a list of names, or one text with a name per line (the editor's box).
    Anything else is refused by name; each name is whitespace-folded and
    a blank one is dropped."""
```

- `None` or `""` is `()`.
- A `str` is `splitlines()`.
- A `list` or `tuple` is taken as is.
- Anything else (a number, a mapping, `True`) raises
  `ManifestError(f"{MEMBERS_LABEL} must be a list of names")`.
- Each entry is `" ".join(str(one).split())`; empty results are dropped.

Both `_cmd_create` and `_cmd_edit_household` call it and nothing else parses
members. Behaviour for a list and for the editor's text is unchanged.

**Tests** (`tests/test_api.py`):
- `test_create_reads_a_members_string_as_lines_and_never_as_letters`:
  `members="Jane Doe\nJohn Doe"` creates two members; `members=7` is refused
  with `MEMBERS_LABEL must be a list of names`; nothing is written on refusal
  (no household folder).
- `test_create_and_edit_household_parse_members_through_one_helper`: both
  commands, same input, same stored members.

## 2. R2 - a person's name is one line of at most 1,000 characters (P288)

**Root cause.** `api._people_from_spec` folds whitespace and refuses only a
blank name; `records.person_from_json` takes `str(raw.get("name", ""))`
with no bound, and the store's admission asks only `people_from_json`. Every
other name is held to `records.text_problem`.

**Change.**
- `tracker/records.py` `person_from_json`: after `kind` is checked, read
  `name = raw.get("name", "")`; if `text_problem(name)` is non-empty, raise
  `ValueError(f"a person's name {text_problem(name)}")`. A non-string name
  is refused by that same check (it returns `TEXT_BOUNDS` for anything but
  `str`), so the `str()` wrapping goes.
- `tracker/api.py` `_people_from_spec`: after the whitespace fold and the
  blank check, `if (problem := records.text_problem(name)): raise
  ManifestError(f"{PEOPLE_LABEL}: a name {problem}")`. The sentence a person
  sees is therefore "People: a name must be one line of text of at most 1000
  characters, with no control character".
- The store's admission (`store._refuse_a_malformed_line`, the
  `people_from_json` call) needs no change: `ValueError` already becomes
  "carries people this version cannot read". A record written before this
  rule with such a name would now be refused on read; no real record holds
  one (a name over 1,000 characters is not a name), and the audit found the
  gap, not a victim. Say so in the decision row.

**Tests:**
- `tests/test_records.py`
  `test_a_persons_name_is_held_to_the_one_line_text_rule`: 1,001
  characters, a newline, a non-string each raise `ValueError` naming "a
  person's name"; 1,000 characters pass.
- `tests/test_api.py` `test_a_persons_name_longer_than_the_text_rule_is_refused_by_name`:
  `edit` with `engagement.people` naming a 10,000-character taxpayer is
  refused with the sentence above and the record is unchanged (same
  `list_head`).
- `tests/test_store.py`
  `test_a_person_with_an_overlong_name_is_a_line_the_store_refuses`: a
  `rules_changed` line whose `info.people[0].name` is 1,001 characters is
  refused as "carries people this version cannot read".

## 3. R3 - the firm's name and phone are one-line text (P289)

**Root cause.** `settings.set_firm` and `set_firm_phone` go through
`_set_text`, which strips and stores. `_cmd_set_root` passes `str(spec["firm"])`
straight in.

**Change** in `tracker/api.py` `_cmd_set_root` only (the layer table pins
`settings` to `layout` and `fsio`; the API is where a typed value is judged):

```python
for key, label in (("firm", FIRM_NAME_LABEL), ("phone", FIRM_PHONE_LABEL)):
    if spec.get(key) is not None and (problem := records.text_problem(str(spec[key]))):
        raise ManifestError(f"{label} {problem}")
```

placed before `set_clients_root` is called, so a refused firm text writes
nothing, the root included. Blank stays allowed (it clears the value, as
today). `settings.set_firm` / `set_firm_phone` keep their docstring's
"stripped and otherwise as typed"; add one sentence to each: the API holds
the text to the one-line rule before it arrives here.

**Tests** (`tests/test_api.py`):
- `test_the_firms_name_and_phone_are_held_to_the_one_line_text_rule`:
  a 1,001-character firm, a phone with a newline, a firm with a NUL are each
  refused as `Firm Name must be one line ...` / `Firm Phone must be one line
  ...`, and the settings file is unchanged (no root written); a 1,000-character
  firm and a phone with an extension (`555-0100 x12`) are accepted.

## 4. R4 - no invisible character in an identifier or a short name (P290)

**Root cause.** `records.identifier_problem` and `short_title_problem`
refuse `layout.WINDOWS_ILLEGAL_CHARS`, a trailing dot or space and a device
name, but not `layout.is_invisible` characters, which `segment_problem`
refuses for folder names. Both values become part of every working copy's
file name.

**Change.**
- `tracker/layout.py`: a public
  `invisible_problem(text: str) -> str | None` that returns
  `NAME_INVISIBLE.format(character=_character(hidden))` for the first
  invisible character, else `None`. `segment_problem` uses it (one rule,
  worded once; its behaviour and sentence are unchanged).
- `tracker/records.py`: import `invisible_problem` beside `is_reserved_name`
  (the same import line; the layer test's "the record imports that rule and
  nothing else of it" still holds - it is the same rule). `identifier_problem`
  and `short_title_problem` each call it after the illegal-character check and
  return its phrase, so an identifier `W-2‮` is refused with
  "may not contain an invisible character (U+202E RIGHT-TO-LEFT OVERRIDE)".
- Because `identifier_problem` is also the store's gate
  (`records.py`, the rule admission near `BLANK_BOUNDS`), a stored identifier
  with such a character is now a refused line. That is wanted: the audit
  names the right-to-left override as the file-name spoofing trick, and the
  record is untrusted input (decision 187). Say so in the decision row.

**Tests:**
- `tests/test_layout.py` `test_invisible_problem_names_the_first_hidden_character_and_segment_problem_asks_it`.
- `tests/test_records.py`
  `test_an_identifier_or_short_name_with_an_invisible_character_is_refused_by_code_point`:
  the RTL override and the zero-width joiner in each; a plain `W-2` passes.
- `tests/test_api.py` `test_a_short_name_hiding_a_right_to_left_override_is_refused_in_the_editor`
  (through `edit`, sentence begins `Row 1: Short name may not contain an
  invisible character`).

## 5. R5 - an identifier is at most 80 characters, said as such (P291)

**Root cause.** `identifier_problem` has no length rule, so a long identifier
is caught only by `_refuse_a_changed_row_past_the_limit`, whose
`layout.PATH_TOO_LONG` sentence ends "shorten the household or the return
name". In `_cmd_edit` the rows are parsed (`item_from_fields`), then the room
check runs, then `save_rules` → `validated` → `identifier_problem`; so the
room sentence wins.

**Change.**
- `tracker/records.py`: `IDENTIFIER_MAX_CHARS = 80` (the same width as
  `layout.NAME_MAX_CHARS`, for the same reason: it begins every file name) and
  `typed_identifier_problem(identifier: str) -> str` = `identifier_problem`
  then, if longer, `f"may have at most {IDENTIFIER_MAX_CHARS} characters, got {n} (it begins a file name)"`.
  `identifier_problem` itself is unchanged: it is the store's gate and a
  record's identifier is not re-judged by a typing limit.
- `tracker/manifest.py` `item_from_fields`: after the identifier is read and
  found non-blank, `if (problem := typed_identifier_problem(identifier)):
  raise ManifestError(f"{where}: {COL_IDENTIFIER} {quoted(identifier)} {problem}")`
  where `quoted` is R7's helper. This runs before the room check in both
  `edit` and `create`; `validated`'s own check stays as the gate behind it.
- `tracker/templates.py` `item_from_spec` calls `typed_identifier_problem`
  instead of `identifier_problem`.

**Tests:**
- `tests/test_records.py` `test_a_typed_identifier_longer_than_eighty_characters_is_refused_as_too_long`.
- `tests/test_api.py` `test_a_long_identifier_is_refused_as_too_long_and_never_as_a_long_folder_name`:
  `edit` with a 200-character identifier is refused with "Row 1: Identifier
  ... may have at most 80 characters, got 200" and the sentence does not
  contain "shorten the household".
- `tests/test_manifest.py`: `item_from_fields` with an 81-character identifier
  raises with `Row 3` as `where`.

## 6. R6 - a refused change is worded as a change (P292)

**Root cause.** `store.record` admits each new event through
`_refuse_a_malformed_line(json.loads(line), number, path, kind=...)`, whose
`refuse()` always words `MALFORMED_LINE` ("{where}: line {seq} of the record
is malformed ({event} {problem}); the journal is not applied past it"), and
`record` appends "; nothing was written". A typed value outside a store rule
therefore reads as a corrupt journal.

**Change** in `tracker/store.py`:
- `REFUSED_CHANGE = "This change {problem}; nothing was written"` beside
  `MALFORMED_LINE`.
- `_refuse_a_malformed_line(event, seq, where, *, kind=KIND_RETURN, written=True)`:
  `refuse()` raises `StoreError(MALFORMED_LINE...)` when `written` and
  `StoreError(REFUSED_CHANGE.format(problem=problem))` when not. Every other
  caller (`_apply`, `check`, `_judge_the_applied_lines`) is unchanged.
- `record`'s admission loop passes `written=False` and no longer wraps the
  exception (the sentence already ends "nothing was written"); the wrap
  around `_judge_the_applied_lines` stays, since that judges lines on disk.
- The `problem` phrases already read as a clause of "This change ..."
  ("carries details whose 'members' must be a list of text", "carries a row
  whose ...", "names a removed identifier that ..."): no phrase changes.
- `docs/runbook.md` names `MALFORMED_LINE` for the read path only; nothing
  there changes. `tests/test_errors.py` and `tests/test_tripwire.py` run in
  the gate because an error sentence changed.

**Tests** (`tests/test_store.py`):
- `test_a_change_the_store_refuses_is_worded_as_a_change_and_never_as_a_malformed_line`:
  `record()` of a `household_changed` whose `members` is a string raises
  `StoreError` matching `This change carries details whose 'members' must be a
  list of text; nothing was written`, with no "line " and no "malformed" in
  it; the journal has the same line count after.
- `test_a_malformed_line_read_from_disk_keeps_its_line_number_sentence`: the
  existing read-path wording is unchanged (extend an existing test or add one).
- `tests/test_api.py` `test_an_overlong_member_is_refused_as_a_change_not_a_corrupt_record`:
  `edit-household` with a 10,000-character member → the sentence above.

## 7. R7 - a refusal quotes at most 80 characters (P293)

**Root cause.** `layout.NAME_REFUSED` echoes `{typed}` whole; `door.NOT_UNDER_ROOT`
echoes `{path}`; `layout.NOT_A_RETURN` / `NOT_A_HOUSEHOLD` echo `{name}`;
`manifest.validated` echoes `{identifier!r}`.

**Change.**
- `tracker/layout.py`: `QUOTE_MAX_CHARS = 80` and
  `quoted(text: object) -> str`: `str(text)` when at most 80 characters, else
  its first 77 characters + `"..."` (three ASCII dots, so the sentence itself
  never carries a character the rule refuses). Used at both `NAME_REFUSED`
  format sites (`checked_name`, `_named`), and at the `NOT_A_RETURN` /
  `NOT_A_HOUSEHOLD` sites (`return_at`, `household_at`; the `{name}` there is
  `Path(path).name or path`).
- `tracker/door.py`: `NOT_UNDER_ROOT.format(path=layout.quoted(folder), root=root)`.
- `tracker/manifest.py` `validated` and R5's `item_from_fields`: `quoted(identifier)`
  in place of `identifier!r` (keep the surrounding quotes by writing
  `'{quoted(identifier)}'`, so short identifiers read exactly as before).
- The reasons that already state the length (`NAME_TOO_LONG`,
  `typed_identifier_problem`) are untouched, so nothing is lost by the cut.

**Tests:**
- `tests/test_layout.py` `test_quoted_cuts_a_long_value_to_eighty_characters_and_leaves_a_short_one`.
- `tests/test_layout.py`: `checked_name("x" * 10_000, "household")` raises a
  sentence shorter than 200 characters that still ends with
  `NAME_TOO_LONG.format(limit=80, n=10_000)`.
- `tests/test_door.py` `test_a_refused_path_is_quoted_cut`: a 10,000-character
  typed folder's `NOT_UNDER_ROOT` sentence is under 300 characters.
- Existing tests that assert `NAME_REFUSED.format(typed=<short>, ...)` keep
  passing unchanged.

## 8. R8 - stdin that is not JSON is the same refusal as a non-object (P294)

**Root cause.** `api._read_spec` lets `json.JSONDecodeError` escape, so it is
reported as an unexpected error and logged.

**Change.** In `_read_spec`, catch `json.JSONDecodeError` and raise
`ManifestError(NOT_A_SPEC)` (the existing sentence "The app sent something
that is not a JSON object; nothing was changed" covers it; no new constant).

**Test** (`tests/test_api.py`):
`test_stdin_that_is_not_json_is_refused_like_a_non_object_and_logs_nothing`:
`set-schedule` with stdin `not json` exits 1 with `NOT_A_SPEC` and writes no
error log.

## 9. R9 - the signature box's limit is pinned (P295)

**Change** in `tests/test_single_source.py`: assert that
`app/renderer/pilot.js` contains
`name.setAttribute("maxlength", "{api.SIGNED_BY_LONGEST}")` exactly, so the
page-side limit follows the API's constant. No code change.

---

## 10. Decision rows (the builder adds these to `pilot/DECISIONS.md`)

| # | Date | Decision | Why |
|---|------|----------|-----|
| P287 | 2026-10-12 | `members` is parsed by one helper for New household and Edit household: a list, or one text with a name per line; anything else refused by name (SPEC-form-inputs R1). | The audit (V1): create iterated a string as letters. |
| P288 | 2026-10-12 | A person's name is one line of at most 1,000 characters, checked where typed and at the store's gate (R2). A record holding a longer one is refused on read. | V2: the one name with no bound, and the one the matcher searches every page for. |
| P289 | 2026-10-12 | The firm's name and phone are held to the one-line text rule by the API before settings stores them (R3). | V3: stored as typed, including control characters, into every letter. |
| P290 | 2026-10-12 | An identifier and a short name refuse an invisible character by code point, through `layout.invisible_problem`, the same rule folder names use (R4). A stored identifier holding one is a refused line. | V4: a right-to-left override in a file name is the classic spoof. |
| P291 | 2026-10-12 | A typed identifier is at most 80 characters, said as such before the path-room check; the store's gate keeps the unbounded rule (R5). | V5: a long identifier was told to shorten the household. |
| P292 | 2026-10-12 | A change the store's admission refuses is worded "This change ...; nothing was written", never as a malformed line (R6). | V6: a typing mistake read as a corrupt record. |
| P293 | 2026-10-12 | A refusal quotes at most 80 characters of what was typed, through `layout.quoted` (R7). | V7: a 10,000-character echo. |
| P294 | 2026-10-12 | Stdin that is not JSON gets the non-object refusal, logging nothing (R8). | V8. |
| P295 | 2026-10-12 | The signature box's `maxlength` is pinned to `api.SIGNED_BY_LONGEST` by the single-source test (R9). | V9. |

## 11. Files

Code: `tracker/api.py`, `tracker/records.py`, `tracker/layout.py`,
`tracker/door.py`, `tracker/manifest.py`, `tracker/templates.py`,
`tracker/store.py`, `tracker/settings.py` (docstrings only).
Tests: `tests/test_api.py`, `tests/test_records.py`, `tests/test_store.py`,
`tests/test_layout.py`, `tests/test_door.py`, `tests/test_manifest.py`,
`tests/test_single_source.py`.
Logs and maps: `pilot/DECISIONS.md`, then `python tools/repo_map.py update`
(no curated change: no module's role changes).

## 12. The gate the builder runs (CLAUDE.md, decision 207)

Dead code first in every changed file. Then, in parallel, one process per
file: `test_api`, `test_records`, `test_store`, `test_layout`, `test_door`,
`test_manifest`, `test_templates`, `test_settings`, `test_scaffold`,
`test_filer` (prepared names depend on identifiers), `test_names` (imports
`records`), `test_single_source`, `test_layers`, `test_repo_map`,
`test_errors`, `test_tripwire`. Then `python -m ruff check .`,
`python tools/repo_map.py check`. The whole suite is not run; the router and
the readers are untouched.

The cloud container has no office interpreter; the floor interpreter alone
runs here, and the handoff says so.

## 13. Handoff

The builder writes `pilot/HANDOFF-form-inputs.md`: what was built against
each R, the gate's output (file by file, counts), anything left, and the files
the reviewer needs. The reviewer reads the SPEC, the diff and that handoff,
never the builder's transcript, and writes numbered findings against the
SPEC into the same handoff under "Review".
