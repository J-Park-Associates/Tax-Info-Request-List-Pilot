# Shell S5 - the side sheet, the links, the right-click menus and the dialogs (built)

Session: S5 builder (sonnet), 2026-09-30. **Branch: `claude/shell-s5-sheet`**, built on S4's reviewed
tip `2016303` (`origin/claude/shell-s4-pages`, review 2 with its two fixes). S8a's engine keys are on
`claude/shell-s8a-links` (86569b0, still in review) and are **not merged**: the harness mirrors their
documented shape and words. Nothing here is reviewed yet; the last commit is named on the last line.
Made-up names only; nothing here reads a client document.

## Done, in plain English

| SPEC 16, S5's row | Where |
|---|---|
| `sheet.js` (7): Check a file and Draft reminder in one modal drawer, More fold, Next arrow, open icon | `app/renderer/sheet.js`; frame and parts in `index.html`; styling in `shell.css` |
| The page side of right-click menus (5.2, 5.3) | `pages.js`: `pagesPopup`, `pagesEnableFor`, `pagesMenu`, Shift+F10 / the menu key in `pagesKey`, the H1's menu; `shell.js`: `shellPopup(.., enable)`, `shellEnabled(at)`, `shellAnswer` |
| Four dialogs: roll forward, safeguards, about, folders skipped (E92-E95) | `index.html` (`#roll-modal`, `#safeguards-modal`, `#about-modal`, `#misfits-modal`), `app.js` (`openRoll`, `openSafeguards`, `openAbout`, `openMisfits`), all four in `DIALOGS` |
| Dialogs' help lines cut (E84-E91) | see "What was cut" |
| The three link kinds (3.9, rulings 8-13) and "{Return Name} ({Year})" | `pages.js` |
| Terms read-only in Help | already built (S3: `PilotTerms.show()`, one Close, Esc closes); checked in `interact.mjs`, not changed |
| Renderer literals in Title Case | `index.html`, `app.js` (`BELONGS_TO`); the tour and pilot content are S6's |
| Review 2's notes for S5 | see "S4 review 2's notes" |

**The sheet.** It opens from a row's step, Enter, a double click, or a right-click item, on the same rows
S4 draws. It is a `role="dialog"` `aria-modal` drawer in the one dialog registry (`DIALOGS.sheet`,
`attr: true` because it hides by its `hidden` attribute): focus goes to its title, Tab stays inside, Esc
and a click on the scrim close it, and focus goes back to the row it came from (`pagesWhere` /
`pagesFocusAt`, because a write redraws the page). Check a file shows the file's name as the title, a
status line (the short reason and the date; "Moved by Hand"; "Not Requested"), the "Belongs To…" picker
with the suggestion reasons under it, the K-1 issuer box, the one-click "file where it waits" block, and
**More** (the header's icon, `aria-expanded`): Keyword, Spelling, Reason and "File Under Another Return".
The footer is the secondary answer then the primary (Not Requested / File It; Keep It Here / Put It
Back). `reviewRow` and `movedRow` (app.js) still build every part and the writes are the same functions;
`sheet.js` only places their parts and one delegate on `#sheet` answers the buttons. Next moves on
without writing, in the order the page was drawn (`pagesFiles()`: a return page's parked and moved files,
every file of Needs Review; `pagesDrafts()` on Reminders); after a write that works the file is gone from
the state and the sheet shows the next file, or closes after the last with no message
(`sheetStateArrived`). A file opened from a firm page reads that return's state first (`showReturn`, one
call), shows its name and outline rows while it does, and a failed read is the read's own notice and a
shut sheet. Draft reminder needs no drawing of its own: the letter's parts sit in the sheet from the start
with the ids `drawReminder()` uses, so `loadReminder`, `copyReminder` and `approveReminder` are unchanged;
the stages read by their short names, the hint and "Open the draft file" are gone, the caption is
"Drafted Mar 3, Stage 3", a held reminder shows the hold and no Copy or Approve.

**The links.** A file name is a `.row-link` whose tooltip is `screen.show_in_explorer`; a click asks
`window.tracker.open(path, "reveal")` for the path looked up by the API's key in the map the row came with.
The keys (S8a): a parked or set-aside row `index[i].shown_key`, a moved row `moved[i].open_key`, a filed
request's detail `index[i].open_keys[0]` (only when exactly one file answers it), and on the firm-wide
Needs Review page `firm.files[i].open_key` through `firm.paths` (ruling 15). An empty or missing key is
plain text. A household name navigates (`screen.navigate_client`) and a return name navigates
(`screen.navigate_return`); neither calls the engine or File Explorer. A refused open is a notice in the
API's own "Not Opened; It Has Changed" (the operating system's text goes to the error log). The path is
never drawn: a test builds every page from state that holds absolute paths and walks every node,
attribute, dataset and tooltip. "Show in File Explorer" is also a right-click item on file and moved rows
(`pagesMenu`), which answers O3 and O4: a keyboard user reaches it with Shift+F10.

**Return links** read `"{Return Name} ({Year})"` on Overview's Work Waiting, Reminders, the household
and year pages and the Needs Review group headings (which are also the link); the group caption's household
name is a link. The name is the list's `return_name`, the year the row's own `year`. See departure 1.

