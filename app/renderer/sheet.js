// The side sheet (pilot SPEC-shell.md section 7; decision P74): Check a file
// and Draft reminder, in one drawer from the right over a scrim.
//
// A classic script, loaded after pages.js and before shell.js, sharing the
// globals of app.js, tooltip.js and pages.js. It is modal like every dialog
// (app.js's DIALOGS registry, openDialog, requestClose, trapTab): focus goes
// to its title, Tab stays inside, Escape and a click on the scrim close it,
// and closing puts focus back on the row that opened it. It types no word of
// its own: the title is the file's name or vocab.screen.sheet.reminder, the
// status is a short reason or a label the vocabulary holds, the icons are
// named by data-tip-key in index.html, and every button is the API's.
//
// What it does not do is decide anything about a file. Check a file places the
// parts of one row (app.js's reviewRow and movedRow already build every part
// and the handlers that write) in the sheet's body, its More fold and its
// footer, and restyles them; every write is the same call it always was,
// through the same functions, and the one delegate in app.js finds the row
// this file is showing with sheetRow(). Draft reminder needs nothing drawn
// here: the letter's parts sit in the sheet from the start with the ids
// drawReminder() looks up, and it draws them whenever a return's state
// arrives. Next moves on without writing, in the order the page was drawn:
// this return's Needs you files from a return page, every file of Needs
// Review from that page, the drafts in the Reminders page's order.
//
// A file opened from a firm-wide page belongs to a return that may not be
// the one whose state is on screen: the sheet reads that return's `state`
// (showReturn, one call; its failure is said as a notice by the caller of
// the read and the sheet closes) and only then draws. After a write that
// works the row is gone from the state and the sheet moves to the next file,
// or closes after the last: no message, because the row leaving is the news.

"use strict";

let sheetNow = null;       // what the sheet holds: {kind, ret, handle, order, opener, ready, row}
let sheetGeneration = 0;   // a late read never draws into a sheet that has moved on

// The row the sheet is showing, for app.js's delegate.
function sheetRow() {
  return sheetNow && sheetNow.kind === "check" ? sheetNow.row || null : null;
}

// ── the frame: title, scrim, the icons the kind uses ──────────────────
function sheetSet(id, on) {
  $(id).hidden = !on;
}

function sheetFrame(now, title) {
  const words = screenWords();
  sheetNow = now;
  $("sheet-title").textContent = title;
  setTipIfCut($("sheet-title"), title);
  sheetSet("sheet-check", now.kind === "check");
  sheetSet("check-actions", now.kind === "check");
  sheetSet("sheet-reminder", now.kind === "reminder");
  // The reminder's buttons are shown by the card's own draw, with the
  // letter they act on (P213), never by the frame.
  sheetSet("reminder-actions", false);
  $("sheet").removeAttribute("aria-busy");
  for (const id of ["sheet-open", "sheet-more", "sheet-next"]) sheetSet(id, false);
  sheetMore(false);
  if (now.kind === "check") {
    $("check-actions").replaceChildren();
    $("sheet-check").replaceChildren(h("span", { className: "visually-hidden" }, words.loading), ...shellSkeleton(3));
  }
  $("sheet-scrim").hidden = false;
  openDialog("sheet");
}

// The sheet is shut: nothing of the file stays in it, the scrim goes, the lock
// belongs to the page again, and focus goes back where it was (openDialog's
// own return finds the row it came from unless the page was drawn anew).
function sheetClosed() {
  const now = sheetNow;
  sheetNow = null;
  sheetGeneration += 1;
  $("sheet-scrim").hidden = true;
  $("sheet-check").replaceChildren();
  $("check-actions").replaceChildren();
  sheetMore(false);
  const back = dialogOpener.sheet;
  if (now && now.opener && !(back && document.contains(back))) pagesFocusAt(now.opener);
  appRouteChanged(shellRoute);   // a return read only for the sheet has no lock on this page
}

function closeSheet() {
  if (dialogStack.indexOf("sheet") !== -1) closeDialog("sheet");
}

// ── More: the rarely used fields and answers (SPEC 7.1) ───────────────
function sheetMore(on) {
  const button = $("sheet-more");
  button.setAttribute("aria-expanded", on ? "true" : "false");
  const fold = sheetNow && sheetNow.row ? sheetNow.row.querySelector(".sheet-more") : null;
  if (fold) fold.classList.toggle("hidden", !on);
}

// ── Check a file (SPEC 7.1) ───────────────────────────────────────────
// Where the file is in a return's state: parked, set aside by a person
// (Not requested), or moved by hand. A file filed since, or a moved one a
// person marked missing, is not there to check.
function sheetFind(state, handle) {
  const decisions = vocab.decisions;
  const moved = (state.moved || []).find((one) => one.handle === handle);
  if (moved) return { kind: "moved", moved };
  const entry = (state.index || []).find((one) => one.handle === handle);
  if (entry && entry.decision === decisions.needs_review) return { kind: "parked", entry };
  if (entry && entry.decision === decisions.dismissed) return { kind: "aside", entry };
  return null;
}

