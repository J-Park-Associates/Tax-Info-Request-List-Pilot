# SPEC: Hide the Under Construction sections (P197)

Decision P197 (`pilot/DECISIONS.md`). Jason, 2026-09-30: "Add a setting to
hide "Under Construction" sections from sidebar"; 2026-10-01: "add the hide
Under Construction setting next". Branch `claude/hide-under-construction`,
stacked on `a4a8e07` (the tip of `claude/zen-easley-93548b`).

## 1. What counts as "Under Construction"

Every side-panel item marked `data-soon` (lane 4b, P154, P175; pilot
SPEC-lists 15.1). Five items, and the one heading that holds only them:

| Item | Where |
|---|---|
| Ready to Sign (Under Construction) | `app/renderer/index.html:36` |
| Family Entities (Under Construction) | `app/renderer/index.html:37` |
| the **Workspace** heading and its list | `app/renderer/index.html:46-47` |
| Personal Trusts (Under Construction) | `app/renderer/index.html:48` |
| Corporate Entities (Under Construction) | `app/renderer/index.html:49` |
| Portal Settings (Under Construction) | `app/renderer/index.html:50` |

The words are `api.SCREEN["side"]["soon"]` (`tracker/api.py:1373-1377`);
`shellSideWords` fills them (`app/renderer/shell.js:166`). Not affected: the
four pages, the Taxpayer Types, and Settings at the foot of the panel - each
of those is built and works.

## 2. Rulings and reasons

1. **One setting hides all five items, and the Workspace heading with them.**
   A heading with nothing under it would read as a broken section. The rule
   is general: a heading-and-list whose every item is Under Construction is
   hidden with its items; the pages list (which also holds built pages) keeps
   its heading-less list and loses only its two Under Construction rows.
2. **Hidden means gone, not faded.** Each hidden item's `<li>` (and the
   Workspace `<h2>` and `<ul>`) gets the `hidden` class, which is
   `display: none` (`app/renderer/style.css:509`; the shell's display rules
   are all written under `:not(.hidden)`, `shell.css:13`). `display: none`
   takes the item out of the Tab order and out of what a screen reader reads,
   not just out of sight. The `hidden` attribute is not used: the shell's
   `#side-sections li:not(.hidden)` rule outranks the browser's own
   `[hidden]` rule and would show the item anyway.
3. **Where focus goes.** An Under Construction item opens no page (it shows a
   toast, P154), so hiding one never changes the page on screen. If keyboard
   focus sat on one of them when it was hidden, focus moves to the side
   panel's current page (else its first item) - the same place F6 puts it
   (`focusRegion("side")`) - so focus is never lost to the window. A tooltip
   showing for a hidden item is hidden with it.
4. **The setting is a checked item in the View menu, "Show Under
   Construction"** (Q1 as recommended). Ticked = shown. Choosing it flips
   the setting at once; nothing else changes. It is enabled from the first
   frame, on every page (the first-run page included), because it needs
   nothing of the page - it joins the menu's ALWAYS set (`app/main.js:563`).
5. **Kept on this PC, the way column widths are** (P139, P180): in the
   window's own storage (`localStorage`, key `tracker.underConstruction`,
   value `hidden` when hidden; no key = shown), never in `settings.json`,
   never in a household record, never through the engine. A PC whose storage
   cannot be read or written shows the items (the default) and keeps a
   choice made while the app is open until it closes - the same fallback as
   the column widths (`pages.js:865-904`).
6. **The menu's tick follows the page.** The page owns the setting; on every
   change it sends main.js `{ enable, checked }` on the one menu channel
   (SPEC-shell 5.4). `checked` lists the checkable ids that are on; main.js
   keeps only ids it knows to be checkable (`CHECKABLE`, one id), ignores a
   message without `checked`, and rebuilds the menu only when the enable
   list or the tick changed. Until the page speaks the item is ticked (the
   default, Q2).
7. **Keyboard and Windows behaviour (Fluent 2).** The item is a native
   Windows menu check item, so Windows draws its tick, its focus and its
   High Contrast colours; Alt, V, U reaches it (`&U`: no other View item
   uses U). No Ctrl shortcut: Ctrl+1..4, Ctrl+F, F5 are the View menu's, and
   a once-in-a-while preference does not need a key of its own. No motion is
   added: the items leave without animation.
