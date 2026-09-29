# Review E1 - Build E, the structure pass

Reviewer: a separate Opus 5.5 session that built nothing in Build E.
Branch `claude/keen-keller-vx7xxj`, build commits `d6b077c..6ddf71c` against the
SPEC commit `b8ad769`. Date 2026-09-29.

**Verdict: one blocking finding, two should-fix, three nits.** The blocking one
is a hidden wizard link that the new CSS makes visible again. It is a small
fix, but it changes behaviour, so it has to be fixed before this lands. The rest
of the build matches the SPEC closely, and the rendered checks hold up when I
re-run them myself.

## What was checked

- **SPEC sections 2-10 and 12, one by one, against `pilot-ui.css`,
  `pilot-style.css`, `tour.js` and `tests/test_pilot_ui.py`.** This covered the
  tokens, the type ramp, the two weights, the button shape and its four
  importances and two sizes, selected vs primary, and whether each subtle or
  danger context selector matches exactly the buttons it should. It also
  covered the command bar, the dialog action rows and the unsaved bar, inputs,
  P55, forced-colors and reduced motion.
- **Rule 1.** `git diff --stat b8ad769..HEAD` touches no line of `style.css`,
  `app.js`, `main.js`, `preload.js` or `tracker/`. `index.html` gains the one
  link line and `tour.js` the one `classList.add`, both named in SPEC 2.
- **Specificity and the cascade.** No rule in `style.css` still wins over the
  new look:
  - `.btn-primary:hover` loses to `.btn:hover` by source order and to
    `.btn:disabled:hover` by specificity (0,3,0).
  - `.mode-toggle .btn.on` has the same selector in both files, so the later
    file wins.
  - `.editor-table .ed-unlearn` is overridden for both padding and size.
  - `#btn-stop-pass`'s danger id (1,0,0) beats the command bar's
    `.toolbar > .btn:not(.btn-primary)` (0,3,0).
  - `.person .editor-actions .btn` matches only the two per-person Remove
    buttons, both in the wizard and in the editor.
  - Every 700 weight in `style.css` is overridden.
  - What does win is `.hidden`, and not in the direction intended: see
    finding 1.
- **Rendered checks, run again by me.**
  - `shoot.mjs` into my own output folder: 13 screenshots, no console error.
    They match the committed `after-*` set; the only pixel differences are in
    areas that depend on timing.
  - The builder's sweep: 0 findings in 11 scenarios. The toolbar at 1100 is
    clean. In forced-colors, all 33 buttons have borders.
  - My own probe (`scratchpad/e1/probe.mjs`) covered what the builder only
    spot-checked:
    - Hover, press, disabled, disabled+hover and disabled+press on
      primary, command-bar subtle, secondary, notice Dismiss, danger (Unfile),
      Stop, Clear lock, Open the draft file, both segmented buttons, the
      selected return and a small secondary.
    - Tab through the toolbar and the Schedule dialog. Every stop shows a 2px
      ring (blue, or Highlight under forced-colors).
    - The terms' Accept before ticking: drawn as disabled, and hover changes
      nothing. The tour's Back on step 1: disabled, subtle, and hover changes
      nothing.
    - The unsaved bar in the Schedule dialog: the text on the left, then Keep
      editing and Discard my changes (danger) on the right.
    - Every dialog's action row: Cancel then the primary at the right, with
      the spacer's display computed as `none`.
    - The toolbar at every width from 1100 to 1920 in 4px steps.
    - Forced-colors with hover: a subtle button keeps a visible border.
    - Reduced motion: transitions `0s`, and 150ms without it.
    - A scan for any element with `.hidden` that is still displayed, before
      and after the build.
- **Screenshots.** I looked at all 26 in `pilot/reviews/ui-screens/`, plus
  crops of every section of the full-height main shots and side-by-sides of
  the dialogs, terms, tour and setup. Every name in them is made up (Rivera,
  Okafor, Nakamura, `example.invalid`, Example Tax Partners). Nothing got worse
  apart from the findings below. Several problems that are visible in both sets
  were already there before this build and are not listed: the review rows' stray `0`, the
  `16 characters short...` note sitting flush with the card edge, and the
  spellings textarea inline in the wizard's help text.
