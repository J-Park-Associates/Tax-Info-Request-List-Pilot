# Brief: the app shell (firm view, explorer breadcrumb, funnel menus)

Status: **confirmed by Jason** (2026-09-29), decisions P58-P62. Shaped with the
Impeccable skill (`shape`); product facts in [`../PRODUCT.md`](../PRODUCT.md).
This brief refines [`PLAN-ui.md`](PLAN-ui.md) and replaces its sidebar tree and
tabs. It is the input to the SPEC session; nothing is built yet.

Jason's answers (2026-09-29): side panel holds **firm sections only**; a return
shows **one grouped list**, not tabs; a firm keeps **200-500 households**.
Reference look: Dribbble "file manager UI" (a quiet side panel, a breadcrumb
title, one flat file list, status as coloured words). Reference rules:
Microsoft `winui-design` (P57) and Jason's design principles, below.

## 1. Job and audience

A preparer at a CPA firm, in season, checking what each return still needs and
clearing what waits for a person. Mode: **Operate**. Daily visits, many per day,
often over Remote Desktop.

## 2. Outcome

- Open the app and see, for the whole firm, what needs a person now.
- Drill from the firm to one return in at most three clicks, always knowing
  where you are (the breadcrumb).
- On a return, see every tracked document as one short line with its status.
- Nothing on screen that is not needed for the task in front of you.

## 3. Structure

```
┌ File  Client  View  Tools  Help ─────────────────────────────────────────────┐
├──────────────┬───────────────────────────────────────────────────────────────┤
│ ▣ Tracker    │ Clients › Smith Family › 2025 › 1040 - J…   🔍 Find client  ⟳ │
│              │                                                               │
│ Overview     │                                                               │
│ Needs review 3│ 1040 - John & Jane Smith                                     │
│ Reminders   2│ 3 need you · 2 waiting on client · 9 received                 │
│ Clients      │                                                               │
│              │ Needs you  3                                                  │
│              │ scan0012.pdf             Could not tell what it is    Check › │
│              │ IMG_2231.jpg             Fits two requests            Check › │
│              │                                                               │
│              │ Waiting on client  2                        Draft reminder ›  │
│              │ 1099-B      Schwab       Asked Mar 1                          │
│              │ 1098        Chase        Asked Mar 1                          │
│              │                                                               │
│              │ Received  9                                                   │
│ Sorted 6:00 ✓│ W-2         Acme Corp    Mar 3                                │
└──────────────┴───────────────────────────────────────────────────────────────┘
```

**Side panel (firm sections, the general menu).** Four sections, each a
vague-to-specific funnel into the main area:

| Section | Opens | Count shown |
|---|---|---|
| Overview | the landing page: firm totals, then returns with work waiting, oldest first | none |
| Needs review | every file waiting for a person, grouped by return | files waiting |
| Reminders | returns with a reminder draft ready | drafts ready |
| Clients | all households, searchable; opens filtered to "work waiting", one switch to "all" | none |

Below them only the last-sort line ("Sorted 6:00 AM" with a tick, or the
problem in words; during a sort, its progress and a Stop). The pilot badge and
tour stay where `pilot.js` puts them.

**Breadcrumb (the explorer path).** `Clients › household › year › return`,
every segment clickable, as the page's title row. At its right end: the
**search bar** (find a household or return by name, Ctrl+F) and, next to it,
the **sort icon** (P60). The current level's name is
the page heading beneath it. The **year is always in the path**, even when a
household has one year: the path matches the folders on disk (P61).

**Pages, one per level:**

- **Overview:** three numbers as large type (need a person / waiting on
  clients / returns complete), then the list of returns with work waiting.
- **Clients:** one row per household: name, returns this year, a short status.
- **Household:** its years and returns as rows; sharing and contact details
  as one quiet line under the heading.
- **Return:** one list in groups, in this order: **Needs you**, **Waiting on
  client**, **Received**, then **Set aside** folded shut. Group headings carry
  the dividing (size and weight, no boxes). One row = document, from whom,
  short status, date. The long explanation and the file path move into the
  row's tooltip.

## 4. The funnel: fewer buttons

**Rule:** one control is visible; everything else sits one level down, behind
the broader control that owns it (P60).

- **On screen, always, and the only button:** the **sort icon** beside the
  search bar. It runs Sort now. Being icon-only, it carries its name for screen
  readers, a tooltip with its words from the API ("Sort now"), and F9. While a
  sort runs it turns into Stop.
- **A level's actions** (household: Edit household, Add a return, Mark as
  shared, Open client folder, Open inbox; return: Edit request list, Open
  working folder, Open client folder, Open this return's report) live in the
  menu bar's **Client** menu and in a **right-click menu** on the breadcrumb,
  a row, or the page heading. No Actions button on screen.
