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

---

## 14. Amendments after the first review (Opus, 2026-10-13)

The review's findings F1-F12 are in `pilot/HANDOFF-form-inputs.md` under
"Review (Opus, 2026-10-13)". These amendments change what R4, R5 and R7
say; the builder fixes every finding against the SPEC as amended here. F7 is
not built (raised with Jason as a later row: a person's spellings are still
unbounded). Everything else is.

**R4, amended (F2).** The store's gate must not refuse what an ordinary paste
produces. `layout.is_invisible` catches the no-break space, the soft hyphen
and the byte-order mark, which a short name or an identifier typed before
this rule may well hold (they were stripped, never folded), and the admission
version 4 judges every old record again at its next sync - a household would
stop on every pass over a space. So two rules:

- `layout.spoofing_problem(text) -> str | None`: refuses only the characters
  that change how a name is *read* - the bidirectional controls (U+061C,
  U+200E, U+200F, U+202A-U+202E, U+2066-U+2069) and the zero-width characters
  (U+200B, U+200C, U+200D, U+2060, U+FEFF) - with the `NAME_INVISIBLE`
  sentence naming the code point. `records.identifier_problem` and
  `records.short_title_problem` (the store's gate, and `validated`) ask this
  one, not `invisible_problem`.
- `layout.invisible_problem(text)` (the full rule, as section 4 wrote it) is
  asked where a person types: `records.typed_identifier_problem` (R5) and a
  new `records.typed_short_title_problem(short_title) -> str` =
  `short_title_problem` then `invisible_problem`. `manifest.item_from_fields`
  calls `typed_short_title_problem` where it calls `short_title_problem`
  today, and `templates.item_from_spec` reaches it through `item_from_fields`.

Tests change to match: the store refuses an identifier holding U+202E and one
holding U+200D; the store **admits** an identifier `A 01` and a short
name `W­X` (one test, named as that claim); the editor refuses all four.
`ADMISSION_VERSION` stays 4 (the gate still refuses more than 3 did).
Decision rows P288 and P290 each end with "The store's admission rises to 4."
(F6). **For Jason:** before this lands at the office, run the new gate
read-only over the real records (`python -m tracker.store check`, or the
runbook's equivalent); if the narrow rule still trips on a real record, say
so and it is widened back to the typed rule, not the other way round.

**R5, amended (F1).** The 80-character cap is a rule for a *new or changed*
identifier, never for one the list already holds:

- `tracker/filer.py` `rename_request` (and `manifest.renamed_rules` if it
  checks the new name): the new identifier is held to
  `records.typed_identifier_problem`, refused with the same
  `Row`-less sentence the editor's would carry
  (`f"{COL_IDENTIFIER} '{quoted(new)}' {problem}"`).
- `manifest.item_from_fields(fields, *, where, recorded=frozenset())`:
  `recorded` is the set of `identifier_key`s the list already holds; the
  typed cap (and only the cap - the invisible rule still applies to every
  row) is skipped for an identifier whose key is in it. `api._cmd_edit`
  passes `{identifier_key(i.identifier) for i in held}`; `create` and
  `templates.item_from_spec` pass nothing. Test: a list holding a
  120-character identifier (written straight into a record by the test) can
  still be edited; a new 81-character row on the same list is refused.

**R7, amended (F3, F4).** `layout.quoted` writes every character
`is_invisible` or a control character names as `<U+XXXX>` (the code point,
four or more upper-case hex digits), *then* cuts to 80. Its docstring says
why: the sentence must never carry the character it refuses, and the
manifest's `!r` used to escape these. `templates.item_from_spec` quotes its
identifier with `quoted` too (F4). Test: the sentence for `W-2‮fdp`
contains `<U+202E>` and no U+202E.

**R6, amended (F5).** The nested `also` loop in `_refuse_a_malformed_line`
passes `written` through, so a refused `also` reads as a change too and ends
with "nothing was written".

**R8, amended (F12).** `_read_spec` catches `UnicodeDecodeError` beside
`json.JSONDecodeError`, same sentence.

**Nits (F8-F11):** the `edit-household` test asserts the whole sentence; the
store test writes `"‮"` as an escape, never the literal; the dead
`log is None or` branch goes; the layers test's docstring says `records`
imports `quoted` from `layout` to re-export it to `manifest`, and why.

The gate after the rebuild: only the test files the fixes touch
(`test_api`, `test_records`, `test_store`, `test_layout`, `test_manifest`,
`test_templates`, `test_filer`, `test_layers`, `test_single_source`,
`test_repo_map`), ruff, the map check. The builder appends
`## Rebuild 1 (Sonnet, 2026-10-13)` to the handoff: each finding, what
changed, the gate's counts.

---

## 15. Amendments after the second review (Opus, 2026-10-13)

Findings G1-G5 are in `pilot/HANDOFF-form-inputs.md` under "Review 2". G1 is
F1 surviving a rebuild, so by Jason's rule the rebuild is Opus's. All five
are built.

**R4 and R5, amended again (G1).** The rule since section 14 - a value the
list already holds is never re-judged by a typing rule - was applied to the
cap alone. It applies to the whole typed rule:

- `manifest.item_from_fields(fields, *, where, recorded=None)`: `recorded`
  is a mapping from `identifier_key` to the `RequestItem` the list holds
  (`api._cmd_edit` passes `{identifier_key(i.identifier): i for i in held}`;
  `create` and `templates.item_from_spec` pass nothing). For a row whose key
  is in it: an identifier spelt exactly as recorded is judged by the store's
  rule alone (`records.identifier_problem`: no cap, spoofing characters
  only); a short name equal to the recorded one likewise
  (`records.short_title_problem`). A value that differs from the recorded
  one is new, and gets the typed rule (`typed_identifier_problem` with the
  cap, `typed_short_title_problem`). `records.typed_identifier_problem`
  loses its `capped` option, since the exemption is now whole.
- Test (`tests/test_api.py`): a record written with identifier
  `"A 01"` and short name `"W­X"` can have its Document edited and
  saved; changing that identifier's spelling to another with a no-break
  space is refused with the typed sentence.

**R4, amended (G2, G5).** The short name a row *derives* when none is typed
(`derived_short_title`: the Document title, or an issuer row's name) becomes
part of every working copy's name, so it is judged as a short name is:
the typed rule when its source field is new or changed by the rules above,
the store's rule when the row is held unchanged. The refusal names the field
the person typed, never "Short name":
`f"{where}: {label} '{quoted(text)}' {problem} (it is also the short name)"`,
where `label` is the Document column's label for a document row and the
issuer column's label for an issuer row (the builder takes both from the
existing `COL_*` constants). Tests: a Document `"W-2‮fdp.exe"` with a
blank short name is refused naming the Document; an issuer name with a soft
hyphen is refused naming the issuer field; the same values on a held,
unchanged row are not refused by the typed rule.

**R8 (G3).** A test pins non-UTF-8 stdin:
`test_stdin_that_is_not_utf8_is_refused_like_a_non_object_and_logs_nothing`.

**Decision rows (G4).** P290 also says a stored short name holding a
spoofing character is a refused line. P291 says the cap and the typed rules
apply to a new or changed value only, never to one the list already holds,
and that Rename is held to them.

The gate after rebuild 2: `test_api`, `test_manifest`, `test_records`,
`test_templates`, `test_filer`, `test_layers`, `test_single_source`,
`test_repo_map`, ruff, the map check. The builder appends
`## Rebuild 2 (Opus, 2026-10-13)` to the handoff.

---

## 16. Amendments after the third review (Opus, 2026-10-13)

Findings H1-H3 are in `pilot/HANDOFF-form-inputs.md` under "Review 3". None
is a finding that survived a rebuild, so the rebuild is Sonnet's. All three
are built, with the wording amendment the review asked for.

**R4 and R5, amended (H1): "spelt as recorded, case aside".** Decision 160
makes a change of case the same request everywhere (`identifier_key` folds
case; `rename` refuses a case-only rename and sends the person to the
editor), and neither typed rule can see a case change. So in
`manifest.item_from_fields`, an identifier whose *key* is held
(`recorded.get(identifier_key(identifier))` is not `None`) is judged by the
store's rule alone, whatever its case; only an identifier whose key the list
does not hold is new and gets the typed rule. Section 15's "spelt exactly as
recorded" reads as "spelt as recorded, case aside" from here. Tests: in
`test_a_held_identifier_past_eighty_characters_is_not_refused_but_a_new_one_is`
the case respelling of the held 120-character identifier saves again (the
claim rebuild 1 made and rebuild 2 reversed); in
`test_a_list_holding_what_an_older_paste_left_stays_editable_...` the refused
respelling becomes a different key (`B<NBSP>01`, not `a<NBSP>01`). The short
name's rule is unchanged (equal to the held one, or new). P291 says "sent back
as the list holds it, a change of case aside".

**R7 (H2).** `filer.RENAME_CASE_ONLY` and `manifest.RENAME_NOT_ON_THE_LIST`
format `quoted(old)` / `quoted(new)`, so a rename refusal echoes at most 80
characters as P293 says. Test: two 120-character identifiers differing only
in case are refused in a sentence shorter than 260 characters (two 80-character
echoes and the fixed words), each quoted name closed by the ellipsis `quoted`
leaves and neither echoed whole; a 10,000-character `old` the same through
`RENAME_NOT_ON_THE_LIST`; wherever the rename tests already pin the whole
sentence, keep them passing. (The first draft of this paragraph said 240 and
"ends with the ellipsis"; the builder's reading is the right one.)

**G5's single source (H3).** `tests/test_api.py`, beside the pin of the
page's `issuer_label` as "Issuer Name": `assert api.ISSUER_LABEL is
manifest.COL_ISSUER`.

**Section 15, reworded (the review's reading of the derived short name).**
The derived short name is "judged for invisible characters as a short name
is": the derivation already cuts the length and the trailing separators, and
the filer turns an illegal character into a hyphen, so the rest of the
short-name rule does not apply to it. The code as built already does this;
no code changes for it.

The gate after rebuild 3: `test_api`, `test_manifest`, `test_filer`,
`test_records`, `test_row_columns`, `test_layers`, `test_single_source`,
`test_repo_map`, `test_errors`, ruff, the map check (`test_errors` has one
failure that belongs to the client-folder lane, named in its SPEC's section
11; it is fixed there, in parallel). The builder appends
`## Rebuild 3 (Sonnet, 2026-10-13)` to the handoff.

---

## 17. Amendments after the fourth review (Opus, 2026-10-13)

Findings I1-I4 are in `pilot/HANDOFF-form-inputs.md` under "Review 4". None
survived a rebuild, so the rebuild is Sonnet's. I1 and I3 are built; I2 and
I4 are recorded here and not built.

**Decision row (I1).** Section 16 worded P291 as "an identifier or short name
sent back as the list holds it, a change of case aside", and that was this
SPEC's slip, not the builder's: "case aside" is the identifier's rule only
(its key folds case, decision 160); a short name has no key, so one changed
by case alone is a new value and gets the typed rule. P291 is reworded so the
"case aside" clause attaches to the identifier alone, with the short name
"sent back as the list holds it". No code changes.

**Test (I3).** `tests/test_api.py`
`test_a_list_holding_a_long_identifier_stays_editable_and_renames_it_away`
gains the two steps that pin section 16's way out of the dead end: Rename of
the held 120-character identifier by case alone is refused with
`RENAME_CASE_ONLY`, and then the editor's case-only respelling of the same
identifier saves.

**Not built (I2, nit).** `api._refuse_a_changed_row_past_the_limit` counts a
case-only change as a changed row (decision 131), so a held row already past
what Windows opens would be refused a change of case with the "shorten the
folder" sentence. It predates this SPEC and needs a row of its own; left for
Jason as a later item.

**Record (I4).** Section 16's "240" was corrected to "260" by the landing
session (this SPEC's author), not the builder, after the builder's handoff
named it. The `Co-Authored-By` trailer on every commit of this branch is the
session's required attribution line and does not name which model built a
rebuild; the handoff does.

The gate after rebuild 4: `test_api`, `test_single_source`, `test_repo_map`,
ruff, the map check (a decision row and one test change touch nothing else).
The builder appends `## Rebuild 4 (Sonnet, 2026-10-13)` to the handoff.

---

## 18. The store's gate reads the Document (P301)

Section 14 and decision P290 say the store's gate itself does not read the
Document, and section 15 left it to Jason whether it should. He ruled that it
does (2026-10-13): `pilot/SPEC-document-gate.md` and decision **P301**
reverse that sentence. `records.document_problem` refuses a spoofing character
in a request's Document (`layout.spoofing_problem`, the same narrow set as an
identifier or a short name), `rule_row_fault` names the field `document`, the
store's admission rises from 4 to 5, and `manifest.item_from_fields` applies
the rule to every row's Document, typed or held, naming the row and the
Document, or the Issuer Name for an issuer row, before the derived-short-name
check of section 15 can say it of the same character. Sections 14 to 17 otherwise stand as written.

---

## 19. F7: a typed spelling is held to the name's rule (Jason, 2026-10-13; decision P304)

Jason's ruling on F7 (Review 1): option 1 - where typed, not at the gate.
A person's spellings are searched on every page as the name is, and
`api._people_from_spec` held each only to `is_a_spelling` (two words or
more): a 10,000-character spelling or one with a control character was
saved and searched every pass. The build is Sonnet's.

**R2, extended.** In `_people_from_spec`, after the two-word check, each
spelling (whitespace-collapsed, as today) is held to `records.text_problem`
with the name's sentence form: `raise ManifestError(f"{PEOPLE_LABEL}: a
spelling {problem}")`. `_people_from_spec` serves both `create` and
`edit-household`'s people, so one check covers both. The store's gate is
unchanged (admission stays 5); a stored spelling is not re-judged.

**Tests** (`tests/test_api.py`, beside the P288 name tests): a 1,001-character
two-word spelling is refused with the sentence and nothing is written; a
spelling with a control character likewise; a 1,000-character two-word
spelling saves; the one-word refusal (`ONE_WORD_SPELLING`) still comes first
for a one-word value.

**Decision row (added by the landing session):**

| P304 | 2026-10-13 | A person's typed spelling is held to the name's rule - one line of at most 1,000 characters, no control character - where it is typed (`api._people_from_spec`); the store's gate does not re-judge stored spellings (SPEC-form-inputs section 19). | F7 of the first form-inputs review: the spellings are searched on every page as the name is and were bounded only to two words. |

Gate: `test_api`, `test_single_source`, `test_layers`, `test_repo_map`,
ruff, the map check. The builder appends `## Rebuild 5 (Sonnet, 2026-10-13)`
to `pilot/HANDOFF-form-inputs.md`.

---

## 20. I2: the path-room check matches rows by the identifier's key (Jason, 2026-10-13; decision P305)

Jason's ruling on I2 (Review 4): option 1. `api._refuse_a_changed_row_past_the_limit`
(decision 131) builds `stored` keyed by the exact identifier, so a respelling
by case alone reads as a new row and is measured; a held row already past
what Windows opens would be refused a change of case with `PATH_TOO_LONG`,
though a case change cannot alter a path's length. Decision 160 makes a
change of case the same request everywhere; section 16 applied that to the
editor's judgment, this applies it to the one check still using exact
spelling. The build is Sonnet's, after section 19's build has handed back
(both edit `tracker/api.py` and `tests/test_api.py`).

**R4, extended.** In `_refuse_a_changed_row_past_the_limit`, `stored` is
keyed by `identifier_key(item.identifier)` and each sent item is looked up
by `identifier_key(item.identifier)`; everything else in the check is
unchanged (a row whose path fields differ, a row newly Asked, and a row the
list does not hold are measured; a row the person did not touch is not). The
docstring says a change of case is the same row (decision 160).

**Tests** (`tests/test_api.py`, beside the decision-131 tests): a list whose
held row's working copy is already past the limit (make the room small the
way the existing 131 tests do) has that row's identifier respelt by case
alone → the save succeeds, nothing is measured for it; the same list with
that row's Document lengthened → refused with `PATH_TOO_LONG` as today; a
new row past the limit → refused as today.

**Decision row (added by the landing session):**

| P305 | 2026-10-13 | The editor's path-room check (decision 131) matches a sent row to the stored one by the identifier's key, so a change of case alone is the same row and is not measured; it had matched by exact spelling (SPEC-form-inputs section 20). | I2 of the fourth form-inputs review: a held row past the limit was refused a change of case with "shorten the folder". |

Gate: `test_api`, `test_single_source`, `test_layers`, `test_repo_map`,
ruff, the map check. The builder appends `## Rebuild 6 (Sonnet, 2026-10-13)`
to `pilot/HANDOFF-form-inputs.md`.

---

## 21. Section 20 as built (2026-10-13)

Section 20 said "everything else in the check is unchanged", which could
not hold: `_PATH_FIELDS` named the identifier among the fields a matched
row is compared on, so a row matched by key and then compared on its exact
identifier still read a change of case as a change. The builder dropped
`"identifier"` from `_PATH_FIELDS`, leaving document, period and file
types, and said why in the comment on the constant. That is the SPEC's
intent: rows are matched by the identifier's key (`records.identifier_key`,
which strips and lowers and so cannot change a path's length), and the
fields compared are the ones a case change does not reach. A respelling
that changes the key is a row the list does not hold and is measured, as
before. The review of section 20 judges the build against this section.

---

## 22. Amendments after the seventh review (Opus, 2026-10-13)

Review 7 found sections 19, 20 and 21 built as written on every case they
name. Three small corrections follow; two larger observations (a stored
spelling past the rule blocks every save of that return; the short title is
not among the fields the path-room check compares) are Jason's calls and
are not built here. The build is Sonnet's, together with
SPEC-error-handling-small section 14 (both edit `tests/test_api.py`).

**F3 - one respelling keeps the key and changes the length.** Section 21
said a change of case cannot alter a path's length. One character can:
`"İ".lower()` is two code points, so a held row `İ01` past the limit,
respelt `i̇01`, kept its key and saved with a path one character longer
than before (the reviewer's probe: 270 to 271 against 260; refused before
section 20). In `_refuse_a_changed_row_past_the_limit`, a matched row also
counts as changed when `len(item.identifier) != len(held.identifier)`, with
a comment naming the one pair. Test: that exact respelling of a held row
past the limit is refused with `PATH_TOO_LONG`; the case-only test keeps
passing.

**Nit 4.** The case-only test also asserts the respelt identifier is what
the record now holds (read the list back and find `b01`), not only that
the save answered 0.

**Nit 2.** Section 19 and Rebuild 5 say the check reaches "edit-household's
people"; edit-household takes `members` (bare names, no spellings). The
check reaches `create`, the editor's `edit` and `rollover`, through
`_info_from_spec`. This section corrects the record; the earlier text
stays as written.

Gate: `test_api`, `test_single_source`, `test_layers`, `test_repo_map`,
ruff, the map check. The builder appends `## Rebuild 7 (Sonnet, 2026-10-13)`
to the handoff (append only).