**Right-click.** Every row carries `data-menu` (the template) and `data-token` (its id, never a path). A
right-click, Shift+F10 or the menu key asks for the native menu with the ids that apply to that row (a live
lock greys the writing items; Keep only where the copy sits in a request's folder; Unfile only where one
original answers the request; Mark Missing only where a statement answers it without a copy). The chosen id
comes back with the token: the file items open the sheet on that file and **press the sheet's own button**
(so the write is the sheet's, with everything it checks); a household or return row takes the app to that
page and then answers the item as if chosen there (Draft Reminder on the Reminders page opens the sheet
directly so its Next order survives). The H1 and the crumbs keep their tokens and the shell answers them.

**Dialogs.** Roll forward (title "Roll Forward to {year}", the ticks, the unticked-retire warning, Cancel,
Roll Forward; opens only when the API names the year), Safeguards (one line per rule from
`vocab.rules[].short`, a rule without one is a loud failure), About (product name, "Pilot 0.2"), Folders
Skipped (a row per folder, its own name, no path). All four are in `DIALOGS` (Esc, focus, Tab).

## What was cut (help lines, E84-E91)

Household editor: the members and feeds help lines. Schedule: the "Scan works either way" note; the
loading sentence is now three outline rows and the one word for a screen reader (`shellSkeleton`). New
household / Add a return: the intro, the second heading, the form step's note, each form card's blurb, the
input tooltips (contact, members, link, return name, year), the form chip, the 31-word note, request IDs and
rule summaries on the ticks, the People help, and the custom rows' extension and keyword columns. Editor:
the second heading, the read-only fields, every column, field and routing help tooltip and the routing note,
the paste and rename hints, the keyword tooltip. Kept: the sharing and feed warnings and the Active warning
(P77). The household sharing checklist that `create` returns (it names folders by path) is no longer drawn.

## S4 review 2's notes for S5

1. The legacy renderers outside `shellStateArrived`'s catch are gone (`renderMoved`, `renderReview`,
   `renderUnfileList`, `renderHousehold`); `render()` now guards what it still runs after the assignment
   (`renderLock`, `renderReminder`) in the same way, so an error of the page's own after a write's reply is a
   notice and never the write's failure. `sheetStateArrived` runs inside `shellStateArrived`'s try.
2. The harness stub carries `firm.returns[].year` and `label` (the engine's real pattern, household year
   return name, so it is plain that the link text does not use it), `firm.files[].handle`, `year`,
   `open_key`, `firm.paths`; moved rows carry `identifier`, `in_request` and `open_key`.
3. A menu channel that throws is a notice and does not stop navigation (`shellEnable`, `shellPopup`,
   `appRouteChanged` inside `shellGo`, all caught); `interact.mjs` has a `menu-throws` scenario.
4. Not done: the loud-failure test is still a static read for `renderMisfits` / `renderShortOfRoom`
   (`openMisfits` itself now has a behavioural test).

## Departures and things raised

1. **Return link text is `return_name` + `year`, not `label` + `year`.** The brief said `returns[].label`.
   The engine's `label` is `layout.ENGAGEMENT_LABEL_PATTERN` = `"{household} {year} {return_name}"`, which
   already carries the household and the year; `label (year)` would read "Smith Family 2025 1040 - John
   & Jane Smith (2025)". The renderer uses the list's `return_name` (or the household row's) and the row's
   own `year`, so no word or year is typed or worked out here. S6: keep, or ask S1 for a `return_name` on `firm.returns`.
2. **The folders-skipped dialog has no two-word reason.** SPEC E95 wants one; the API sends only a long
   sentence per folder and no vocabulary key. The dialog shows the folder's own name (last part of `where`),
   sends the sentence to the error log, and logs the missing key `vocab.screen.misfits.reason` once. Needs an
   S1 word (or a short per misfit).
3. **The three info dialogs close with `screen.icons.dismiss` ("Dismiss").** The SPEC says "Close"; the API has no
   such word (the pilot's `terms.close` is the pilot layer's). S1 could add `screen.close`.
4. **"Unfile" is not offered for a request that several files answer** (a "3 files" row): which original would
   it be? Unfile is per original, and the old per-file list is gone. Needs a decision (a picker in the menu, or a
   file row).
5. **A filed request with several copies (decision 94) has no link**, and a request answered by several
   files shows "{n} Files" as text; a link needs exactly one file with one copy.