- **On a row, on hover or focus only:** its one next step (**Check ›**,
  **Draft reminder ›**). Filing choices open from there.
- **In the menu bar (one-time and rare actions):**

| Menu | Items |
|---|---|
| File | New household… (Ctrl+N), Change clients folder…, Open clients folder, Exit |
| Client | Edit household…, Add a return…, Edit request list… (Ctrl+E), Mark as shared, Open client folder, Open inbox. Greyed when no client is open |
| View | Overview (Ctrl+1), Needs review (Ctrl+2), Reminders (Ctrl+3), Clients (Ctrl+4), Find (Ctrl+F: focuses the search bar), Refresh (F5: re-reads, never reloads the page) |
| Tools | Sort now (F9), Stop sorting, Schedule…, Repair the schedule, Firm status report, Clear a stuck lock |
| Help | Take the tour, Safeguards, Terms, Tester guide, About (version 0.2) |

Edit (Cut, Copy, Paste, Select all) is kept by role so text boxes keep their
keyboard shortcuts. No Reload, Zoom reset or Developer tools item: the council's
E-7 reason for hiding Electron's default menu still holds.

## 5. Design rules (Jason's principles, made testable)

1. **Grid:** every size, gap and padding is a step of **4, 8, 16, 24, 32 or
   48px**. The old 2, 12 and 20px steps are retired in the new shell. Rows are
   40px tall; controls 32px; the side panel 240px wide.
2. **Keep it or cut it:** for every element, if removing it does not stop the
   task, it goes or moves back a level (tooltip, Actions menu, menu bar). The
   SPEC lists each element of today's screen and where it goes.
3. **Hierarchy by type, not boxes:** no card inside a card. Groups are divided
   by heading size, weight and space. Hairlines only between rows.
4. **Type:** five roles only: **H1** page heading, **H2** group heading, **H3**
   row name, **body**, **caption**. Segoe UI Variable, sizes from the Build E
   ramp (20/16/14/14/12, plus 28 for the Overview numbers), line-height written
   unitless and landing on the 4px grid.
5. **Contrast:** WCAG AA for everything; AAA (7:1) for body text and row
   names. Status is a word plus a small dot, never colour alone.
6. **Light and dark:** the shell follows the Windows setting, light or dark,
   in 0.2 (P59). Every token gets a dark value, and both are checked for
   contrast. The window's first-paint colour follows the setting too.
7. **Alignment:** everything on the page aligns to one left keyline; numbers
   right-aligned in their column; icons nudged optically where needed.
8. **Consistency:** one button shape (P52), one menu style, one row style used
   on every page.
9. **Motion:** 150ms for hover, press and menus; a short fade for notices; no
   motion on page change. Windows "reduce motion" turns it all off.
10. **Five words at most (P63):** no label, heading, notice, error, tooltip
    or dialog line over five words; no path of any kind on screen; an icon that
    explains itself carries no words. Every element's verdict is in
    [`AUDIT-shell.md`](AUDIT-shell.md).
11. **Real content:** household names up to 60 characters, return names up to
    80, counts up to 4 digits, 500 households; long names end in "…" with the
    full name in the tooltip. Mock-ups use made-up names only.

## 6. States the SPEC must draw

First run (no clients folder: the setup form fills the main area, the side
panel greyed); loading (row outlines, never a lone spinner); empty (Overview:
"Nothing is waiting. The next sort is at 6:00 PM."); sort running (the last-sort
line shows progress and a Stop); sort failed (one notice at the top of the main
area with Retry); another PC holds the lock (notice, with Clear lock in Tools);
a return with nothing received yet; a household with no returns.

## 7. Boundaries

- **Untouched:** everything under `tracker/`, the reminder letter's text, the
  four standing rules' wording (still reachable: Help > Safeguards and the
  start-up line from PLAN-ui section 6).
- **Approved changes to fixed files (P58, P59):** `main.js` gains a custom
  menu and follows the Windows light/dark setting for its first paint;
  `preload.js` gains one channel from the menu to the page. P10 and P51 kept
  both files unedited; P58 relaxes that for these lines only. The grid steps in
  `pilot-ui.css` change.
- **Anti-goals:** a dashboard of charts; icons without words (the sort icon is
  the one exception, and carries its name and tooltip); tabs; a second button
  row; anything glass or blurred.
- Carried over from PLAN-ui unchanged: the custom tooltip, plain English
  everywhere with a wording table for Jason, the start-up safety line, one
  notice area.

## 8. Decisions (Jason, 2026-09-29)

| Question | Answer | Row |
|---|---|---|
| Edit `main.js` and `preload.js` for the menu bar | Yes | P58 |
| Dark mode in 0.2 | Yes, following Windows | P59 |
| What stays visible | Only Sort now, as a sort icon next to a search bar | P60 |
| Year in the path | Always | P61 |
