# Shell S5 - review 1 (the side sheet, the links, the right-click menus and the dialogs)

Reviewer: first review of S5, opus, 2026-09-30. I did not build S5. Branch `claude/shell-s5-sheet`,
reviewed at `04de3d5`, diff `2016303..04de3d5`.
Against: SPEC-shell as synced (`claude/shell-spec-sync`: 2.7, 3.9, 5.2-5.4, 5.7, 6, 7, 8.5, 11, 14, 16,
19) with `wording-shell.tsv` and `shell-test-pins.md`; `shell-rulings.md` rows 1-15 and `shell-ledger.md`
(`claude/amazing-maxwell-b4hdzo`); the builder's handoff `shell-S5.md`; S4 review 2's notes for S5; and
S8a's real reply (`claude/shell-s8a-links` at 62b76fa: `tracker/api.py`, `app/main.js`, `app/preload.js`).
Made-up names only; nothing here reads a client document.

## What I ran

- Tests, each file its own process, Python 3.11 (`/tmp/v`) then 3.13 (`/tmp/v313`): `test_shell` 81,
  `test_pilot_ui` 11, `test_single_source` 165, `test_layers` 29, `test_tour` 8, `test_pilot` 18,
  `test_api` 368, `test_row_columns` 26, `test_pilot_installer` 12, `test_repo_map` 80 - **all pass on
  both**. `ruff check .` clean. `repo_map.py check` current (292 nodes).
- `interact.mjs` (real `app.js`): "all interactions pass".
- Two probes on a scratch copy of the harness: (a) the stub's `dismiss` changed to keep the file's handle,
  as the engine does (F1); (b) a walk of every text node, attribute and tooltip the sheet draws, file by
  file with More open, flagging anything with a slash or over five words (F2, F6, F14).
