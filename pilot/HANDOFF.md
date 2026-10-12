# Pilot handoff

The pilot is Tax Document Console for a first batch of test firms: the
tracker, the Electron app that fronts it, and the Windows installer and check
kit in this folder. [`README.md`](README.md) says what it is and the rules for
this repository; [`SPEC.md`](SPEC.md) says what it builds.

## Where the record is

- **`main` is `401cdf4`** (pull request #36, the Mac re-run 1 fixes, P260-P263);
  this branch, `claude/ui-polish`, is cut from it and carries P264 (the UI
  review's no-brainers, built) and Jason's sixteen menu answers, P265-P280
  (recorded; their SPECs follow).

- **Decisions live in [`DECISIONS.md`](DECISIONS.md), rows P1 to P281.** The
  badge reads **Pilot 0.4** (P281, 2026-10-11): 0.3 plus the UI review's work. Code
  and tests cite those numbers, so a row is never renumbered or removed. Why
  a thing is the way it is: search the row, do not guess.
- **Pilot decisions never go in `docs/ROADMAP.md`**, which stays the
  original's log.
- **A SPEC is built from, not read for history.** The SPECs beside this file
  are cited by section from the code; each names the P-rows that built it.

## Current work

**P285 - a scan or a photo is prepared before the reader reads it
([`SPEC-ocr-prepare.md`](SPEC-ocr-prepare.md)), built on `claude/ocr-prepare`**
in three commits on top of the SPEC's (the stage with its tests; the bench,
both prompts, the docs and the map; the first handoff), then rebuilt to the
SPEC's section 9 amendment in four more (the detector's long side; the box-line
step; the Mac prompt's counts; a leftover print) and a handoff, then rebuilt
again to section 9.4 (the processor child's cap; Sauvola on box filters; the
runbook, the record and this handoff). Not yet reviewed (Opus's, in a session
that did not build it) and **not pushed**. Jason ruled every section 8
question to its stated default. **The processor child's cap, 4 GB from P285,
is an assumption of the orchestrating session held for Jason's word (decision
169 is his); one constant reverses it.**

What was built, in the software's words: every scanned page and photo is now
prepared in memory before the reader sees it - drawn at 300 dots per inch,
turned level if it leans up to five degrees (and left alone when the lean
cannot be measured plainly), made black and white by a threshold that follows
the paper's own shading, cleared of lone specks and of a form's box lines.
The file is never touched and nothing is written. The verdict cache moved, so
the first pass after the install reads every document again (slow once; a row
already in Needs Review stays there). The reader bench grew from 36 to 21
variants: prepared against raw at 300 and 144 dpi, and the shipped settings
with each step turned off one at a time, so the office numbers say which steps
earn their place. README, runbook, tools page, the office prompt and the map
say so; nothing tells a person to do anything.

