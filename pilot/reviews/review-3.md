# Review 3 - Build D (glass theme) and Mica, pull request #9, branch `build-d`

Reviewer: a session that built nothing (Opus, high effort), 2026-09-29.
Against: `SPEC-glass.md` section 13, `SPEC-mica.md` (the code and the SPEC
itself), decisions P30-P46, the Build D and Mica entries in `HANDOFF.md`.

**Verdict: not ready to merge. 5 findings. Finding 1 must be fixed before any
further test run on a PC where `Setup.bat` has run.** The other four are
wording and test-model fixes. No finding is in the look or behaviour of the
glass theme itself.

## What was run

| Check | Where | Result |
|---|---|---|
| `test_glass` (28), `test_pilot` (11), `test_tour` (8), `test_pilot_installer` (12), `test_api` (357), `test_layers` (29), `test_single_source` (167), `test_repo_map` (80), `test_tripwire` (19), `test_errors` (83), each its own process | cloud, Python 3.11 and 3.13 | all pass, none skipped (node on PATH, so the Mica node test ran) |
| `ruff check .`, `tools/repo_map.py check` | cloud | clean; map current (198 nodes) |
| `test_glass`, `test_single_source`, `test_layers`, `test_pilot`, `test_tour`, `test_repo_map` | Jason's PC, Windows 11 build 26200, clone of `build-d` after `Setup.bat` | 323 passed, **but the decision-185 tripwire reported six reaches into the checkout's settings file** (finding 1) |
| Contrast under Mica over the whole colour cube (not only black and white) | cloud, the test's own model | passes: card 8.78, toolbar 5.3, header 8.82 worst case (finding 4) |
| `git diff origin/main...HEAD` for `app.js`, `preload.js`, `style.css`, `tracker/` | cloud | empty |

**Not run by this review, by Jason's direction** ("skip contrast sweep, check
the actual application"): the rendered contrast sweep, the four
reduced-preference emulations, the speed probe and a motion recording in the
cloud Chromium (SPEC-glass 13.6, 13.7, 13.12). A scratch harness was built
(the real `index.html`, the real engine on the made-up Smith Family root) but
the sweep was stopped before it reported. The screenshots in
`pilot/reviews/glass-screens/` were not viewed; Jason's hands-on check on the
installed build replaces them. The builder's sweep, emulation and probe
results in `HANDOFF.md` stand unverified by a second session.

**Pending: Jason's hands-on Windows check** (SPEC-mica section 8 and
SPEC-glass section 12) on the same PC. Record the answers below it when given.

## Findings

### 1. The Mica node test starts the real after-install job against the checkout (SPEC-mica 7; decision 185)

`tests/test_glass.py:657` - the stand-in Electron in `_MICA_HARNESS` resolves
`whenReady`, so the real `main.js` goes on past `createWindow()` to
`spawnTracker(["after-install"])` (`app/main.js:430-435`). On any PC where
`Setup.bat` has made `.venv`, that starts the checkout's real Python on the
real `after-install` command (the schedule and the other one-time steps of
decision 209) with the settings folder set to the checkout. The five
pretend-`win32` launches do this on Windows. The cloud has no `.venv`, so
there the command stops at `NOT_SET_UP` and the gate could not see it. On
Jason's PC the tripwire caught five of them ("open of the checkout's settings
file", one per `win32` launch) and stopped each child at its first open, so
nothing was changed. But a test must never get that far.

SPEC-mica 7 asked for "a node test that runs the real `main.js` against a
stand-in Electron" and did not say the stand-in must stop the launch job. That
gap is in the SPEC too.

**Fix:** in `_MICA_HARNESS`, also stand in for `child_process`: return a
`spawn` that records its call and returns an inert process object, and assert
in the test that no spawn happened before the window was made. Alternatively,
have the stand-in's `whenReady` return a promise that never resolves and read
the window options another way. Either way, add one line to SPEC-mica 7: the
stand-in must stop `main.js` starting any process. Re-run `test_glass` on
Windows after `Setup.bat`, and confirm that the tripwire heading does not
appear.

