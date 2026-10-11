# Pilot 0.3 - UI polish: the no-brainers, and a menu for Jason - SPEC

Status: written 2026-10-11 from a review of the app's look and speed on the
build of `401cdf4` (every page in both themes, drawn by the screenshot
harness with made-up names; the engine's command times on the test root;
a read of the renderer's data flow). Decision **P264** (`pilot/DECISIONS.md`)
covers section 1. Source: Jason, 2026-10-11: "Analyze the UI and UX for
aesthetics and speed. Take into consideration the implementation of UI
components. Apply all the no brainer improvements, but present various
options for each UI component that could be implemented so I can choose
from a menu of options."

**What the review found, in one paragraph.** The look is coherent and
calm: one token set, light and dark both pass their contrast table, a 4px
grid, one row style on every page, a skeleton at start. The engine is not
the bottleneck: `list`, `firm` and `state` each answer in about 0.15 s on
the test root, cold. The costs are in the page: whole-page rebuilds where
a smaller redraw would do, sorts that build a collator per comparison,
linear lookups inside sorts, a hidden reminder letter rebuilt on every
read, timers that keep spawning engine processes while the window is
hidden, and a few seams in the look (ragged filter cards, a pager drawn
for one page, notices that each take two lines, native controls that stay
light in dark mode). Section 1 fixes those; nothing in it changes a word,
a column, a colour or a ruling. Section 2 is everything that would.

**Hard rules kept.** No generative AI reads a client document. No test
reads a real folder. The screenshot harness's names are made up.

---

## 1. The no-brainers (P264): built, reviewed, landed

Each item names its file, what changes and its acceptance. Nothing here
adds a word to the vocabulary, moves a column, or changes a token's value.

### 1.1 Speed

**N1. One collator.** `pages.js` `pagesByName` (and any other
`localeCompare(..., {numeric: true})` in the renderer) compares through
one module-level `Intl.Collator(undefined, { numeric: true, sensitivity:
"base" })` built once. Same order as before (the acceptance test sorts a
list of mixed names and numbers both ways and asserts equality).

**N2. Lookups by key, not by scan.** `shellReturn` (`shell.js`),
`pagesFirmReturn`, `pagesHouseholdPath`, `pagesFormKey` and
`pagesReturnGroups`'s `filedBy` (`pages.js`) read from Maps built once
when the list or the firm reply is adopted (`adoptList` / `shellAdopt`
for engagements and households; the firm adopt for `firm.returns`; the
return state's `index` for `filedBy`; `pagesFormKey`'s flattened form
table built once at vocabulary time). No comparator or per-row call scans
an array. Acceptance: a lifted test builds the maps from a list and firm
reply and asserts each lookup answers what the scan answered; a text pin
that no `.find(` or `.filter(` remains inside `pagesByName`'s callers'
comparators.

**N3. Draw a page once per visit.** The household and year pages are drawn
once, not three times (`shellGo` → `shellDraw`, then
`shellStateArrived` → `shellDraw`, then the `.then` in `shellOpenState`):
when the state that arrives is one the page already shows, or the page
does not read state (a firm page), `shellStateArrived` does not call
`shellDraw`, and `shellOpenState`'s `.then` does not draw again. The
return page keeps its skeleton-then-page sequence (two draws). A firm
page under an open sheet is **not** rebuilt when the sheet's `state`
lands: `shellStateArrived` skips the page draw when `shellRoute.level` is
a firm page. Acceptance: lifted tests count `shellDraw` calls per route
(household 1, year 1, return 2, firm page with the sheet opened 0 extra).

**N4. The hidden letter is not rebuilt.** `render()` (`app.js`) calls
`renderReminder` only when the reminder sheet is open (or being opened);
the sheet's own open path draws it. Acceptance: a lifted test with the
sheet closed asserts `drawReminder` is not reached on a state reply, and
is when the sheet is open.

**N5. Search is debounced and folds once.** `drawFound` runs at most once
per 80 ms of typing (trailing), and `findOptions` reads folded names from
a cache built when the list is adopted (one NFD fold per household,
return and file), not per keystroke. Acceptance: a lifted test types three
characters within 80 ms and sees one draw; a test asserts the fold cache
is rebuilt on adopt and read by `findOptions`.

**N6. Timers sleep while the window is hidden.** The last-pass watch
(`shellArmLastPass` / `shellWatchLastPass`) and the lock watch
(`app.js`) do not send while `document.hidden`; on `visibilitychange` to
visible each ticks once at once. A `focus` tick within 5 s of the last
tick is skipped. Acceptance: lifted tests with a fake `document.hidden`
and a fake clock: no `last-pass` or `watch` command while hidden, one at
once on becoming visible; two focus events 2 s apart send one ask.

**N7. Small hot paths.** (a) The column grip's pointer-move writes its CSS
variables inside one `requestAnimationFrame` per frame. (b)
`outlineRefused` queries `#sheet` rows only, never the document. (c)
`pagesClientSpecs` is computed once per Clients draw and reused for the
count and the list. (d) `replaceTip`'s scroll listener returns at once
when no tip is showing. Acceptance: text pins in the file's existing
shape, and for (c) a lifted test counting `pagesClientSpecs` calls per
draw (1).

**N8. Dead CSS goes.** `style.css`: `@keyframes spin`, `.roll-grid.four`,
the `.summary` rules (and their restatements in `pilot-ui.css`), the
`.btn-primary` block that `pilot-ui.css` fully overrides, and the moot
1100px `max-width` rule. Acceptance: `tests/test_shell.py`'s restatement
test still passes (its retired list gains the rules), and a pin that the
selectors are gone.

### 1.2 Look

**N9. `color-scheme`.** `pilot-ui.css` declares `color-scheme: light` in
the light `:root` and `color-scheme: dark` in the dark block, so native
controls (selects' popups, checkboxes' parts, date fields) follow the
theme. Acceptance: a text pin.

**N10. No pager for one page.** `pagesFoot` (`pages.js`) draws Previous
and Next only when there is more than one page; the "Showing 1-3 of 3
Drafts" count line stays. Acceptance: a lifted test with 3 of 3 draws no
buttons; with 50 of 83 draws both.

**N11. Even filter cards.** The Needs Review reason cards (`pagesReasonCards`,
styled in `shell.css`) sit in a grid whose rows are always full: three
columns up to 1240px of window width, six above it, so six cards are 2 × 3
or 1 × 6 and never 4 + 2. Acceptance: a text pin on the two rules.

**N12. Details on the notice's line.** A notice's closed `Details`
summary sits at the right end of the notice's one line, before the action
and dismiss buttons, so a closed notice stays 40px; opened, the sentence
unfolds under the line at the notice's width (`pilot-ui.css`,
`drawNotice` in `app.js` if the markup order must change). The one line
stays one line and path-free (P257). On the setup page it is drawn open,
as P259 says. Acceptance: the existing Details tests pass; a text pin on
the summary's placement; the harness's `notices` and `setup` scenarios are
shot and attached to the pull request.

