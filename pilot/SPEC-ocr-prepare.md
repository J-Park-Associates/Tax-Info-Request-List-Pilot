# A scan is prepared before the reader reads it - SPEC

Status: written 2026-10-11 (late) from Jason's ruling of the same evening,
recorded as **P285** (`pilot/DECISIONS.md`). Cut from `main` at `10a42e9`,
which holds P282 and P283 (`pilot/SPEC-ocr-scans.md`). Built on
`claude/ocr-prepare`. **P284 stays reserved** for the shipped reader settings
the office numbers choose; after this decision it chooses among *prepared*
settings (section 3).

Source: Jason, verbatim as typed: "ocr dcouments should be preppred before
feeing the machine," - scans and photos are prepared before the reader gets
them. His "OCR Pre-processing Notes" (Google Doc, 2026-09-25) give the steps
by impact: (1) about 300 dpi - below 200 accuracy falls off a cliff, past
400-600 is wasted, upscaling recovers nothing; (2) binarization, "the
biggest lever" - Sauvola's local threshold, a window about one character
wide, k and R to explore; (3) de-skewing - even 1-2 degrees hurts; (4) noise
removal - "better to under-clean"; (5) de-lining (P283's `ocr.delined`,
off). His open item, "how to measure which pre-processing steps actually
help", is what `tools/reader_bench.py` answers; section 3 gives it the steps.

**What this changes, in plain words.**

1. **Every scanned page and photo is prepared in memory before the reader
   sees it.** A page is drawn at 300 dots per inch (today 144), turned level
   if it leans a little, made black and white by a threshold that follows the
   paper's own shading, and cleared of lone specks and of a form's box lines.
   The file is never touched; nothing is written.
2. **Every document is read once more on the first pass after the install**,
   because what the reader sees changed (the verdict cache moves to version
   14). Text-layer documents cost little; scans and photos make that pass
   slow, once.
3. **The reader bench measures the preparation**: prepared against raw, at
   144 and 300 dpi, and each step turned off one at a time, so the office
   numbers say which steps earn their place. P284 may turn a step off.

**Hard rules kept.** The four standing rules (`STANDING_RULES` in
`tracker/__init__.py`) hold, no sentence of them changes:

- *No generative AI ever reads a client financial document.* Every step is
  fixed pixel arithmetic in OpenCV and numpy, deterministic, generating
  nothing; the same page prepared twice is the same pixels (4.1). No model
  is added or fetched.
- *Originals are never altered.* The stage works on an in-memory copy of a
  page already rendered or decoded, never touches the image it is given
  (4.1), and writes nothing.
- *Nothing is guessed.* Routing is untouched: P282's six guards read the
  prepared page's words exactly as they read today's. Deskewing refuses to
  guess too: a page whose lean it cannot measure plainly, or that leans past
  5 degrees, is left as it is (1.3.2).
- *Nothing is ever sent.* No network call is added; `ocr._refuse_downloads`
  stands; the bench's report holds counts and seconds only.

Client data never enters the repository, a test, a commit, a log or a
report: every test draws its own pages from the suite's made-up names.

**Where this SPEC departs from the brief it was written from** (checked
against the code at `10a42e9`; each is argued where it is specified, and the
reviewer holds the build to the SPEC):

- `ReaderSettings()`'s defaults stay the reading before P285, named
  `ocr.RAW`; `SHIPPED` states its values field by field (1.1).
- The stage first holds a page to the settings' long side, as rapidocr would
  anyway: the threshold is then taken at the resolution the engine reads, and
  a 40-million-pixel photo cannot push the stage toward the reading child's
  2 GB cap (1.3.1).
- Sauvola's window is a hundredth of the page's shorter side - 25 px, one
  character, on a 300 dpi letter page - because a photo has no dpi (1.3.3).
- Deskewing refuses two more cases besides the ±5° bound: no plain winner
  (a quarter-turned page), and a best angle at the search's edge (1.3.2).
- Noise removal counts connected pixels instead of a median, which would
  erase a faded one-pixel stroke (1.3.4).
- `delined` keeps its Otsu steps - redundant on a black-and-white page,
  needed by the ablation's grey one - and is factored, not changed (1.3.5).
- The gate adds, per CLAUDE.md, the own test file of every module importing
  a changed one, as P283's gate did (section 6).
- Tests the brief did not name change (4.5): two pin `CACHE_VERSION == 13`,
  two pin a render scale of 2.0, one hands `read_page` an `object()` the
  stage cannot read, and the bench's tests select by `--delining`.
- The office prompt is already stale: it checks out `claude/ocr-scans`,
  which landed as PR #45 and is gone; its "after" numbers now carry P282 and
  P285 together, which the bench's raw and prepared rows separate (3.4).
- A cache bump re-reads every document's verdict, not only scans' (text is
  cheap); it does not re-route a row already parked - P282's handoff, "What
  the pass does with a row already parked" (section 2, Q2).
- `pilot/SPEC-ocr-scans.md` §3 says P284 moves the cache to 14. P285 takes
  14; P284, if it changes what is read, takes the next. That SPEC is not
  edited; the P285 row says so.

---

## 1. The stage (`tracker/ocr.py`)

### 1.1 The settings

`ReaderSettings` (frozen, `slots=True`) gains three fields, and its fields
are reordered into the order a page is processed in. Positional construction
is not used outside `tests/test_ocr.py`, whose one positional call is
rewritten (4.1).

| field | type | `RAW` (`ReaderSettings()`) | `SHIPPED` | what it is |
|---|---|---|---|---|
| `render_dpi` | `int` | 144 | **300** | a PDF page is drawn at `render_dpi / 72` |
| `confident_score` | `float` | 0.5 | 0.5 | P282's floor (unchanged until P284) |
| `max_side_len` | `int` | 2000 | **3300** | rapidocr's `Global.max_side_len`, and the long side the stage holds a page to (1.3.1) |
| `deskew` | `bool` | False | **True** | turn a page leaning up to 5° level (1.3.2) |
| `binarize` | `str` | `"off"` | **`"sauvola"`** | one of `BINARIZERS = ("off", "otsu", "sauvola")` (1.3.3) |
| `denoise` | `bool` | False | **True** | whiten lone specks (1.3.4) |
| `delining` | `bool` | False | **True** | whiten a form's long box rules (1.3.5) |
| `model_tier` | `str` | `"small"` | `"small"` | unchanged |
| `model_folder` | `str` | `""` | `""` | unchanged |

- **`RAW = ReaderSettings()`**, with a `#:` comment: the reading P283
  shipped - 144 dpi, floor 0.5, long side 2000, no step of preparation, the
  small models. The bench's raw rows are built from it.