8. **Words** (SPEC-shell 11.1, Title Case, five words or fewer, no
   monospace - the item is drawn by Windows' own menu font): one new menu
   word, `api.MENU["show_under_construction"] = "Show &Under Construction"`
   (Q3 as recommended), mirrored word for word in main.js's
   `DEFAULT_MENU_WORDS`.

## 3. Owner questions (each built as recommended meanwhile)

- **Q1. Where does the setting live?**
  (a) **Recommended, built:** a checked item in the View menu, "Show Under
  Construction", remembered on this PC the way column widths are - it is a
  screen preference, not a firm setting, and needs no engine change.
  (b) A line in the settings dialog (File > Change Clients Folder / the side
  panel's Settings), kept in `settings.json` for every PC of the firm.
- **Q2. What does a new install start with?**
  (a) **Recommended, built:** shown - nothing changes until a person turns it
  off. (b) Hidden.
- **Q3. The menu item's words.**
  (a) **Recommended, built:** "Show Under Construction" (the items' own tag,
  so the link is plain). (b) "Show Unfinished Pages".

## 4. Files, functions and lines to touch

| File | Change |
|---|---|
| `tracker/api.py` (`MENU`, after `reset_columns`, ~1255) | `"show_under_construction": "Show &Under Construction"` (words only). |
| `app/main.js` | `DEFAULT_MENU_WORDS.show_under_construction`; `BAR`'s View menu gains it after Reset Column Widths; `ALWAYS` gains it; new `CHECKABLE` and `menuChecked` (default: ticked); `buildTemplate` makes a checkable id a `checkbox` item with `checked`; `onMenuMessage` reads an optional `checked` list. |
| `app/preload.js` (comment, 19-20) | The message now may carry `checked`. |
| `app/renderer/shell.js` | New `SOON_KEY`, `shellSoonHidden`, `shellReadSoon`, `shellChecked`, `drawSoon`, `shellToggleSoon`; `drawSide` calls `drawSoon`; `shellEnabled` lists the id; `shellEnable` sends `checked`; `MENU_ANSWERS.show_under_construction`. |
| `app/renderer/index.html` (comment, 22-27) | Says the setting can hide the Under Construction items. |
| `tests/test_shell_menu.py` | The harness records `checked`; the ALWAYS set; the View menu's order; the tick follows the page; a stray `checked` id is dropped. |
| `tests/test_shell.py` | The menu-id table (878), the send shapes (902); new node tests of `drawSoon` / `shellToggleSoon` (hides five items and the Workspace heading, focus moves, storage kept and unreadable storage shows). |
| `pilot/wording-shell.tsv` | One `api.MENU` row. |
| `pilot/SPEC-shell.md` 11.3 | The table gains the row. |
| `pilot/SPEC-lists.md` 15.1 | One line: P197's setting. |
| `docs/repo-map.curated.json` | `app/main.js` and `app/renderer/shell.js` notes gain a P197 sentence; `python tools/repo_map.py update`. |
| `pilot/DECISIONS.md` P197 | Status line. |

No engine module, no `settings.json` field, no new package. Owning test
files: `tests/test_shell.py`, `tests/test_shell_menu.py`; `tests/test_api.py`
holds the five-word rule over `api.MENU` (one test,
`test_every_short_word_the_engine_adds_is_five_words_or_fewer`); guards
`tests/test_layers.py`, `tests/test_single_source.py`,
`tests/test_repo_map.py`. `tests/test_settings.py` is not run:
`settings.json` does not change.

## 5. What staff will notice

The View menu has a new last item, **Show Under Construction**, ticked.
Choosing it removes the five "(Under Construction)" items and the Workspace
heading from the side panel at once; choosing it again brings them back. The
choice holds across restarts on that PC; other PCs keep their own.

## 6. Docs the change makes true

README and `docs/runbook.md` say nothing of the side panel's Under
Construction items or of the View menu's items, so no line changes there.
`pilot/HANDOFF.md`'s top paragraph is the orchestrator's to write when P197
lands. The wording table, SPEC-shell 11.3 and SPEC-lists 15.1 change as in
section 4.