### 1.3 Measurement (in the handoff, not a test)

Before and after sections 1.1-1.2, with the harness's 500-household stub
in Electron (`?scenario=` default, 1400 × 900), the builder records the
time of: the Overview's draw, the Clients draw, a Search keystroke, and
opening the Smith household page, each as `console.time` around the draw
or the route change, median of five. The handoff pastes the numbers.

### 1.4 Job

One builder (sonnet) for sections 1.1-1.2 in: `app/renderer/shell.js`,
`app/renderer/pages.js`, `app/renderer/app.js`, `app/renderer/tooltip.js`,
`app/renderer/pilot-ui.css`, `app/renderer/shell.css`,
`app/renderer/style.css`, `tests/test_shell.py`, `tests/test_pilot_ui.py`,
`pilot/SPEC-shell.md` (3.5 and 8.4: the Details placement; 8.3 nothing),
`pilot/harness/stub.js` only if a scenario needs a reply shape it lacks.
Tests it runs: `tests/test_shell.py`, `tests/test_shell_menu.py`,
`tests/test_pilot_ui.py`, `tests/test_single_source.py`,
`tests/test_tripwire.py`, `tests/test_errors.py`, `tests/test_layers.py`.
No commit, no map update: the orchestrator refreshes the map, runs ruff,
`repo_map.py check`, `test_repo_map`, and commits after an Opus review
(high effort, a session that did not build) has no findings; a finding
that survives one rebuild is fixed by the reviewer's tier.

---

## 2. The menu: one question per component, for Jason

Each question names the component, what the review saw, the options with
their cost, and a recommendation. An answer becomes a P-row and a job;
nothing in this section is built until then. "Effort" is the builder's,
in rounds of the loop (S = under an hour, M = a half day, L = a day or
more).