- **`SHIPPED = ReaderSettings(render_dpi=300, max_side_len=3300, deskew=True,
  binarize="sauvola", denoise=True, delining=True)`**, with a comment: P285,
  Jason's ruling; 3300 is a letter page's long side at 300 dpi
  (`ceil(11 × 300)`, the bench's `long_side(300)`), so a 300 dpi page is not
  shrunk back to 2000 (182 dpi) by rapidocr; a legal page (14 in, 4200 px) is
  still held to 3300, about 236 dpi. `SETTINGS: ReaderSettings = SHIPPED`.
- **The detector never reads the 3300 page** (amendment 9.1). `_build_engine`
  sets rapidocr's `Det.limit_type` to `"max"` (1.4): detection runs on a copy
  the engine holds to its own 2000-pixel long side, as it did under P283, and
  recognition crops its words from the 3300 one. Without it the engine's
  memory on a letter page is 2.4-2.8 GB on this Mac, past the reading
  child's 2 GB (`PROCESSOR_CHILD_MEMORY`, decision 169, unchanged), and the
  pass ends the child as `reading-crashed`.
- The class docstring describes the new fields; its defaults are `RAW`.
  **`use_settings`** also refuses (`ValueError`) a `binarize` not in
  `BINARIZERS`, naming the three; nothing else in it changes.

### 1.2 `prepared(image, settings: ReaderSettings) -> PIL.Image.Image`

The name matches `delined`: it names what comes back, a prepared copy. One
public function, placed after `delined`:

1. When every step is off (`not settings.deskew and settings.binarize ==
   "off" and not settings.denoise and not settings.delining`) it returns
   **`image` itself** - the same object, untouched. This is what makes "raw"
   in the bench exactly the P283 reading (4.1).
2. Otherwise: a greyscale copy (`numpy.asarray(image.convert("L")).copy()`,
   `uint8`); held to the long side (1.3.1); then, each only when its switch
   is on and in this order: levelled (1.3.2), thresholded (1.3.3),
   despeckled (1.3.4), de-lined (1.3.5); returned as
   `Image.fromarray(grey, "L").convert("RGB")`.

The order is not the notes' order of impact; it is the order each step needs
its input in. Grey first: every step works on one channel, and a tax form
is one ink on paper. **Level before black and white**: a black-and-white
page turned by a fraction of a degree gets jagged, grey-edged strokes the
threshold would have to clean again; a grey page turned and thresholded after
keeps clean strokes. **Black and white before specks**: a speck is only a
speck once paper and ink are told apart. **Box lines last**: a rule is found
as a long run of ink, which is crisp on the thresholded page, and its repair
lays back black only inside the rule it whitened.

Any step on makes the page grey, deskew alone included: the engine is handed
a grey page replicated to RGB. Said so in the docstring, which also states
the rules: pure, in memory, never touches `image`, writes nothing.

### 1.3 The steps

Each is a private function on a `uint8` greyscale array, returning a new
array; constants are module-level with a `#:` comment each, after the
`DELINE_*` constants. None of them is a setting (the bench measures the
switches, not the constants; question 4).

**1.3.1 Held to the long side** - `_held(grey, long_side: int)`: when
`max(height, width) > long_side`, resized by `cv2.resize(...,
interpolation=cv2.INTER_AREA)` to `round(width × r)` by `round(height × r)`,
`r = long_side / max(height, width)`; otherwise the array as it is. Why:
rapidocr shrinks any image past `Global.max_side_len` anyway
(`rapidocr/utils/process_img.py`, `reduce_max_side`), so doing it first
takes the threshold at the resolution the engine reads (a black-and-white
page resampled afterwards turns grey at every edge again), and it bounds the
stage's memory - a photo may be 40 million pixels (`PIXEL_BUDGET`), and
Sauvola's float arrays at that size would near the processor child's 2 GB
(`PROCESSOR_CHILD_MEMORY`). Never enlarged: upscaling recovers nothing.

**1.3.2 Level** - `_skew_degrees(grey) -> float` and `_levelled(grey,
degrees)`.

*Method: projection profile.* `_skew_degrees` reduces a copy to a long side
of `DESKEW_SAMPLE_SIDE = 1000` px (`INTER_AREA`; a smaller page is used as
it is), takes its ink (`cv2.threshold(..., THRESH_BINARY_INV | THRESH_OTSU)`),
and scores each trial angle θ as the variance of the row sums of that ink
turned by θ about its centre (`cv2.warpAffine`, `INTER_NEAREST`, border 0,
same size): lines of print stacked level make tall, separate peaks; a lean
smears them. Coarse: θ from −`DESKEW_SEARCH_DEGREES` (5.5) to +5.5 in steps
of `DESKEW_COARSE_STEP` (0.5), 23 angles; fine: ±0.5 around the best in
steps of `DESKEW_FINE_STEP` (0.1), 11 angles. 34 turns of a 1000 px sample:
tens of milliseconds.

It returns the angle the page leans by, counter-clockwise positive as
`PIL.Image.rotate` turns (a level page turned by `rotate(2)` gives about
2.0), and **0.0 - leave it alone - when any of these holds**:

- the sample has no ink;
- the best angle is past `DESKEW_LIMIT_DEGREES` (5.0): the search reaches
  half a degree further than the limit precisely so that a page leaning more
  (the 12° claim) shows its best at the search's edge rather than inside it;
- the best angle's score is under `DESKEW_GAIN` (1.10) times the level score:
  no plain winner - a page turned a quarter, whose lines run down the page,
  has none, and is left for the engine, which already reads it (decision
  169, ruling 6);
- the angle is under `DESKEW_LEAST_DEGREES` (0.25): too small to be worth a
  resampling of the page.

`_levelled(grey, degrees)` turns the full page back:
`cv2.getRotationMatrix2D(centre, -degrees, 1.0)` (OpenCV turns
counter-clockwise for a positive angle), `cv2.warpAffine` with
`INTER_LINEAR`, `BORDER_CONSTANT`, `borderValue=255`, **the same canvas
size**. Same size, not expanded: an expanded 3300 px page at 5° is about
3510 px long, which rapidocr would shrink by 6% and round to 32; a paper the
size of the canvas turned level stays inside it, so nothing printed is cut
that the scanner had not already cut; and the boxes keep the page's frame,
which the existing sideways claim pins (`test_a_sideways_page_keeps_its_words`
asserts the size handed to the engine).

*Why projection profile.* `minAreaRect` over all ink measures the outline of
everything inked - a logo, a stamp or a form's layout sways it - and OpenCV
changed its angle convention in 4.5, a trap across versions. A Hough
transform needs long straight edges: a form has rules, but a letter, a
receipt or a broker's page may not, and its thresholds depend on the scan.
The profile asks the question directly - at which angle do the lines of print
stack most sharply - works with or without rules, is bounded by the range it
searches, and on a page it cannot judge finds no winner, which the gain rule
turns into "leave it alone".

*Why it matters for P282.* `_upright_lines` groups boxes into lines by their
centres, within half a box's height. A 2° lean drifts 89 px over a 2550 px
line - two lines' height at 300 dpi - so one printed line breaks into several
and the title's words can fall past `TITLE_CHARS`, failing P282's title
guard for a reason that has nothing to do with the form.

**1.3.3 Black and white** - `_sauvola(grey)` and `_otsu(grey)`.

`_otsu`: `cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY |
cv2.THRESH_OTSU)` - one threshold for the page, from its histogram.

`_sauvola`: a threshold per pixel from its window:
- window `w = max(SAUVOLA_WINDOW_FLOOR, min(height, width) //
  SAUVOLA_WINDOW_DIVISOR) | 1` - `SAUVOLA_WINDOW_DIVISOR = 100`,
  `SAUVOLA_WINDOW_FLOOR = 15`, always odd so a pixel sits at its window's
  centre. Derivation: a letter page's shorter side is 8.5 in, 2550 px at
  300 dpi; 10-point type is 42 px to the em there, and a character's advance
  is about 0.55-0.6 em, 23-25 px; a hundredth of 2550 is 25. A phone photo
  framed on its page (3300 × 2475 once held) gives 24, so 25. At 144 dpi
  (1224 px) a hundredth is 12; the floor keeps 15 pixels, enough
  neighbourhood for a standard deviation to mean something.
- box filters in single precision (amended, 9.4; integral images in
  double precision were the first build's): `g = grey.astype(float32)`;
  `m = cv2.boxFilter(g, -1, (w, w), normalize=True,
  borderType=cv2.BORDER_REFLECT_101)` and the same of `g * g` for the mean
  of the squares `sq`; standard deviation `s = sqrt(max(0, sq − m²))`.
  OpenCV's box filter is a running sum, constant time per pixel whatever
  the window, and the whole step holds four page-sized float32 arrays
  instead of two double-precision integral images of the padded page plus
  the four-corner differences. Measured on a 2550 x 3300 page: 29 ms
  against 49, 265 MB left held by the allocator afterwards against 404,
  and 0 pixels differ on a faded page and on a smooth shadow, 1 pixel in
  8.4 million on a noisy one.
- `T = m × (1 + SAUVOLA_K × (s / SAUVOLA_R − 1))`; a pixel `<= T` is ink (0),
  any other paper (255). `SAUVOLA_K = 0.2`, `SAUVOLA_R = 128`.

*Why these numbers.* R is the largest standard deviation an 8-bit grey can
show (half its range, 127.5), so `s / R` stays at or under about 1 and `T`
between `0.8 m` and `m`: a flat region - clean paper, or a smooth shadow -
is never darker than its own threshold and stays white ("won't hallucinate
ink where there's just a shadow"), while a stroke beside paper raises `s` and
falls under it. k = 0.5 was Sauvola's paper's value; a larger k lowers the
threshold and drops the faint parts of a stroke. 0.2 (scikit-image's default,
and the usual choice for degraded documents) keeps a faded stroke black: the
notes' "better to under-clean". `<=` rather than `<`, so a solid black fill
(m = 0, T = 0) stays black. What Sauvola does to a dark fill wider than its
window - a reverse-printed band - is to keep only its edges; tax forms print
few, and the bench's "otsu" and "no-binarize" rows measure it.

**1.3.4 Specks** - `_despeckled(grey)`: the ink is `cv2.threshold(grey, 0,
255, THRESH_BINARY_INV | THRESH_OTSU)` - on a black-and-white page that
splits exactly black from white, on a grey page (binarize off) it is Otsu's
ink - and `cv2.connectedComponentsWithStats(ink, connectivity=8)` labels it;
every component of area `<= DENOISE_SPECK_AREA` (2) pixels is whitened (255)
in a copy. Nothing else changes, pixel for pixel. Why 2: a dust speck left
by the threshold is one or two pixels; an i's dot is 3-4 px across at 300
dpi and 2-3 at 144 (4 pixels and up), a full stop larger. A median or an
opening was rejected: both erase a one-pixel-wide stroke and round every
letter's corners, which is exactly the fragile faded text the notes protect.

**1.3.5 Box lines** - `_delined_grey(grey) -> numpy array`: today's
`delined` arithmetic moved onto a greyscale array (steps 1-5 of
SPEC-ocr-scans 2.2, the repair as amended), **with step 3 amended (9.2): a
rule is a run of ink that is both long and thin.**

- *Long*: the opening kernels are `(max(DELINE_RULE_LEAST, width //
  DELINE_FRACTION), 1)` and `(1, max(DELINE_RULE_LEAST, height //
  DELINE_FRACTION))`, `DELINE_RULE_LEAST = 60`. A fortieth of the page is a
  letter page's rule as before (63 and 82 px at 300 dpi); the least length is
  a fifth of an inch at 300 dpi - shorter than the shortest cell edge a tax
  form draws (about four tenths of an inch), longer than any stroke of 40 px
  type - and it only bites on a canvas under 2400 px, where a fortieth falls
  below it: on the 1100 x 260 `w2_photo` fixture a fortieth of the height was
  6 px and every stem of its type was taken for a rule.
- *Thin*: `heavy = cv2.morphologyEx(ink, cv2.MORPH_OPEN,
  cv2.getStructuringElement(cv2.MORPH_RECT, (t, t)))`, `t =
  max(DELINE_THICK_FLOOR, max(width, height) // DELINE_THICK_DIVISOR) + 1`
  (`DELINE_THICK_FLOOR = 3`, `DELINE_THICK_DIVISOR = 500`; 7 px on a letter
  page at 300 dpi, 4 at 144): every pixel that lies inside a `t x t` square
  of ink belongs to something thicker than a rule. The rule mask is `(across
  | down) & ~heavy`, dilated by `DELINE_GROW` as before, and then cleared
  again where `heavy` is (`rules[heavy > 0] = 0`): the vertical opening
  kernel has an even length on a letter page (82), so a run's end drifts a
  pixel past a stem's end, and the growth would carry that into the stem's
  last row. Why: a printed
  rule is half a point to a point and a half - 2 to 6 px at 300 dpi - while
  the stem of 28 pt bold type is about 16 px and of 14 pt bold about 8. The
  first build's step took the title of a 1099-INT at 28 pt for rules and the
  reader lost its form number (`=orm 099- nterest ncome`); with the thin
  test the title reads whole at 28 and 36 pt and at 100, 117 and 150 px of
  PIL's default face, and a 3 px box rule still goes (no ink left in its
  rows). The constants are named at module level with a `#:` comment each,
  after the other `DELINE_*` ones; none is a setting.
- The known limit, not fixed here: at 48 pt bold and above the
  black-and-white step itself garbles the type (under Otsu too; the raw grey
  page reads it), and the reader is poor at 72 pt even raw. Form titles are
  8 to 20 pt; the bench's `no-binarize` row measures the rest on the
  office's paper.

`delined(image)` stays, as `Image.fromarray(_delined_grey(<image as grey>),
"L").convert("RGB")`; its two tests run unchanged (their rules are 1 to 3 px
on canvases where `t` is 4 or 5). On a black-and-white page its two Otsu
steps split exactly black from white - redundant there, harmless (one
histogram pass each), and needed when the ablation de-lines a grey page;
they stay. Its docstring drops "off in the product" and says it runs last
in the stage.

### 1.4 `read_page` and the self-test

- `read_page`: `pixels = _pixels(prepared(image, SETTINGS))`, replacing the
  `delined(...) if SETTINGS.delining else image` branch. The card-fault retry
  reads the same, already prepared, pixels (no second preparation). The stage
  runs inside the reading child, so it is bounded by the document's safety
  stop and the child's memory cap, and its seconds are in `Routing.seconds`.
  The docstring says the page is prepared first.
- `_self_test` reads its drawn line **unprepared**, as today: it tests that
  the card reads, not the paper.
- `_build_engine` adds `"Det.limit_type": "max"` to its params (9.1), with a
  comment: under rapidocr's default (`min`, 736) a page whose shorter side is
  already past 736 is never shrunk for detection, so the detector ran on the
  whole 3300 x 2550 page - about 2.8 GB on this Mac; under `max` its own
  `get_preprocess` holds any page over 1500 px to a 2000-pixel copy
  (`Det.limit_side_len` is ignored there and is not set), maps the boxes back
  and `detect_and_crop` cuts the recognition crops from the 3300 page. So
  detection is at P283's resolution and recognition at 300 dpi. Measured on
  a drawn letter page: peak 1.03 GB and 0.41 s against 2.43 GB and 0.86 s,
  the same lines read. Decision 169's cap is not touched.
- The module docstring's settings paragraph is rewritten: the stage and its
  order, `RAW`, `SHIPPED`, P285, and why the verdict cache moved.

### 1.5 Photos

`content_check._ocr_image` is unchanged: it undoes the phone's EXIF turn,
holds the photo to `PIXEL_BUDGET`, and calls `read_page`, so a photo goes
through the same stage. **The dpi does not apply to a photo**: its pixels
are what the phone took. The stage holds it to the long side (3300, where the
engine would shrink it anyway) and never enlarges it. One consequence, said
plainly: the long side rising from 2000 to 3300 lets a 4032 × 3024 photo be
read at 3300 × 2475, about 2.7 times the pixels it was read at; the photo's
own seconds are measured (section 5) and are a bench row (question 3).

### 1.6 The trade-off, said plainly

PP-OCR's models were trained on natural grey and colour crops. Pure black and
white can lower recognition on a clean, sharp scan - anti-aliased edges carry
information the threshold throws away - while it helps a faded or shadowed
one. A wrong deskew angle is worse than none. Removing box lines can clip a
character a rule ran through, which the repair only partly restores. So each
step is a switch, the stage refuses to guess an angle, and the bench measures
prepared against raw and each step alone. The product ships prepared because
Jason ruled it; the office numbers may turn a step off in P284.

---

## 2. `tracker/content_check.py`

- **`CACHE_VERSION = 14`.** Its comment: "docs/ROADMAP.md holds what each
  bump (3 to 13) was for; 14 is the pilot's P285 (`pilot/DECISIONS.md`): the
  page is prepared and drawn at 300 dpi, so every verdict on a scan or a
  photo was reached on other pixels." Every verdict row at 13 is ignored on
  load and dropped on save; the first pass after the install reaches every
  verdict again.
- `render_scale`'s docstring: "300 as shipped, so 300/72"; `_ocr_pdf`'s:
  "(300 as shipped)". The function is unchanged: `PIXEL_BUDGET` stays the
  hard ceiling (a 300 dpi letter page is 8.4 million pixels, far inside 40).
- `_ocr_image`'s docstring: the reader prepares the photo (`ocr.prepared`)
  and never enlarges it. Nothing else in the module changes.

---

## 3. The bench and its prompt

### 3.1 The grid (`tools/reader_bench.py`)

The first value of each tuple is the shipped one (`grid`'s assertion that
the shipped variant is `ocr.SHIPPED` stays):

- `DPIS = (300, 144)` - 300 is the notes' target and the shipped value; 144
  is P283's, so its raw rows are the reading before P285. 200 goes (P283's
  middle point; the notes put the cliff below it).
- `FLOORS = (0.5, 0.7)` (0.85 goes); `TIERS = ("small", "medium")`.
- `PREPS = ("prep", "raw")` - `SHIPPED`'s four steps, or every step off.
- `ABLATIONS = ("no-deskew", "no-binarize", "otsu", "no-denoise",
  "no-delining")` - the shipped settings with one step off (or, for `otsu`,
  Otsu in Sauvola's place), each by `dataclasses.replace(ocr.SHIPPED, ...)`.

**21 variants**: the main grid, 2 × 2 × 2 × 2 = 16, and the 5 ablation rows
at 300 dpi, floor 0.5, small. Every variant's `max_side_len` is
`long_side(dpi)` (unchanged: 3300 at 300, 2000 at 144). A raw variant is
`replace(ocr.RAW, render_dpi=..., confident_score=..., max_side_len=...,
model_tier=..., model_folder=...)`, a prep variant the same from
`ocr.SHIPPED`; so `dpi144-floor0.50-raw-small` equals `ocr.RAW` exactly and
`dpi300-floor0.50-raw-small` is P283's `dpi300-floor0.50-off-small`.

**Names**: `dpi<d>-floor<f>-<prep>-<tier>`, `<prep>` being `prep`, `raw` or
`prep-<ablation>` - `dpi300-floor0.50-prep-small` (the shipped one, always
first), `dpi144-floor0.70-raw-medium`, `dpi300-floor0.50-prep-otsu-small`.
Order: the shipped variant; the rest of the main grid in the order dpi,
floor, prep, tier; then the ablation rows in `ABLATIONS`' order.

`grid(dpis, floors, preps, tiers, *, ablation=True, models="")`. **Flags**:
`--prep` (comma list of `prep`, `raw`) replaces `--delining`, which goes;
`--ablation on|off` (default `on`); `--dpi` and `--floor` take the new
values. The shipped variant is always measured, whatever the flags leave out.

**The report**: `SCHEMA_VERSION = 2`. A variant's `settings` gains `deskew`,
`binarize` and `denoise` beside the fields it states today (still never the
models folder). Nothing else in the report changes; counts and seconds only.

The module docstring follows: the grid, the ablation, raw and prep, and
"draws a scanned page at 144 dots per inch" becomes history.

### 3.2 The time it takes

Let `m` be the shipped variant's per-page median, printed on the table's
first row. A 300 dpi small variant costs about `m` a page, a 144 dpi one about
half, a medium one about 2.6 times its small one (P283's figure). So:

- small main grid (8) ≈ 4 × 0.5 m + 4 × m = 6 m; ablation (5) ≈ 5 m:
  **13 small variants ≈ 11 m a page**;
- medium main grid (8) ≈ 2.6 × 6 m ≈ 16 m a page;
- **all 21 ≈ 27 m a page.** For example, 500 pages at m = 2 s is 7.5 hours.

If `pages × m × 27` passes ten hours, the small tier first (`--tier small`,
13 variants), then the medium tier at the best small dpi, floor and prep
alone (`--tier medium --dpi d --floor f --prep p --ablation off`, the
shipped variant measured again so both reports share a row).

### 3.3 `docs/tools.md`

The reader bench section: the grid of 21, the names, `--prep` and
`--ablation` for `--delining`, schema 2, and the product reading prepared
(P285); the commands block follows.

### 3.4 `pilot/PROMPT-reader-bench.md`

- Header and "For Jason": the measurement covers P282 and P285 (P283's tool,
  P285's grid). The checkout is **the branch and head Jason names** - P285's
  head on `claude/ocr-prepare`, or `main` once it has landed - never
  `claude/ocr-scans`, which is gone. The "before" checkout stays the commit
  P282 stacks on (`dcb02c3`), which holds neither P282 nor P285.
- Step 1: "Part B's head" becomes "the head Jason gives".
- Step 4: `variants` prints **the 21 names, the first
  `dpi300-floor0.50-prep-small`**; the time arithmetic of 3.2 (27, 11, and
  the 144 rows at half); the small-first order with `--prep` and `--ablation
  off`; every `--delining` goes.
- Step 5: "Part A installed" becomes "the build carrying P282 and P285
  installed"; its first scheduled pass reads every verdict again (slow once)
  and is waited for before `review-codes`. Its numbers carry both decisions.
- "Why the prompt reads as it does" gains a bullet: the bench's raw rows are
  P285's "before", on the same code, so P285 needs no second checkout.

### 3.5 `pilot/mactest/PROMPT-OCR-SCANS.md`

In the one sentence at lines 172-175 (the bench step's expectation):
"36 names and the first is dpi144-floor0.50-off-small" becomes "21 names and
the first is dpi300-floor0.50-prep-small"; "the 18 medium variants" becomes
"the 8 medium variants"; "the 18 small variants" becomes "the 13 small
variants" (9.3). Nothing else in the file is touched. (`main` has since
changed the neighbouring `--expectations` path in that step to
`made-up-expectations.csv`, PR #48; if GitHub's rebase reports a conflict
there at this lane's turn, the lane rebases locally keeping both changes,
as CLAUDE.md allows.)

---

## 4. Tests (claims)

### 4.1 `tests/test_ocr.py` - the stage

Pages are drawn in memory with PIL at letter size and 300 dpi (2550 × 3300)
unless a claim says otherwise, with `tests/samples.py`'s made-up lines.

- `test_the_shipped_settings_are_the_prepared_reading_at_300_dpi` (renamed
  from `test_the_shipped_settings_are_todays_reading`): `SHIPPED ==
  ReaderSettings(render_dpi=300, confident_score=0.5, max_side_len=3300,
  deskew=True, binarize="sauvola", denoise=True, delining=True,
  model_tier="small", model_folder="")`; `SETTINGS is SHIPPED`; `RAW ==
  ReaderSettings()` holds P283's values (144, 0.5, 2000, every step off).
- `test_every_step_off_hands_the_engine_the_page_as_it_stands` - a drawn page
  (a real PIL image), a `FakeEngine` that keeps the array it is called with:
  under `RAW`, and under `replace(SHIPPED, deskew=False, binarize="off",
  denoise=False, delining=False)`, `prepared(page, settings) is page` and the
  engine's array equals `_pixels(page)` byte for byte (dtype, shape,
  values): "raw" in the bench is P283's reading.
- `test_the_engine_is_handed_the_prepared_page` (replaces
  `test_delining_is_off_in_the_product_and_on_hands_the_engine_the_delined_page`,
  which hands `read_page` an `object()` the stage cannot read): with
  `prepared` replaced by a recorder returning a marker, `read_page` passes
  `(page, SETTINGS)` to it and hands `_pixels` the marker, under `SHIPPED`.
- `test_a_page_skewed_two_degrees_is_read_level_within_a_third_of_a_degree`
  - a page of the 1099-INT's lines and, on an otherwise empty row, two 30 px
  black squares 2000 px apart; turned with `rotate(2, fillcolor="white")`
  (same size); `_skew_degrees` gives 2.0 ± 0.3; after `prepared` with
  deskew alone, the line through the squares' centroids (a measure
  independent of the estimator) is within 0.3° of level.
- `test_a_level_page_is_left_untouched_by_deskewing` - `_skew_degrees` is
  exactly 0.0, and `prepared` with deskew alone equals the page's grey copy
  (as RGB) pixel for pixel.
- `test_a_page_skewed_twelve_degrees_is_left_alone` - turned by 12:
  `_skew_degrees` is 0.0 and the stage with deskew alone changes nothing but
  the grey.
- `test_a_quarter_turned_page_is_not_turned_by_deskewing` - the drawn W-2
  photo of `w2_photo(turn=90)`: `_skew_degrees` is 0.0 (no plain winner).
- `test_sauvola_blackens_faded_text_and_leaves_a_shadow_white_where_otsu_blackens_it`
  - two 1600 × 1000 pages. Faded: grey 230 paper, lines of text in grey 150
  (the same text drawn on a blank layer marks its pixels); after `_sauvola`
  at least 95% of the text's pixels are 0 and every pixel farther than one
  window from the text is 255. Shadow: no text, falling smoothly from 230 at
  the left edge to 100 at the right; after `_sauvola` every pixel is 255,
  after `_otsu` more than 30% are 0.
- `test_the_sauvola_window_is_about_one_character_and_always_odd` - 25 for
  2550 × 3300, 15 for 1224 × 1584, 25 for 3300 × 2475; odd for every size
  from 100 to 5000 px.
- `test_a_lone_speck_is_removed_and_an_is_dot_and_a_hairline_are_kept` - a
  white page with a 1-pixel speck, a 2-pixel speck, a 3-pixel L, a 3 × 3 dot
  and a 1 px wide, 40 px long stroke: after `_despeckled` the two specks are
  white and everything else is unchanged pixel for pixel.
- `test_a_page_longer_than_the_long_side_is_held_to_it_before_it_is_prepared`
  - a 2550 × 4200 page (legal at 300 dpi) under `SHIPPED` comes back with a
  long side of 3300; a 2550 × 3300 page keeps its size; under `RAW` a page of
  any size is never resized.
- `test_the_stage_never_touches_the_page_it_is_given_and_is_the_same_every_time`
  - the input's bytes are unchanged and two calls give equal pixels.
- `test_a_prepared_real_scan_of_a_1099_int_files_under_p282_level_and_skewed_two_degrees`
  - the real reader under `SHIPPED`: an image-only PDF drawn by
  `samples.scanned_pdf` from `lines_1099_int` (made-up payer and recipient),
  and the same lines with `rotate=2`; each routed with `route_file` against a
  made-up any-keyword 1099-INT row and a made-up 1098 row files the 1099-INT
  row with `router.MATCHED_FROM_SCAN`.
- `test_a_thick_stroke_is_type_and_a_thin_one_a_rule_whatever_their_length`
  (9.2) - on a 2550 x 3300 white canvas: a 3 px wide, 600 px tall line and a
  600 px wide, 3 px tall one are white where they were after `_delined_grey`;
  a 16 px wide, 160 px tall bar (a 28 pt bold stem) and a 160 x 16 one are
  unchanged pixel for pixel; and the 1100 x 260 `w2_photo` canvas of the
  P283 fixture, drawn as `w2_photo` draws it, comes back with exactly the
  ink it had.
- `test_a_large_title_keeps_its_form_number_when_prepared` (9.2) - the real
  reader under `SHIPPED`, a 2550 x 3300 page: "Form 1099-INT Interest Income"
  in `ImageFont.load_default(size=150)` over the 1099-INT's lines at
  `size=46` and a 3 px box around the body; the first line read from the
  prepared page contains "1099-INT", as the raw page's does (the first build
  read `orm 099 1 n:crcs: ncomc` at this size).
- `test_the_shipped_reading_of_a_scan_fits_the_reading_child` (9.1) - the
  real reader through the product's own path, `content_check.judge_bounded`
  in the pass's reading child on the processor, under `SHIPPED`: a drawn
  five-page image-only PDF (the 1099-INT's lines on each page, drawn in the
  test the way `samples.scanned_pdf` draws one page) gets a reading, not
  `reading-crashed` and not transient, OCR's (`from_ocr`), with words
  (`has_words`), and - since a judgment from the child carries no raw text
  by design - the test asks it a question: a `Questions` of one made-up
  `RowQuestion(required_keywords=("1099-INT",))`, whose answer's
  `required_matched` is true (9.4, as ruled after the second rebuild). Never
  skipped: the file's real-reader tests carry no skip, since the models
  ship with the code. The first build saw this child killed at 2814 MB, and
  the first rebuild still did, at the 2 GB cap (9.4).
- **`w2_photo`** keeps its P283 canvas (1100 x 260) and docstring; the first
  build's page-sized canvas and its note about the box-line step go (9.2).
- **Changed**: `test_the_engine_is_built_with_the_settings_floor_and_long_side`
  expects `Global.max_side_len` 3300 and `Det.limit_type` `"max"` under
  `SHIPPED`;
  `test_unknown_settings_are_refused` adds `binarize="adaptive"`.
- **Unchanged, must pass prepared**: every other claim in the file, the
  real-reader ones included; `test_a_sideways_page_keeps_its_words` holds its
  size claim because the canvas is kept and its photo is under 3300 px.

### 4.2 `tests/test_content_check.py`

- `test_the_cache_version_moved_so_a_verdict_read_sideways_is_read_again`
  and `test_a_verdict_row_at_another_cache_version_is_ignored_and_dropped_on_save`
  assert 14; each one's history text adds "version 13 was read before P285
  prepared the page".
- `test_a_giant_pdf_page_is_rendered_within_the_pixel_budget`: the letter
  page is asked at `612 × 300 / 72` by `792 × 300 / 72` (the shipped dpi);
  the giant page's claim is unchanged.
- `test_a_page_is_rendered_at_the_settings_dpi_within_the_pixel_budget`:
  under `use_settings(RAW)` a letter page is asked at `612 × 2` by `792 × 2`
  and the giant page still at the budget; put back, `render_scale(612, 792)
  == 300 / 72`.
- `test_on_every_corpus_form_the_scans_miss_verdict_equals_the_routers_kept_verdict`
  runs unchanged and must pass: no verdict rule changed.

### 4.3 `tests/test_reader_bench.py`

The stand-in reader (`_ocr_pdf` / `_ocr_image` patched) never runs the stage;
`SHIPPED_ONLY` becomes `["--dpi", "300", "--floor", "0.5", "--prep", "prep",
"--tier", "small", "--ablation", "off"]`, and every test selecting by
`--delining` selects by `--prep`.

- `test_the_grid_is_every_dpi_floor_preparation_and_tier_and_the_ablation`
  (renamed from `test_the_grid_is_every_dpi_floor_delining_and_tier`): 21
  variants, the 16 combinations and the 5 ablation rows, names as 3.1.
- `test_the_shipped_variant_is_always_measured_first`: the first is
  `dpi300-floor0.50-prep-small` and its settings are `ocr.SHIPPED`, with any
  flags.
- `test_each_variants_long_side_holds_a_letter_page_at_its_dpi`: 3300 at 300,
  2000 at 144; the shipped variant's equals `ocr.SHIPPED.max_side_len`.
- `test_the_raw_variant_at_144_dpi_is_the_reading_before_p285`:
  `dpi144-floor0.50-raw-small`'s settings `== ocr.RAW`.
- `test_each_ablation_row_turns_off_one_step_of_the_shipped_settings`: each
  differs from `SHIPPED` in exactly the one field its name says
  (`binarize="otsu"` for `otsu`).
- `test_ablation_off_leaves_the_ablation_rows_out`.
- `test_the_report_states_every_step_and_is_schema_2`: `schema == 2`; a
  variant's `settings` is exactly `render_dpi, confident_score, max_side_len,
  deskew, binarize, denoise, delining, model_tier` (never the models folder).
- `test_the_office_prompt_names_the_grid_its_first_variant_and_its_flags`:
  `pilot/PROMPT-reader-bench.md` says `len(grid())` names and the first
  variant's name, uses `--prep` and `--ablation`, and never `--delining`.
- `test_a_real_scan_is_read_under_each_dpi_it_is_asked_for`: `--dpi 144,300
  --floor 0.5 --prep raw --tier small --ablation off` gives three measured
  variants - the shipped one, then the raw ones at 300 and 144 - each with
  one `right`.
- Every other claim keeps its name and assertions, with the new flags.

### 4.4 Router and filer

`tests/test_router.py` and `tests/test_filer.py` change nothing and must
pass: they hand readings in or patch the reader, and the real reader they
reach reads prepared now.

### 4.5 What changes, for the reviewer

Renamed: `test_the_shipped_settings_are_todays_reading`,
`test_the_grid_is_every_dpi_floor_delining_and_tier`. Replaced:
`test_delining_is_off_in_the_product_and_on_hands_the_engine_the_delined_page`.
Changed: the two `CACHE_VERSION == 13`, 4.2's two render claims, the
engine's long side and detector limit, the bench's flags, names, schema and
long side. Added by the amendment (section 9): the three claims of 9.1 and 9.2
in 4.1.

---

## 5. Docs and the record

- `README.md`, the OCR paragraph (lines 457-464) gains, first: "Before it is
  read, a scanned page is drawn at 300 dots per inch and prepared in memory -
  turned level if it leans a little, made black and white, cleared of specks
  and of a form's box lines; a photo is prepared the same way. The file
  itself is never changed." No clause tells a person to do anything.
- `docs/runbook.md` §1, the list of what an upgrade does once: a new bullet
  after decision 169's ("the first pass after the install reads every scan
  and photo again"), in its words: "**Once, when P285 lands** (the prepared
  reading). Nothing to delete and no step to take. Every scan and photo is
  now drawn at 300 dots per inch and prepared before it is read, so the
  verdict cache moved and the **first pass after the install reads every
  document again** - text is quick, scans and photos are slow, once, as
  above. A row already in Needs Review stays there until a person files it;
  only documents that arrive after the install are sorted by the new
  reading." (It must not trip `test_single_source`'s one-time-step matcher:
  it gives no instruction.) The runbook names no dpi today; nothing else
  changes.
- `docs/tools.md`: 3.3.
- `docs/repo-map.curated.json`:
  - `tracker/ocr.py` `notes`: a P285 passage - `prepared`, its order, the
    steps by function and constant, `RAW`, `SHIPPED`, the long-side hold,
    `_self_test` unprepared; the P283 passage's "off in the product" and
    "nothing read changed" become history ("as P283 shipped it").
  - `tracker/content_check.py` `notes`: the render-scale sentence says "300
    dpi as shipped (P285)"; one sentence: P285 moved `CACHE_VERSION` because
    the prepared page means new verdicts. (No present-tense value of the
    constant: `tests/test_repo_map.py` refuses it.)
  - `tools/reader_bench.py` `notes`: the grid of 21, raw against prep, the
    ablation, schema 2.
- `pilot/HANDOFF.md` "Current work": what was built, in the software's words;
  the gate table; the measurements of section 5.1; every place the build
  departed from this SPEC.
- `pilot/DECISIONS.md` row **P285** (written with this SPEC). P284 stays
  reserved for the office numbers, now choosing among prepared settings.
- `docs/ROADMAP.md` is `main`'s log and is not edited.

### 5.1 What the build measures and records in the handoff

On this Mac (Apple silicon, processor, small models), P283's builder read a
drawn page in 0.33 s at 144 dpi and 0.77-0.92 s at 300. The build records,
from drawn pages only: the stage's seconds step by step on a 2550 × 3300 page
and a 4032 × 3024 photo (median of five); a whole reading at `SHIPPED` and at
`RAW`, page and photo; the stage's peak memory on the photo (`ocr._footprint`
before and after), against the child's 2 GB; and the gains `_skew_degrees`
saw on the level, 2°, 12° and quarter-turned test pages, against
`DESKEW_GAIN`; and (9.1) the whole process's peak footprint after
one shipped reading of a 2550 x 3300 page with the detector held, against
the child's 2 GB, and the outcome of the five-page scan through the reading
child.

Jason's ceiling is 6 s a page (decision 127, D-2). If the shipped reading
passes 3 s a page on this Mac, the build stops and says so before review: the
office PC is slower.

---

## 6. Build order and gate

One sonnet build on `claude/ocr-prepare`, then an Opus review (high effort)
in a session that did not build it; a finding that survives one rebuild is
Opus's to fix. Build order: sections 1, 2, 3, then the docs and the map.

The gate, in the worktree, before any push (decisions 207 and 211, the
2026-09-29 rule):

1. Dead code first, in `tracker/ocr.py`, `tracker/content_check.py`,
   `tools/reader_bench.py` and the changed test files (the `--delining` flag,
   `DELININGS`, the old grid constants and any helper they leave unused go).
2. The affected test files, each as its own process, under **both**
   interpreters - the office's (`.venv`, 3.14) and the floor (`.venv311`,
   3.11) - with no `-m "not corpus"`:
   - changed / own: `test_ocr`, `test_content_check`, `test_reader_bench`;
   - the own file of every module importing `ocr` or `content_check` (P283's
     list): `test_router`, `test_filer`, `test_scanner`, `test_containers`,
     `test_names`, `test_after_install`, `test_api`, `test_runner`,
     `test_resident`, `test_backtest`, `test_vocab_report`,
     `test_learned_keywords`;
   - guards: `test_layers`, `test_single_source`, `test_repo_map`,
     `test_tripwire`, `test_errors`.
   After review fixes, only the files the fix touches run again.
3. `python -m ruff check .`
4. `python tools/repo_map.py update`, then `check` (exit 0), the map in the
   same commit as the code.
5. `python tools/vocab_report.py build`: the only diff expected is the
   recorded input hash of `tracker/content_check.py`; any keyword, row or
   count in the diff is a finding.
6. The backtest baseline is still unrecorded; the office prompt records it
   on the "before" commit.

Nothing is pushed until Jason says so; then one draft pull request, marked
ready once (decision 211), landed with a merge commit. No `windows` label
(no lock, atomic replace or path handling); a Windows check, if asked for,
runs step 2's files and repeats only the hands-on scan steps.

---

## 7. Jason's rulings

- **Preparation is built into the reader and on in the product** (2026-10-11,
  late: "ocr dcouments should be preppred before feeing the machine,"):
  `SHIPPED` is prepared, at 300 dpi, and the cache moved.
- **His notes (2026-09-25) are the steps.** Their order and every constant
  are this SPEC's (section 1), each with its reason.
- **P284 stays reserved** for the office numbers (P283's ruling).

---

## 8. Questions for Jason

Each has a default the build follows unless Jason rules otherwise before it
starts.

**Q1 - two slow passes this season.** P285 moves the verdict cache now, so
the first pass after its install reads every document again; P284, if the
office numbers change a setting, moves it again. Not moving it would leave
filed scans' statuses resting on the old reading, two readings disagreeing
in one record. *Default: move it now; accept a second slow pass at P284.*

**Q2 - rows already in Needs Review.** As after P282, a row already parked
as Read From Scan Only stays parked until a person files it (a pass decides
only what is new). Reading those scans again would be a decision of its own
(a one-time re-route, built into installation per decision 209). *Default:
no; parked rows stay for a person.*

**Q3 - photos read larger.** The long side rises from 2000 to 3300 for
every image, so a phone photo is read at about 2.7 times the pixels it was:
sharper, and slower. A photo could be held to 2000 while a scanned page gets
3300 (one more setting). *Default: one long side for both; the bench reports
photo seconds on their own and P284 can split them if the photos run long.*

**Q4 - Sauvola's k and R.** The notes list k and R "to explore". This SPEC
fixes them (k 0.2, R 128) and the bench measures Sauvola against Otsu and
against no threshold, not k against k: each k would add a row per dpi and
floor to a night that is already full. *Default: fixed now; if the Sauvola
rows disappoint, P284 adds a k row or two.*

---

## 9. Amendment after the first build (2026-10-12)

The first build (commits `3ff65bbe`, `3ed9567a`, `e52e514e` on
`claude/ocr-prepare`) built sections 1-6 as written and reported two things
the SPEC had not seen. Both were measured again by the orchestrating session
before this amendment; the numbers are in the sections it changes. Jason's
rulings (section 7) and the section 8 defaults are untouched: 300 dpi, the
long side 3300, every step on, the child's cap as decision 169 set it.

**9.1 The engine, not the stage, broke the memory cap.** The SPEC bounded the
stage's memory (1.3.1) and never asked what the detector does with a 3300
page: rapidocr's `Det.limit_type: min` leaves it whole, and the detector
needs about 2.8 GB on this Mac, so the pass's reading child was killed
(`reading-crashed`, "reached its memory limit (2 GB)") on a five-page drawn
scan. The remedy is one engine parameter, `Det.limit_type: "max"` (1.1,
1.4): detection on a 2000-pixel copy as under P283, recognition on the 300
dpi page. 1.03 GB against 2.43 on a drawn letter page, the same lines read,
and faster. Tests in 4.1; the handoff records the footprint (5.1). Raising
`PROCESSOR_CHILD_MEMORY` or lowering the long side were the build's two
options; neither is taken, since neither was needed.

**9.2 The box-line step ate large type.** The first build enlarged the
`w2_photo` fixture to a page-sized canvas because the step took every stem of
its 40 px type for a rule, and said so. Measured on a letter page at 300 dpi,
the same step took the stems of a 28 pt bold title for rules and the reader
lost the form number the title guard (P282) depends on - a scan that should
file would park. A rule is now long *and* thin (1.3.5): a least rule length
of 60 px, and a thickness test that keeps any run thicker than a printed
rule. 28 and 36 pt titles, and PIL's default face at 100 to 150 px, read
whole; a 3 px box rule still goes; the P283 fixture comes back pixel for
pixel and is restored. What stays open is written down in 1.3.5: at 48 pt
bold and above the black-and-white step itself garbles type, which the
office bench's `no-binarize` row measures.

**9.3 The Mac check prompt's counts** (3.5): the sentence the SPEC named
also counted "18 medium" and "18 small" variants; it now says 8 and 13.

**9.4 The reading child's cap, and a lighter threshold (after the first
rebuild, 2026-10-12).** With the detector held (9.1) a one-page reading peaks
at about 1.6 GB on this Mac, but a multi-page document still crossed the 2
GB line: the engine's own working memory grows from the first page to the
second and settles about 0.6 GB higher (1.05 GB after one page, 1.54 after
two, 1.68 after five, measured on the engine alone with the detector held;
flat after a `gc.collect()`, so not a leak - the shapes of the pages it has
seen), and the stage's allocator keeps about 0.6 GB after its first page,
0.4 GB of it Sauvola's. Five pages read in one process under `SHIPPED`
peaked at 2.24 GB (`RAW` through the same path, measured by the second
rebuild: 2.03 GB; the first rebuild's 1.31 GB for `RAW` came through
`open_and_read` and was not reproduced), and the five-page child test of
4.1 ended as `reading-crashed` in every run. After 9.4: one page 1.33 GB,
five pages 2.28 GB, and the child test passes under both interpreters. Two things follow:

- *The cap.* `PROCESSOR_CHILD_MEMORY` becomes `4 * 1024**3` (4 GB); the
  card's 6 GB stays. Decision 169 set 2 GB for a reader at 144 dpi and a
  2000-pixel long side; Jason's 300 dpi ruling (section 7) is a page read at
  2.7 times the pixels, and the honest need is about 2.3 GB on this Mac,
  with Windows counting committed memory, which runs higher than a physical
  footprint. 4 GB is the first power of two with room above that; one child
  runs per pass, and this Mac has 24 GB. **This is the orchestrating
  session's assumption, pending Jason's ruling**: decision 169 (and 248,
  the watch off Windows) are his; the SPEC's own options were this or a
  lower long side, and a lower long side undoes his 300 dpi. One constant
  reverses it. Every sentence that states the number follows the constant:
  the error wording already does (`ReadingChild._memory_words`); the module
  docstring, the `_build_engine` comment, `docs/runbook.md` §(the helper
  process, "may use at most 2 GB on the processor") and the curated map's
  `tracker/ocr.py` note say 4 GB; the tests of `tests/test_ocr.py` that pin
  the figure (`test_the_child_memory_caps_are_decision_169s` or however the
  file names the `(2 * 1024**3, 6 * 1024**3)` claim, the `"(2 GB)"` error
  wording claim, and any docstring that says 2 GB) move to 4 GB in their
  claims and docstrings. `pilot/DECISIONS.md`'s P285 row gains one
  sentence: the processor child's cap is 4 GB from P285 (decision 169
  amended), assumed by the orchestrating session on the numbers above and
  held for Jason's word. README names no figure.
- *The threshold.* Sauvola moves to single-precision box filters (1.3.3 as
  amended): the same pixels to one in eight million, faster, and 140 MB
  less held by the allocator after the first page. Its docstring says box
  filters, not integral images; `test_the_sauvola_window_is_about_one_character_and_always_odd`
  and the faded-page claim are unchanged and must pass as they stand.

After both, the five-page child test must pass on this Mac, and the
handoff records the five-page in-process peak under `SHIPPED` and `RAW`
again, and the one-page peak with the box filters.

The rebuild that built 9.1-9.3 departed from the SPEC in one place that is
now the SPEC: the `rules[heavy > 0] = 0` line of 1.3.5. Its report that
`test_reader_bench` never checks the Mac prompt's sentence stands; no test
is added for it.

**Not P285's, recorded for its own row:** the arm64 macOS wheel of OpenCV
(`opencv-python-headless` 5.0.0.93, KleidiCV) segfaults in `cv2.resize` for
some sizes (for example 2598 x 3300 and 2596 x 3300; 2597 and 2600 pass),
about one page size in twenty, with or without P285, inside rapidocr's own
detection resize; in the child it parks the document as a crash. The office
PC's Windows wheel does not show it. The Mac is a viewer and build machine,
not the one that runs a clients root; the row waits for Jason.

**The rebuilds:** sonnet, on `claude/ocr-prepare`; the first built exactly
9.1-9.3 (commits `708af6c8` to `fc62897c`), the second builds exactly 9.4
and the tests and docs it names, then the gate of section 6 on `test_ocr`,
`test_content_check`, `test_errors`, `test_layers`, `test_single_source`,
`test_repo_map`, `test_tripwire` and, since the runbook changes,
`test_single_source` again is enough. The first rebuild's scope was exactly 9.1-9.3 and the
tests and docs they name (the `_build_engine` comment, the `DELINE_*`
constants and docstring, the curated map's `tracker/ocr.py` note gains one
sentence on each, `pilot/HANDOFF.md` "Current work" gains the new
measurements and drops the blocking finding), the gate of section 6 on the
files the fixes touch (`test_ocr`, `test_content_check`, `test_layers`,
`test_single_source`, `test_repo_map`, `test_tripwire`, `test_errors`; ruff;
the map; the vocabulary report), then the Opus review of the whole branch
against this SPEC as amended.