**Memory finding (SPEC 9.1, 9.4): resolved on this Mac, with the cap raised on
an assumption.** Found by the first build: rapidocr's detector, left at its
default (`Det.limit_type` `min`, 736), never shrinks a page whose shorter side
is already past 736, so with the long side at 3300 it read the whole 3300 x 2550
page and the process reached 2.85 GB on a drawn letter page (the stage is not
the problem: a 4032 x 3024 photo grows the process by about 530 MB through the
whole stage). In the real product path - a drawn five-page scan judged through
`content_check.judge_bounded` in the pass's reading child, on the processor -
the memory watch ended the child at 2814 MB (`reading-crashed`, "it had
reached its memory limit (2 GB)").

What 9.1 did: `_build_engine` sets `Det.limit_type` to `"max"` (and not
`Det.limit_side_len`). Detection runs on a copy the engine holds to its own
2000-pixel long side, as under P283; recognition crops its words from the
3300 page. The same lines are read. Numbers on this Mac (drawn pages, counts
only, in GB of 10^9 bytes; the child's cap was 2 x 1024^3 bytes, 2.15 here):

| reading | without 9.1 | with 9.1 |
|---|---|---|
| the engine alone, a drawn unprepared 2550 x 3300 page, peak after the first call | 2.61 | 1.12 |
| the same, after the second call | 3.86 | 1.66 |
| the whole process, peak after one shipped reading of a drawn 2550 x 3300 page (stage and engine; median of three: 1.604, 1.605, 1.612) | 2.85 (first build's footprint) | 1.61 |
| the same process's footprint after that reading (median of three) | - | 1.55 |

What 9.1 left (found by the first rebuild): a multi-page scan still crossed 2
GB. The engine's working memory settles about 0.6 GB higher after its second
page (the shapes of the pages it has seen, flat after a garbage collection, so
not a leak), and the stage's allocator held about 0.6 GB after its first page.

What 9.4 did: `PROCESSOR_CHILD_MEMORY` is `4 * 1024**3` (the card's 6 GB
stays), and Sauvola takes its mean and mean of squares from single-precision
`cv2.boxFilter` calls instead of double-precision integral images. Decision
169's 2 GB was a reader at 144 dpi and a 2000-pixel long side; a 300 dpi page
needs about 2.3 GB on a Mac and more where Windows counts committed memory
(the job object was not measured), and 4 GB is the first power of two with
room. **This is the orchestrating session's assumption, held for Jason's
word**; the runbook's memory bullet, the module's comments, the curated map
and the P285 row say 4 GB, and the other option (a lower long side) undoes
his 300 dpi. Measured again on this Mac after 9.4 (drawn 2550 x 3300 pages
through `ocr.read_page`, each in a fresh `.venv/bin/python` process,
`resource.getrusage(...).ru_maxrss`, GB of 10^9 bytes; the 4 GB cap is 4.29):

| reading | peak |
|---|---|
| one page, `SHIPPED`, box filters (median of three: 1.327, 1.329, 1.326) | 1.33 |
| five pages, `SHIPPED` | 2.28 |
| five pages, `RAW` | 2.03 |

Sauvola on a 2550 x 3300 page takes 0.032 s now (median of five; 0.050 before).
The five-page scan through the reading child is no longer ended: the child
test passes on this Mac under both interpreters (3.23 s on 3.14): no
`reading-crashed`, not transient, read by the reader (it was killed at 2.1 s
before). Its last claim first read the judgment's text, which is empty by
design (decision 189), so it now asks a question: a row keyed on the form
number, `1099-INT`, whose `required_matched` shows the child read the words.
The Windows job object, which counts committed
memory, was not measured and is the office bench's to confirm.

**Second finding (not P285's, but it bit the build): the arm64 macOS wheel of
OpenCV (`opencv-python-headless==5.0.0.93`, KleidiCV) segfaults inside
`cv2.resize` for some sizes.** rapidocr's own detection resize crashes the
reading process outright - for example a 3-channel 2598 x 3300 image (resized
to 2592 x 3296), or 2596 x 3300, while 2597 x 3300 and 2600 x 3300 pass; it
reproduces with a bare `cv2.resize` and with one thread. About 5% of random
page sizes crashed at either long side (2 of 40 at 2000, 3 of 40 at 3300), so
it exists without P285, and in the child it parks a document as a crash. Not
seen on the office's Windows wheel. The build did not touch it; the real-scan
test draws its crooked page on the same canvas (below) so it does not hit it.
Worth its own row if the Mac is ever to read for real.

Seconds on this Mac (Apple silicon, processor, small models), drawn pages
only, median of five, warm engine:

| step, a 2550 x 3300 page / a 4032 x 3024 photo (held to 3300 x 2475) | page | photo |
|---|---|---|
| grey copy and held to the long side | 0.002 s | 0.006 s |
| lean measured (34 turns of a 1000 px sample, plus the level score) | 0.019 s | 0.018 s |
| turned level | 0.001 s | 0.001 s |
| Sauvola | 0.050 s | 0.045 s |
| specks | 0.010 s | 0.011 s |
| box lines | 0.029 s | 0.029 s |
| **the whole stage** | **0.11 s** | **0.11 s** |

| whole reading (render or decode, stage, engine) | shipped (prepared, 300 dpi) | raw (144 dpi) |
|---|---|---|
| a drawn scanned page (PDF, 150 dpi source) | 1.05 s | 0.45 s |
| a drawn 4032 x 3024 photo | 0.94 s | 0.50 s |

The shipped reading is about 1.05 s a page, under the 3 s the SPEC set as the
stop and far under Jason's 6 s; the stage is about a tenth of it, the rest is
the engine reading a page 2.7 times larger. A drawn five-page scan read in
this process took 5.8 s.

What `_skew_degrees` saw (best angle, then the score over the level score,
against `DESKEW_GAIN` 1.10): a level page 0.0, 1.000; two degrees +2.0, 1.676;
twelve degrees +6.0 (past the limit, at the search's edge), 1.250; the
quarter-turned W-2 photo -0.9, 1.050. The quarter-turned page is refused by
the gain rule with a margin of 0.05 only; a different drawn quarter-turn could
sit nearer the line, and the real engine reads such a page anyway. Sauvola on
the faded page (grey 150 on 230, a 15 px window): every pixel of the text drawn
without anti-aliasing is black and no pixel beyond one window of it is not
white; drawn *with* anti-aliasing, 94% of the pixels that are at least half
text and 85% of those a quarter text are black - the faint edge pixels stay
white by design, which is why the SPEC's "95% of the text's pixels" claim is
tested on hard-pixel text. On the smooth shadow Sauvola blackens 0 pixels,
Otsu 50%.

Gate of the second rebuild (SPEC 9.4), each file its own process, `.venv`
(3.14) and `.venv311` (3.11), no `-m "not corpus"`, the real reader ran (the
skips are the platform ones already there), on the final tree:

| file | 3.14 | 3.11 |
|---|---|---|
| `test_ocr` | 70 passed, 4 skipped | 70 passed, 4 skipped |
| `test_content_check` | 115 passed, 1 skipped | 115 passed, 1 skipped |
| `test_errors` | 83 passed | 83 passed |
| `test_runner` | 229 passed | 229 passed |
| `test_layers` | 31 passed | 31 passed |
| `test_single_source` | 217 passed | 217 passed |
| `test_repo_map` | 82 passed | 82 passed |
| `test_tripwire` | 23 passed | 23 passed |

`test_single_source` and `test_repo_map` were run again after this handoff,
and `test_ocr` after the test's rewrite.
`ruff check .` clean; `repo_map.py update` then `check` exit 0; `vocab_report.py
build` changed nothing. `test_reader_bench` was not rerun (the bench is
untouched by 9.4). The backtest baseline is still unrecorded (the office
prompt records it).

Tests: renamed `test_the_shipped_settings_are_the_prepared_reading_at_300_dpi`
and `test_the_grid_is_every_dpi_floor_preparation_and_tier_and_the_ablation`;
replaced the delining-off-in-the-product test with
`test_the_engine_is_handed_the_prepared_page`; added in `test_ocr`
`test_every_step_off_hands_the_engine_the_page_as_it_stands`, the skew, level,
twelve-degree and quarter-turn claims, the Sauvola, window, speck, long-side
and untouched-and-repeatable claims and the real-scan one; in
`test_reader_bench` the raw-variant, ablation, ablation-off, schema 2 and
office-prompt claims, all named as the SPEC's section 4 names them; the four
`test_content_check` claims changed as 4.2 says. The rebuild adds
`test_a_thick_stroke_is_type_and_a_thin_one_a_rule_whatever_their_length`,
`test_a_large_title_keeps_its_form_number_when_prepared` (a real-reader claim)
and `test_the_shipped_reading_of_a_scan_fits_the_reading_child` (a real
reading child, five drawn pages on the 1275 x 1650 canvas of `scanned_pdf` so
the OpenCV fault below is not hit), and changes
`test_the_engine_is_built_with_the_settings_floor_and_long_side` to expect
`Det.limit_type` `max`. None of the real-reader tests in this file carries a
skip of its own (they run wherever the models are), so neither does the new
child claim.

Where the SPEC and the code differ, and what the build did:

- **The memory finding above** was the SPEC's gap, not a departure: 9.1 and
  9.4 are built exactly. One departure from the SPEC's words in 4.1: the
  child test asks a question (a row keyed on `1099-INT`) and reads its
  answer, since the judgment's text is empty by design (Jason's ruling).
- **The box-line step is long and thin (SPEC 9.2), and the `w2_photo` fixture
  is back to its P283 form** (1100 x 260, the P283 docstring): the first
  build's page-sized canvas and its note are gone. One departure from the
  SPEC's words in `_delined_grey`: after the rule mask is dilated by
  `DELINE_GROW`, any pixel of `heavy` is taken out of it again (`rules[heavy >
  0] = 0`). Without it the SPEC's own claim - a 16 x 160 bar comes back
  unchanged pixel for pixel - fails by one row: the vertical opening's even
  kernel (`height // 40`, 82 on a letter page) drifts a pixel past the stem's
  end, outside `heavy`, and the growth carries that into the stem's last row.
  Thick ink is never whitened; thin rules and the two existing de-lining tests
  behave as before. Measured: "Form 1099-INT Interest Income" in PIL's default
  face at 150 px, over a made-up body at 46 px with a 3 px box, reads
  `Form 1099-INT Interest Income` as its first line both unprepared and
  prepared.
- **The real-scan test's crooked page** is drawn by a helper in the test file,
  `scanned_pdf`'s page turned two degrees on the *same canvas*, not
  `scanned_pdf(rotate=2)`, which grows the canvas to a size at which the OpenCV
  segfault above hits (2598 x 3300 once held). `tests/samples.py` is not
  changed.
- **Sauvola's faded-page claim** is tested on hard-pixel text (see above).
- **`_levelled`'s sign:** the angle that levels a page is the opposite of the
  way it leans, so `_skew_degrees` returns the lean (counter-clockwise
  positive, as `PIL.Image.rotate`) and the search's best trial is negated; the
  angle is rounded to a tenth (the fine step) so a page leaning exactly five
  degrees is not refused by float noise.
- **A letter page drawn at 300 dpi is 2550 x 3301**, not 3300: pdfium rounds
  the height up. `_held` therefore resizes it by one pixel (INTER_AREA, before
  the threshold, which is harmless and is what rapidocr would do itself); a
  2549 x 3300 page results. No SPEC change needed, but the "keeps its size"
  claim is tested on a drawn 2550 x 3300, not a rendered page.
- **The mactest prompt**: line 172's names changed as the SPEC says, and
  (SPEC 9.3) the same sentence now says "the 8 medium variants" and "the 13
  small variants", the grid's real counts (21 in all). Nothing else in the
  file moved. Done.
- **`tests/test_layers.py`** needed no change (the stage imports cv2, numpy and
  PIL inside functions; cv2 was already a reader's import).
- **Bench order**: `--dpi 144,300` runs in the grid's order, 300 first, whatever
  order the flag lists them in (the SPEC's "the raw ones at 300 and 144").

For the reviewer: the SPEC's own mutations to try are the deskew sign (a wrong
sign gives about 4 degrees of error and fails the two-degree test), the gain
rule (a quarter-turned page), `_held` (a 2550 x 4200 page), the speck area (a
3 x 3 dot), and Sauvola's `<=` (a solid black fill).

---

The earlier handoffs follow, unchanged.

[`SPEC-ocr-scans.md`](SPEC-ocr-scans.md) Part A (P282), **built on
`claude/ocr-scans`** in commit `ff938b7`, not yet reviewed (the review is
Opus's, in a session that did not build it) and not pushed. Part B (P283) is
a separate build, stacked on this one, and is built (below), not yet reviewed
and not pushed.

What Part A built, in the software's words: a scan or a photo that a request
accepts on its looser keywords now files under that request when the top of
the page shows the request's own form number, no other request accepted it,
the household's issuer rule passes, and the page names no other form as itself
and shows no other request's form number. The name on the page still has to
confirm a named request, and an unnamed one files by its keywords alone when
the page names nobody (Jason's ruling on Q1). Anything less parks as Read From
Scan Only, byte for byte as before. The reader's confidence floor is now the
product's own number (0.5, the same floor the reader already applied), and a
reading that comes back with no scores fails loudly. No keyword, catalog row,
store, event or cache version changed (`CACHE_VERSION` stays 13; the vocabulary
report rebuilt with no diff).

Gate, each file its own process, `.venv` (3.14) and `.venv311` (3.11), no
`-m "not corpus"`; every file passed under both:

| file | 3.14 | 3.11 |
|---|---|---|
| `test_router` | 92 passed | 92 passed |
| `test_filer` | 405 passed, 6 skipped | 405 passed, 6 skipped |
| `test_ocr` (the real reader ran, not skipped) | 44 passed, 4 skipped | 44 passed, 4 skipped |
| `test_backtest` | 21 passed | 21 passed |
| `test_content_check` | 114 passed, 1 skipped | 114 passed, 1 skipped |
| `test_api` | 505 passed | 505 passed |
| `test_runner` | 229 passed, 1 warning | 229 passed, 1 warning |
| `test_resident` | 39 passed | 39 passed |
| `test_reasons` | 58 passed | 58 passed |
| `test_layers` | 31 passed | 31 passed |
| `test_single_source` | 217 passed | 217 passed |
| `test_repo_map` | 82 passed | 82 passed |
| `test_tripwire` | 23 passed | 23 passed |
| `test_errors` | 83 passed | 83 passed |

Also: `ruff check .` clean; `repo_map.py update` then `check` exit 0 (the map
is in the same commit); `vocab_report.py build` (run with the `.venv`
interpreter, which has pytest) left no diff. The skips are the platform ones
already there (the Windows job object, `/proc`, a directory junction, and
the like). The sample-pile flow (SPEC section 4) was run on this Mac after the build,
by the orchestrator: the pile from `tests/samples.build_scratch_root` plus
`make_samples.add_container_samples`, a real pass with a throwaway data home
and settings folder, then `tracker.api state`. The zip's `scan 0002.pdf` filed
under A02 with code `matched`, reason "content matched this request's
keywords, read from a scan that shows its form number; name confirmed (Jane R.
Smith)", and evidence `1099-int` at the title, `TY2025` at the title and the
name on the first page. The five review rows left are the macro workbook, the
gsheet stub, the .docx, the .bmp and the prior-year W-2 - no scan among them.
Pass summary: filed 10, review 5, syncing 1. Not run here: a Windows check.

Where the SPEC and the code differed, none that stopped the build. Notes for
the reviewer:

- The SPEC's claim that `.gitignore` gains `.venv311/` in Part A's first
  commit was already done (`8a77916`); nothing to add.
- `test_a_scan_whose_form_number_is_only_below_the_title_parks_as_ocr_only`
  is built as the SPEC words it. Its page puts `dividend` in the title and
  "Form 1099-DIV" far below, where the form number is neither in the title
  nor the page's dominant form, so A02's verdict does not record it and the
  scan is a plain looser match. It fails with guard 1 removed outright; it
  still passes when the title restriction is merely loosened to the first
  page, which is why the review added two tests built on a page whose form
  number is the first page's dominant form
  (`test_a_form_number_shown_only_as_the_first_pages_dominant_form_parks_as_ocr_only`
  and its one-row twin). `evaluate_rules` records every matching looser
  keyword, not only the best-placed one. Each guard was mutated: guard 6
  (both halves), exactly-one (two rows on the same form number, and the
  broker's page), the issuer exit, and the title-only restriction (swapping in
  `_shows_its_form_number`, or accepting the first page) each fail a test.
- The two new filer tests each make two returns in separate roots: two
  image-only PDFs with no text are byte-identical, so a second scan dropped in
  the same return would be a Duplicate of the first, not a second reading.
- The real-reader test's quarter-turned page reads as "matched no request"
  here (the reader keeps the words but not the order); the test accepts
  parking or filing under the 1099-INT row and forbids the 1098 row, as the
  SPEC says.
- Tests added: router `test_a_scan_whose_title_shows_1099_int_files_on_the_rows_looser_keywords`,
  `test_a_scan_whose_form_number_is_only_below_the_title_parks_as_ocr_only`,
  `test_a_scan_two_requests_accept_on_their_titles_parks_with_both`,
  `test_a_scan_that_passes_the_title_guard_beside_a_loose_match_parks`,
  `test_a_sideways_reading_whose_title_lines_came_late_parks`,
  `test_a_scan_accepted_by_a_row_issuer_rows_narrow_parks_as_issuer_not_named`,
  `test_a_scan_of_last_years_1099_int_parks_and_never_files`,
  `test_a_scan_filed_on_its_form_number_carries_no_answers_and_no_split`,
  `test_a_scanned_1099_c_read_as_1099_g_beside_a_second_form_name_parks`,
  `test_a_scan_whose_page_shows_another_requests_form_number_parks`,
  `test_a_page_naming_only_its_own_form_files`,
  `test_a_page_naming_two_families_as_itself_is_decision_94s_and_never_reaches_the_scan_rule`
  (and the one rename); filer `test_a_scan_filed_on_its_form_number_still_needs_the_name_confirmed`,
  `test_a_scan_filed_on_its_form_number_into_an_unnamed_request_needs_no_name`;
  ocr `test_a_box_under_the_confidence_floor_is_not_read`,
  `test_a_box_at_the_confidence_floor_is_read`,
  `test_a_reading_without_confidence_scores_fails_loudly`,
  `test_a_real_scan_whose_title_shows_1099_int_files_on_the_rows_looser_keywords`.
  Added by the review's fixes: router
  `test_two_requests_whose_looser_keyword_is_the_same_form_number_park_with_both`,
  `test_a_form_number_shown_only_as_the_first_pages_dominant_form_parks_as_ocr_only`,
  `test_a_row_whose_only_looser_keyword_is_a_form_number_the_page_shows_below_its_title_parks`;
  and `tests/samples.scanned_pdf` gained `rotate=0` (default bytes unchanged),
  which the real-reader test's quarter-turned page now uses.

**What the pass does with a row already parked as Read From Scan Only after
the install** (read from the code, for the office prompt's before-and-after
count): nothing. A pass decides only what is new - a drop in the inbox, or a
stray in the year's folder with no row - and the only road that routes a
document it already has on record again is a re-send whose earlier row was
set aside, filed with its copy gone, or marked missing
(`filer._sort_one`). A parked row's original has already left the inbox; the
same bytes sent again are a Duplicate of the parked row (`DUPLICATE_OF_PARKED`),
not a second reading, and the scanner only re-checks filed documents against
their request's rules. So every row parked as Read From Scan Only before the
install stays parked until a person files it; only scans that arrive after it
file by the new rule. The before-and-after count on the office PC therefore
moves only on documents dropped after Part A is installed.

**Part B (P283), built on `claude/ocr-scans`** in commits `2d3ceff` (the seam)
and `ebd2f78` (the bench, its prompt, the docs and the map), stacked on Part
A's head `253a09a`; not yet reviewed (Opus's, in a session that did not build
it) and not pushed. It changes nothing the product reads.

What Part B built, in the software's words: every setting of how a page is
drawn and read - the dots per inch a PDF page is drawn at, the confidence
floor, the long side the reader shrinks an image to, whether a form's box
lines are removed first, and which size of models reads - now lives in one
place, and the shipped values are exactly what the reader did before (144
dpi, floor 0.5, long side 2000, no box-line removal, the small models; the
cache version did not move). Removing a form's box lines is built as a switch
that is off. A measuring tool, `tools/reader_bench.py`, reads a folder of
already-sorted documents once per combination of settings (36 in all) and
writes down, in counts and seconds only, how many landed where a person put
them and how long each took; its `review-codes` command counts Needs Review by
code from the `firm` command's reply. `pilot/PROMPT-reader-bench.md` is the
office session's prompt. Not the runbook and not the README: nothing a person
sees at the firm changes.

Gate, each file its own process, `.venv` (3.14) and `.venv311` (3.11), no
`-m "not corpus"`, every file passed under both. The real reader ran (nothing
in the real-reader tests skipped; the skips are the platform ones already
there). The 3.11 column ran on the final tree; the 3.14 column ran before the
last two edits below (the `DOOR_EXEMPT` line and the curated prose), and
`test_single_source` and `test_repo_map` were run again on the final tree
under 3.14 (217 and 82 passed).

| file | 3.14 | 3.11 |
|---|---|---|
| `test_ocr` | 53 passed, 4 skipped | 53 passed, 4 skipped |
| `test_content_check` | 115 passed, 1 skipped | 115 passed, 1 skipped |
| `test_reader_bench` | 15 passed | 15 passed |
| `test_layers` | 31 passed | 31 passed |
| `test_router` | 92 passed | 92 passed |
| `test_filer` | 405 passed, 6 skipped | 405 passed, 6 skipped |
| `test_scanner` | 42 passed | 42 passed |
| `test_containers` | 62 passed | 62 passed |
| `test_names` | 6 passed | 6 passed |
| `test_after_install` | 105 passed, 1 skipped | 105 passed, 1 skipped |
| `test_api` | 505 passed | 505 passed |
| `test_runner` | 229 passed, 1 warning | 229 passed, 1 warning |
| `test_resident` | 39 passed | 39 passed |
| `test_backtest` | 21 passed | 21 passed |
| `test_vocab_report` | 28 passed | 28 passed |
| `test_learned_keywords` | 17 passed | 17 passed |
| `test_single_source` | 217 passed | 217 passed |
| `test_repo_map` | 82 passed | 82 passed |
| `test_tripwire` | 23 passed | 23 passed |
| `test_errors` | 83 passed | 83 passed |

Also: `ruff check .` clean; `repo_map.py update` then `check` exit 0 (the map is
in the commit); `vocab_report.py build` left one line of diff, the recorded
input hash of `tracker/content_check.py` (the report pins its inputs, and that
file changed) and no keyword, row or count.

The shipped variant's time on this Mac (Apple silicon, processor, small
models), from a run of the real tool on two made-up image-only 1099-INT pages
- `test_a_real_scan_is_read_under_each_dpi_it_is_asked_for` asserts but does
not print its seconds: the engine loads in 0.19 s, and a page reads at 0.33 s
at 144 dpi (the shipped one), 0.45 s at 200 and 0.77 to 0.92 s at 300, all far
inside the 6-seconds-a-page ceiling; box-line removal added nothing at 144 and
200 and about 0.05 s at 300. Those are two clean drawn pages, not the firm's
paper: the office numbers are the measurement.

Where the SPEC and the code differed (none stopped the build):

- **rapidocr takes `Det.model_type` and `Rec.model_type` as its own `ModelType`
  enum, never as text** (`rapidocr/utils/parse_parameters.py` raises "must be
  Enum Type"). The SPEC said the tier name; `_build_engine` passes
  `ModelType(tier)` (`from rapidocr.utils.typings import ModelType`). Found by
  the real reader refusing to build.
- `Global.model_root_dir` is the tier's folder (the SPEC left it alone); with
  the shipped settings that is the same folder as before.
- The corpus counts: a document that is neither a text layer, a scan nor a
  photo (one no extractor reads, or whose reading failed) is in `documents` and
  in none of the three kinds, and nothing is read for it. The SPEC's schema has
  no field for it.
- `variants` also takes the four restriction flags (the prompt's time
  arithmetic uses them), and `run` requires `--out`. Each variant's row is printed
  the moment it is measured, and (after the review, below) the report is
  rewritten at the same moment.
- `tests/test_single_source.py` lists `tools/reader_bench.py` in `DOOR_EXEMPT`,
  as `tools/backtest.py` is: its folder is the firm's sorted documents, never the
  clients root. The SPEC did not name that file.
- `tests/test_repo_map.py` refuses the curated prose quoting a constant's value,
  so the notes say the cache version "did not move" instead of "stays 13".
- `test_the_bench_never_downloads_a_model` replaces `ocr._refuse_downloads`
  with a no-op so its own failing guard on rapidocr's downloader is not
  overwritten by the real refusal; the shipped variant then builds the real
  engine from the app's models.
- The office prompt's "before" numbers run on a checkout of the commit Part A
  stacks on (first written as `main`; see the review, below), and its
  `check` runs there too: the SPEC has one checkout on `claude/ocr-scans`, but
  Part A's rule is in that code, so a baseline measured there would already
  hold Part A and could not show it, and `check` reads the baseline file of the
  checkout it runs in. The prompt lists the bench reports beside the four
  before-and-after files in what comes back.
- Once, a combined `pytest` run of `test_reader_bench` and `test_ocr` printed
  `libc++abi: terminating due to uncaught exception ... recursive_mutex lock
  failed` after the summary (exit code 0); five reruns did not repeat it. It is
  ONNX Runtime's teardown on macOS at interpreter exit, the in-process engine
  the older real-reader tests already build; worth knowing if it shows up.

**Part B's review, round 1, and the rebuild** (Opus reviewed `253a09a..cc8e4a5`
against SPEC section 2; the gate had passed; product behaviour unchanged).
Ten findings: seven fixed here, three notes left as they were (8-10).

1. De-lining never rejoined a letter a rule crossed (the cut is the rule's
   thickness plus the growth's margin, wider than the repair bridged, and the
   repair re-binarised the whole page). Now the repair span is worked out per
   page, only the bridging pixels inside the removed rule go back to black, and
   nothing else on the page changes (SPEC 2.2 step 5, as amended). One new
   test, run for a 1, 2 and 3 px rule.
2. A bad catalog name could reach the screen through a file name that shifts a
   column. The bench and the backtest now say the row number and never the
   value; one new test each.
3. The office prompt's "before" checkout is the commit Part A stacks on, which
   Jason supplies as a hash beside Part B's head (today's value `dcb02c3`),
   because `main` will already hold Part A.
4. The bench rewrites its report after every variant; a variant that fails is
   recorded as not measured, with the exception's class only; a Ctrl-C writes the
   report and exits 130 with one sentence. Two new tests; one old test now
   makes the survey (not a variant's reading) fail, because a failing reading
   no longer stops the run.
5. The curated map's note on the render scale says one thing, and the
   bench's note and the repair's description follow the code.
6. The prompt's report names are fixed labels (firm, photos), never a corpus
   folder's name, and the shipped variant is the first row under the header.
7. The bench's reading does keep the safety stop (no page starts after a page
   overran 60 s or the document's 600 s); only a page under way is unbounded,
   so a slow variant can park a multi-page scan, which counts as a park. Said so
   in the bench's text, `docs/tools.md` and the prompt.

Tests added: ocr `test_delining_rejoins_a_letter_a_rule_crossed` (three
parameters); reader bench
`test_a_variant_whose_reading_raises_is_unmeasured_and_the_run_goes_on`,
`test_a_ctrl_c_writes_the_report_so_far_and_exits_130_with_one_sentence`,
`test_a_bad_catalog_is_named_by_its_row_number_and_never_by_its_value`;
backtest `test_a_catalog_no_row_may_name_is_reported_by_its_row_number_and_never_by_its_value`.
Gate after the fixes, each file its own process, both interpreters, every file
the same under both (`test_ocr` 56 passed, 4 skipped; `test_reader_bench` 18;
`test_backtest` 22; `test_content_check` 115 passed, 1 skipped; `test_layers`
31; `test_single_source` 217; `test_repo_map` 82; `test_tripwire` 23;
`test_errors` 83); `ruff check .` clean; `repo_map.py update` then `check` exit
0; `vocab_report.py build` left no diff. `SHIPPED` and `CACHE_VERSION` did not
move. SPEC section 4's office-prompt sketch was then aligned with the prompt
(the before-checkout and the fixed report labels); the prompt is the source.

Tests added: ocr `test_the_shipped_settings_are_todays_reading`,
`test_the_engine_is_built_with_the_settings_floor_and_long_side`,
`test_the_medium_tier_reads_its_models_from_the_folder_it_is_given`,
`test_the_medium_tier_without_its_models_is_unavailable_and_fetches_nothing`,
`test_using_other_settings_drops_the_built_engine_and_says_what_it_replaced`,
`test_unknown_settings_are_refused`, `test_the_floor_follows_the_settings`,
`test_delining_removes_long_rules_and_keeps_the_words`,
`test_delining_is_off_in_the_product_and_on_hands_the_engine_the_delined_page`;
content_check `test_a_page_is_rendered_at_the_settings_dpi_within_the_pixel_budget`;
reader_bench, all of section 2.5's names plus
`test_review_codes_names_what_is_wrong_with_a_reply_and_exits_2`.

[`SPEC-ui-polish.md`](SPEC-ui-polish.md): the UI and UX review of 2026-10-11.
Section 1, the no-brainers (P264), is built on `claude/ui-polish` in one
commit after a clean Opus review: one collator, keyed lookups, one draw per
page visit, no hidden letter rebuild, debounced search, timers that sleep
while the window is hidden, smaller hot paths, dead CSS gone, `color-scheme`,
no pager for one page, even filter cards, a notice's Details on its one line.
Measured on the 500-household harness: the Clients draw 31 -> 10 ms, a search
keystroke 9.7 -> 0.1 ms.

Section 2 is the menu Jason answered on 2026-10-11, one P-row per answer
(P265-P280; P269 re-decided the same day when the Date column's real content
came to light, and P272 reworded to one heading per return). Three SPECs are
written from them and build in this order, each item its own sonnet build and
Opus review:

1. `SPEC-ui-menu-small.md`: P265 (Soon tag), P266 (brand band), P267
   (underline on hover), P268 (Tax Year column only when years differ), P269
   ("Since Mar 3" / "Due Apr 15" cells), P270 (chevron at rest), P274 ("Sort Now" button), P280
   (the type stack by platform). **Built on `claude/ui-menu-small`** after
   three Opus reviews (the third with no findings); each named test file
   passed on this Mac under 3.14. Not run here: the floor interpreter (3.11),
   and `pilot/harness/interact.mjs` under real Playwright (through a
   puppeteer shim it passes every new check; nine older checks fail there
   and failed before this change: search typing, All lists 50/50, pause and
   feed, two ruling-21 checks, Show in Finder, the right-click menu). Both
   go on the next Windows check, with the SPEC's section 2 list.
2. `SPEC-ui-menu-layout.md`: P271 (Compact Rows), P272 (Needs Review as one
   flat list), P273 (notices in a right-hand panel), P275 (the household
   page's header card). **Built on `claude/ui-menu-layout`** after four Opus
   reviews (the first found Compact Rows not reaching the editor's fields,
   a CSS specificity miss; the fourth had no findings). The editor's
   Comfortable fields now draw at the 28px and 8px padding P52 wrote, where
   the general control rule had kept them at 32px and 16px. The five open
   questions (J1-J5) were built as the defaults. Not run here: the floor
   interpreter; interact.mjs under real Playwright (through the shim: no
   new failure).
3. `SPEC-ui-menu-speed.md`: P277 (the app watches the last-pass file;
   **built on `claude/ui-menu-speed-1`**, two Opus reviews, the second with
   no findings; write-to-message 263 ms on this Mac), P279
   (long lists draw only the rows in view; **built on
   `claude/ui-menu-speed-2`**, two Opus reviews, the second with no
   findings; return page at 1,050 rows 46 -> 18 ms, 10,178 -> 782 nodes), P276 (one engine process for the session; **built on
   `claude/ui-menu-speed-3`**, three Opus reviews, the third with no
   findings; a Sonnet rebuild then an Opus fix; passes, the after-install
   step, the schedule commands and set-root keep their own process; state
   296 -> 7 ms on this Mac; the office PC and the packaged build go on the
   Windows check, with: after an edit that re-reads, the error log has no
   "engine retired" and Task Manager shows the same tracker-api pid; one
   engine normally, a second only during a Sort or an overlapping click), P278 (the engine pages the firm lists; **built on
   `claude/ui-menu-speed-4`**, three Opus reviews, the third with no
   findings, a Sonnet rebuild then an Opus fix; a page turn 9-24 ms in the
   engine where the window rebuilt the whole 1.4 MB reply; the reply fell
   39%, and a leaner turn on the same view is left for Jason in SPEC §4).

Found by review 3 of P278, outside its build and older than it: a refused
clients folder's notice (SPEC-shell, Settings) is meant to carry a Retry, but
the window draws Retry only for a failed or stale notice, so none appears;
its test checks only that a retry function was handed over. Its own small
job: let `retryOf` honour a given retry for a refusal and pin the drawn button.

Left from review 1 of section 1, outside its build: after a failed return
read, Retry calls `showReturn` directly and the page keeps showing its title
only until the person moves to another page (`shellPageFailed` is reset only
in `shellGo`); its own small job.

Landed before this: [`SPEC-mac-rerun1-fixes.md`](SPEC-mac-rerun1-fixes.md), the
fixes from the Mac check's re-run 1 of 2026-10-10 (P260-P263, pull request
#36): the Login Items switch is told apart from a missing agent (P260), the
suite stands on the Linux floor's computer on a Mac (P261), an open return
page follows a scheduled pass (P262), the reader sends no telemetry (P263).
Re-run 2 of the Mac check on that build passed every fixed step.

Landed before this: [`SPEC-mac-check-fixes.md`](SPEC-mac-check-fixes.md): the fixes from Jason's
Mac check of 2026-10-10, built and landed on `claude/trusting-tesla-or0wm2`
(P256-P258), each job its own commit after a clean Opus review:

1. A running scheduled pass is drawn as "Sorting", never as Sort Failed,
   and the shell follows the last pass by itself (P256).
2. Notices carry a closed Details disclosure for the machine warnings and
   the setup findings; the schedule's registration is toasted at Start and
   at an upgrade's first open (P257).
3. The Mac check kit reads the run log's summary line, the sample pile gains
   a macro workbook, an email and a zip, and the prompt says what the app
   shows and what to record when a session's rules deny a folder (P258).
4. Jason's rulings on the SPEC's questions: Details open on the setup page;
   the household pause, the prior-year feed and the reader warning show
   their sentences under Details (P259).

What has not run: the next Mac check. Its list is the SPEC's "Not in this
SPEC" paragraph - the two Gatekeeper steps, the overnight run, a real Google
Drive folder, step 10 with the three new files, step 13, and H4-H10 named in
the prompt - plus the two cosmetic CSS points the review left (a notice with
Details has a shorter first line than its neighbours; Tab reaches Details
before Dismiss). Jason decided the SPEC's Q1-Q4 on 2026-10-11 (P259): Q1 stays
as built; Q2-Q4 landed as job 3, Details open on the setup page and the
pause, feed and reader sentences under Details.

`SPEC-cleanup.md` (P231-P237) landed before this in pull request #33.

## How a session hands over

**In the pull request description**, not in a file. The folder
`pilot/handoffs/` is gone: what a session decided is a P-row, what it built
is its commits, and what is left is the pull request's checklist. A job's
description says its branch, its commits, what it did and skipped, the
commands it ran with their last line, and what the reviewer should look at
first.

## Open for Jason

- Whether to turn GitHub Actions back on for this repository (it is off; the
  gate runs locally, `pilot/README.md` rule 4).
- The schedule stays off at Jason's word.
- Questions built as recommended meanwhile: P196 Q1-Q5
  (`SPEC-taxpayer-words.md`), P197 Q1-Q3 (`SPEC-hide-under-construction.md`),
  P199 Q1 (`SPEC-check-notes-0.3.md`).
- Check once by hand that a tooltip does not outlive its page (hover a name,
  press Ctrl+4; P202), and that a laptop at 125-150 % display scaling opens
  within its screen (older than P203).

## Left

- F6 by hand needs the schedule on.
- `run_checks.ps1` runs whole at the next Windows check.
- The production tracker's own private copy under the Claude package, and its
  `checkpoint-left-behind` pass, belong to its own repository.

## Environment notes for cloud sessions

`pip install -r requirements.lock` fails in the cloud container (a wheel will
not build) and the system `cryptography` breaks `pypdf`. Use a fresh virtual
environment and install only what the affected tests need:
`pytest==9.1.1 ruff==0.16.9 pypdf==6.19.0 openpyxl==3.1.5`, plus
`pdfplumber==0.11.10 pdfminer.six==20260107 pillow==12.3.0 pypdfium2==5.13.0
charset-normalizer==3.5.1 cryptography==50.0.1 cffi==2.1.1 pycparser==3.0`
(`test_api` and `test_build` fail without them).
