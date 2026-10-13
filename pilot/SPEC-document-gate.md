# The store's gate reads the Document - SPEC

Status: written 2026-10-13 for a separate builder and a separate reviewer.
Decision **P301** (`pilot/DECISIONS.md`; the row is added by the session
that lands this, not by the builder), amending **P290**. Source: Jason's
ruling of 2026-10-13 on the question `pilot/SPEC-form-inputs.md` section 15
and its Review 3 left open ("read document"). The store's admission rises
from 4 to 5.

**Not in this SPEC:** E2 to E7 of the error-handling audit
(`pilot/SPEC-error-handling-small.md`), built in parallel by another builder
in the same checkout. This build touches none of its files.

**Hard rules kept.** No generative AI reads a client document. The gate
refuses only the spoofing characters P290 names (bidirectional controls and
zero-width characters, `layout.spoofing_problem`), never a no-break space or
a soft hyphen, so a household stops only on a character that can disguise a
file name. No layer moves: `records` keeps importing `layout`'s rule, `store`
reaches the Document through `records.rule_row_fault` as it reaches every
other field.

## What staff will notice (plain English)

A request whose Document title carries a right-to-left override or a
zero-width character is refused when the list is saved, whether the row is
new or old, and a record already holding one is a refused line that stops
the household until the line is repaired - the same as an identifier or a
short name holding one since P290. Nothing else changes.

---

## 1. The gap

P290's gate judges the identifier and the short name. A row with no short
name of its own is named by its Document (`manifest.derived_short_title`),
and an issuer row by the entity its Document names, so a held Document
holding U+202E reaches every working copy's name: the pass never asks
`item_from_fields`, and the gate never reads the Document. The third
form-inputs review confirmed it. Jason ruled the gate reads the Document.

## 2. R1 - the store's rule (`tracker/records.py`)

- `document_problem(document: str) -> str`: `layout.spoofing_problem(document) or ""`,
  beside `identifier_problem` and `short_title_problem`, with the same
  docstring form (why only spoofing characters; that this is the store's
  gate). The whole Document is judged, not the derived cut: the issuer
  entity is a substring of it, and a spoofing character anywhere in a
  Document title is never legitimate.
- `rule_row_fault`: after the `_RULE_TEXT` loop, `if given("document"):
  checks.append(("document", document_problem(row["document"])))`, so a
  refused line is named by its field as the others are.
- `tracker/store.py`: `ADMISSION_VERSION = 5`, with the comment line that
  records what 5 refuses. `tests/test_store.py` pins the sources of every
  function the admission reaches to the version (near line 3679) and names
  which pin to move; the builder moves exactly those.

## 3. R2 - the editor says it by row (`tracker/manifest.py`)

`item_from_fields` applies `records.document_problem` to every row's
Document, typed and held alike (it is the store's rule, so a held value is
judged by it as held identifiers and short names are since section 15 of
SPEC-form-inputs); the refusal is
`f"{where}: {COL_DOCUMENT} '{quoted(document)}' {problem}"`. Without this the
gate would refuse the save as `REFUSED_CHANGE` with no row named. The
derived-short-name check (section 15, G2) stays as built; where both would
fire on the same character, the Document's own refusal comes first and the
test asserts that one.

## 4. R3 - the catalog and the records

- All `FORM_TEMPLATES` rows pass `templates.item_from_spec` (a test already
  walks them; it must still pass; none holds a spoofing character).
- `SPEC-form-inputs.md` gets a one-paragraph **section 18** pointing here:
  P290's "the store's gate itself does not read the Document" is reversed by
  P301. The builder appends it.
- `docs/runbook.md`: nothing, unless a sentence there names what the gate
  refuses; then the Document is added to it by exact find-and-replace. The
  builder says which in the handoff.

## 5. Tests

- `tests/test_records.py`: `document_problem` refuses U+202E and U+200B by
  code point with the spoofing sentence, accepts a no-break space and a
  soft hyphen, and `rule_row_fault` names `document` for a row holding one.
- `tests/test_store.py`: a record line whose Document holds U+202E is a
  refused line (`MALFORMED_LINE`, the field named) on sync, and a record
  admitted under version 4 is judged again under 5 (the existing
  re-admission test pattern); the admission-source pins moved.
- `tests/test_manifest.py`: a held row whose Document holds U+202E and whose
  short name is blank is refused on save naming the row and the Document,
  through `item_from_fields` with `recorded` holding the row; a new row the
  same; a Document holding only a no-break space saves.
