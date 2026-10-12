# Scans file on their form number, and a bench measures the reader - SPEC

Status: written 2026-10-11 from Jason's approved plan of the same day
(`~/.claude/plans/deep-inventing-fern.md`, "OCR for scans"), recorded as
**P282** and **P283** (`pilot/DECISIONS.md`). **P284** is reserved for the
shipped reader settings the office numbers choose (section 3); it is not
specified here. Built on `claude/ocr-scans`, cut from `main` at `dcb02c3`.

Source: Jason, 2026-10-11 - too many Needs Review items are **Read From Scan
Only**, and the software should get what it needs out of a scan easily. His
two decisions: (1) a scan may file into a request that accepts it on its
looser keywords, **with guards** - decision 50 revised, and said as such;
(2) the measurement runs on the office PC, by a Claude Code session there,
from a tool and a prompt this work ships.

The engine question is settled by the plan and is not reopened here: the
reader stays RapidOCR with PaddleOCR's PP-OCRv6 small models. What changes
is the routing rule for what it reads (Part A) and how its settings are
held and measured (Part B).

**What this changes, in plain words.**

1. **A scan or a photo whose title shows the request's own form number can
   be filed** (P282). Today a scanned 1099-INT, 1099-R, 1099-NEC, 1098-T,
   1095-A or 5498 parks as *Read From Scan Only* however well it was read,
   because the reader's words could file a document only on a request's
   strictest keywords, and most requests have none. After this change, a
   scan files when the top of the page names the form the request asks for
   ("Form 1099-INT"), the page names no other form as itself, exactly one
   request accepts it, and - for a request that needs a name - the name on
   the page is one of the return's people.
   Anything less parks exactly as it does today.
2. **The reader's settings live in one place, and a measuring tool tries
   other settings on the firm's own scans** (P283). Nothing the product
   reads changes in this part. The tool reads a folder of already-sorted
   documents once per setting - sharper rendering, a stricter confidence
   floor, removing a form's box lines before reading, the larger models -
   and writes down, in counts and seconds only, how many landed where a
   person had put them. A Claude Code session at the office runs it from a
   prompt that names every command.
3. Later, and not in this SPEC (P284): the settings the office numbers
   favour become the shipped ones.

**Hard rules kept.** The four standing rules, worded once in
`STANDING_RULES` in `tracker/__init__.py`, hold unchanged and no sentence of
them changes:

- *No generative AI ever reads a client financial document.* The reader is
  the same deterministic OCR engine (decision 169); the new rule reads only
  what the verdicts already recorded (`Evidence`: a row's own keyword, a
  place, a page), never a word of the page. The bench adds no model of any
  other kind and fetches none.
- *Originals are never altered.* De-lining (Part B) works on a copy in
  memory of a page already rendered or decoded; nothing is written.
- *Nothing is guessed.* A document is filed only when exactly one request
  accepts it. Part A adds a filing path, never a looser acceptance: the
  row's own rules - every keyword it asks for, its year - must pass first,
  and the scan then needs *more* than a text layer would (its form number
  in the title). Two requests passing, or one passing beside a looser
  match, parks.
- *Nothing is ever sent.* No new network call: the bench never downloads a
  model (rapidocr's downloader stays replaced by a refusal,
  `ocr._refuse_downloads`), and its report is written to a file a person
  names, outside the repository.

Client data never enters the repository, a test, a commit, a log line or a
report: every test uses the suite's made-up names and firm; the bench's
report holds counts and seconds only - no document name, no word, no path.

**Decision 50 is revised, not discarded.** Its reasoning stands: OCR
misreads words, and the looser any-keyword tier is where a misread "1099"
would file a document under the wrong request. What P282 adds is the
evidence that answers that reasoning for one well-defined case - the
request's own form number printed where a form prints its own name, the
title, with no other form named on the page - and the six guards keep
every other OCR match a lead for a person.
Decisions 92 (a name files nothing), 128 (the name on the page), 140 (the
near-miss shortlist and its hold) and 146 (the broker rule never on OCR's
word) are untouched. Decision 50's other halves - one reading, the verdict
cache, the per-run PDF memo - are untouched.

**Where this SPEC departs from the plan, and why** (checked against the
code on `dcb02c3`; the reviewer should hold the build to the SPEC):

- The plan says only 5 of 49 catalog rows carry required keywords. The
  1040 template has 26 rows, 10 with required keywords (A01, A07, A08,
  A09, B01, C01, L02, L03, N01, Z01); across the six templates 30 of 107
  rows do. The conclusion holds: the 1040's 1099s, 1098-T, 1095-A and 5498
  have none.
- The plan lists the K-1 and the property-tax bill among what Part A
  reaches. It does not reach them: guard 1 needs a keyword that is a form
  number (`content_check.form_key`), and neither F01 (K-1: "partner's share
  of income" ...) nor G01 (property tax: "secured property tax bill" ...)
  has one. See 1.6.
- Guard 2 (a confidence floor) is already in force today: rapidocr drops
  every box below `Global.text_score`, 0.5 by default
  (`rapidocr/main.py`, `filter_by_text_score`). Part A makes the floor the
  product's own number, applied in its own code and testable with a fake
  engine; at 0.5 it drops nothing more, which is why no cache bump.
- The runbook row for `router.OCR_ONLY` is in **section 4** ("What the
  index's Reason column means", row at line 1898), not section 5.
- `content_check.render_scale(width, height)` already exists; Part B
  changes what it reads, not its name.
- `tools/backtest.py` does **not** read in its own process: with `--ocr` it
  opens no reading session, so each OCR'd document is read in a child of
  its own (`ocr.run_in_child` with no session open), paying the engine's
  load every time; its `route_corpus` docstring says otherwise. The bench
  must read in its own process for its settings to apply at all (2.4), so
  it does that itself. The backtest's own behaviour is left alone here.
- OpenCV is installed (rapidocr's dependency, `opencv-python-headless` in
  `requirements.lock`) but `cv2` is not on `tests/test_layers.py`'s
  `ALLOWED_THIRD_PARTY`; Part B adds it (2.2).
- The plan says Part A and Part B may build in parallel lanes. They meet in
  one place - the confidence floor, which Part A introduces as a constant
  and Part B moves into the settings - so Part B is **stacked on Part A**
  (section 4). Each is still its own build and its own review.
- The plan's end-to-end check adds a scanned 1099-INT to the sample pile.
  The pile already holds one: `Scanned forms.zip` in
  `pilot/wintest/make_samples.py` carries `scan 0002.pdf`, an image-only
  1099-INT drawn from `tests/samples.py` (`lines_1099_int`), and
  `pilot/mactest/PROMPT-RERUN-1.md` step 10 already expects "the zip's scan
  should have been filed" - which today it is not (it parks Read From Scan
  Only). No sample is added (the pile's count, 17, is pinned in
  `tests/test_pilot.py`); the zip's scan is the end-to-end case.
- The plan says the floor interpreter (3.11) is not on this Mac. It is:
  `/opt/homebrew/bin/python3.11`, with an environment `.venv311/` in the
  checkout (1.7 says what that costs the map check).
- The plan puts the K-1 issuer test in `tests/test_filer.py`. The issuer
  rule is the router's, so its claim is in `tests/test_router.py`.

---

## 1. P282 - a scan files when its title shows its form number (Part A)

**Why, for a person.** The reader is good: it reads printed tax forms
nearly word for word. But the rule it reads under was written before
there was a reader we trusted, and it lets a scan file only on a request's
strictest keywords - and most requests (every 1099 but the 1099-C and
1099-Q, the 1098-T, the 1095-A, the 5498) have none. So every one of those
parks for a person, however clearly it was read. After this change the
software files such a scan itself when the page's own title names the
form the request asks for and nothing else on the list wants it; a person
still gets every scan where that is not plain.

### 1.1 The rule

A document read by the reader (a scan with no text layer, or a photo:
`Extraction.from_ocr`) that a request accepts on its looser keywords - the
row's verdict passes (`verdict.ok`: every rule of the row, its year
included) and its required keywords did not match (the row has none) - is
**filed under that request when all six hold**, and parks otherwise:

1. **Its own form number is in the title.** The row's verdict recorded, as
   its evidence, one of the row's own keywords that is a form number
   (`content_check.form_key(term) is not None`), under `RULE_REQUIRED` or
   `RULE_ANY`, at `WHERE_TITLE`. Title only: stricter than decision 140's
   near miss, which also takes a first-page dominant form. An OCR reading
   has no page breaks, so the title is the first `TITLE_CHARS` (400) of the
   whole reading, extended to the end of the word it cuts
   (`content_check._title`). A form number is recorded at `WHERE_TITLE`
   when the title names that form in its own right (`_title_forms`: a
   mention shaped like a form naming itself, not a sentence about another
   form), or when the number is the reading's dominant form and its first
   mention falls in the title (`_one_says_where`). A sideways page whose
   line order the reader scrambled usually puts its title past the first
   400 characters, fails this guard and parks - it never files elsewhere
   for it. A bare family number the row lists (K01's `5498`) counts, as it
   does for decision 140; `form_key` already keeps `5498` and `5498-SA`
   apart. The form keys this guard found are **the row's title forms**,
   which guard 6 reads.
2. **Only confident words were read.** The reader drops every box whose
   recognition score is below `ocr.CONFIDENT_SCORE` (0.5) before the lines
   are built (1.3). This is today's floor, made the product's own number;
   Part C may raise it from the office measurement.
3. **Exactly one request accepts it.** Exactly one row passes guard 1, and
   no other row accepted the scan on its looser keywords. Two rows passing
   guard 1 (a broker's consolidated 1099 names 1099-INT, 1099-DIV and
   1099-B in its title), or one passing beside another that matched loosely
   without its form number, parks. A row matched on its required keywords
   files first, exactly as today (the existing strong tier is unchanged and
   is read before this one).
4. **The name on the page confirms a named request** (decision 128,
   untouched). Nothing new: the household pass's name tier
   (`filer._by_the_name`) runs on this filing as on any other. A named
   request (every 1099, 1098, 1095-A and 5498 row of the 1040 is named)
   files only where the page names one of the return's people; someone
   else's name, or none, parks it with the name tier's own reason
   (`NAME_NOT_ON_PAGE`, `NAMES_ANOTHER_RETURN`, `NO_PEOPLE_ON_FILE`), as a
   scan filed on required keywords parks today. An unnamed request (the
   `form 4562` rows of the business templates, the 990's 990-T row) files
   by its keywords alone when the page names nobody, exactly as decision
   128's table says; another return's name still vetoes it (Jason's ruling
   on Q1, section 5). Guards 1, 2, 3, 5 and 6 apply to it in full.
5. **The issuer rule still applies; the broker rule does not** (decisions
   93 and 146). Where the one row that passed is narrowed by issuer rows
   (`manifest.narrowing_rows`) the scan parks `ISSUER_NOT_NAMED`, the
   shortlist led by that row and naming the issuer rows, exactly as a
   text-layer document does. The broker rule (`_filed_whole`, decision 146)
   reads `medium` only, which is text-layer only, so it never sees a scan:
   an OCR'd consolidated 1099 still parks with its shortlist.
6. **Its title form is the only form the page names as itself** (Jason's
   ruling on Q2, section 5). Two readings the judgment already holds
   decide it, and no new one is made:
   - every form the page prints its own name on - `Judgment.self_named`,
     which is `content_check.self_named_forms` over the reading (decision
     85's predicate asked of every mention, the reading decision 94's split
     uses; computed once in the reader child, `content_check.judge`) - is
     one of the row's title forms; and
   - no other considered row's recorded evidence (the router's `record`,
     which already holds every row's verdict evidence) carries a
     form-number keyword (`RULE_REQUIRED` or `RULE_ANY`, `form_key` not
     None) whose form is not one of the row's title forms - that is, the
     page does not also show another request's own form number.

   A page that names two forms **of different families** as itself never
   reaches this guard: decision 94's split reads it first
   (`own_forms(self_named)` is not None, `_multi_form`), and it files a
   copy under each or parks `SEVERAL_FORMS_UNSORTED`, exactly as today. A
   page naming a second form **of the same family** (a 1099-C read as
   "1099-G" printed beside a "Form 1099-S" line), or showing another
   request's form number, fails this guard and parks as `OCR_ONLY`. A page
   that names no form as itself in decision 85's shape - the commonest
   scan, whose title runs "Form 1099-INT Interest Income - 2025" -
   passes the first half (`self_named` is empty), so guard 6 costs nothing
   on an ordinary single form.

   **What guard 6 does not catch, said plainly.** A 1099-C whose "C" the
   reader took for a "G" and which names no second form still shows
   "1099-G" alone in its title, A06 accepts it on that, and A08 records no
   form number (its "1099-c" was never read). Such a scan files under A06.
   The bench's `wrong` count at the office (section 2) is how often that
   happens; P284 or a later decision answers it if the number says so.

**What parks, and how.** A scan that fails guard 1, 3 or 6 parks as
`router.OCR_ONLY` exactly as today: the same sentence
(`"matched only by OCR text (<rows>); a person should confirm"`), the same
code `ocr-only`, the same short label "Read From Scan Only", the same
candidates in the manifest's order, the same evidence record, the same
reminder hold - except where decision 94's split already parked it
`SEVERAL_FORMS_UNSORTED` before any of this is read. Guard 4's parks are
the name tier's (above); guard 5's is `ISSUER_NOT_NAMED`. Nothing is fuzzy:
no tolerance on a keyword, a form number or a name, no one-character slack
(decision 128's question 3b stays strict).

**What a filed scan says.** Its Reason is the new sentence
`router.MATCHED_FROM_SCAN` = `"content matched this request's keywords,
read from a scan that shows its form number"`, followed by the filer's
`"; name confirmed (<spelling>)"` on a named row. Its code is
`reasons.MATCHED_CODE` (`matched`), the code every filing by keywords
carries, so `reasons.SHORT_REASONS`, the app's labels and
`tests/test_reasons.py` (every code has a short label) are untouched. Its
evidence is the row's own verdict evidence (`_recorded_for(record,
[row])`), so the index's Evidence column shows `'1099-int' in the title`.

**No cache bump.** The verdicts are unchanged (`evaluate_rules` is not
touched), and the floor at 0.5 drops no box rapidocr did not already drop.
`content_check.CACHE_VERSION` stays 13. Part A changes how a drop is
routed from the next pass on; it re-routes nothing already parked by
itself (a row already parked as Read From Scan Only stays where the pass
leaves parked rows today). The builder states in the handoff what the
pass does with such a row after the install, from the code, so the office
prompt's before-and-after count is read correctly.

### 1.2 `tracker/router.py`

- **New constant** beside `OCR_ONLY` (line 221):
  `MATCHED_FROM_SCAN = "content matched this request's keywords, read from a
  scan that shows its form number"`, with a `#:` comment naming P282. It is
  a router sentence like the two filing sentences in the loop at line 947,
  which also live here; it is exported (no leading underscore), so the
  repo map lists it.
- **New helper** `_title_form_keys(evidence: tuple[Evidence, ...]) ->
  frozenset[str]`, placed just above `_shows_its_form_number` (line 306):
  the `form_key(found.term)` of every `found` in `evidence` with
  `found.rule in (RULE_REQUIRED, RULE_ANY)`, `form_key(found.term) is not
  None` and `found.where == WHERE_TITLE` - the row's title forms (guard 1
  holds when it is not empty). `_shows_its_form_number` calls it for its
  title branch (`if _title_form_keys(evidence): return True` before its
  loop), so the two read "a form number in the title" one way; its
  first-page branch is unchanged and its result is unchanged for every
  input (decision 140's tests hold). Docstring: guard 1, title only and why
  (a sideways page), reads only what the verdict recorded.
- **New helper** `_names_only_its_own(title_forms: frozenset[str],
  self_named: tuple[str, ...], record: dict[str, tuple[Evidence, ...]],
  only: str) -> bool`, beside it - guard 6, read off what the decision
  already holds and nothing else: False when any key in `self_named` (the
  judgment's `self_named`, `content_check.self_named_forms` as the reader
  child computed it for decision 94) is not in `title_forms`, or when any
  identifier in `record` other than `only` carries a `found` with
  `found.rule in (RULE_REQUIRED, RULE_ANY)` whose `form_key(found.term)` is
  not None and not in `title_forms`; True otherwise. No new reading, no new
  question to the judgment, nothing read off the page again. Its docstring
  says Jason's ruling (Q2, 2026-10-11), why the same-family case is the
  one it exists for (a different-family second form is decision 94's,
  read earlier), and what it does not catch (1.1, guard 6).
- **`_decide`** (line 722):
  - Beside `ocr_only` (line 786) add `scan_strong: list[str] = []  # OCR's
    looser match, and the row's own form number in the title (P282)`.
  - At line 848-849, where a passing row with no required match on an OCR
    reading is appended to `ocr_only`, keep that append unchanged and also
    append to `scan_strong` when `_title_form_keys(verdict.evidence)` is
    not empty.
    `ocr_only` therefore still holds every looser OCR acceptance, in the
    manifest's order, so the park in the last clause below is byte for byte
    today's. `scan_strong` is never added to `medium`.
  - After the strong/medium filing loop (ends line 972) and before the
    `if ocr_only:` exit (line 975), insert:

    ```python
    # A scan whose title shows the request's own form number, accepted by
    # that request alone (P282, revising decision 50): ...
    if len(scan_strong) == 1 and ocr_only == scan_strong and _names_only_its_own(
            _title_form_keys(record[scan_strong[0]]), judgment.self_named, record, scan_strong[0]):
        [only] = scan_strong
        issuer_rows = tuple(dict.fromkeys(
            narrowing_rows(i for i in items if _considers(i)).get(only, ())))
        if issuer_rows:
            shortlist = (only, *issuer_rows)
            return Routing(path=path, identifier=None,
                           reason=ISSUER_NOT_NAMED.format(listed=", ".join(issuer_rows)),
                           candidates=shortlist, evidence=EVIDENCE_CONTENT,
                           evidence_record=_recorded_for(record, shortlist),
                           code=ISSUER_NOT_NAMED.code)
        return Routing(path=path, identifier=only, reason=MATCHED_FROM_SCAN,
                       candidates=(only,), evidence=EVIDENCE_CONTENT,
                       evidence_record=_recorded_for(record, scan_strong),
                       code=reasons.MATCHED_CODE)
    ```

    The comment block above it says the six guards in the software's
    words (2, the floor, is the reader's; 4, the name, is the household
    pass's after this decision; 1, 3, 5 and 6 are here), why the issuer
    rule is asked here and the broker rule is not, and that guard 6 reads
    the judgment's `self_named` - the decision-94 reading - rather than a
    reading of its own. `judgment.self_named` is read directly: the local
    `self_named` above (line ~901) exists only inside the decision-94
    block. By construction nothing before this point has changed: `signed`,
    `near`, the decision-94 split, the text-layer issuer rule, the broker
    rule and the strong/medium loop read exactly what they read today
    (for an OCR reading `medium` is always empty, and a non-empty `strong`
    has already filed or parked in the loop).
  - The `if ocr_only:` exit is untouched; its comment gains one sentence:
    what reaches it is a looser OCR match that did not show its form number
    in the title, that another request also accepted, or whose page names
    another form as itself or shows another request's form number (P282).
- **Comment at line 938** ("Never on OCR's word (``medium`` is text-layer
  only; decision 50)"): say that a scan's own filing (`scan_strong`, P282)
  is a separate list the broker rule never reads.
- **`route_file` docstring** (line 630, "decision 50 reads OCR's words more
  strictly"): "decision 50, as P282 revised it, reads ...".
- **Module docstring**, lines 31-42 (the paragraph ending "those matches go
  to a person instead (``OCR_ONLY``)"): rewrite to say OCR text files on a
  row's required keywords as before, **or** on its looser keywords when the
  page's title shows that row's own form number, no other row accepted
  it, and the page names no other form as itself and shows no other
  request's form number (P282, revising decision 50, with decision 50's reason kept: a misread
  word in the looser tier is how a document lands under the wrong request,
  which is why the form number must be in the title and the match must be
  alone); everything else is `OCR_ONLY`, a lead for a person. One more
  sentence: the name tier (decision 128) and the issuer rule (decision 93)
  apply to such a filing; the broker rule (decision 146) never does.

### 1.3 `tracker/ocr.py`

- **New constant** after `SELF_TEST_WORDS` (line 164):
  `CONFIDENT_SCORE = 0.5`, with a `#:` comment: the lowest recognition
  score a box may have and still be read (P282's guard 2); rapidocr's own
  default floor (`Global.text_score`), held here so the product owns the
  number and a test can see it applied; Part C may raise it from the
  office measurement.
- **`_upright_lines`** (line 458): read `scores = getattr(page_result,
  "scores", None)` beside `boxes` and `txts`. When `boxes` or `txts` is
  None the answer is `[]`, as today. When both are present and `scores` is
  None, raise `ValueError("the reader gave no confidence scores")` - fail
  loudly: rapidocr always gives one score per box (`RapidOCROutput.scores`,
  verified on rapidocr 3.9.2), and a reading that silently skipped the
  floor would file on words the floor exists to drop. Zip the three
  (`strict=False`, as today) and skip a box whose `float(score) <
  CONFIDENT_SCORE`, before the blank-text skip. A box *at* the floor is
  read. The docstring adds the floor to what the seam does ("it drops the
  boxes the reader was not confident of, and blank ones; it never turns a
  page").
- The module docstring's "Lines, not a turn" paragraph gains one sentence
  on the floor.

### 1.4 Tests (claims)

`tests/test_router.py`, beside the OCR claims at lines 141-224, using
`_read_by_ocr` (line 920; an `Extraction(text, from_ocr=True)` handed in)
and `_catalog_1040()` where the catalog is meant, the module's `ITEMS`
where the made-up rows are:

- `test_a_scan_whose_title_shows_1099_int_files_on_the_rows_looser_keywords`
  - the 1040 catalog, `"\n".join(lines_1099_int(...))` from
  `tests/samples.py` with a made-up payer and recipient: files A02, reason
  `MATCHED_FROM_SCAN`, code `matched`, evidence record `{"A02": ...}` with
  `'1099-int'` at `WHERE_TITLE`.
- `test_a_scan_whose_form_number_is_only_below_the_title_parks_as_ocr_only`
  - `ITEMS` (A02 accepts on `dividend`): a reading whose first line is a
  "Year-end dividend summary 2025" heading, then more than `TITLE_CHARS` of
  box lines, then "Form 1099-DIV": parks `OCR_ONLY`, candidates `("A02",)`,
  reason and code byte for byte today's.
- `test_a_scan_two_requests_accept_on_their_titles_parks_with_both` - the
  1040 catalog and `SCHWAB_D146` (its title names 1099-INT, 1099-DIV,
  1099-MISC and 1099-B, so A02, A04 and E01 pass guard 1): parks
  `OCR_ONLY`, candidates `("A02", "A04", "E01")` in the manifest's order.
- `test_a_scan_that_passes_the_title_guard_beside_a_loose_match_parks` -
  two made-up rows: one whose any-keyword `1099-int` is in the title, one
  whose any-keyword phrase is said on the page; parks `OCR_ONLY` with both,
  the passing row first only because the manifest lists it first.
- `test_a_sideways_reading_whose_title_lines_came_late_parks` - the
  1099-INT's lines in a scrambled order with the "Form 1099-INT" line past
  the first 400 characters (what the reader makes of a quarter-turned page)
  and a phrase of the row's in the title: parks, never files.
- `test_a_scan_accepted_by_a_row_issuer_rows_narrow_parks_as_issuer_not_named`
  - made-up rows: a broad row with any-keywords `1099-misc, royalties` and
  no required keywords, and an issuer row with required keyword
  "Northwind Royalty Trust" and any-keyword `royalties` (so
  `narrowing_rows` pairs them); a reading titled "Form 1099-MISC" from
  another payer: parks `ISSUER_NOT_NAMED`, candidates `(broad, issuer)`.
- `test_a_scan_of_last_years_1099_int_parks_and_never_files` - the 1040
  catalog, the 1099-INT lines for 2024: the year fails, the row's verdict
  does not pass, and it parks as today (decision 73's lead); guard 1 is
  never reached.
- `test_a_scan_filed_on_its_form_number_carries_no_answers_and_no_split` -
  `routing.answers == ()` and `routing.also == ()` for the filed 1099-INT
  (the broker rule and the split are not involved).
- `test_a_scanned_1099_c_read_as_1099_g_beside_a_second_form_name_parks`
  - guard 6, the case Jason ruled on: the 1040 catalog and a reading whose
  title is "Form 1099-G 2025 Cancellation of Debt Copy B For Debtor" with a
  second line "Form 1099-S 2025 Proceeds From Real Estate Transactions",
  then the debt lines (`self_named_forms` gives `("1099g", "1099s")`, one
  family, so decision 94's split does not read it; A06 alone passes guards
  1 and 3; no 1040 row asks for the 1099-S): parks `OCR_ONLY`, candidates
  `("A06",)`, byte for byte what it parks as today.
- `test_a_scan_whose_page_shows_another_requests_form_number_parks` - guard
  6's second half: two made-up rows, one with any-keyword `1099-int` (in
  the title) and one with any-keyword `1099-oid` and a typed Date Pattern
  for another year, the reading titled "Form 1099-INT Interest Income -
  2025" and printing "Form 1099-OID" on its last lines often enough to be
  the dominant form (`dominant_forms` gives `{"1099oid"}`), so the second
  row's verdict fails on its year but its evidence records `1099-oid`:
  parks `OCR_ONLY` with the first row (checked against the code on
  `dcb02c3`).
- `test_a_page_naming_only_its_own_form_files` - the 1040 catalog and a
  reading whose title names "Form 1099-R 2025" in decision 85's shape
  (`self_named_forms` gives `("1099r",)`) and no other form: files E02 with
  `MATCHED_FROM_SCAN`. With the ordinary 1099-INT reading of the first
  claim above (`self_named` empty) guard 6 passes too; that claim stands.
- `test_a_page_naming_two_families_as_itself_is_decision_94s_and_never_reaches_the_scan_rule`
  - a reading that prints a 1099-INT's and a W-2's own names: it splits or
  parks `SEVERAL_FORMS_UNSORTED` exactly as `_multi_form` decides today,
  and is never filed with `MATCHED_FROM_SCAN`.
- **Renamed, claim restated:** `test_ocr_text_alone_never_routes_on_any_keywords`
  (line 156) becomes
  `test_ocr_text_does_not_file_on_a_looser_keyword_that_is_not_its_form_number_in_the_title`;
  its assertions stay (the reading "Consolidated 1099 dividend summary
  2025" matches A02 on `dividend` only, and a bare `1099` is not one of
  A02's keywords), its comment says why under P282.
- **Docstrings only:** `test_a_photo_files_on_required_keywords_and_parks_as_ocr_only_on_looser_ones`
  (line 169) and `test_a_consolidated_1099_read_by_ocr_is_never_filed_on_its_looser_words`
  (line 1178) name P282 beside decision 50; their assertions hold unchanged
  (the second's reading puts three rows' numbers in its title).
- `test_a_w2_whose_ocr_lost_one_phrase_parks_with_a01_on_its_shortlist`
  (line 937) must pass unchanged: A01 is a required-keyword row, its
  verdict fails, so it is never in `ocr_only` or `scan_strong`.

`tests/test_filer.py`, beside `test_ocr_text_still_files_on_required_keywords_only_with_the_name_confirmed`
(line 5251), with that test's pattern (an image-only PDF and `_ocr_pdf`
patched to return a made-up reading) and a made-up any-keyword 1099-INT
row added to the engagement's items:

- `test_a_scan_filed_on_its_form_number_still_needs_the_name_confirmed` -
  with `Recipient: John Park` the scan files under the 1099-INT row and its
  reason ends `"; name confirmed (John Park)"`; with a made-up name not on
  the return it parks `reasons.NAME_NOT_ON_PAGE`.
- `test_a_scan_filed_on_its_form_number_into_an_unnamed_request_needs_no_name`
  - Jason's ruling on Q1: a made-up unnamed row (`named=False`) with
  any-keywords `form 4562, depreciation schedule`, and a reading "Form 4562
  Depreciation and Amortization 2025" with the depreciation lines and no
  person's name: files under that row with `MATCHED_FROM_SCAN` and no
  "name confirmed" note (decision 128's table: unnamed, absent, stays); the
  same reading naming a person on another return of the household parks
  `NAMES_ANOTHER_RETURN`.
- The existing test at 5251 keeps its name and claim; its docstring says
  "Decision 50 (as P282 revised it) through decision 128".

`tests/test_ocr.py`:

- `test_a_box_under_the_confidence_floor_is_not_read` - a result with two
  boxes on two lines, scores `(0.99, CONFIDENT_SCORE - 0.01)`: only the
  first line comes back.
- `test_a_box_at_the_confidence_floor_is_read` - score exactly
  `CONFIDENT_SCORE`: read.
- `test_a_reading_without_confidence_scores_fails_loudly` - boxes and texts
  with `scores=None`: `ValueError`.
- `test_the_lines_are_built_from_the_boxes_in_reading_order` (line 208)
  gains `scores` (all 0.99); its docstring says the floor and blank text
  are what is dropped. The `boxes=None, txts=None` case stays `[]`.
- `FakeEngine.__call__` (line 226) returns `scores=tuple(0.99 for _ in
  self.lines)`.
- `test_a_real_scan_whose_title_shows_1099_int_files_on_the_rows_looser_keywords`
  - beside `test_a_scan_is_read_by_rapidocr` (line 72), the real reader: an
  image-only PDF drawn with `tests/samples.py`'s `scanned_pdf` and
  `lines_1099_int` (made-up payer and recipient), routed with
  `route_file` against a made-up any-keyword 1099-INT row and a made-up
  1098 row: files the 1099-INT row with `MATCHED_FROM_SCAN`. The same page
  turned a quarter is routed too and must **not** file under the 1098 row
  (it files the 1099-INT row or parks with it on its shortlist): the claim
  that matters for a sideways page is that it never misfiles; whether the
  reader scrambles a particular page's title is the reader's, not the
  rule's.

`tests/test_content_check.py`:
`test_on_every_corpus_form_the_scans_miss_verdict_equals_the_routers_kept_verdict`
(line 553) runs unchanged and must pass: the corpus files no OCR reading,
and no verdict changed.

### 1.5 Docs that change

- `README.md` lines 457-461, replaced by: "A scan with no text layer, or a
  photo, is read by OCR - the same reading the scanner makes later. OCR
  text files a document on a request's *required* keywords, as a text
  layer does; on a request's looser keywords it files only when the top of
  the page shows that request's own form number ("Form 1099-INT") and no
  other request accepts it and no other form is named on the page, and
  the name on the page still has to confirm a named request. Any other looser match on OCR text goes to review as
  *Read From Scan Only*, with the lead noted, because a misread word is how
  a document lands under the wrong request." (No clause tells a person to
  run anything; `tests/test_single_source.py`'s one-time-step matcher
  passes.)
- `docs/runbook.md` section 4, the table "The index says":
  - the `router.OCR_ONLY` row (line 1898): "A scan or a photo with no text
    layer. OCR read it and a request accepted it on its looser words, but
    the top of the page did not show that request's own form number, more
    than one request accepted it, or the page also names another form
    (P282)." What you do: unchanged.
  - a new row after `filer.FILED`: `router.MATCHED_FROM_SCAN` - "Filed from
    a scan or a photo: OCR read it, the top of the page shows the request's
    own form number and names no other form, no other request accepted it,
    and a named request's name was confirmed (P282)." What you do: "Nothing. If it is wrong, send
    it back to Needs Review from its row and file it by hand." (Use the
    app's own words for that action - the builder takes them from the
    runbook's existing `filer.UNFILED_BY_PERSON` wording.)
- Module docstrings: `tracker/router.py` (1.2), `tracker/ocr.py` (1.3).
- `docs/repo-map.curated.json`:
  - `tracker/router.py` `role`: "(OCR routes on required keywords only)"
    becomes "(OCR files on required keywords, or on looser ones when the
    title shows the row's own form number and no other row accepts it -
    P282)".
  - `tracker/router.py` `notes`: the sentence "OCR text routes only on
    required keywords - an any-keyword match on OCR text is OCR_ONLY, a
    lead for a person, because a misread word is how a document lands under
    the wrong request" gains P282's six guards in one sentence, and
    `_title_form_keys` / `_names_only_its_own` / `MATCHED_FROM_SCAN` by
    name.
  - `tracker/ocr.py` `notes`: one sentence on `CONFIDENT_SCORE` and the
    floor in `_upright_lines`.
- `pilot/DECISIONS.md` row P282 (written with this SPEC).
- `docs/ROADMAP.md` is `main`'s log and is not edited; decision 50's row
  stays as written, as history (the docstrings name P282).

### 1.6 What Part A does not reach

Said so that nobody expects it. A request whose looser keywords include no
form number cannot pass guard 1, so its scans park as today: on the 1040
the K-1 (F01), the property-tax bill (G01), charitable receipts (D01),
estimated-tax vouchers (H01), child-care statements (J01) and business
income (M01); on the business templates every row but the payroll returns
(E01/G01 `form 941`, `form 940`, `form w-3`), the depreciation rows
(`form 4562`) and the 990's 990-T row. Reaching them is a keyword change,
which this SPEC does not make (the plan's "not in this plan"), or the
bench's evidence for a different rule.

### 1.7 Gate for Part A

Per CLAUDE.md (decisions 207 and 211, and the 2026-09-29 rule), in the
worktree, before any push:

1. Dead code first: in `tracker/router.py`, `tracker/ocr.py` and the
   changed test files - unused imports and locals, commented-out code,
   names nothing uses. (`.gitignore` gains `.venv311/`, below.)
2. The affected test files, each as its own process, under **both**
   interpreters - the office's (`.venv`, Python 3.14.8) and the floor
   (Python 3.11, `pyproject.toml`'s `requires-python`). On this Mac the
   floor environment is `.venv311/` in the checkout (Python 3.11.17, made
   on 2026-10-11 from `/opt/homebrew/bin/python3.11`). It is untracked and
   **not** ignored - `.gitignore` names `.venv/` and `venv/` only - so
   `python tools/repo_map.py check` reports the map stale on its 3,000-odd
   files while it sits there. Part A's first commit adds `.venv311/` to
   `.gitignore` beside `.venv/`. If the locks will not install in it, the
   floor row runs at the office and the handoff says so.
   - changed / own: `tests/test_router.py`, `tests/test_filer.py`,
     `tests/test_ocr.py`;
   - importers of `router` and `ocr`: `tests/test_backtest.py`,
     `tests/test_content_check.py`, `tests/test_api.py`,
     `tests/test_runner.py`, `tests/test_resident.py`;
   - `tests/test_reasons.py` (the code labels Part A relies on);
   - guards: `tests/test_layers.py`, `tests/test_single_source.py`,
     `tests/test_repo_map.py`, `tests/test_tripwire.py` (tests changed),
     `tests/test_errors.py` (a new error sentence).
   - A gate never adds `-m "not corpus"`.
3. `python -m ruff check .`
4. `python tools/repo_map.py update`, then `python tools/repo_map.py check`
   (exit 0), the map in the same commit as the code.
5. `python tools/vocab_report.py build`: no keyword changes, so no diff is
   expected; a diff is a finding.
6. The backtest baseline is unrecorded (`docs/backtest-baseline.json`), so
   `check` says so and holds nothing; the office prompt (2.6) records it
   **before** Part A is installed there.

A Windows check, if one is asked for, runs the **whole suite**: Part A
reaches the sorting engine (the router), which is the 2026-09-29 rule's
case for it. No `windows` label: nothing here touches the engagement lock,
the atomic replace, path handling or a Windows-only test.

---

## 2. P283 - the reader's settings are one seam, and a bench measures them (Part B)

**Why, for a person.** Nobody has measured which reading settings help on
the firm's own paper. The reader draws a scanned page at 144 dots per inch,
below the 200-300 every reader wants; Jason's own pre-processing notes ask
for removing a form's box lines and end with the open item "how to measure
which steps actually help". This part does not change how anything is read.
It gathers every setting into one place, adds box-line removal as a switch
that is off, and ships a tool that reads a folder of already-sorted
documents once per combination of settings and counts how many land where a
person put them, and how long each took. The office PC runs it; Part C then
ships whatever the numbers favour.

### 2.1 The seam (`tracker/ocr.py`)

- **`ReaderSettings`**, a frozen dataclass (`slots=True`) after the model
  constants (line 156):

  | field | type | shipped value | what it is |
  |---|---|---|---|
  | `render_dpi` | `int` | `144` | a PDF page is drawn at `render_dpi / 72` (today's `RENDER_SCALE`, 2.0) |
  | `confident_score` | `float` | `CONFIDENT_SCORE` (0.5) | P282's floor; rapidocr's `Global.text_score` and `_upright_lines`' skip |
  | `max_side_len` | `int` | `2000` | rapidocr's `Global.max_side_len`: an image whose long side passes it is shrunk before detection |
  | `delining` | `bool` | `False` | remove a form's long box rules before reading (2.3) |
  | `model_tier` | `str` | `"small"` | `"small"` or `"medium"` (`MODEL_TIERS`) |
  | `model_folder` | `str` | `""` | where the tier's detection and recognition models are; `""` is the app's own `models_folder()` |

- **`MODEL_TIERS: dict[str, tuple[str, str]]`** =
  `{"small": (DETECTION_MODEL, RECOGNITION_MODEL), "medium":
  ("PP-OCRv6_det_medium.onnx", "PP-OCRv6_rec_medium.onnx")}` - the medium
  names are the files rapidocr's `download_models` writes (the last part
  of the `model_dir` URLs in `rapidocr/default_models.yaml`,
  `multi_PP-OCRv6_det_medium` / `multi_PP-OCRv6_rec_medium`). The direction
  model is always the shipped one.
- **`SHIPPED = ReaderSettings()`** and **`SETTINGS: ReaderSettings =
  SHIPPED`**: the settings this process reads with. The product never
  changes them.
- **`use_settings(settings: ReaderSettings) -> ReaderSettings`**: make
  `settings` this process's, drop the built engine (`_ENGINE, _DEVICE =
  None, ""`) so the next reading builds one with them, and return the
  settings it replaced. Refuses (`ValueError`) a `model_tier` not in
  `MODEL_TIERS`, a `render_dpi` under 72 or a `confident_score` outside
  0-1. For the bench and the suite only; its docstring says so, and says
  it must never run in a reading child (the module's rule that a reading
  leaves no module state behind: a child imports `SETTINGS` afresh, as
  `SHIPPED`).
- **`_build_engine`** (line 249): take the detection and recognition files
  from `MODEL_TIERS[SETTINGS.model_tier]`, in `Path(SETTINGS.model_folder)`
  when it is set and `models_folder()` otherwise; the direction model from
  `models_folder()`. A file missing is `ReaderUnavailable(f"the model
  {name} is missing")`, as today (nothing is fetched). `params` gains
  `"Global.text_score": SETTINGS.confident_score`, `"Global.max_side_len":
  SETTINGS.max_side_len`, `"Det.model_type": SETTINGS.model_tier` and
  `"Rec.model_type": SETTINGS.model_tier` (so any key rapidocr resolves
  from the config names the files it was given). With the shipped settings
  the engine is built from the same three files with the same values
  rapidocr defaulted to, so nothing read changes.
- **`_upright_lines`**: the floor reads `SETTINGS.confident_score` in place
  of `CONFIDENT_SCORE`. `CONFIDENT_SCORE` stays as the shipped default
  `ReaderSettings` reads (one number, one home).
- **`read_page`** (line 423): when `SETTINGS.delining`, the page is handed
  to `delined(image)` before `_pixels`; otherwise the engine gets the page
  as it stands, as today. The graphics-card retry path reads the same
  (already de-lined) pixels.

### 2.2 De-lining: `ocr.delined(image) -> PIL.Image.Image`

Jason's step 5 ("de-lining for forms"), built as a switch the bench turns
on; off in the product until Part C. Pure, in memory, never writes:

1. A greyscale copy (`numpy` array, `uint8`).
2. Ink as white on black: `cv2.threshold(grey, 0, 255,
   cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)`.
3. Long rules: `cv2.morphologyEx(ink, cv2.MORPH_OPEN, kernel)` with a
   horizontal kernel `(max(1, width // 40), 1)` and a vertical one `(1,
   max(1, height // 40))` - a stroke shorter than a fortieth of the page is
   a letter, longer is a rule; the two masks joined (`cv2.bitwise_or`) and
   dilated once with a 3x3 kernel so a rule's anti-aliased edge goes too.
4. The rules whitened in the greyscale copy (`grey[mask > 0] = 255`).
5. Repair, confined to where a rule was (corrected after Part B's review,
   finding 1; the first wording could never rejoin a letter). A letter a
   rule crossed lost a sliver as thick as the rule plus the dilation's
   margin, so the gap to bridge is the rule's thickness plus
   `DELINE_GROW - 1`, never the rule's thickness alone. The repair span,
   worked out per page, is `DELINE_GROW + max(DELINE_RULE_FLOOR,
   min(width, height) // DELINE_RULE_DIVISOR) + 1` pixels (`DELINE_RULE_FLOOR
   = 3`, `DELINE_RULE_DIVISOR = 250`): it bridges a rule up to a 250th of the page's shorter side
   (about 4 px at 144 dpi, 10 px at 300) and leaves a thicker border's cut
   alone. A closing of the ink that remains with a `(1, span)` kernel and
   then a `(span, 1)` kernel finds the bridges; only the bridging pixels
   that lie inside the whitened rule mask (step 3's dilated mask) are laid
   back as black (`grey[(closed > 0) & (rules > 0)] = 0`). Nothing outside
   the mask changes, so the rest of the page keeps its grey and two letters
   that merely sit close are never joined.
6. Returned as an `"RGB"` PIL image the same size as the input.

The constants (`DELINE_FRACTION = 40`, `DELINE_GROW = 3`, `DELINE_RULE_FLOOR`,
`DELINE_RULE_DIVISOR`) are named at module level with a comment each; the bench
measures the switch, not the constants.

**OpenCV is a reader's import now.** `tests/test_layers.py`:
`ALLOWED_THIRD_PARTY["optical character recognition"]` gains `"cv2"`, and
`DISTRIBUTION_OF` gains `"cv2": "opencv-python-headless"` (it is in
`requirements.lock`, so `test_every_allowed_third_party_import_is_a_locked_package`
holds). `READER_MODULES` is unchanged: `rapidocr.main` already imports
`cv2` (verified), so its network reach is already measured. The comment
above `ALLOWED_THIRD_PARTY` says why: page clean-up arithmetic on pixels,
deterministic, generating nothing.

### 2.3 `tracker/content_check.py`

- `RENDER_SCALE` (line 186) goes. `render_scale(width, height)` (line 1748)
  returns `min(ocr.SETTINGS.render_dpi / 72, (PIXEL_BUDGET / area) **
  0.5)`, read at call time (the bench changes the settings between
  variants). `PIXEL_BUDGET` stays the hard ceiling (decision 137): a 300 dpi
  letter page is 7.6 million pixels, far inside it. Its docstring and
  `_ocr_pdf`'s (line 1769) say "the settings' dpi" where they said the
  scale.
- **No `CACHE_VERSION` bump** (it stays 13): the shipped settings render at
  exactly 2.0 and build the same engine, so every verdict is the same.
- Module docstring, lines 25-27 ("The router asks for the text layer first
  and OCR only when the file's name tells it nothing"): stale since
  decision 92 (a name no longer excuses the reading). Corrected to: the
  router asks for the text layer and, for a scan or a photo, the reader;
  OCR's words are read under decision 50 as P282 revised it
  (:mod:`tracker.router` says how).

### 2.4 The bench: `tools/reader_bench.py`

Its own `tests/test_reader_bench.py`. A tool (the repo map's `tooling`
layer): `tests/test_layers.py`'s layer table, load-time rule and import
allow-list cover `tracker/` only, so the bench sits outside the package
layering, as `tools/backtest.py` does; it may import `tracker` modules and
the backtest. If the layer test's path-spelling walk (`ALLOWED_SPELLINGS`,
which reads `tools/` too) flags it, it gets the backtest's entry and reason
(`("tools/reader_bench.py", "*"): "the repository's paths, never a
client's"`). A module docstring in the house register says what it
measures, what it refuses and why it reads in its own process.

**What it reuses from `tools/backtest.py`** (imported by name, private
helpers included; a rename there is a change to both, and the docstring
says so): `_harness()` (the suite's `read_expectations` and `catalog_rows`
- one owner of the expectations format), `_corpus`, `_document_path`,
`_linked_under_a_neutral_name` (every document read through a hard link
named `document.<ext>` in a scratch folder, so no client's file name reaches
the router or the report), `_temp_pointed_at` with
`tracker.settings.process_scratch()` (what a library writes through the temp
folder lands in this process's scratch and goes with the run - the same
`try/finally` as `route_corpus`), `_outside_the_repository` (the report is
refused inside the tree), `write_json`, `CATALOGS`, `BacktestError`, the
`READING_*` kinds and `EXPECTATIONS_FILENAME` as the default expectations
file.

**It reads in its own process.** A reading child imports `tracker.ocr`
afresh, at `SHIPPED`, so settings changed in the bench's process would
never reach it. For the whole run the bench sets
`content_check.READ_IN_A_CHILD = False` (the switch the suite's
`tests/conftest.py` throws) and opens `ocr.reading_session(in_a_child=False)`
around each variant, and puts both back - and `ocr.use_settings(previous)`
- in a `finally`. The cost, said in the docstring: there is no safety stop
for a reading in the bench (a person is watching a measurement, not a
pass), and the bench reads on the processor only (`gpu_pack()` is None run
from source), which is the conservative number for Jason's ceiling.

**The corpus.** A folder and its expectations file in the backtest's format
(`expectations.csv` beside the documents by default, `--expectations`
otherwise): the photo corpus (the folder `TRACKER_REAL_CORPUS` names at the
office, if its expectations file is filled) and the firm's sorted
documents (the backtest's corpus). Before any variant each row's document
is linked once and read once with `content_check.extract(link, ocr=False)`:
a document with a usable text layer is counted (`text_layer`) and never
routed again - the reader's settings cannot change it - and the rest are
the scans (a PDF that `needs_ocr`) and the photos (an image extension).
Their pages are counted once (`pypdfium2`, capped at
`content_check.MAX_PAGES`; a photo is one page).

**The variants.** A fixed grid, every combination of:

- `render_dpi` in {144, 200, 300};
- `confident_score` in {0.5, 0.7, 0.85};
- `delining` in {off, on};
- `model_tier` in {small, medium};

36 variants, each named `dpi<d>-floor<f>-<off|on>-<tier>`
(`dpi144-floor0.50-off-small` is the shipped one and is always measured
first). Each variant's `max_side_len` is `max(2000, ceil(11 * dpi))` - a
letter page's long side at that dpi - so 300 dpi is not silently shrunk
back to 182 by rapidocr (`rapidocr/utils/process_img.py`): 2000, 2200 and
3300. A photo is read up to the same long side, and its own timing (below)
shows what that costs. `--dpi`, `--floor`, `--delining` and `--tier`
(comma lists) restrict the grid; the shipped variant is always included.
The medium tier needs `--models <folder>` holding both medium files; without
it, or with a file missing, every medium variant is in the report as
`"measured": false` with the fixed note `MEDIUM_NOT_MEASURED` ("the medium
models are not in a folder the bench was given; a person fetches them with
rapidocr download_models") and nothing is read for it. The bench never
downloads: it calls nothing of rapidocr's downloader, and the reader's
refusal (`ocr._refuse_downloads`) stands under it.

**Per variant.** `ocr.use_settings(variant)`; `ocr.warm_up()` timed as
`first_load` (a `ReaderUnavailable` there makes the variant `"measured":
false` with the error's class only); then every scan and photo routed with
`tracker.router.route_file(link, items)` - no reading handed in, so the
router reads (OCR, in this process, under these settings) and applies its
own rule, P282's included - against `catalog_rows` for the row's catalog
and year, with no verdict cache (nothing is kept between variants). Each
`Routing` is scored:

| outcome | when |
|---|---|
| `right` | it filed under the expected row, or the row is meant to park (`expected` blank) and it parked |
| `parked_shortlist` | it was meant for a row, it parked, and that row is on its shortlist (`routing.candidates` or a key of `routing.evidence_record` - what the review card offers, decision 140 included) |
| `parked_no_lead` | it was meant for a row, it parked, and that row is not on its shortlist |
| `wrong` | it filed, and not under the expected row (a meant-to-park document that filed is wrong) |

and counted: `ocr_only` (routings whose `code == reasons.OCR_ONLY_CODE`)
and its share of the documents read, and `parked_by_code` (a count per
`Routing.code` of the parked ones - codes only). Seconds come from
`Routing.seconds` (the reading's own, decision 127): per document median
and worst, by kind (scan, photo); per page median and worst (a document's
seconds over its pages read); and `over_ceiling`, the documents slower
than `CEILING_SECONDS_PER_PAGE = 6.0` a page - Jason's ceiling (decision
127 D-2: 6 s a photo, 60 s a ten-page scan on the office PC).

**The report** (schema 1), written by `write_json` to `--out`, refused
inside the repository, and printed as a short table (variant, the four
outcomes, `ocr_only`, per-page median and worst, `over_ceiling`):

```
{"schema": 1, "note": BENCH_NOTE,
 "corpus": {"documents": n, "text_layer": n, "scans": n, "photos": n, "pages": n},
 "variants": [{"name": "...", "settings": {"render_dpi": 144, "confident_score": 0.5,
               "max_side_len": 2000, "delining": false, "model_tier": "small"},
               "measured": true, "note": "",
               "outcomes": {"right": n, "parked_shortlist": n, "parked_no_lead": n, "wrong": n},
               "ocr_only": n, "ocr_only_share": x, "parked_by_code": {"<code>": n},
               "seconds": {"first_load": s, "per_page_median": s, "per_page_worst": s,
                           "scan_median": s, "scan_worst": s, "photo_median": s,
                           "photo_worst": s, "over_ceiling": n}}]}
```

Counts and seconds only: no document name, no folder below the corpus, no
row number (unlike the backtest, which needs one to point a person at a
confusion; the bench does not), no word of a document, no path - the
settings' `model_folder` is not written either. `BENCH_NOTE` says so in
the report itself.

**Commands.**

```
python tools/reader_bench.py variants                                   # the grid's names, one a line
python tools/reader_bench.py run <folder> --out <report> [--expectations <file>]
       [--models <folder>] [--dpi 144,200,300] [--floor 0.5,0.7,0.85] [--delining off,on] [--tier small,medium]
python -m tracker.api firm | python tools/reader_bench.py review-codes  # Needs Review, counted by code
```

`review-codes` reads the `firm` command's JSON reply on its standard input
and prints `{"<code>": n, ...}` over its `files` list - the rows waiting
for a person - and nothing else; `--out` writes the same counts to a file
outside the repository. It never prints or writes a name, a path or a
reason sentence from the reply. Errors are `BacktestError`-style: the
tool's own sentence, exit 2, never a traceback with a path in it.

### 2.5 Tests (claims)

`tests/test_ocr.py`:

- `test_the_shipped_settings_are_todays_reading` - `SHIPPED ==
  ReaderSettings(144, 0.5, 2000, False, "small", "")` and `SETTINGS is
  SHIPPED`.
- `test_the_engine_is_built_with_the_settings_floor_and_long_side` -
  `RapidOCR` replaced by a recorder; with the shipped settings the params
  carry `Global.text_score` 0.5 and `Global.max_side_len` 2000 and the
  three shipped model paths; with other settings, theirs.
- `test_the_medium_tier_reads_its_models_from_the_folder_it_is_given` - a
  temporary folder holding two empty files of the medium names: the
  recorder sees those paths for detection and recognition and the shipped
  direction model.
- `test_the_medium_tier_without_its_models_is_unavailable_and_fetches_nothing`
  - no folder, or a folder missing one file: `ReaderUnavailable` naming the
  missing model, and rapidocr's downloader is never reached.
- `test_using_other_settings_drops_the_built_engine_and_says_what_it_replaced`.
- `test_unknown_settings_are_refused` - an unknown tier, a dpi under 72, a
  floor outside 0-1.
- `test_the_floor_follows_the_settings` - a box scored 0.6 is read at 0.5
  and dropped at 0.7.
- `test_delining_removes_long_rules_and_keeps_the_words` - a white page
  drawn in memory with a full-width rule, a full-height rule and a line of
  text crossing neither: after `delined`, the rules' rows and columns are
  white away from the text, the text's ink is still there, and the size is
  unchanged.
- `test_delining_rejoins_a_letter_a_rule_crossed` (added after Part B's
  review, finding 1) - a white page at letter size and 144 dpi with a
  2 px full-width horizontal rule and a 4 px wide, 25 px tall vertical
  stroke crossing it, plus a mid-grey block touching neither: after
  `delined`, every pixel of the stroke's columns is black from its top to
  its bottom, the rule's row is white away from the stroke, the grey block
  still reads mid-grey (the repair touched nothing outside the rule), and
  the same holds for a 1 px and a 3 px rule.
- `test_delining_is_off_in_the_product_and_on_hands_the_engine_the_delined_page`
  - with a `FakeEngine` and `_pixels` recorded: shipped settings hand the
  page as it stands; `delining=True` hands `delined(page)`.

`tests/test_content_check.py`:

- `test_a_page_is_rendered_at_the_settings_dpi_within_the_pixel_budget` -
  `test_a_giant_pdf_page_is_rendered_within_the_pixel_budget`'s (line 1054)
  stopping render, under `use_settings(ReaderSettings(render_dpi=300))`: a
  letter page is asked at `612 * 300 / 72` by `792 * 300 / 72`, the giant
  page still at the budget; settings put back after. The existing test at
  1054 runs unchanged (an ordinary page at 2.0).

`tests/test_layers.py`: no new test; the two tables change (2.2), and
`test_every_import_under_tracker_is_allowed` and
`test_every_allowed_third_party_import_is_a_locked_package` must pass.

`tests/test_reader_bench.py` (the reader is a stand-in throughout:
`content_check._ocr_pdf` / `_ocr_image` patched to return a made-up reading
chosen by the settings in force, so a test can make one variant file and
another park; one test uses the real reader on one drawn page):

- `test_the_grid_is_every_dpi_floor_delining_and_tier`;
- `test_the_shipped_variant_is_always_measured_first`;
- `test_each_variants_long_side_holds_a_letter_page_at_its_dpi`;
- `test_a_document_with_a_text_layer_is_counted_and_never_read_by_the_reader`;
- `test_the_four_outcomes_are_counted_as_the_spec_defines_them` - a
  made-up corpus with one of each: filed right, meant to park and parked,
  parked with the expected row on its shortlist, parked with no lead,
  filed elsewhere;
- `test_parked_documents_are_counted_by_code_and_ocr_only_has_its_share`;
- `test_the_report_holds_counts_and_seconds_and_no_name_path_or_word` - a
  corpus whose file names, folder and readings carry distinctive made-up
  words: none of them, and neither the corpus path nor the models folder,
  appears anywhere in the report's text or the printed table;
- `test_the_report_is_refused_inside_the_repository`;
- `test_the_medium_tier_is_not_measured_without_its_models_and_says_so`;
- `test_the_bench_never_downloads_a_model` - with the downloader made to
  fail the test if reached, a run with `--tier medium` and no models
  completes;
- `test_the_settings_and_the_reading_switch_are_put_back_after_the_run` -
  also after a run that raised;
- `test_the_seconds_are_counted_per_page_and_against_the_ceiling`;
- `test_review_codes_counts_codes_and_prints_nothing_else` - a made-up
  `firm` reply whose rows carry made-up names and reasons: the output is
  the code counts alone;
- `test_a_real_scan_is_read_under_each_dpi_it_is_asked_for` - the real
  reader, one drawn image-only page, `--dpi 144,300 --floor 0.5 --delining
  off --tier small`: two measured variants, each with one `right`.

### 2.6 The office prompt: `pilot/PROMPT-reader-bench.md`

For a Claude Code session on the **office PC only** (the designated
machine, JPPC; never this Mac or any viewer). It names the exact commands
and the reason each is run, as `pilot/wintest/PROMPT.md` does. It never
asks the session to open, read, name or quote a document; every number it
asks for back is a count or a time. Sections:

1. **Before anything, refuse if not the office PC** (the clients root is
   set and the schedule is registered here), and check out
   `claude/ocr-scans` at Part B's head in the office checkout; `Setup.bat`'s
   hash-checked installs.
2. **Today's numbers, before Part A is installed** (the app still at
   `main`'s build):
   - `python -m tracker.api firm | python tools/reader_bench.py review-codes
     --out <outside>\review-before.json` - Needs Review by code;
   - `python tools/backtest.py run <firm corpus> --ocr --out
     <outside>\backtest-before.json` and `python tools/backtest.py record
     --report <outside>\backtest-before.json` - the baseline every later
     routing change is held to, with the reader on (decision 92 parks every
     scan without it, so a baseline without `--ocr` says nothing about
     Part A). The recorded `docs/backtest-baseline.json` is the one file the
     session commits, on its own branch, as a draft pull request.
   - If the photo corpus has no filled expectations file:
     `python tools/backtest.py collect <photo corpus> --catalog 1040 --year
     2025 --out <outside>\photo-expectations.csv`, and **stop** for a person
     to fill it in; the session does not fill it.
3. **The medium models**, fetched by a person (the session may type the
   commands, a person approves the download): `.venv\Scripts\rapidocr
   config --save_cfg_file <outside>\medium.yaml`; in that file set
   `Global.model_root_dir` to `<outside>\medium-models`, `Global.use_cls:
   false`, and `Det.model_type` and `Rec.model_type` to `"medium"`;
   `.venv\Scripts\rapidocr download_models --config <outside>\medium.yaml`
   (rapidocr checks each file's SHA-256 against its own list). The folder
   must then hold `PP-OCRv6_det_medium.onnx` and
   `PP-OCRv6_rec_medium.onnx`. Outside the repository and outside the
   clients root.
4. **The bench**, on each corpus: `python tools/reader_bench.py run
   <corpus> --out <outside>\bench-<corpus>.json --models
   <outside>\medium-models`; the full grid. The prompt gives the arithmetic
   for the time it will take (documents x pages x 36 variants at the
   shipped variant's per-page median, medium about 2.6 times small) and,
   when that is more than one night, runs the small tier first
   (`--tier small`) and the medium tier at the best small dpi and floor
   second.
5. **Part A installed** (the Part A build on the office PC by the usual
   route), the first scheduled pass after it, then the same `review-codes`
   to `review-after.json`, and `python tools/backtest.py run <firm corpus>
   --ocr --out <outside>\backtest-after.json` with `check --report` on it:
   exit 1 is a finding to report, not to fix.
6. **What comes back**: the four JSON files' contents (counts and seconds
   only), pasted into the CODE UPDATE for Jason, and nothing else. The
   reports stay on the office PC outside the repository.

The prompt lists the exact paths as placeholders the session fills from
the office PC's own folders, and says that `<outside>` is a folder outside
both the repository and the clients root (the backtest's and the bench's
`--out` refuse the repository themselves).

### 2.7 Docs that change

- `docs/tools.md`: a section after the backtest's, "The reader bench: which
  reading settings help on the firm's paper" - why (2.0's "Why"), the grid,
  the four outcomes, the in-process reading and its cost, the report's
  counts-only rule, the commands, and that P284 ships from its numbers. The
  title line of the page becomes "The routing tools: vocabulary report,
  learned keywords, backtest, reader bench".
- Module docstrings: `tracker/ocr.py` (the seam, `use_settings`'s rule,
  `delined`), `tracker/content_check.py` (2.3), `tools/reader_bench.py`.
- `docs/repo-map.curated.json`:
  - `tracker/ocr.py` `notes`: `ReaderSettings` / `SHIPPED` / `SETTINGS` /
    `use_settings` / `delined`, shipped values equal to the reading before
    P283;
  - `tracker/content_check.py` `notes`: `render_scale` reads the settings'
    dpi; `RENDER_SCALE` gone;
  - new nodes `tools/reader_bench.py` (`role` and `notes`, as
    `tools/backtest.py` has) and `tests/test_reader_bench.py` (`role`);
  - new edges: `tools/reader_bench.py` `writes` `artifact:reading scratch`
    (as the backtest does), and `pilot/PROMPT-reader-bench.md` `documents`
    `tools/reader_bench.py`.
- `pilot/DECISIONS.md` row P283 (written with this SPEC).
- Not the runbook, not the README: nothing a person sees at the firm
  changes in this part.

### 2.8 Gate for Part B

1. Dead code first, in `tracker/ocr.py`, `tracker/content_check.py`,
   `tools/reader_bench.py` and the changed tests (`RENDER_SCALE` has no
   reader left: it goes).
2. The affected test files, each its own process, both interpreters (as
   1.7):
   - changed / own: `tests/test_ocr.py`, `tests/test_content_check.py`,
     `tests/test_reader_bench.py`, `tests/test_layers.py`;
   - importers of `ocr` and `content_check`: `tests/test_router.py`,
     `tests/test_filer.py`, `tests/test_scanner.py`,
     `tests/test_containers.py`, `tests/test_names.py`,
     `tests/test_after_install.py`, `tests/test_api.py`,
     `tests/test_runner.py`, `tests/test_resident.py`,
     `tests/test_backtest.py`, `tests/test_vocab_report.py`,
     `tests/test_learned_keywords.py`;
   - guards: `tests/test_single_source.py`, `tests/test_repo_map.py`,
     `tests/test_tripwire.py`, `tests/test_errors.py`.
3. `python -m ruff check .`
4. `python tools/repo_map.py update` and `check`.
5. `python tools/vocab_report.py build` (no diff expected).

No CACHE_VERSION bump, no change to the shipped models, so `tests/test_build.py`
is not in the list.

---

## 3. P284 - the shipped settings, set by the numbers (reserved)

Not specified here. When the office reports are back, a SPEC section of its
own picks the dpi, floor, de-lining and tier that raise `right` and lower
`wrong` within Jason's ceiling (6 s a photo, 60 s a ten-page scan), changes
only `SHIPPED`'s values (and, if medium wins, adds its two models to the
shipped set in `api_entry.spec`, `build-mac.sh` and the lockfile notes, with
`tests/test_build.py`), bumps `content_check.CACHE_VERSION` to 14 so every
scan is read once more under the new settings (the runbook's existing
wording for a reading change), records P284 with the numbers, and records
the backtest baseline again.

---

## 4. Build order

Two lanes, each its own sonnet build and its own Opus review (high effort)
in a session that did not build it, per CLAUDE.md's loop; a finding that
survives one rebuild is Opus's to fix.

1. **Part A (P282)** on `claude/ocr-scans`: section 1. Verification beyond
   the unit claims: the real-reader claim in 1.4, and on this Mac the
   sample pile through the `pilot/mactest/run_checks.sh` flow - the
   `Scanned forms.zip` scan files under its 1099-INT request, byte for
   byte, with "name confirmed" in its reason, where today it parks.
2. **Part B (P283)** stacked on Part A (a branch from Part A's head): it
   moves Part A's floor into the settings (2.1), so it is built after
   Part A's build exists. It is behaviour-neutral and reviewed on its own:
   the review holds it to "nothing read changes" (the shipped settings'
   engine parameters, the render scale at 2.0, no cache bump).
3. Both land together, in landing order, one draft pull request marked
   ready once (decision 211). Then the office session runs
   `pilot/PROMPT-reader-bench.md`; Part C waits for its reports.

---

## 5. Jason's rulings on the two questions (decided, 2026-10-11)

Both were put to Jason in this session and are decided; no question is
open.

**Q1 - a scan on an unnamed request.** Decided: **no change to decision
128.** A scan filing on its form number into an unnamed request (the
`form 4562` rows, the 990's 990-T row) files by its keywords alone when no
name is on the page, as decision 128's table says; another return's name
still vetoes it, and the title guard, the confidence floor, exactly-one and
guard 6 still apply (1.1, guard 4). The build changes nothing in the
household pass. Test: `test_a_scan_filed_on_its_form_number_into_an_unnamed_request_needs_no_name`.

**Q2 - a misread suffix.** Decided: **add the sixth guard.** Jason: "Yes,
add the guard". A scan files on the new rule only when the form number in
its title is the only form the page names as itself - read from the
judgment's `self_named` (`content_check.self_named_forms`, decision 94's
reading, not a new one) - and the page shows no other request's own form
number; a page that does parks exactly as today, `SEVERAL_FORMS_UNSORTED`
where decision 94's split fires and `OCR_ONLY` otherwise (1.1, guard 6;
1.2, `_names_only_its_own`). What the guard does not catch - a misread
suffix on a page that names no second form - is said in 1.1 and measured
by the bench's `wrong` count. Tests:
`test_a_scanned_1099_c_read_as_1099_g_beside_a_second_form_name_parks`,
`test_a_scan_whose_page_shows_another_requests_form_number_parks`,
`test_a_page_naming_only_its_own_form_files`,
`test_a_page_naming_two_families_as_itself_is_decision_94s_and_never_reaches_the_scan_rule`.
