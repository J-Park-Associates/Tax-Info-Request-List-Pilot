# Shell S3 - rebuild 2

Rebuilder: Sonnet 5.5 at default effort. Branch `claude/friendly-archimedes-33y9uk`
(worked on as `rebuild-s3-2`, pushed to it). Last commit: see the final line of this file's
commit message; the sha is reported in the hand-back.

Scope: review 2's findings 2-7 and nothing more. The two "For Jason" departures
(`tour.js`/`pilot.js` keydown listeners against SPEC 14.1; no tooltip on a focused text box
against SPEC 8.5) are untouched and still proposed decisions 2 and 3 in `shell-S3.md`.

## Findings

1. **Review 1's F3 (ring colour in a contrast theme): still holds.** The reviewer's rule
   (`#bar #find:focus-visible, #main #notices :focus-visible, #main #page .setup
   :focus-visible { outline: 2px solid CanvasText; }`) is in `shell.css`'s forced-colours block
   and `test_the_contrast_theme_fills_and_rings_follow_spec_10_4` pins it. Not changed.
2. **`interact.mjs` timed out on a firm page with no data: fixed.** `open()` now waits for
   `#page > *, #notices > *` (something drawn) instead of `#page h1`. `interact.mjs` prints
   "all interactions pass" with finding 4's H1s gone.
3. **Selected section count and selected search caption grey on `Highlight`: fixed.** One
   rule in the forced-colours block of `shell.css`:
   `.side-section[aria-current="page"] .side-count, .find-option[aria-selected="true"]
   .find-note { color: HighlightText; }`. Measured on Needs review with the search list open:
   light contrast draws white (`rgb(255,255,255)`) on navy `rgb(5,0,73)`; dark contrast draws
   black on cyan `rgb(0,230,255)`, for both the count and the caption. I looked at both shots
   (the sidebar row and the selected option both read clearly). The contrast test now pins the
   rule.
4. **Harness pages drew an H1 on the four firm pages: fixed.** The four `h1` pushes are gone
   from `pilot/harness/pages-stub.js` (Overview, Needs review, Reminders, Clients). The
   household page keeps its name as a heading, as SPEC 6 gives it one.
5. **`shell-S3.md:74` said the last-sort line shows `scan.scanning`: fixed.** It now says the
   bar shows alone when `n`/`of` are missing, and S6 supplies no word for that case.
6. **Real-app smoke hid an error notice: fixed.**
   - The stub's `state` reply now carries `items: []` and a whole `household` block (`path`,
     `name`, `members`, `contact`, `link`, `open_years`, `pause`, `returns`, `queue`,
     `roll_year`); `items: []` alone removed the first TypeError, and the next one, in
     `renderHousehold`, showed up as soon as the smoke looked, which is why the second half of
     that block was needed.
   - `shoot.mjs` now reads `HARNESS.logged` and the visible notice text after the real-app
     run and reports either as a PROBLEM (exit 1); the summary line prints the counts, e.g.
     "0 page errors, 0 logged, no visible error". Before the stub fix the same run printed
     the TypeError and the "The app met an error of its own" notice and failed, so the check
     works.
7. **Empty crumb button: fixed.** `crumbList()` in `shell.js` leaves out the household and
   return segments when they are not in the latest list, so the path shows Clients > year
   with no unnamed control. `test_a_household_or_return_not_in_the_list_never_shows_its_path_as_a_name`
   now expects `["Clients", "2025"]`.

No finding was wrong.

## Harness

`shoot.mjs`: 81 shots, real-app line clean. `interact.mjs`: all interactions pass. Looked at
the contrast-theme shots (light and dark, Needs review with the search list open) and the
side panel: readable, the ring is `CanvasText`.

## Tests run

Python 3.11 (`/tmp/v`) and 3.13 (`/tmp/v13`), each file its own pytest process, in parallel:
`test_shell`, `test_pilot_ui`, `test_tour`, `test_pilot`, `test_single_source`, `test_layers`,
`test_repo_map`, `test_pilot_installer`. Results are in the hand-back message. `ruff check .`
clean; `repo_map.py update` then `check` current. `test_api` not rerun: no Python module the
API imports changed.