- **Gate.**
  - `ruff check .`: clean.
  - `repo_map.py check`: current, 197 nodes.
  - `test_pilot_ui`, `test_pilot`, `test_tour`, `test_single_source`,
    `test_layers`, `test_repo_map` and `test_api` pass under Python 3.11.15
    and then 3.13.12: 9, 15, 8, 167, 29, 80 and 368 tests.
  - `test_single_source.py` exits 1 with all 167 passed. The only cause is the
    decision-185 tripwire in `test_the_app_opens_one_window` ("open of the
    checkout's settings file"). I reproduced the same exit 1 in the pre-build
    tree at `b8ad769` with the venv linked in, so this build did not cause it.

## Findings

### 1. BLOCKING - a hidden link shows again: "Change household details" appears when adding a return

- **SPEC:** 2 and 5.4. The file's own header also says a `display` in this
  file "would out-rank .hidden".
- **Where:** `app/renderer/pilot-ui.css:262-263`
  (`.rem-quiet, .wiz-back { display: inline-flex; ... }`). The same pattern is
  at `:400` (`.household-return`) and `:407-408` (`.chosen-badge`).
- **What is wrong:**
  - `style.css:691` is `.hidden { display: none }`, at specificity (0,1,0).
  - `pilot-ui.css` loads later and gives `.wiz-back` a `display` at the same
    specificity, so the later rule wins and `.hidden` no longer hides it.
  - `index.html:544` is `<button id="wi-household" class="wiz-back hidden">`.
    `app.js:2822` keeps it hidden whenever a return is being added to an
    existing household (`addingTo`).
  - In the after page, the computed display is `flex` in every state. In the
    before page it is `none`. My `.hidden` scan finds no other element shown
    despite `.hidden`.
  - Four other elements can no longer be hidden by `.hidden`: `#btn-open-draft`,
    `#wi-back`, `#chosen-form` and each `.household-return`. None of them is
    toggled today, but each is the same trap waiting.
- **Failure scenario:**
  1. On a household card, press **Add a return** and pick Form 1040.
  2. The request list step now shows **← Change household details**, which the
     app deliberately hides in this flow.
  3. Pressing it opens the empty **New household** step (Household, Contact,
     Shared with, Inbox link). Meanwhile the dialog is still adding a return to
     the existing household, so a person can type a "new household" that is
     never created.
  4. I reproduced this in the harness (`scratchpad/e1/addret.mjs`, screenshot
     `shots/addreturn-after-clicked.png`). The before page hides the link.
- **Fix:**
  - Declare `display` only on `:not(.hidden)`, as the file already does for
    `#eng-form:not(.hidden)`. That means `.rem-quiet:not(.hidden),
    .wiz-back:not(.hidden) { display: inline-flex }`, and the same for
    `.chosen-badge` and `.household-return`.
  - Add a test to `test_pilot_ui.py`: every rule outside `:root` that declares
    `display` has `:not(.hidden)` in its selector, with a named allow-list for
    containers that are never toggled (`.mode-toggle`).
  - Add the Add a return flow to the harness, or at least to the review
    checklist.

### 2. SHOULD-FIX - "Open the draft file" is disabled but looks enabled

- **SPEC:** 5.2 (disabled is drawn, not faded; "every control" has a disabled
  state) and 5.4 (`.rem-quiet` gets the subtle look).
- **Where:** `app/renderer/pilot-ui.css:262-284`. No `:disabled` rule exists
  for `.rem-quiet` or `.wiz-back`, and the forced-colors block at `:572-593`
  has none either.
- **What is wrong:**
  - `app.js:562` disables `#btn-open-draft` whenever no draft file exists.
    That is the harness's own main screen ("not drafted yet"), and it is every
    return before its first draft.
  - The disabled button renders navy `#14335c`, weight 600, with the pointer
    cursor. Hover still fills it with `--surface-hover` and press with
    `--surface-pressed`: measured, identical to the enabled state.
  - Before the build it was muted `#64748b`. The new look makes a dead control
    look more clickable than before.
  - The `.btn` family was handled carefully; these two non-`.btn` controls
    were missed.
- **Failure scenario:** A person on a return with no draft yet sees a confident
  navy **Open the draft file**, clicks it, and nothing happens: no message and
  no disabled cue.
- **Fix:**
  - Add `.rem-quiet:disabled, .rem-quiet:disabled:hover, .rem-quiet:disabled:active`
    (and the same for `.wiz-back`) with `color: var(--text-disabled);
    background: transparent; cursor: default`.
  - Add `.rem-quiet:disabled, .wiz-back:disabled { color: GrayText;
    border-color: GrayText }` to the forced-colors block.
  - Record it in the HANDOFF. The existing note about `.rem-stage:disabled`
    still fading is the only disabled gap the HANDOFF currently lists.

### 3. SHOULD-FIX - the "contrast themes last" test does not check "last"

- **SPEC:** 10 (`test_the_structure_pass_honours_contrast_themes_last`: the
  file ends with a forced-colors block).
- **Where:** `tests/test_pilot_ui.py:129-135`.
- **What is wrong:**
  - The regex `@media \(forced-colors: active\) \{(.*)\n\}\n?$` uses a greedy
    `.*` with `re.S`. It runs from the first forced-colors block to any `\n}`
    at the end of the file.
  - So a multi-line rule appended after the block still passes. I verified
    this by appending `.btn {\n  border: 0;\n}` to a copy.
  - That rule would strip the contrast-theme borders the test exists to
    protect.
  - The `Highlight` / `ButtonText` / `GrayText` checks also run on unstripped
    text, so those words in a comment would satisfy them.
- **Failure scenario:** A later edit adds a normal rule after the forced-colors
  block that overrides a border or outline in contrast themes. The test stays
  green.
- **Fix:**
  - Use the file's own `blocks()` parser and assert that every rule after the
    first `forced-colors` rule sits inside that media block.
  - Assert that the text after the block's closing brace, with comments
    stripped, is empty.
  - Check the three system-colour names on the stripped text of the block.

### 4. NIT - three other tests are narrower than their names

- **SPEC:** 10.
- **Where:**
  - `tests/test_pilot_ui.py:20` and `:92`: colour.
  - `:96-104`: type ramp.
  - `:107-121`: spacing grid.
  - `:138-144`: `!important`.
- **What is wrong:** I checked each gap by mutating a copy of the file:
  - The colour test passes on `color: red` and on `hsl(0 100% 50%)`. A named
    colour is a literal colour.
  - The type-ramp test passes on `font: 700 15px/1.5 sans-serif`.
  - The grid test passes on `padding-inline-start: 18px`. It also does not
    cover `inset`.
  - `!important` inside `:root` is never checked, because the test iterates
    `outside_root()`.
- **Failure scenario:** A later edit writes `font: 700 13px/1.4 inherit` or
  `color: white` in `pilot-ui.css`. The "uses only the type ramp" and
  "writes no literal colour" tests stay green.
- **Fix:**
  - Reject `font:` outright, or parse its size and weight.
  - Add a small named-colour list (or reject any bare alphabetic colour value
    other than `transparent`, `currentColor`, `inherit` and system colours) and
    `hsla?(` / `hwb(` to `COLOUR`.
  - Extend the grid properties to `*-inline-start/end`, `*-block-start/end`
    and `inset`.
  - Check `!important` on every rule, `:root` included.

### 5. NIT - a wrapped toolbar row starts 12px further in than the row above it

- **SPEC:** 6.2 (runs set apart by `margin-left: var(--sp-3)` on `#btn-edit`,
  `#btn-view`, `#btn-scan`) and 12.3 (the bar wraps cleanly).
- **Where:** `app/renderer/pilot-ui.css:345`.
- **What is wrong:**
  - When one of those three buttons starts a wrapped line, its run gap becomes
    a 12px indent.
  - With the fallback font this happens at 1160-1180px, at 1396-1592px
    (1440 and 1536 included) and at 1724-1920px (1920 included).
  - The second row's first label then starts about 12px right of where the
    picker's row starts.
  - See `scratchpad/e1/shots/tb-after-1536.png` and `tb-after-1920.png`. Before
    the build, every row started flush.
- **Failure scenario:** On a 1920x1080 or 1536x864 office screen, the command
  bar's second row looks misaligned.
- **Fix:** Put the gap on the last button of the run before it instead:
  `#btn-repair-schedule, #btn-schedule, #btn-status { margin-right:
  var(--sp-3) }`. A trailing margin at the end of a line is invisible, so
  every row starts flush and the runs still read as groups.

### 6. NIT - the docs that were not updated

- **SPEC:** 2 (files that change), and README rule 1.
- **Where:**
  - `pilot/README.md:19-22`.
  - `pilot/SPEC.md:966`.
  - `pilot/HANDOFF.md`, the Build E "Deviations" list.
- **What is wrong:**
  - README rule 1 still lists the pilot's renderer files without
    `pilot-ui.css`, and still says "the four added lines in `index.html`".
    There are five now.
  - `SPEC.md:966` repeats "the four `index.html` lines".
  - The HANDOFF deviations record the tour card's `h3` but not
    `.pilot-terms-section h3`. SPEC 4 says the terms card's `h2`/`h3` take the
    dialog title size; the build set the section headings at body 14/20 600.
    That is the right call, since six 20px headings would be loud, but it is
    not recorded.
- **Failure scenario:** The next merge from the original, or the next builder,
  checks the pilot's differences against README rule 1. It finds an unlisted
  file and a fifth `index.html` line, and either flags a false violation or
  concludes the list is not kept.
- **Fix:**
  - Add `pilot-ui.css` to README rule 1's file list and change "four added
    lines" to five, naming `SPEC-ui.md`.
  - Update `SPEC.md:966` the same way.
  - Add the terms `h3` line to the HANDOFF deviations.

No other findings. The rest checks out as described:
- The selectors in the subtle and danger contexts match exactly the intended
  buttons. That includes hidden Stop becoming danger when shown, and
  per-person Remove.
- The dialog spacer is hidden only inside `.modal-actions`, so the unsaved
  bar still pushes its buttons right.
- P55 fixes the collapsed cards without side effects: no child of `.main`
  depended on shrinking.
- Disabled buttons are drawn correctly on primary, secondary, subtle and
  danger, including hover and press on disabled.
- The forced-colors block and reduced motion behave as SPEC 9 asks.
- The letter preview is untouched.

## Notes for Jason (product questions and Windows-only checks)

1. **Two primaries in one review row (SPEC 5.7)** is still open: **File it**
   and **File it under {label}**. The tinted "where it waits" box now spans the
   full row under the reasons, so each primary leads its own block. Which one
   should lead is your call.
2. **The command bar's groups are quiet.**
   - With subtle buttons, the gap between labels is about 28px inside a run
     and about 40px between runs.
   - In the fallback font the bar still wraps at every width up to 1920, and a
     wrap can split a group across two rows.
   - Please look at it on Windows 11 with Segoe UI Variable at 1366, 1536 and
     1920. If the groups do not read as groups, a thin divider between runs
     would be a later SPEC.
3. **Only a Windows PC can confirm these:**
   - Segoe UI Variable's real widths. Re-check the wizard's Change-form row,
     the tour's six stage chips and the reminder stage label "Response
     Requested; Deadline Approaching", which wraps to two lines at 1366 here.
   - A real contrast theme (Aquatic, Desert), rather than Chromium's
     emulation: button edges, the 2px Highlight on the selected return and on
     Cards/List, and the GrayText of disabled buttons.
   - `.rem-stage:disabled` still fades to 0.55 opacity, as it did in 0.1.
     That is known and was left alone, because the SPEC says nothing about it.
4. **Smaller visual choices you may want to weigh in on:**
   - On the first-run setup screen, the empty engagement picker is now a
     260px-wide empty box.
   - The tour's buttons read Back, **Next**, Close, so its primary sits in the
     middle. Dialogs end with Cancel and then the primary.
   - The pilot badge now reads "Pilot edition 0.2" in sentence case, with 8px
     corners.
5. **The builder's workflow.** The harness never opens **Add a return**, so
   finding 1 could not show up in the builder's rendered checks. It is worth
   adding that scenario to the harness before the next UI build.