**Q1. Side panel: the five "Under Construction" items.** They wrap to two
lines each and take a third of the panel. (a) Keep as built, hidden by
View › Show Under Construction (today's default shows them). (b) Show them
by default *hidden*, the menu item unticked. (c) Keep them shown but as a
short name with a small "Soon" tag at the right, one line each, the
tooltip "Under Construction" kept. (d) Collapse them into one disclosure
row "Coming later (5)". Recommend **(c)**: a buyer sees what is coming
without losing a third of the panel. Effort S; changes wording (P154).

**Q2. Side panel: the brand band.** The lockup's firm line is 133px wide
and unreadable at 1x; the band is 64px. (a) Keep. (b) Mark only, 32px,
with "Tax Document Console" beside it; the firm's name only in the window
title. (c) Lockup at 48px tall on a 72px band. Recommend **(b)**. Effort
S; changes P179.

**Q3. Links in lists.** Every name is underlined, which reads as noise on
a 50-row page. (a) Keep (SPEC-lists 15.2 says names stay underlined). (b)
Underline on hover and focus only; the link colour stays. (c) No
underline; the row's whole surface is the link and the chevron says so.
Recommend **(b)**. Effort S; changes P135's wording.

**Q4. Overview and the firm lists: the Tax Year column.** In a season every
row says the same year. (a) Keep. (b) Drop the column; the year moves
into the Taxpayer cell as a caption when it differs from the current
season. (c) Keep but show it only when more than one year is listed.
Recommend **(c)**. Effort S; changes the column rulings (P135-P139).

**Q5. The "Date" header.** It says Date; the value is the last activity.
(a) Keep. (b) "Last Activity". (c) "Updated". Recommend **(b)**. Effort
S; a word (P-row).

**Q6. The row's next step is hover-only.** "Check ›" appears only on
hover, so a new user does not know a row can be acted on. (a) Keep. (b) A
quiet chevron at rest on every row with a step; the words on hover. (c)
The step word always visible in `--link`. Recommend **(b)**. Effort S.

**Q7. Row density.** 40px rows show about 15 rows at 1400 × 900. (a)
Keep. (b) A View › Compact Rows switch (32px rows, caption-size dates),
kept per PC. (c) Compact by default, Comfortable as the switch. Recommend
**(b)**. Effort M.

**Q8. Needs Review's layout.** Each household is a bordered card holding
its files, with a "1 Document" pill and a "…" menu; the page mixes card
and table idioms. (a) Keep. (b) One flat list with group headings like the
return page (no card border, no pill; the count in the heading). (c) Cards
but flatter: no border, a hairline between households. Recommend **(b)**:
one row style on every page, as SPEC-shell 3.6 set out. Effort M.

**Q9. Notices.** Several notices stack to a third of the page (notices
scenario: four of them, 300px). (a) Keep, with N12's one-line form. (b)
One summary line "3 things need attention" with the list unfolding under
it. (c) Notices in a right-hand panel, the page kept whole. Recommend
**(a)** after N12, revisit if real use shows stacks. Effort S/M/L.

**Q10. The sort icon.** The circular-arrows icon reads as "refresh"; its
tooltip is "Open a Household to Sort". (a) Keep. (b) A different icon
(a funnel-with-arrow or a "play" mark) with the same words. (c) A small
labelled button "Sort now" on the household and return pages, no icon on
firm pages. Recommend **(c)**. Effort S; changes P60/P70.

**Q11. The household page.** Three lines of content on a 900px page: title,
contact, two year groups; the status far right. (a) Keep. (b) A header
card with contact, shared-with and inbox link beside a returns list whose
status sits next to the name. (c) Fold the year groups into one list with
a year column. Recommend **(b)**. Effort M.

**Q12. Speed: the engine process per command.** Every command spawns a
Python process (about 0.15 s here, about 0.85 s on the office PC); the
spare hides one of them. (a) Keep. (b) A long-lived engine process per app
session answering commands over stdin, started at launch and restarted on
failure (decision 193's safety case to be re-read: a stuck pass must still
be killable). (c) Keep spawning but keep two spares. Recommend **(b)** as
the one change that makes every click feel instant on the office PC;
effort L, its own SPEC.

**Q13. Speed: the idle watch.** Once a minute an idle window spawns a
process to ask whether a pass ran. (a) Keep (N6 already stops it while
hidden). (b) Watch the last-pass file from `main.js` (`fs.watch`) and tell
the page when it changes: no polling at all. Recommend **(b)**; effort S
once the data home's path is handed to `main.js` by `list`.

**Q14. Speed: the firm reply.** It can be several MB and every firm page
rebuilds all of it before paging. (a) Keep. (b) The engine pages the firm
lists (`firm?page=`), the page asks for a page at a time. (c) The page
keeps the parsed specs between navigations and rebuilds only on a new
`firm`. Recommend **(c)** now (effort S), **(b)** when a firm passes 2,000
returns. 

**Q15. Lists that are not paged.** Household, year and return pages and
the editor draw every row. (a) Keep. (b) `content-visibility: auto` on
rows below the fold (CSS only). (c) Virtualize. Recommend **(b)**; effort
S.

**Q16. Typography on a Mac.** The stack is Segoe UI first, system-ui on a
Mac. (a) Keep. (b) Put `system-ui` first on a Mac (`-apple-system`), Segoe
on Windows, through one token. Recommend **(b)**; effort S.