// What the sheet was drawn from: the kind the file is in and the record
// version its buttons will send. A write that worked changes one or the other
// even when the file keeps its handle (Not requested rewrites the same row;
// a Put back that parks it turns a moved copy into a parked file).
function sheetSeen(found) {
  const one = found.kind === "moved" ? found.moved : found.entry;
  return `${found.kind}:${one.seq}`;
}

// The footer's buttons, in the order the SPEC gives them (the secondary
// first, the primary at the right), taken out of the row that built them.
function sheetFooter(row, moved) {
  const buttons = [...row.children].filter((one) => one.tagName === "BUTTON");
  const rank = (one) => {
    const names = moved ? ["r-keep", "r-restore", "r-withdraw"] : ["r-dismiss", "r-file"];
    return names.findIndex((name) => one.classList.contains(name));
  };
  buttons.sort((a, b) => rank(a) - rank(b));
  for (const one of buttons) row.removeChild(one);
  return buttons;
}

// The short reason and the day it was received. A moved copy's row (state.moved)
// carries no date: its index row, by the same handle, does.
function sheetStatus(found, state) {
  const words = screenWords();
  const entry = found.entry;
  const said = found.kind === "moved" ? words.moved
    : found.kind === "aside" ? vocab.review_labels.dismiss : pagesReason(entry.code);
  const dated = entry || (state.index || []).find((one) => one.handle === found.moved.handle);
  const received = dated ? pagesDay(dated.received) : "";
  return h("p", { className: "sheet-status" },
    h("span", { className: "sheet-reason" }, said),
    received ? h("span", { className: "sheet-received" }, received) : null);
}

// Draw the file `handle` of the state on screen. False when it is not there.
function sheetDrawCheck(handle) {
  const state = lastState;
  const found = state ? sheetFind(state, handle) : null;
  if (!found) return false;
  const now = sheetNow;
  const choices = state.items.filter((one) => !isSetAside(one.manual_override));
  const ids = new Set(state.items.map((one) => one.identifier));
  const triage = new Map((state.review || []).map((one) => [one.handle, one]));
  const people = (state.engagement || {}).people || [];
  const row = found.kind === "moved" ? movedRow(found.moved, choices, state.items)
    : reviewRow(found.entry, choices, ids, found.kind === "parked", triage.get(handle), people);
  const name = found.kind === "moved" ? found.moved.original_name : found.entry.original_name;
  $("sheet-title").textContent = name;
  setTipIfCut($("sheet-title"), name);
  const buttons = sheetFooter(row, found.kind === "moved");
  now.row = row;
  now.handle = handle;
  now.shown = sheetSeen(found);
  $("sheet-check").replaceChildren(sheetStatus(found, state), row);
  $("check-actions").replaceChildren(...buttons);
  const entry = found.entry;
  const copy = $("sheet-open");
  copy.dataset.key = entry && entry.open_key && !notADocument(entry) ? entry.open_key : "";
  sheetSet("sheet-open", Boolean(copy.dataset.key));
  const fold = row.querySelector(".sheet-more");
  if (fold) fold.id = "sheet-more-body";
  sheetSet("sheet-more", Boolean(fold));
  sheetSet("sheet-next", sheetAfter(now).length > 0);
  sheetMore(false);
  applyLock();
  $("sheet-title").focus();
  return true;
}

// The files that follow this one in the order the page was drawn.
function sheetAfter(now) {
  const at = now.order.findIndex((one) => one.ret === now.ret && one.handle === now.handle);
  return at === -1 ? [] : now.order.slice(at + 1);
}

// One file of the order: read its return if it is not the one on screen,
// then draw it. True when the sheet drew it or has closed for a failed read;
// false when the file is no longer there, so the caller tries the next.
async function sheetShow(now, step) {
  const gen = sheetGeneration;
  now.ret = step.ret;
  now.handle = step.handle;
  now.ready = false;
  now.row = null;
  $("sheet-title").textContent = step.name;
  const onScreen = lastState && lastState.paths && lastState.paths.engagement === step.ret;
  if (!onScreen) {
    // An outline, as the frame draws one, never a blank sheet (P213).
    $("sheet-check").replaceChildren(h("span", { className: "visually-hidden" }, screenWords().loading), ...shellSkeleton(3));
    if (!(await showReturn(step.ret))) {
      if (gen === sheetGeneration) closeSheet();
      return true;
    }
  }
  if (gen !== sheetGeneration) return true;
  if (!sheetDrawCheck(step.handle)) return false;
  now.ready = true;
  return true;
}