*Not this build's, same cause:* the sixth hit,
`tests/test_single_source.py::test_the_app_opens_one_window`, uses the same
resolving `whenReady` (`tests/test_single_source.py:217`) and is on `main`
already. It is not a finding against pull request #9. It is raised as its own
task.

### 2. SPEC-mica promises a fallback the code does not have (SPEC-mica 3)

`pilot/SPEC-mica.md:59-60` says "If the constructor throws ... the window is
exactly today's". Section 3 specifies no `try`, and `app/main.js:386-394`
has none. If `new BrowserWindow({ backgroundMaterial: "mica" })` ever threw,
the app would open no window at all. Electron ignores a material the system
cannot draw, so this is unlikely. But the SPEC states a guarantee that nothing
provides.

**Fix (SPEC only, preferred):** replace the sentence with "On a platform
that is not Windows 11 22H2+ the window is exactly today's; Electron ignores
the material where Windows cannot draw it". Wrapping the constructor would be
a further `main.js` change, beyond what P46 allows, and it is not needed.

### 3. SPEC-glass still says `main.js` is untouched (SPEC-glass 1, 2, 11, 13.1; P46)

P46 relaxes P32 for the Mica lines, but `SPEC-glass.md` was not given a
pointer to that change:
- `SPEC-glass.md:53-54`: the non-goal "Any change to ... `main.js`".
- `SPEC-glass.md:62-63`: the non-goal on window options.
- `SPEC-glass.md:84`: the fact that the window flashes `#f5f7fa`, which is
  no longer true on Windows 11, where the window starts clear.
- `SPEC-glass.md:908`: "Done when" says `git diff main -- app/main.js` must be
  empty.
- `SPEC-glass.md:955-956`: review criterion 13.1 says the same.

The Review 3 prompt covers the gap, but the next reader of SPEC-glass will not
have that prompt.

**Fix:** a one-line note under each of those lines: "Since P46,
`main.js` carries the Mica lines of `SPEC-mica.md` section 3 and nothing
else".

### 4. The Mica contrast proof models only grey wallpapers (SPEC-mica 6; SPEC-glass 10.2)

`tests/test_glass.py:384` puts only the wash over black and over white behind
the glass. The saturation step (1.6) is not monotone per channel, so a
coloured Mica under the wash saturates outside the box of the two greys. For
example, red under the wash gives green 212, below the grey box's lowest
green. So the test does not prove what SPEC-mica 6 says ("any colour from
black to white").

The same run over all eight corners of the colour cube still passes with the
same margins (toolbar 5.3:1 is the worst), so no colour on screen is wrong
today.

**Fix:** in `test_every_text_on_glass_meets_aa_contrast_over_mica`, use the
wash over the eight RGB cube corners, `itertools.product((0, 255),
repeat=3)`, instead of the two greys. In SPEC-mica 6, say "any colour" and
state the eight corners.

### 5. SPEC-mica's claim about text directly on the page is unchecked (SPEC-mica 6)

`pilot/SPEC-mica.md:93-94`: "Text that sits directly on the page (not on a
card) is unchanged from Build D and not part of this proof." Under Mica the
colour behind that text is no longer Build D's gradient. It is the 0.88 wash
over an unknown colour, so the text is unchanged but its background is not.
A mid-grey such as `--subtle` (`#64748b`) on the wash over black would be
about 3.4:1. Neither the SPEC nor the handoff names which text, if any, sits
directly on the page. The Mica sweep in `HANDOFF.md` covered text on glass
only.

