# Shell S3 - review 1

Reviewer: a separate Opus 5.5 session at high effort. It did not build S3. Date: 2026-09-29.
Branch `claude/friendly-archimedes-33y9uk` at `622b440`, diffed against `0776ea6`.
Checked against SPEC-shell sections 1, 3-5 (the page's side), 6 (common states),
6.8, 8.1-8.7, 10, 11, 12, 14 and 16 (S3's row).

**10 findings** (F1-F10). F1 loses data. F2 makes the selected section
unreadable in a contrast theme. The rest are smaller mismatches with the SPEC.

## What was run

- Python 3.11 (`/tmp/v`) and Python 3.13 (a fresh venv with the pinned
  packages), each file in its own process, in parallel: `test_shell` (29),
  `test_pilot_ui` (11), `test_tour` (8), `test_pilot` (18), `test_single_source`
  (167), `test_layers` (29), `test_repo_map` (80), `test_api` (368),
  `test_pilot_installer` (12). All pass under both interpreters.
- `ruff check .`: clean. `tools/repo_map.py check`: current (276 nodes).
- Harness: `shoot.mjs` took 81 shots (0 problems, and the real `app.js` gave 0
  page errors). `interact.mjs` passed every check. I looked at these shots,
  light and dark, at 1100x700 and 1400x900: Overview, Needs review, household,
  return, setup, search, loading, sort running, sort failed, locked, counts
  failed, tooltip by mouse and by keyboard, the sheet frame and forced colours.
  I also ran my own Playwright probes: long path segments at 1100, the tooltip
  on the disabled sort icon, Esc in search, the F6 cycle, forced colours with
  and without `forced-color-adjust`, and File > Change clients folder on the
  real `app.js`.
- I recomputed a sample of contrast pairs from SPEC 10.2 myself: `--text-caption`
  on `--bg-selected` (4.91 / 5.38), `--link` on `--bg-hover` (11.56 / 8.1),
  `--scroll-thumb` on `--bg-page` (3.12 / 4.10), `--border-input` on `--bg-raised`
  (3.34 / 4.05), `--st-attention` on `--bg-page` (7.8 / 9.44), `--focus` on
  `--bg-nav` (4.73 / 8.16), `--accent` on `--bg-selected` (10.46 / 7.48) and
  `--on-accent` on `--accent` (12.67 / 9.78). Every one matches the table.
  Pairs the shell draws that the table leaves out also pass:
  `--link` on `--bg-pressed` (10.28 / 7.15), `--text-caption` on `--bg-nav-hover`
  (5.0 / 6.37) and `--text-caption` on `--bg-pressed` (4.82 / 5.14). Every token
  value in both `:root` blocks matches the table in 10.1.

## These hold

- `app.js` gained only the six seams: `shellVocabulary`, `shellAdopt`,
  `shellNeedsRoot` (2 call lines), `shellChanged` (4 call lines), `shellProgress`
  (2 call lines) and `shellKey`, which runs first in the one listener. That is
  11 one-line calls. No card code changed.
- The standing rules hold. The new files make no network call (the guards
  test and my own reading agree), nothing reads a document, and nothing is
  sent. The CSP is unchanged, and there is no inline script, no inline style
  and no `innerHTML`.
- Every icon has an accessible name and a tooltip of five words or fewer:
  `#sort`, `#sheet-close` and `#find` get both from `data-tip-key`, and the
  done mark gets `role=img` plus its name. The tooltip also shows on the
  disabled sort icon ("Open a client to sort").
- Reduced motion works: `pilot-ui.css` sets every duration to 0 with
  `!important`, which also covers the sheet's keyframes.
- Spacing sits on the 4/8/16/24/32/48 grid, and line heights land on 4px.
- The path cuts long names correctly at 1100. The household segment shrank
  to 146px and the current one to 238px. Both are cut with "…" and carry the
  tooltip. Clients and the year never shrink, and nothing scrolls sideways.
- The search list works: it folds accents, shows at most 8, lists households
  first, shows "No match" as a disabled option, and Esc clears and closes it.
  F6 cycles side panel > path row > page.
- The wording is exactly SPEC 11.4 in the stub, and the tour's lines match
  `wording-shell.tsv` row for row.

## Findings

### F1 - File > Change clients folder… wipes the firm's name and phone

- **Where:** `app/renderer/shell.js:557-558` (the setup page seeds its fields
  from `#firm-input` and `#phone-input`), `:569-570` and `:573` (Start copies
  them back and calls `saveRoot()`), and `:608-610` (`shellChangeRoot`).
  `app/renderer/app.js:2222-2224` fills `#firm-input` and `#phone-input` only
  when `listed.needs_root` is set.
- **SPEC:** 6.8 says the setup page is reached "at first run, and File > Change
  clients folder…". Choosing a folder must not rewrite other settings. S3's
  row allows no behaviour change outside the shell.
- **Code:** On an ordinary launch `#firm-input` and `#phone-input` stay empty,
  because only the `needs_root` branch fills them. I checked this on the real
  `app.js` in the harness: after `shellChangeRoot()`, `#setup-firm` and
  `#setup-phone` are `""`. A person picks the new folder and presses Start.
  `saveRoot()` then sends `firm: ""` and `phone: ""`. `_cmd_set_root` calls
  `set_firm("")` and `set_firm_phone("")` for any value that is not None
  (`tracker/api.py:4648-4651`), so the firm's name and phone are erased
  silently. The final-notice reminder letter prints both.
- **Smallest fix:** In `shellChangeRoot()` (or in `setupPage()` when
  `shellRootSet` is true), seed the fields from the vocabulary, as `app.js`
  does at first run:
  `$("firm-input").value = vocab.firm || ""; $("phone-input").value = vocab.settings.phone || "";`.
  Add a node test: after `shellChangeRoot()` the two setup fields show the
  kept values.

### F2 - In a contrast theme, the selected section's name cannot be read

- **Where:** `app/renderer/shell.css:574`, and the same pattern at `:579`
  (the selected search option and the focused row).
- **SPEC:** 10.4 says the selected section and the focused row use
  `Highlight` / `HighlightText`, and must be readable.
- **Code:** The computed colours are right. But Chromium paints its
  forced-colours readability backplate (`Canvas`) behind the text, so
  `HighlightText` lands on a `Canvas` plate. In the harness that is white on
  white: "Clients" disappears (`forced-colors-1100x700.png`). The handoff blames
  the emulator's Highlight opacity. It is the backplate: the same page with
  `forced-color-adjust: none` on that one rule draws "Clients" legibly.
  Chromium paints the backplate on Windows too, and in a dark contrast theme
  both `HighlightText` and `Canvas` are dark.
- **Smallest fix:** Add `forced-color-adjust: none;` to the three
  forced-colours rules that fill with `Highlight`:
  `.side-section[aria-current="page"]`, `.find-option[aria-selected="true"]`
  and `.rows:focus-visible .row.is-active`. They already name only system
  colours, so nothing else changes. Check the shot again.

### F3 - The contrast-theme focus ring is `Highlight`; the SPEC says `CanvasText`

- **Where:** `app/renderer/shell.css:587`.
- **SPEC:** 10.4 says "the selection pill, the focus ring, hairlines, the sheet's
  edge and notices use `CanvasText`".
- **Code:** `:focus-visible { outline: 2px solid Highlight; }`. The focused
  row's ring (`:580`) correctly uses `CanvasText`.
- **Smallest fix:** `outline: 2px solid CanvasText;`.

### F4 - Firm pages draw an H1 in the loading, failed and fallback states

- **Where:** `app/renderer/shell.js:498` (`routeTitle()` returns the section
  name for firm levels), which feeds `:533`, `:537` and `:544`.
- **SPEC:** 6 says "Firm pages (Overview, Needs review, Reminders, Clients)
  have no H1" (P75). The loading state is "the page's frame at once (H1 from
  `list` where there is one)", and a failed read "with nothing drawn yet
  draws only its frame".
- **Code:** In the loading shot and the counts-failed shot, an H1 "Overview"
  sits under a path that already says "Overview" beside the selected section.
  The name appears three times, which is exactly what P75 removes.
- **Smallest fix:** Make `routeTitle()` return `""` for `FIRM_LEVELS`.
  `shellLoading("")` already leaves the title out. At `:537` and `:544`, draw no
  H1 when the title is empty (`page.replaceChildren()`).

### F5 - The path can show a folder path as a segment name

- **Where:** `app/renderer/shell.js:323` (`household ? household.name : route.household`)
  and `:335` (`ret ? ret.return_name : route.ret`).
- **SPEC:** 11.1 says "No path of any kind". The overview (section 0) says
  "no path is ever shown".
- **Code:** A route's `household` and `ret` are the API's full paths
  (`shell.js:34`). When the household or return is not in the latest `list`,
  for example after F5 while that folder was renamed or removed, the segment
  prints the whole path. `routeTitle()` (`:500`, `:503`) already falls back to
  `""` for the same case.
- **Smallest fix:** Fall back to `""` in both places, matching `routeTitle()`.

### F6 - The last-sort line says "Scanning…", which is not an approved word

- **Where:** `app/renderer/shell.js:275` (`: vocab.scan.scanning`).
- **SPEC:** 8.3 says the Sorting state reads "Sorting {n} of {total}". 11.1
  says never write "scan". P66 and P84 say the approved table is the only
  source of words, and `scan.scanning` has no row in `wording-shell.tsv`.
- **Code:** At the start of every sort, until the first numbered progress
  line arrives, the side panel's foot reads "Scanning…".
- **Smallest fix:** While `n`/`total` are unknown, draw only the bar with no
  text line. Or ask Jason for a word and have S1 add the key. Do not borrow
  `scan.scanning`.

### F7 - Two tour step titles are not the SPEC's: "Scan" and "Needs Review"

- **Where:** `app/renderer/pilot-content.js:112` (`"title": "Scan"`) and `:136`
  (`"title": "Needs Review"`).
- **SPEC:** 12's anchor table names these steps "Sort" and "Needs review".
  11.1 says sentence case and never "scan". The handoff's proposed decision 5
  says "the approved table has no row for them". But section 12 does give the
  words.
- **Smallest fix:** Change the two titles to `"Sort"` and `"Needs review"`,
  and drop proposed decision 5, or narrow it to the titles that already match.

### F8 - Section names start 24px from the side panel's edge; the SPEC says 16px

- **Where:** `app/renderer/shell.css:69`
  (`padding-inline: var(--sp-4) var(--sp-2)`).
- **SPEC:** 3.3 says "Sections: 40px rows, 16px from the panel's edges
  (`margin-inline: var(--sp-2)`, `padding-inline: var(--sp-2)`)".
- **Code:** The margin is 8 and the start padding is 16, so the name sits at
  24px (see any shot: "Overview" at x=24). The end padding is 8, which is
  correct.
- **Smallest fix:** `padding-inline: var(--sp-2);`.

### F9 - The handoff's "Loud failures" list leaves out four hidden warnings, and the "locked" shot fakes the notice

- **Where:** `pilot/handoffs/shell-S3.md:85-92` and
  `pilot/harness/shoot.mjs:52`.
- **SPEC:** 8.4 lists the notices S4 must draw. S3's row owns "notices'
  placement", and the handoff is what S4 reads.
- **Code:** These are inside `#legacy` (hidden) and are drawn nowhere now:
  the reader warning, the machine-warnings block, `#last-pass`,
  `#after-install`, `#lock-notice`, `#banner` and the "clients folder set" line.
  The handoff lists all of those. It leaves out:
  - `#misfits-card`: "{n} folders skipped", with Show (E34).
  - `#room-card`: "Names shortened to fit" (E35).
  - `#household-two-years`: "Two years open" (E46).
  - `#household-paused` and `#btn-accept-folder-name`: "Folder renamed" with
    Accept (E47). The household's sorting stays paused until someone accepts,
    so this one is a real silent failure.

  Separately, the "locked" scenario calls
  `notice({sentence: "In use on FRONT-DESK", kind: "locked"})` itself
  (`shoot.mjs:52`). The real lock notice (`#lock-notice`) is hidden. The shot
  and the handoff's "locked (with its notice)" therefore show a notice the
  real app would not draw.
- **Smallest fix:** Add the four to the handoff's list for S4. Say in the
  handoff (or in a comment on that scenario) that the locked notice is the
  harness's stand-in until S4 moves `showLock` to a notice.

### F10 - `shell.css` writes a second 3px size, and `pilot-ui.css` adds a size token nothing uses

- **Where:** `app/renderer/shell.css:181` (`text-underline-offset: 3px`) and
  `app/renderer/pilot-ui.css:48` (`--size-menu-row: 28px`, used nowhere).
- **SPEC:** 1 says `shell.css` uses "Tokens only: no colour, size or step
  written outside `pilot-ui.css`'s `:root` blocks". 10.3 says sizes are
  multiples of 4, with the selection pill as "the one 3px value". 28 is not a
  size 10.3 lists, and a token no rule uses is dead code (CLAUDE.md's gate).
- **Smallest fix:** Change the underline offset to `var(--sp-1)`, or drop it.
  Delete `--size-menu-row`.

## Not findings (noted for Jason and S6)

- **Proposed decisions 2 and 3** in the handoff (one keydown listener *per new
  file*, with the pilot's and tour's capturing listeners kept; no tooltip on
  focus for a text box) depart from SPEC 14.1 and 8.5 as written. The builder
  raised both openly as decision rows. They need Jason's yes, not a rebuild.
- **SPEC 14.1's vocabulary tests** (`test_every_screen_word_is_five_words_or_fewer`,
  `test_no_screen_word_names_a_path`, `test_every_short_reason_is_there_and_short`)
  walk `_vocab()`, so they depend on S1. None of S1, S2 or S3 has
  `test_shell.py`'s vocabulary part in its row. S6 should make sure they exist.
- `#last-sort` is a `div` holding a `p`, where the skeleton in 3.1 says
  `p#last-sort`. The role and live region are right, and the progress bar
  inside could not legally sit in a `p`. That is fine.
- The notice template still says "Look again" and "Dismiss" as text buttons.
  That is S4's work, and the handoff says so.