// Check a file: the sheet opens on it at once with its name, and draws when
// the return's state is in. `ret` is the return's path, `handle` the file's.
async function openCheck(ret, name, handle) {
  const now = { kind: "check", ret, handle, order: pagesFiles(), opener: pagesWhere($("page")), ready: false, row: null };
  sheetFrame(now, name);
  const gen = sheetGeneration;
  try {
    // A firm page's state, if it is this return's, may be older than the
    // page: read it again. A return page has just read its own.
    const fresh = FIRM_LEVELS.indexOf(shellRoute.level) === -1 && lastState && lastState.paths && lastState.paths.engagement === ret;
    if (!fresh && !(await showReturn(ret))) {
      if (gen === sheetGeneration) closeSheet();
      return;
    }
    if (gen !== sheetGeneration) return;
    if (!sheetDrawCheck(handle)) {
      closeSheet();
      unanswered("check");
      return;
    }
    now.ready = true;
  } catch (err) {
    if (gen === sheetGeneration) closeSheet();
    failed(err);
  }
}

// The next file, without writing anything; the last file has no Next, so the
// sheet closes only when the files run out under a write.
async function sheetAdvance() {
  const now = sheetNow;
  if (!now || now.kind !== "check") return;
  const gen = sheetGeneration;
  try {
    for (const step of sheetAfter(now)) {
      if (await sheetShow(now, step)) return;
      if (gen !== sheetGeneration) return;
    }
    closeSheet();
  } catch (err) {
    // A file that cannot be drawn is said (a word the vocabulary lacks, a
    // state read that failed) and the sheet is shut: never left half drawn.
    if (gen === sheetGeneration) closeSheet();
    failed(err);
  }
}

// shell.js: one return's state has arrived. A file the sheet is showing that
// has left the list, or is there in another kind or at another record
// version, was answered (a write that worked): the next file, or close. The
// same file as it was drawn is a read, or a refusal: left as it is, with what
// the person typed.
function sheetStateArrived(state) {
  const now = sheetNow;
  if (!now || now.kind !== "check" || !now.ready) return;
  if (!state.paths || state.paths.engagement !== now.ret) return;
  const found = sheetFind(state, now.handle);
  if (found && sheetSeen(found) === now.shown) return;
  now.ready = false;
  sheetAdvance();
}

// ── Draft reminder (SPEC 7.2) ─────────────────────────────────────────
// The reminder of `ret` (a path), or the return on screen. Opened from the
// Reminders page it knows the drafts that follow, for Next.
async function openReminder(ret) {
  const target = ret || active;
  const order = shellRoute.level === "reminders" ? pagesDrafts() : [];
  const now = { kind: "reminder", ret: target, handle: "", order, opener: pagesWhere($("page")), ready: false, row: null };
  sheetFrame(now, screenWords().sheet.reminder);
  const gen = sheetGeneration;
  try {
    const onScreen = FIRM_LEVELS.indexOf(shellRoute.level) === -1 && lastState && lastState.paths && lastState.paths.engagement === target;
    if (!onScreen) {
      // Until this return's own state is in, the card held is another
      // return's: nothing on the sheet may copy or approve it (P213).
      forgetReminderCard();
      if (!(await showReturn(target))) {
        if (gen === sheetGeneration) closeSheet();
        return;
      }
    } else if (reminderCard && reminderCardFor === target) {
      drawReminder(reminderCard);   // the card on screen is this return's: its buttons come back with it
    } else {
      drawReminderReply(lastState.reminder_card || { reminder: null, not_yet: "" });   // the state on screen is this return's
    }
    if (gen !== sheetGeneration) return;
    now.ready = true;
    sheetSet("sheet-next", sheetDraftsAfter(now).length > 0);
    applyLock();
    $("sheet-title").focus();
  } catch (err) {
    if (gen === sheetGeneration) closeSheet();
    failed(err);
  }
}

function sheetDraftsAfter(now) {
  const at = now.order.findIndex((one) => one.ret === now.ret);
  return at === -1 ? [] : now.order.slice(at + 1);
}

async function sheetNextDraft() {
  const now = sheetNow;
  const next = now ? sheetDraftsAfter(now)[0] : null;
  if (!next) return;
  const gen = sheetGeneration;
  try {
    now.ret = next.ret;
    now.ready = false;
    forgetReminderCard();   // the draft on the sheet is the last one's until this one is read (P213)
    if (!(await showReturn(next.ret))) {
      if (gen === sheetGeneration) closeSheet();
      return;
    }
    if (gen !== sheetGeneration) return;
    now.ready = true;
    sheetSet("sheet-next", sheetDraftsAfter(now).length > 0);
    applyLock();
  } catch (err) {
    if (gen === sheetGeneration) closeSheet();
    failed(err);
  }
}

// A button of the file on the sheet, pressed for a right-click item that stands
// for it (Not requested, Another return, Put back, Keep here): the write is the
// sheet's own. False when the sheet has no such button.
function sheetPress(className) {
  const button = $("sheet").querySelector(`.${className}`);
  if (!button || button.disabled) return false;
  button.click();
  return true;
}

// ── wiring ────────────────────────────────────────────────────────────
$("sheet-more").addEventListener("click", () => sheetMore($("sheet-more").getAttribute("aria-expanded") !== "true"));
$("sheet-next").addEventListener("click", () => {
  if (!sheetNow) return;
  if (sheetNow.kind === "reminder") sheetNextDraft();
  else sheetAdvance();
});
$("sheet-scrim").addEventListener("click", () => requestClose("sheet"));