- `tests/test_api.py`: one end-to-end `edit` of a record written into the
  store with such a Document is refused with the Row N sentence and nothing
  written. Added near the section-15 tests; the file is not rewritten whole
  (the other lane adds its own tests elsewhere in it).

## 6. Files

Code: `tracker/records.py`, `tracker/store.py`, `tracker/manifest.py`.
Docs: `pilot/SPEC-form-inputs.md` (section 18). Tests:
`tests/test_records.py`, `tests/test_store.py`, `tests/test_manifest.py`,
`tests/test_api.py`. Then `python tools/repo_map.py update`. **Not**
`pilot/DECISIONS.md`, not `docs/runbook.md` unless section 4 applies, and
not any file the other lane owns (`tracker/{rollover,api,filer,settings,errors}.py`
and `tests/test_{rollover,filer,settings,errors}.py`).

## 7. The gate

Dead code first. Then one process per file, in parallel: `test_records`,
`test_store`, `test_manifest`, `test_templates`, `test_row_columns`,
`test_api`, `test_filer` (it names working copies from the derived short
name), `test_layers`, `test_single_source`, `test_repo_map`. Then
`python -m ruff check .` and `python tools/repo_map.py check`. Another build
runs in the same checkout; if the map check or `test_repo_map` fails only on
its half-edited files, run `update` again and retry once, and say so.

## 8. Handoff

`pilot/HANDOFF-document-gate.md`: what was built against R1-R3, the gate's
counts, anything done differently and why, and the reminder that Jason's
pre-landing `python -m tracker.store check` (read only) on the office records
now covers admission 5 as well as 4.

## 9. Decision row (added by the landing session)

| P301 | 2026-10-13 | The store's gate reads the Document: a request's Document title holding a spoofing character is refused where it is typed (named by row and field) and is a refused line where it is stored (`records.document_problem`); the admission rises to 5. Amends P290, whose gate did not read the Document, so a held Document named working copies with such a character (SPEC-document-gate). | Jason, 2026-10-13, on the question SPEC-form-inputs' third review left open. |

---

## 10. Amendments after the first review (Opus, 2026-10-13)

Findings F1-F5 are in `pilot/HANDOFF-document-gate.md` under "Review". None
survived a rebuild, so the rebuild is Sonnet's. F1, F2, F4 and F5 are built;
F3 is the landing session's.

**R2, amended (F1).** The Document refusal in `manifest.item_from_fields` is
labelled as `_short_title`'s derived-name refusal is: `COL_DOCUMENT` for a
document row and `COL_ISSUER` with the issuer's entity for an issuer row
(`_issuer_entity(document)` non-empty), so the add-issuer card's refusal
names the one box the person sees -
`f"{where}: {COL_ISSUER} '{quoted(entity)}' {problem}"`. Test
(`tests/test_manifest.py`, and through `issuer_item` if that is how the card
reaches it): a K-1 issuer name holding U+202E is refused naming `Issuer Name`
and the entity, never the whole Document. SPEC-form-inputs section 18's
"sections 14 to 17 otherwise stand" is then true again.

**Docs (F2).** The handoff's reminder and the API test's docstring say a
household stopped by a spoofed stored Document is repaired as any refused
line is - the runbook's malformed-line repair (its section 9; the SPEC first
said 6), as for a spoofed
identifier since P290 - not by retyping the Document in the editor, whose
`state` call the same refused line refuses. The handoff section
"Reminder for Jason" is corrected in place.

**Dead code (F4).** The held-row arm of `_short_title`'s derived-name check
cannot fire now that the Document is judged first; remove it, keep the typed
arm, and say in the docstring why the held case is covered by the Document's
own check.

**Docstring (F5).** `layout.spoofing_problem`'s docstring says the narrow
rule spares a byte-order mark; the code refuses U+FEFF and always has. The
docstring says what the code does. No behaviour change; `layout.py` is
touched for that line only.

**Landing (F3).** The map is refreshed on the combined tree by whichever
commit lands second; the landing session runs `update` and `check` again
before the final push.

Gate after the rebuild: `test_manifest`, `test_api`, `test_layout`,
`test_templates`, `test_layers`, `test_single_source`, `test_repo_map`,
ruff, the map check. The builder appends
`## Rebuild 1 (Sonnet, 2026-10-13)` to the handoff.