6. **A moved file's link text is its original name**, not the basename of where it is now (S8a's review note).
7. **`window.tracker.open(path, "reveal")` and the right-click id `show_in_explorer` need S6's join.** This
   branch's `preload.js` and `main.js` are S4's: the second argument is dropped, so a file link would *open*
   the file in its default program until S8a's preload and `main.js` are merged. The `show_in_explorer` id must
   be in `main.js`'s `file` and `moved` templates (S2's branch) and its word in `api.MENU`
   (`screen.show_in_explorer` is the API's word for "the right-click item that does the same"). Do not run
   this branch in Electron before the join.
8. **`firm.paths` shape.** Built to ruling 15's message and S8a rebuild 3: `firm.files[i].open_key` is `""`
   or a key, `firm.paths` a top-level map key to the absolute path. The resolver (`pagesPathOf`) also accepts
   `{path, kind}` (the coordinator's first wording). S6: check against the real reply; the stub mirrors
   `keys` with a space and the file's handle, the real ones carry `#2` suffixes.
9. **Not done from the audit:** E91's single **Advanced** switch (the editor still has S3's per-row Routing
   fold and its "show every fold" button); E88's "two of three Cancels" (each wizard step still has its own
   Cancel; I could not tell which two the audit means). The custom rows' columns are cut to Document.
10. **The reminder sheet is titled "Reminder" with no client name** (SPEC 7.2). With Next across the
    Reminders page the letter's own greeting is the only name. Jason may want the return's name in the caption.
11. The dialogs' cut words (`roll_intro`, `new_intro`, `form_step_note`, `members_help`, ...) are still in
    the API; S1 can drop them. `test_single_source`'s key lists no longer require the cut ones.
12. `pagesFiles()` (Next's order) leaves out files already set aside (their Check is opened by hand).
13. A right-click **Not Requested / Put Back / Keep Here / Another Return** item opens the sheet on that
    file and presses its button: the write is immediate, as the item says, and the sheet then moves on. If
    Jason wants a confirming look, the item can stop at the open sheet instead.
14. A return read only for the sheet (from a firm page) leaves `active` on it; closing the sheet clears its
    lock notice (`appRouteChanged`).

## Tests

Each file its own process, Python 3.11 (`/tmp/v`) then 3.13 (`/tmp/v313`), one after the other:

RESULTS

New in `tests/test_shell.py` (each names its claim, 23 new): the Title Case rule and every phrase
`index.html` / `app.js` draw; the sheet in the registry, hiding by its attribute; the cards, functions and
rules the sheet and dialogs took are gone; the help lines cut; no sharing checklist; the link kinds built from
the API's keys, no path in any node, attribute or tooltip; running a link (reveal for a file alone,
navigation for the others, a missing key loud); the year on a return link; the firm page's links by
`open_key`/`paths` and the group heading; a link's tooltip wins over a cut name's; the order of Next; a row
menu's ids (lock, Keep, Unfile) and which tokens are the page's; a failing menu answer is a notice; the sheet's
find, advance-only-when-gone, following files and footer order; a channel that throws; `openPath`'s refusal;
the four dialogs (words, no path, loud rule); Shift+F10 and the menu key; the three tooltip keys. Changed on
purpose (SPEC 14.2): the skeleton, the loading order, `RETIRED`, the notice tests (the joined engine's
Title Case words and the fallback), the pages' function lists, the menu-send pattern, `test_single_source`'s
roll, dialog-registry, seq, lock and standing-rules tests, `test_api`'s schedule and moved-row tests.

`interact.mjs` gained the sheet, links, right-click, menu-throws, reminder and dialog sections and "all
interactions pass". `shoot.mjs` gained 15 scenarios; I looked at Check (parked, More open, moved, email,
photo, from the firm page, loading) and the reminder (held, ready), the four dialogs and the link tooltips,
light and dark, at 1100x700 and 1400x900.

**Mutation checks** (scratch worktree, each alone, run against `test_shell` (15 caught of 15 after two
tests were added for the survivors): file link opens without "reveal"; household link opens File Explorer;
return link drops the year; Next walks to set-aside files; sheet does not move on after a write; a live lock
does not grey the row menu; household tooltip says File Explorer (**survived**, then the table pin was
added); firm file names never link; footer order reversed; a refused open is silent; Safeguards draws the
long detail; the sheet's own box is a click behind it; Unfile offered for several files (**survived**, then
the unfile expectation was added); a path as the link's tooltip; and, against `interact.mjs`, the menu
channel's guard removed.

## Files

`app/renderer/sheet.js` (new), `pages.js`, `shell.js`, `app.js`, `index.html`, `shell.css`, `style.css`,
`pilot-ui.css` (dead rules of the review list, the reminder card and the assurances deleted),
`pilot/harness/` (`stub.js`, `serve.mjs`, `shoot.mjs`, `interact.mjs`, `make_vocab.py`, `README.md`; new
`accel.js`, `vocab-mirror.json`; `sheet-stub.js` gone), `tests/test_shell.py`, `tests/test_single_source.py`,
`tests/test_api.py`, `docs/repo-map.curated.json`, the generated map, and the SPEC-sync files brought onto
the branch (`pilot/SPEC-shell.md`, `wording-shell.tsv`, `shell-test-pins.md`, `AUDIT-shell.md`,
`handoffs/shell-rulings.md`, `shell-ledger.md`, `shell-spec-sync.md`).

## For S6

Merge S2's and S8a's branches; then the `show_in_explorer` item, the `reveal` argument and the vocabulary
keys (`screen.misfits.reason`, a close word) meet; `HARNESS_LIVE_VOCAB=1` and delete `vocab-mirror.json`;
the tour anchors and Title Case tour lines; the decision rows for rulings 1-15.