- **Mutation checks** (scratch copy of the tree, one at a time, against `test_shell`; the two that
  survived it re-run against `test_single_source`'s registry and seq tests): 15 mutations, **12 caught by
  `test_shell`, 2 more by `test_single_source`, 3 survived**.
  Caught: sheet advances on another return's state; a return link drops its year; the link node carries
  the absolute path in its dataset; Folders Skipped draws `where`; F10 without Shift opens the menu; the
  system's refusal text is not logged; Unfile offered for several originals; Safeguards falls back to the
  long headline; a household link also opens File Explorer; a menu answer's rejection unhandled; the
  misfits dialog out of the registry (`test_single_source`); Unfile from the menu drops `seq`
  (`test_single_source`).
  **Survived:** (1) Unfile offered on a Received row under a live lock (`pagesEnableFor`, the test locks
  only a file row and a request row); (2) `show_in_explorer` offered on a household or return row menu
  (the condition `menu === "file" || "moved"` removed); (3) the sheet advancing when the file it shows was
  set aside - no test pins either behaviour, which is where F1 lives.

## Findings

**F1. After Not Requested (and after a Put Back that parks) the sheet stays on the same file, stale.**
`sheet.js:247-254` moves on only when `sheetFind` no longer finds the handle, and `sheetFind`
(`sheet.js:98-106`) finds a dismissed row as `aside`. The engine's dismiss rewrites the same index row
(`handle_of` = `ledger_key`, the original's place, unchanged; `app.js:1135` "the row is rewritten"), so
the handle is still there. Scenario (reproduced with the scratch stub keeping the handle): return page,
Enter on `scan0012.pdf`, Not Requested -> the write succeeds, the page behind shows the file under Set
Aside, but the sheet still shows `scan0012.pdf` as a parked file, its Not Requested disabled and File It
enabled with the old `data-seq="1"`; File It then sends the `seq` the dismissal superseded, which the
filer refuses (decision 112), and the person sees a failure notice. The same happens from the right-click Not Requested (it presses the sheet's button), and for a
moved copy whose Put It Back parks it for review (`restored.parked_as`: the row becomes `parked`, the
sheet keeps the stale moved row). SPEC 7.1: "After a write that succeeds the row leaves the list ... and
the sheet shows the next file." The harness hides it: `stub.js:353` gives the set-aside file a new id,
so a new handle. Fix: treat a changed kind (parked -> aside, moved -> parked) or a changed `seq` as
"answered" and move on (or redraw), and make the stub keep the handle; pin it in
`test_the_sheet_moves_on_only_when_the_file_it_shows_has_left_the_list`.

**F2. The held reminder draws request codes and the engine's long hold sentence.** `app.js:486-490`
draws each held row as `row.identifier`, the document, and `row.reason`. The real `reason` is
`reminder.PARKED_HOLD` / `AMBIGUOUS_HOLD` / `CONFIRM_HOLD` ("held - a file the client sent for this could
not be used (...); a person decides whether the client resends it or we file what came", 25+ words;
unchanged on S8a). Scenario: Draft Reminder on a held return -> the sheet shows "R03 1099-B - Northwind
held - a file the client ...". SPEC 7.2: "a warn line ... and the held rows' names under it"; 11.1: five
words, never a request code. The stub's reason is a short label, so no check saw it. Fix: draw the
row's name only (the document or short name), the sentence to nowhere (it is the error log's or the
status page's).

**F3. Unfile and Mark Missing from the right-click menu have no in-flight state and lost their reason
box.** `pages.js:1073-1074` call `unfileDocument(spec.unfile)` / `withdrawAnswer(spec.missing)` with no
button; `app.js:1159-1175` disables nothing and sends `note: ""` always. (a) Scenario: Unfile, then
Unfile again on the same row before the reply (the row and the item stay until the reply, and an unfile
with a re-scan takes seconds) -> the second call carries the same `seq`, is refused, and `refused()`
shows a failure notice although the first unfile worked - the "never reported as failed when it
worked" rule. Fix: mark the row busy (grey its menu ids while its write is in flight) as the sheet's
buttons do. (b) **JASON:** the old list's reason box for Unfile (and the Mark missing note) is gone;
`wording-shell.tsv` row `review_labels.unfile_note` keeps it ("merge ... Reason (Optional) ... Unfile
reason box"), so the approved table expects a place for it. Options: an Unfile item that opens a small
confirm with "Reason (Optional)", or accept that a right-click Unfile carries no note.

**F4. JASON - a request that several files answer can no longer be unfiled or revealed at all.** The
old per-file list (`renderUnfileList`) offered Unfile on every filed original and named each copy.
Now Unfile is offered only where exactly one original is filed under the request
(`pages.js:716`), a "{n} Files" Received row has no file link (`pages.js:715`), and there is no other
place in the app that lists those originals. Scenario: "Childcare receipts" answered by three receipts,
one of them misfiled -> no way to unfile it from the app (the person corrects it in Explorer, which the
record never learns - the reason the list existed). SPEC E80 moved "Unfile, Mark missing" to the
Received rows' right-click, and 13 keeps `unfileDocument`; neither foresaw several files. A decision is
needed: file rows under a multi-file request (each with its own link and menu), or a Check-like sheet
for a Received request listing its originals. Related, a fix without Jason: for one original with
several copies (decision 94) the Received row of its own request (`entry.identifier`) can link
`open_keys[0]` - the first copy is `prepared_location` (`records.filed_locations`), which should be the
one filed under `entry.identifier` (S8a or S6 to confirm before relying on it); today it is plain text (`pages.js:715`), against SPEC 3.9 ("every file name
... is a link").

**F5. Row menus offer items that cannot act, and choosing one says the page failed.**
`pages.js:1023` enables Another Return… on every parked file, but the sheet has an `r-hand-over` only
when `fedReturns()` is non-empty and the file is a document (`app.js:861`); `pages.js:1026` enables Put
Back on a moved copy whose original is gone (`m.gone`: `movedRow` draws only Mark Missing). Scenario: a
household with no fed return, right-click a parked file -> Another Return… -> the sheet opens and
`unanswered("another_return")` shows `vocab.shell.page_error` - a failure notice for an ordinary choice.
SPEC 5.3: send "the ids whose rule holds now". Fix: enable `another_return` only where the sheet would
offer it (a document, `fedReturns().length`), and `put_back` only where `!gone`.

**F6. The renderer still types sentences in its toasts.** `app.js:732`, `1025`, `1072`
("Pick the request this document belongs to first.") and `2690` ("Give each custom request a document
name first."): eight words, sentence case, a full stop, typed in the renderer. SPEC E33 ("Toasts (long)
- Kept, shortened", e.g. "Pick a request first"), 11.1, and S5's row ("the renderer's literals in Title
Case"). `test_every_phrase_the_page_and_the_dialogs_draw_from_index_html_and_app_js_is_in_title_case`
reads only `index.html` and `BELONGS_TO`, so it misses them. Fix: API words (or at least Title Case,
five words) and extend the test to `toast(` literals.

**F7. E91's one Advanced switch is not built; the per-row routing toggles stay** (handoff item 9 /
departure 4). SPEC 2.7 E91 keeps "one **Advanced** switch" and cuts "per-row routing toggles"; the
audit (line 165) says the one switch replaces them and also folds learned keywords, paste and rename.
`app.js:2595` (per-row `ed-fold`) and `app.js:2862` (`ed-fold-all`) remain. Not a Jason question - the
SPEC is explicit. Fix in S5, or the orchestrator moves it to S6 in writing.

**F8. E88's "two of three Cancels" is not cut** (departure 5). The one `#modal` has three Cancels, one
per step (`index.html:289`, `302`, `366`). E88 keeps "Cancel" for step 1 and cuts "two of three
Cancels"; E89 and E90 list no Cancel among what they keep (step 3 keeps Back). My reading: cut
`wf-cancel` and `ne-cancel`; Esc and the scrim still close the wizard. Fix as read, unless Jason wants a
visible Cancel on every step (then the SPEC row changes).

**F9. The three info dialogs' button reads "Dismiss", not the SPEC's "Close"** (departure 8;
`app.js:3342`, `3356`, `3367`). E93-E95 say Close; the API carries no such word (`terms.close` is the
pilot layer's). Acceptable for now; S1/S6 add `screen.close` ("Close") and the three lines use it.
Record it in the S6 list; no Jason call needed (the SPEC already names the word).

**F10. JASON - Folders Skipped has no two-word reason** (departure 7; `app.js:3364-3380`). E95 wants
"name and two-word reason"; the API sends only the long sentence per misfit and no key. The builder's
interim (name only, sentence to the error log, the missing key logged once) is safe and draws no path.
The words themselves are new vocabulary (P66), so Jason approves them: a short per misfit kind (for
example "Not a Household", "Name Not Understood") on the API, or the name alone as built.

**F11. Some links have no keyboard path.** A `.row-link` is a `span` inside a listbox option; the O3
default (ledger) gives file rows "Show in File Explorer" in the row menu. Not covered: the filed copy's
link on a Received row (the `received` menu has no `show_in_explorer`; `pages.js:1036` adds it only for
`file` and `moved`), the Needs Review group heading's return link and its household caption link
(`pages.js:378`), and the household link in the detail of Overview and Reminders rows (Enter opens the
return, not the household). Scenario: a keyboard user on a Received row cannot show its filed copy.
Fix: `show_in_explorer` on the `received` template when the row has a `detailLink` (a POPUPS change at
S6's join), and make heading and caption links focusable buttons (or say in the handoff that the path
row is their keyboard route).

**F12. A household or return row's menu item is answered after navigation without the enable rules
being read again.** `pages.js:1052-1064`: the popup's ids come from `shellEnabled(route)` on the firm
page, where `locked` is the lock of whatever return was last read; after `shellGo` the item runs through
`shellAnswer(id)` unconditionally. Scenario: Overview, right-click a return a live pass holds, Edit
Request List… -> the app goes there, the lock notice shows, and the editor opens anyway (the save is
refused by the engine, so no harm to the record, but SPEC 5.2 says a locked return greys the writing
items). Fix: after the route's state arrives, answer only if `shellEnabled().includes(id)`, else leave
the page where it is.

**F13. The S8a join is named but not pinned, so S6 can miss half of it** (handoff items 7, For S6).
Present: reveal needs S8a's preload/main (`open(p, how)` -> `openPath(p, reveal)`), and
`show_in_explorer` must enter `main.js`'s `file` and `moved` POPUPS and a word. Missing or ambiguous:
(a) the word must be a new **`api.MENU["show_in_explorer"]`** *and* the same line in `main.js`'s default
MENU words (`test_the_menus_default_words_are_the_apis_word_for_word`), not only
`screen.show_in_explorer`, which `main.js` never reads; (b) SPEC 5.2's table and 11.3's menu table
amended (ledger O4 default) and a test that the `file` and `moved` templates carry it - today
`test_every_menu_id_the_page_answers_is_in_the_template_and_the_rest_are_the_rows` lists the row ids by
hand and reads no POPUPS, so a join that forgets the item passes every test and the item silently never
appears (main.js drops unknown enable ids); (c) F11's `received` item if Jason takes it. Fix: a short
numbered S6 checklist in `shell-S5.md` with those lines, and a pin that fails until the POPUPS carry it
(it may be written as S6's).

**F14. Smaller SPEC gaps in the sheet.** (a) A moved copy's status line has no received date
(`sheet.js:121-130` reads it from `found.entry`, undefined for a moved row; the page row has it via
`receivedOf`) - SPEC 7.1 "the short reason ... and received". (b) Request codes are drawn: the picker's
options read "R02 — 1099-B - Northwind Brokerage" (`app.js:774`) and a gone copy's button "Mark R03
Missing" (`app.js:694`, the renderer fills `{identifier}` with the code) - SPEC 11.1 "never ... a request
code", E54 removed the ID column. Fix: the option's text the document (value stays the id); fill the
Mark Missing word with the request's name. (c) Test gaps from the survivors: pin the lock on the
`received` menu and that client-row menus never carry `show_in_explorer`.

**F15. JASON - two behaviours the SPEC allows but Jason may not want.** (a) A right-click write item
(Not Requested, Put Back, Keep Here, Another Return) opens the sheet, presses its button and then the
sheet moves to the next file (handoff item 13 / departure 10): the person asked for one row and lands in
a sheet on another file. SPEC 5.4 is met (the write is the sheet's, with its checks); the alternative is
to stop at the open sheet, or close it after the one write. (b) The reminder sheet is titled "Reminder"
(SPEC 7.2) and, with Next walking the Reminders page, only the letter's greeting says whose draft it is
(handoff item 10); a caption with "{Return Name} ({Year})" would need a SPEC change.

## Departures, one line each

| Departure (handoff item) | Verdict | SPEC line |
|---|---|---|
| 3 (1): return link text is `return_name` + `year`, not `label` | **Acceptable, correct.** S8a's `firm.returns[]` carries `path, household, label, year` and no return name; `label` is `ENGAGEMENT_LABEL_PATTERN` (household, year, name), so `label (year)` would say the year twice. The mock-up and ruling 13's example are the return's own name plus year. SPEC 9.2 already says the page joins `returns[]` to `list` by `path` (`list.engagements[].return_name`, `year`). No S1 change needed. | 3.9 (lines 443-450), 9.2 (line 1116) |
| 4 (9): E91 Advanced switch | **Needs a fix** (F7) | 2.7 E91 |
| 5 (9): E88 two of three Cancels | **Needs a fix** as read (F8) | 2.7 E88-E90 |
| 6 (4, 5): several files per request, decision 94 copies | **JASON** for Unfile of several files (F4); the decision-94 link is a fix | 2.5 E80, 3.9, 13 |
| 7 (2): E95 reason key | **JASON** for the words; interim acceptable (F10) | 2.7 E95 |
| 8 (3): Close word | **Acceptable interim**, S1/S6 add `screen.close` (F9) | 2.7 E93-E95 |
| 10 (13): right-click writes | **Acceptable** per 5.4, with F1, F3, F5 fixed; the move-on is **JASON** (F15a) | 5.2, 5.4, 7.1 |

## Checked and sound

- Hard rules: no generative AI, nothing sent (Copy and Approve only; no mail link), no network call or
  new package, CSP and load order unchanged (`sheet.js` between `pages.js` and `shell.js`). No path in
  any node, attribute, dataset or tooltip of the pages or the sheet (the probe's walk, and the test that
  builds rows from absolute paths); keys only (`data-key`, `data-token`), the path resolved at click time
  from `state.paths` / `firm.paths`; a `""` key is plain text. `sheet.js` types no words.
- The three link kinds and tooltips match rulings 11-13 and 15; only a file name calls
  `open(path, "reveal")`; household and return links navigate with no engine call; the review copy's open
  icon opens (not reveals) by `open_key`, as S8a's kinds require. A refused open is "Not Opened; It Has
  Changed" with the system's text to the error log.
- The sheet is in `DIALOGS` (`attr: true`), focus to its title, Tab kept, Esc and the scrim close, focus
  back to the row (also after a redraw); the four dialogs are in the registry with a first focus; reduced
  motion, forced colours (`.row-link` LinkText, HighlightText on the active row) and the dark tokens hold;
  every new space is a grid step.
- S4 review 2's notes 1-3 are done (`render()` guards what it runs; the stub carries the joined shapes;
  a throwing menu channel is a notice).

## Repository map

Only this file is added. With it staged, `repo_map.py check` says stale for exactly one reason:
"added pilot/handoffs/shell-S5-review-1.md". No `update` was run (reviewer's brief); the rebuild's
`update` picks it up.