**Fix:** run the rendered sweep once with the Mica class and a black page
background (Chromium's `Emulation.setDefaultBackgroundColorOverride`), and
list every text element whose nearest opaque backing is `body`. If there are
none, say so in SPEC-mica 6 in place of "unchanged". If there are some, give
them the same worst-case check as section 10.2.

## Section 13, item by item

| # | Criterion | Result |
|---|---|---|
| 1 | `index.html` only the section 3 lines; app files untouched | Holds. The lens map is a `data:` URI, the fallback section 3 allows (handoff deviation 1). `app.js`, `preload.js`, `style.css`, `tracker/` untouched; `main.js` carries the Mica lines only (P46; finding 3 for the SPEC text) |
| 2 | Tokens match section 4 | Hold. The backdrop is split into `--glass-backdrop-glows` and `--glass-backdrop-linear` with the same values (needed for the Full-level layer). The Mica tokens are SPEC-mica's |
| 3 | Concentric numbers, `corner-shape`, rim on the border | Hold. Spot = anchor + `PAD` 6 (`tour.js:20`). The rim is at `inset: 0` with `border: 0` |
| 4 | Glass on exactly 6.1 | Holds. The reminder hold line on a solid pill (`.rem-hold`, added to `GLASS_TARGETS`) is a reasoned addition, handoff deviation 4 |
| 5 | Refraction and drift only at Full; refraction only on toolbar, dialogs, terms, tour | Hold (header and cards read `--glass-filter`) |
| 6 | Motion limits, no timers, pointer light Full-only, rAF, passive, cached rectangle; probe meets 7.3 | Code holds. Probe and clip not re-run here (see above). The deviations on the overlay fade through `background-color` and on `display` in no transition are sound and keep closing instant |
| 7 | Fallback: no `backdrop-filter`, tints opaque, no animation | Rules hold on reading (both fallback blocks equal Solid, and both reset the Mica body). Not re-emulated here |
| 8 | Contrast test implements 10.2; sweep run and reported | Holds for Build D; finding 4 for Mica; the builder's sweep reported, not re-run |
| 9 | `GLASS_TARGETS` closed, every entry on the page | Holds (tested) |
| 10 | `glass.js` obeys SPEC section 2 and P44 | Holds |
| 11 | No Apple name | Holds (tested) |
| 12 | Reviewer re-runs sweep, emulations, recording; views screenshots | Not done, by Jason's direction; replaced by his hands-on check |

## Is SPEC-mica complete, consistent, and were its checks the right ones?

- **Complete:** mostly. It gives exact lines, tests, the Windows steps and a
  rollback. Its gaps are findings 1 (the node test's reach), 2 (an
  unbacked guarantee) and 5 (an unchecked claim).
- **Consistent with SPEC-glass:** yes in substance: Solid and every "asks
  for less" state stay opaque, the wash sits under the unchanged surfaces,
  and there is no new channel. SPEC-glass was not amended to point to it
  (finding 3).
- **Right checks:** the order test and the both-fallback reset test are the
  right ones. The contrast proof needs the colour cube (finding 4). The node
  test was the right idea but needed a stand-in for the launch job (finding
  1). Its section 2 facts about Electron (a clear `backgroundColor`, the
  material behind the title bar) were not verified here. Jason's step 1 on
  Windows settles them.

## Outside this pull request

- `.mcp.json` (the `fluent-ui` server pinned at 1.0.2) rides this branch. It
  was approved by Jason per `HANDOFF.md` and is not reviewed here.
- `tools/repo_map.py` `_owner_edges` now counts only code files when it
  matches a test file to its module (handoff deviation 5). It is sound, and
  `test_repo_map` passes.

## Jason's Windows check (to be filled in)

PC: Windows 11 build 26200, clone of `build-d` in
`C:\Users\User\Downloads\pilot`, `Setup.bat` run.

1. Wallpaper tint behind the title bar and page: _
2. Header dark, toolbar and cards readable on a dark and a light wallpaper: _
3. Solid opaque, Glass returns the tint: _
4. Transparency effects off: solid without restart, picker greyed with note: _
5. Badge "Pilot edition 0.2"; buttons press: _
