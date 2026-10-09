// The app shell (pilot SPEC-shell.md sections 3, 4, 5.3-5.4, 6.8 and 8;
// decisions P58-P77): the side panel, the path row, the search, the sort
// icon, the one route, the setup page, and the page's side of the `menu`
// channel.
//
// A classic script, loaded after app.js and tooltip.js, sharing their
// globals. app.js keeps the API call, the vocabulary, the notices, the
// dialogs and every write; this file only decides what is on screen around
// the page and which page. It types no word of its own: every name, tooltip
// and line is the API's vocabulary (vocab.screen), and a word the vocabulary
// lacks is a loud failure, never a guess. It builds the page from DOM nodes
// only, with app.js's builder `el` (named `h` here), which sets only the
// attributes it names (decision 137).
//
// What app.js calls (each one line in app.js, so the seam is visible):
//   shellVocabulary()   the vocabulary has arrived or changed
//   shellAdopt(listed)  a `list` reply was adopted (paths, last sort, firm)
//   shellNeedsRoot(on, listed)  no clients folder is set (or it is now)
//   shellChanged()      the sort, the lock or the pass's progress changed
//   shellProgress(said) one progress line of the running pass
//   shellKey(e)         one keydown, before app.js's own (true = handled)
//   shellStateArrived(state)  one return's state arrived: draw its page, and
//                       ask the firm's counts again if the state moved them
// What this file calls in app.js: the shared helpers el (as `h`),
// storeRead/storeWrite, takeReply, shellWaiting() and the setupDraft object,
// and appRouteChanged(route), so the lock (a notice) follows the return on
// screen.
// What this file calls in pages.js, sheet.js and app.js (all loaded before it):
//   pagesDraw(route, page)   draw the route's page into #page
//   pagesLeave()             the setup page took the screen: the pages' notices go
//   pagesTally(state)        how many of each group a state holds
//   pagesKey(e)              a key on a row list (the one keydown listener
//                            stays in app.js and hands keys here)
//   pagesMenu(id, token)     a right-click menu item on a row
//   sheetStateArrived(state) the file on the sheet may have left the list
//   closeSheet()             navigating shuts the sheet
//   openRoll(), openSafeguards(), openAbout(), openReminder()  (app.js, sheet.js)
// A menu id the page cannot answer is said as a notice and logged.

"use strict";

// ── one route (SPEC 4.1) ──────────────────────────────────────────────
// {level, household, year, ret}: `level` is one of LEVELS; household and
// ret are the paths the API reported; year is a number. No history and no
// back button: the path and the side panel are the way around (P75).

const LEVELS = ["overview", "needs-review", "reminders", "clients", "household", "year", "return", "setup"];
const FIRM_LEVELS = ["overview", "needs-review", "reminders", "clients"];
const SCREEN_KEYS = { "needs-review": "needs_review" };
const SOON_KEY = "tracker.underConstruction";   // this PC's own storage, never the record (P197)

let shellRoute = { level: "overview" };
let shellBack = null;          // the route Cancel goes back to, from Change clients folder
let shellRootSet = false;      // a clients folder is set (the menu's "a clients folder is set")
let shellPaths = {};           // the list's `paths`: clients_root, status
let shellLastPass = null;      // the list's last_pass: {text, level, ok, when}
let shellProgressNow = null;   // the running pass's last line: {n, total}
let shellFirmNow = { status: "idle", data: null };   // idle, loading, ok, failed
let shellFirmAsked = false;    // a second ask arrived while one ran
let shellFirmEarly = null;     // a `firm` asked before the load that adopts it (P221, P228)
let shellFirmEarlyLanded = false;   // that `firm`'s reply is here, adopted or not: the last counts are dropped (P229)
let shellFirmLast = null;      // the last counts asked at launch (P229): {reply} until drawn or dropped
let shellFirmAsOf = "";        // the counts shown are the last counts, as of this "HH:MM" (P229); "" once fresh
let shellClock = 0;            // orders a load's sending against a write's landing (P218)
let shellFirmSentAt = 0;       // when the running load sent its `firm`
let shellWroteAt = 0;          // when a write's reply last landed
const shellFirmHeld = new Map();   // return path -> a state whose counts differed while a load sent after the write ran
let shellFirmCount = null;     // the running `firm`'s last count line: {done, total} (P222)
let shellFirmSlow = false;     // the running `firm` has taken longer than SHELL_FIRM_SLOW_MS
let shellFirmTimer = null;
const SHELL_FIRM_SLOW_MS = 2000;   // past this a firm page's wait says how many households are read (P222)
let shellPageBusy = false;     // a return's state is on its way
let shellPageFailed = false;   // it could not be had (the notice says why, with Retry)
let shellFound = [];           // the search list's options
let shellSoonHidden = null;    // View › Show Under Construction is off: read once from this PC (P197)

// The vocabulary blocks this file reads. A block that is missing is the
// failure it looks like: the page is told and the error log has it.
function screenWords() {
  if (!vocab || !vocab.screen) throw new Error("vocab.screen");
  return vocab.screen;
}

// The short line a notice shows for a failure the API words as a long
// sentence (SPEC 11.1: five words, no path): the vocabulary's word for `key`
// in vocab.screen.notices. Where the vocabulary has not been given that word
// yet, the approved short line of the setup notice stands in - never a word of
// the page's own - and the long sentence goes to the error log, whatever is
// shown. The keys asked for and still missing are listed in the S4 rebuild
// handoff for S6. A missing word is loud, not silent: the key the vocabulary
// lacks goes to the error log, once per key while the app runs (review 2, F1).
function shortNotice(key) {
  const said = vocab && vocab.screen && vocab.screen.notices ? vocab.screen.notices[key] : "";
  if (said) return said;
  shortNotice.missing = shortNotice.missing || new Set();
  if (!shortNotice.missing.has(key)) {
    shortNotice.missing.add(key);
    window.tracker.logError(`vocab.screen.notices.${key}`);   // the key it lacks, as pagesReason throws `reasons.${code}`
  }
  return vocab.after_install.wait;
}

// A dotted key ("screen.sort.now") to its words, for data-tip-key.
function shellWords(key) {
  let at = vocab;
  for (const part of key.split(".")) {
    if (at === null || at === undefined || typeof at !== "object" || !(part in at)) throw new Error(key);
    at = at[part];
  }
  return String(at);
}

// ── the builder that sets only what it names ──────────────────────────
// This file and pages.js build with app.js's `el` (its attribute list is the
// union of what every file draws); `h` is its short name here.
function h(tag, attrs = {}, ...children) {
  return el(tag, attrs, ...children);
}

// A drawn icon (SPEC 3.8) from the sprite in index.html.
const SVG_NS = "http://www.w3.org/2000/svg";
function icon(name, small) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.classList.add("icon");
  if (small) svg.classList.add("icon-small");
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS(SVG_NS, "use");
  use.setAttribute("href", `#i-${name}`);
  svg.append(use);
  return svg;
}

// ── the vocabulary ────────────────────────────────────────────────────
// Every icon-only control names its words by data-tip-key; this sets both
// the accessible name and the tooltip from it (SPEC 14.1).
function shellNameIcons() {
  for (const node of document.querySelectorAll("[data-tip-key]")) {
    const words = shellWords(node.dataset.tipKey);
    node.setAttribute("aria-label", words);
    setTip(node, words);
  }
}

function shellVocabulary() {
  const words = screenWords();
  $("side").setAttribute("aria-label", words.side_label);
  $("crumbs").setAttribute("aria-label", words.path_label);
  for (const node of document.querySelectorAll(".side-section[data-section]")) {
    const key = node.dataset.section;
    node.querySelector(".side-name").textContent = words.sections[SCREEN_KEYS[key] || key];
  }
  shellSideWords(words);
  shellNameIcons();
  shellChanged();
  shellDraw();
}

// The side panel's other words (pilot SPEC-lists 15; P153-P155): the brand
// band, the section headings, the Client Types (their forms the tooltip),
// the items not built yet (each "Under Construction" as its tooltip) and
// Settings. A word the vocabulary lacks throws, as every word here does.
function shellSideWords(words) {
  const side = words.side;
  if (!side) throw new Error("side");
  $("side-brand-name").textContent = side.brand;
  $("side-brand-product").textContent = side.product;
  $("side-types-heading").textContent = side.types;
  $("side-workspace-heading").textContent = side.workspace;
  $("side-settings").querySelector(".side-name").textContent = side.settings;
  for (const node of document.querySelectorAll(".side-section[data-soon]")) {
    const said = side.soon[node.dataset.soon];
    if (!said) throw new Error(`side.soon.${node.dataset.soon}`);
    node.querySelector(".side-name").textContent = said;
    setTip(node, side.under_construction);
  }
  for (const node of document.querySelectorAll(".side-section[data-type]")) {
    const label = (words.client_types || {})[node.dataset.type];
    const forms = (vocab.client_type_forms || {})[node.dataset.type];
    if (!label || !forms) throw new Error(`client_types.${node.dataset.type}`);
    node.querySelector(".side-name").textContent = label;
    setTip(node, forms.join(", "));
  }
}

// ── data the list and the firm command bring ──────────────────────────
function shellAdopt(listed) {
  // A write that changes the list carries the list half alone: what it does
  // not carry is kept.
  if (listed.paths) shellPaths = listed.paths;
  if (listed.last_pass) shellLastPass = listed.last_pass;
  shellRootSet = !listed.needs_root && Boolean(listed.root);
  if (listed.needs_root) shellDropEarlyFirm();
  if (shellRootSet) shellLoadFirm();
  shellShowLast();   // the launch's last counts, if they landed before the words did (P229)
  shellChanged();
}

// The Overview asked now, before the list that would start it has landed:
// at launch beside the list (P221) - main.js allows `firm` before the
// allowlist is learned - and when a Sort ends, beside the list and the
// shown return's state (P228). It is sent through window.tracker.call
// itself - call() says a reply's warnings, which needs the vocabulary the
// list brings. The load that follows the list adopts its reply instead of
// sending another. A load already running sends nothing more here (P218):
// one sent before a write cannot hold it, so the list's adopt queues one
// more, as it always has.
function shellAskFirmNow() {
  if (shellFirmEarly || shellFirmNow.status === "loading") return;   // one is on its way already
  shellFirmNow = { status: "loading", data: shellFirmNow.data };
  shellFirmSent();
  shellFirmEarlyLanded = false;
  shellFirmEarly = new Promise((resolve) => resolve(window.tracker.call(["firm"])))
    .then((reply) => ({ reply }), (err) => ({ err }))
    .then((got) => { shellFirmEarlyLanded = true; return got; });
  shellUpdating();
}

// A list that asks for a clients folder has no Overview to show: the early
// reply is never drawn, and neither are the last counts (P229), asked or shown.
function shellDropEarlyFirm() {
  shellFirmLast = null;
  const shown = shellFirmAsOf !== "";
  shellFirmAsOf = "";
  if (!shellFirmEarly && !shown) return;
  shellFirmEarly = null;
  shellFirmDone();
  shellFirmNow = { status: "idle", data: shown ? null : shellFirmNow.data };
}

// ── the last counts at launch (P229; Jason, 2026-10-08) ───────────────
// While the launch's Overview is read afresh, the counts it last had today
// - the API's `firm-last`, read from the firm cache with no fingerprint
// taken and no record read - are drawn under P222's marker (the page busy,
// figures, statuses and side counts muted; the path row's slot says
// Updating) and the Overview says "Updating, as of {time}" in its own Work
// line (Jason, 2026-10-08: "Time on Overview page"; pagesAsOf). The API
// answers {last: null, warnings} unless the cache is today's, this
// program's, this clients folder's and holds every household; a refused or
// failed ask shows nothing, and the page waits as it did. The fresh reply
// replaces the last counts in place; one that lands after it is dropped; a
// fresh reply that fails takes them down, so held counts never outlive a
// failed refresh. Rows stay usable meanwhile, and every action reads afresh
// as it does during any "Updating": Open and Check read the return's state,
// Copy and Approve act only on a card drawn from that read, and every write
// is judged under the household's lock against the record.
// A Retry of the start-up after a failed first list asks again only when
// this ask failed; one held or drawn is not asked twice - harmless, since all
// it brings is today's counts for the seconds before the fresh ones.
function shellAskFirmLast() {
  if (shellFirmLast || shellFirmNow.data) return;   // asked already, or counts are drawn
  const mine = { reply: null };
  shellFirmLast = mine;
  new Promise((resolve) => resolve(window.tracker.call(["firm-last"])))
    .then((reply) => {
      if (shellFirmLast !== mine) return;   // dropped: the fresh counts, or a list that asks for a folder
      mine.reply = reply;
      shellShowLast();
    }, () => {
      if (shellFirmLast === mine) shellFirmLast = null;   // a failed ask shows nothing
    });
}

// The reply's counts and their time, or null. `firm-last` answers the
// `firm` reply's own fields with `last: true` and `as_of` ("HH:MM", as
// next_sort says a time) beside them, or refuses with {last: null,
// warnings}. A refusal, an error, or any other shape shows nothing.
function shellLastOf(reply) {
  if (!reply || typeof reply !== "object" || reply.error || reply.last !== true) return null;
  if (typeof reply.as_of !== "string" || !/^\d{2}:\d{2}$/.test(reply.as_of)) return null;
  if (!Array.isArray(reply.returns) || !reply.totals || typeof reply.totals !== "object") return null;
  const data = { ...reply };
  delete data.last;
  delete data.as_of;
  return { data, asOf: reply.as_of };
}

// Draw the last counts once they, the words and the clients folder are all
// here - and only while the fresh reply is still on its way with nothing
// drawn. Each reply is drawn at most once. A fresh reply that has already
// landed, even one the list's load has not adopted yet, drops them: "if the
// real one lands first, firm-last's reply is dropped" (the SPEC).
function shellShowLast() {
  const mine = shellFirmLast;
  if (!mine || !mine.reply || !vocab || !vocab.screen || !shellRootSet) return;
  shellFirmLast = null;
  if (shellFirmEarlyLanded) return;
  const last = shellLastOf(mine.reply);
  if (!last || shellFirmNow.status !== "loading" || shellFirmNow.data) return;
  if (!screenWords().updating_as_of) {
    window.tracker.logError("vocab.screen.updating_as_of");   // the key it lacks: loud, never a guess
    return;
  }
  shellFirmAsOf = last.asOf;
  shellFirmNow = { status: "loading", data: last.data };
  shellChanged();
  if (shellFollowsCounts()) shellDraw();
}

// The early reply, said as call() says any reply (takeReply).
async function shellAdoptEarly(early) {
  const got = await early;
  if (got.err) throw got.err;
  return takeReply(got.reply, ["firm"]);
}

async function shellAskFirm() {
  if (!Array.isArray(vocab.commands) || vocab.commands.indexOf("firm") === -1) throw new Error("firm");
  return call(["firm"]);
}

// A `firm` has been sent: when, for the writes that land meanwhile (P218),
// and the clock after which its wait says how far it has read (P222).
function shellFirmSent() {
  shellFirmSentAt = ++shellClock;
  shellFirmCount = null;
  shellFirmSlow = false;
  clearTimeout(shellFirmTimer);
  shellFirmTimer = setTimeout(shellFirmTookLong, SHELL_FIRM_SLOW_MS);
}

// Its reply has landed (or it was dropped): the count and the clock go.
function shellFirmDone() {
  clearTimeout(shellFirmTimer);
  shellFirmTimer = null;
  shellFirmSlow = false;
  shellFirmCount = null;
}

function shellFirmTookLong() {
  shellFirmTimer = null;
  shellFirmSlow = true;
  shellDrawReading();
}

// app.js: a write's reply has landed (P218). A load sent before it cannot
// hold what it wrote; one sent after it can.
function shellWriteLanded() {
  shellWroteAt = ++shellClock;
}

// app.js: one count line of the running `firm` (P222; progress.count_line):
// how many of the households it reads afresh it has read. Never a pass's.
function shellFirmProgress(said) {
  if (!said || shellFirmNow.status !== "loading") return;
  const { done, total } = said;
  if (!Number.isInteger(done) || !Number.isInteger(total) || total < 1 || done < 0 || done > total) return;
  shellFirmCount = { done, total };
  shellDrawReading();
}

// How far the running `firm` has read, once its wait has passed
// SHELL_FIRM_SLOW_MS and it has said so - only while no counts are held.
function shellReading() {
  if (!shellFirmSlow || !shellFirmCount || shellFirmNow.status !== "loading" || shellFirmNow.data) return null;
  return shellFirmCount;
}

// The words and the bar for that count, built as the last-sort bar is.
function shellReadingNodes(count) {
  const words = h("span", { className: "firm-reading-words", id: "firm-reading-words" });
  const bar = h("div", { className: "last-sort-bar firm-reading-bar", role: "progressbar", "aria-valuemin": "0", "aria-labelledby": "firm-reading-words" }, h("span"));
  shellSetReading(words, bar, count);
  return h("div", { className: "firm-reading" }, words, bar);
}

function shellSetReading(words, bar, count) {
  words.textContent = fill(screenWords().reading_households, { n: count.done, total: count.total });
  bar.setAttribute("aria-valuemax", String(count.total));
  bar.setAttribute("aria-valuenow", String(count.done));
  bar.querySelector("span").style.setProperty("width", `${Math.round((count.done / count.total) * 100)}%`);
}

// A firm page waiting with no counts held says the count where it said the
// hidden Loading: updated in place once it is drawn, so a screen reader's
// place in the page is kept.
function shellDrawReading() {
  if (!vocab || !vocab.screen || FIRM_LEVELS.indexOf(shellRoute.level) === -1) return;
  const count = shellReading();
  if (!count) return;
  const page = $("page");
  const words = page.querySelector(".firm-reading-words");
  const bar = page.querySelector(".firm-reading-bar");
  if (words && bar) shellSetReading(words, bar, count);
  else drawPage();
}

// The Overview's counts (SPEC 4.2): at start, beside the list (P221); after
// a sort ends, after F5 and after a write that changes a count. While it
// runs a firm page with no counts shows its loading state, and one drawn
// from counts held says Updating (P222); a failure is one notice with Retry
// and the pages keep what they last had.
async function shellLoadFirm() {
  const early = shellFirmEarly;
  shellFirmEarly = null;
  if (!early && shellFirmNow.status === "loading") {
    shellFirmAsked = true;
    return;
  }
  shellFirmNow = { status: "loading", data: shellFirmNow.data };
  if (!early) shellFirmSent();
  shellChanged();
  shellUpdating();
  try {
    const fresh = early ? await shellAdoptEarly(early) : await shellAskFirm();
    shellFirmNow = { status: "ok", data: fresh };
  } catch (err) {
    failureSentence(err);
    // The launch's last counts are never kept past a failed refresh (P229).
    shellFirmNow = { status: "failed", data: shellFirmAsOf ? null : shellFirmNow.data };
    notice({ sentence: screenWords().notices.firm_failed, kind: "failed" }, { retry: shellLoadFirm });
  }
  // A reply, fresh or failed, ends the last counts: drawn or still on their way.
  shellFirmLast = null;
  shellFirmAsOf = "";
  shellFirmDone();
  // A state that arrived during this load, after the write it shows, was
  // held back (P218): one more load only if these counts still differ.
  if (shellFirmNow.status === "ok" && [...shellFirmHeld.values()].some(shellCountsDiffer)) shellFirmAsked = true;
  shellFirmHeld.clear();
  if (shellFirmAsked) {
    shellFirmAsked = false;
    shellFirmNow = { status: "idle", data: shellFirmNow.data };
    shellLoadFirm();
    return;
  }
  shellChanged();
  if (shellFollowsCounts()) shellDraw();
}

// The pages drawn from the firm's counts: the firm pages, and a household's
// and a year's, whose rows carry each return's status (P222).
function shellFollowsCounts() {
  return FIRM_LEVELS.indexOf(shellRoute.level) !== -1 || shellRoute.level === "household" || shellRoute.level === "year";
}

// Counts are held and asked again.
function shellFirmUpdating() {
  return shellFirmNow.status === "loading" && Boolean(shellFirmNow.data);
}

// "Updating" on a page drawn from the counts as a load starts, without
// drawing it again (P222): the page's rows stay usable.
function shellUpdating() {
  if (!vocab || !vocab.screen || !shellFollowsCounts() || shellPageBusy || !shellFirmUpdating()) return;
  const page = $("page");
  page.setAttribute("aria-busy", "true");
  shellMarkUpdating(page, true);
}

// The word sits in the path row, in #page-updating, which index.html keeps
// from the start: nothing on the page moves when it comes or goes, so a
// click aimed at a row never lands on its neighbour. The one status is
// reused and its words set only when they change, so a redraw is not read
// out again.
function shellMarkUpdating(page, on) {
  page.classList.toggle("is-updating", on);
  const said = $("page-updating");
  // Updating alone, the launch's last counts too: their time is said on
  // the Overview itself (P229; pagesAsOf), so the slot stays 8 ch and the
  // path beside it is never squeezed.
  const words = on ? screenWords().updating : "";
  if (said.textContent !== words) said.textContent = words;
}

// What pages.js reads (with shellRoute, shellLoading and shellGo): the
// counts, and while the launch's last counts stand, their time (P229).
function shellFirm() {
  return shellFirmAsOf ? { ...shellFirmNow, asOf: shellFirmAsOf } : shellFirmNow;
}

// ── the household and return a route names ────────────────────────────
function shellHousehold(path) {
  return households.find((one) => one.path === path) || null;
}
function shellReturn(path) {
  return engagements.find((one) => one.path === path) || null;
}
function shellOwnReturns(household) {
  return engagements.filter((one) => one.household === household);
}

function shellHasClient() {
  return ["household", "year", "return"].indexOf(shellRoute.level) !== -1;
}

// ── go (SPEC 4.1) ─────────────────────────────────────────────────────
// Resolves when the return the page needs has been read (or at once when it
// needs none), for a caller that goes on from there (a row's menu).
function shellGo(next) {
  if (LEVELS.indexOf(next.level) === -1) throw new Error(next.level);
  if (shellRoute.level === "setup" && next.level !== "setup" && !shellRootSet) return Promise.resolve();   // the folder comes first
  closeSheet();
  hideFound();
  hideTip();   // tooltip.js: a tip goes with its page, even under a resting mouse (P202 R2)
  if (next.level === "setup") shellBack = shellRoute.level === "setup" ? shellBack : shellRoute;
  shellRoute = next;
  // Nothing the window's other side does may stop the page from going where
  // the person asked: a lock or a menu channel that throws is a notice.
  try {
    appRouteChanged(next);   // app.js: the lock belongs to the return on screen
  } catch (err) {
    failed(err);
  }
  shellPageBusy = next.level === "return";
  shellPageFailed = false;
  shellDraw();
  const page = $("page");
  page.scrollTop = 0;
  page.focus({ preventScroll: true });
  return shellOpenState();
}

// A return's page needs its state, and a household or year page needs the
// state on screen to be one of its own returns' (Sort now sorts the active
// return's household, and the household's notices come with that state).
// Both are app.js's showReturn.
function shellOpenState() {
  const route = shellRoute;
  let path = null;
  if (route.level === "return") path = route.ret;
  else if (route.level === "household" || route.level === "year") {
    const own = shellOwnReturns(route.household);
    const shown = lastState && lastState.paths ? lastState.paths.engagement : "";
    // A working return first - active and not rolled forward, as the list's
    // household says - so the household's Sort reports on one it sorts (P134).
    const working = ((shellHousehold(route.household) || {}).returns || [])
      .filter((one) => one.active !== false && !one.superseded_by).map((one) => one.path);
    if (own.length && !own.some((one) => one.path === shown)) {
      path = (own.find((one) => one.path === active) || own.find((one) => working.indexOf(one.path) !== -1) || own[0]).path;
    }
  }
  if (!path) return Promise.resolve();
  return showReturn(path).then((drawn) => {
    if (shellRoute !== route) return;
    shellPageBusy = false;
    shellPageFailed = route.level === "return" && !drawn;
    shellDraw();
  });
}

// app.js: one return's `state` has arrived (a read, or a write's reply). The
// page is drawn from it; if what it holds no longer matches the firm's
// counts for that return, the counts are asked again (SPEC 4.2: after any
// write that changes a count) - never on a plain read, which changes none.
function shellStateArrived(state) {
  // The state has arrived and a write's reply is a success: an error of the
  // page's own from here on is said as an error of the page (a notice, the
  // details in the error log) and never escapes to the write's caller, which
  // would say a write that worked had failed.
  try {
    shellDraw();
    sheetStateArrived(state);   // sheet.js: the file answered leaves, the next comes
    if (!shellCountsDiffer(state)) return;
    // A load sent after the last write landed may already hold what this
    // state shows (after a Sort, the list's own load): it is remembered and
    // compared when that load lands, never a second load queued against the
    // old counts (P218). A load sent before it is followed by another.
    if (shellFirmNow.status === "loading" && shellFirmSentAt > shellWroteAt) shellFirmHeld.set(state.paths.engagement, state);
    else shellLoadFirm();
  } catch (err) {
    failed(err);
  }
}

// The state's own tally differs from the firm's counts for its return.
function shellCountsDiffer(state) {
  const firm = shellFirmNow.data;
  const mine = firm && state.paths ? firm.returns.find((one) => one.path === state.paths.engagement) : null;
  if (!mine) return false;
  const tally = pagesTally(state);
  return Object.keys(tally).some((key) => tally[key] !== mine.counts[key]);
}

function shellDraw() {
  drawSide();
  drawFindWords();
  drawPath();
  drawPage();
  shellChanged();
}

// ── side panel (SPEC 3.3) ─────────────────────────────────────────────
function shellSection() {
  return FIRM_LEVELS.indexOf(shellRoute.level) !== -1 ? shellRoute.level
    : shellRoute.level === "setup" ? null : "clients";
}

function shellCounts() {
  const totals = shellFirmNow.data && shellFirmNow.data.totals;
  return totals ? { "needs-review": totals.files, reminders: totals.drafts } : {};
}

function drawSide() {
  // First run: drawn disabled, no counts. From Change clients folder the
  // panel stays enabled (SPEC 6.8).
  const off = shellRoute.level === "setup" && !shellRootSet;
  // A Client Type is the current item while Clients shows it (P153).
  const type = shellRoute.level === "clients" ? pagesClientType : "";
  for (const node of document.querySelectorAll(".side-section")) {
    const key = node.dataset.section;
    node.disabled = off;
    const here = key ? key === shellSection() && !type : Boolean(type) && node.dataset.type === type;
    if (here) node.setAttribute("aria-current", "page");
    else node.removeAttribute("aria-current");
    if (key) node.setAttribute("aria-keyshortcuts", `Control+${FIRM_LEVELS.indexOf(key) + 1}`);
  }
  drawSoon();
}

// ── View › Show Under Construction (pilot SPEC-hide-under-construction, P197) ──
// Kept on this PC as the column widths are: storage that cannot be read
// shows the items (a new install's default), and a write it refuses holds
// the choice while the app is open.
function shellReadSoon() {
  if (shellSoonHidden !== null) return shellSoonHidden;
  shellSoonHidden = storeRead(SOON_KEY) === "hidden";   // unreadable: shown
  return shellSoonHidden;
}

// The bar's ticked items, sent with the enable list: main.js draws the tick.
function shellChecked() {
  return shellReadSoon() ? [] : ["show_under_construction"];
}

// Hidden is gone, not faded: the .hidden class is display: none, so a hidden
// item leaves the Tab order and what a screen reader reads (the hidden
// attribute would lose to the shell's `li:not(.hidden)` display rule). A
// heading whose every item is Under Construction (Workspace) goes with them.
function drawSoon() {
  const hide = shellReadSoon();
  for (const node of document.querySelectorAll(".side-section[data-soon]")) node.closest("li").classList.toggle("hidden", hide);
  for (const list of document.querySelectorAll(".side-list")) {
    const items = list.querySelectorAll(".side-section");
    const allSoon = items.length > 0 && list.querySelectorAll(".side-section[data-soon]").length === items.length;
    const heading = $(list.getAttribute("aria-labelledby"));
    list.classList.toggle("hidden", hide && allSoon);
    if (heading) heading.classList.toggle("hidden", hide && allSoon);
  }
}

// The menu's answer: flip, keep, redraw, and tell the menu its tick. Focus
// on an item now hidden moves to the side panel's current page, where F6
// puts it, so it is never lost to the window; a tip it showed goes with it.
function shellToggleSoon() {
  const hide = !shellReadSoon();
  shellSoonHidden = hide;
  storeWrite(SOON_KEY, hide ? "hidden" : null);
  const held = document.activeElement;
  const lost = Boolean(hide && held && held.closest && held.closest(".side-section[data-soon]"));
  drawSoon();
  if (hide) hideTip();
  if (lost) focusRegion("side");
  shellEnable();
}

// ── last sort (SPEC 8.3) ──────────────────────────────────────────────
function sameDay(a, b) {
  return a.toDateString() === b.toDateString();
}

function drawLastSort() {
  const words = screenWords().last_sort;
  const box = $("last-sort");
  box.classList.remove("is-failed");
  const line = (text, ...more) => h("p", { className: "last-sort-line" }, h("span", { className: "last-sort-text" }, text), ...more);
  if (scanning) {
    const p = shellProgressNow;
    const known = p && Number.isInteger(p.n) && Number.isInteger(p.total) && p.total > 0;
    const text = scanning.stopping ? screenWords().sort.stopping
      : known ? fill(words.running, { n: p.n, total: p.total }) : "";
    const attrs = { className: "last-sort-bar", role: "progressbar", "aria-valuemin": "0" };
    if (known) Object.assign(attrs, { "aria-valuemax": String(p.total), "aria-valuenow": String(p.n) });
    const fillBar = h("span");
    if (known) fillBar.style.setProperty("width", `${Math.round((p.n / p.total) * 100)}%`);
    box.replaceChildren(...(text ? [line(text)] : []), h("div", attrs, fillBar));
    return;
  }
  const last = shellLastPass;
  if (!last || !last.when) {
    box.replaceChildren(line(words.never));
    return;
  }
  if (last.ok === false) {
    box.classList.add("is-failed");
    box.replaceChildren(line(words.failed));
    return;
  }
  const when = new Date(last.when);
  const today = sameDay(when, new Date());
  const text = today
    ? fill(words.today, { time: when.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) })
    : fill(words.other_day, { date: when.toLocaleDateString([], { month: "short", day: "numeric" }) });
  const done = h("span", { className: "last-sort-done", tabindex: "0", role: "img", "aria-label": words.done }, icon("done", true));
  setTip(done, words.done);
  box.replaceChildren(line(text, done));
}

// A progress line names the household it is on as `n` of `of` (the API's
// progress.household pattern); the last-sort line says the same two numbers.
function shellProgress(said) {
  if (!said) return;
  if (Number.isInteger(said.n) && Number.isInteger(said.of)) shellProgressNow = { n: said.n, total: said.of };
  else if (!said.pass && !said.household) shellProgressNow = null;
}

// ── path row (SPEC 3.4) ───────────────────────────────────────────────
function crumbList() {
  const route = shellRoute;
  const words = screenWords();
  if (route.level === "setup") return [];
  if (FIRM_LEVELS.indexOf(route.level) !== -1 && route.level !== "clients") {
    return [{ name: words.sections[SCREEN_KEYS[route.level] || route.level] }];
  }
  const household = shellHousehold(route.household);
  const listed = [{ name: words.sections.clients, go: route.level === "clients" ? null : { level: "clients" } }];
  if (route.level === "clients") return listed;
  // A household missing from the latest list has no name to show: leave the
  // segment out rather than draw a button with no accessible name.
  if (household) {
    listed.push({
      name: household.name,
      go: route.level === "household" ? null : { level: "household", household: route.household },
      shrink: "household",
      popup: "household",
    });
  }
  if (route.level === "household") return listed;
  listed.push({
    name: String(route.year),
    go: route.level === "year" ? null : { level: "year", household: route.household, year: route.year },
  });
  if (route.level === "year") return listed;
  const ret = shellReturn(route.ret);
  if (ret) listed.push({ name: ret.return_name, shrink: "current", popup: "return" });
  return listed;
}

function drawPath() {
  const list = $("crumb-list");
  const segments = crumbList();
  const last = segments.length - 1;
  list.replaceChildren(...segments.map((one, i) => {
    const attrs = { className: one.shrink ? "crumb-shrink" : "" };
    if (one.shrink === "household") attrs.className += " crumb-household";
    if (one.shrink === "current" || i === last) attrs.className += " crumb-current";
    const node = one.go
      ? h("button", { type: "button", className: "crumb-button", dataset: { crumb: String(i) } }, one.name)
      : h("span", { className: "crumb-here", "aria-current": "page" }, one.name);
    if (one.go) node.addEventListener("click", () => shellGo(one.go));
    setTipIfCut(node, one.name);
    if (one.popup) node.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      shellPopup(one.popup, `crumb-${one.popup}`, e.clientX, e.clientY);
    });
    return h("li", attrs, i ? h("span", { className: "crumb-sep", "aria-hidden": "true" }, icon("chev", true)) : null, node);
  }));
}

// ── the sort icon (SPEC 8.1) ──────────────────────────────────────────
// The state, from app.js's own: `scanning` (a pass this app started, with
// `stopping`), `locked` (a live lock on the shown return).
function sortState() {
  const words = screenWords().sort;
  if (scanning) {
    return scanning.stopping ? { key: "stopping", words: words.stopping, icon: "stop", off: true, stop: true }
      : { key: "stop", words: words.stop, icon: "stop", off: false, stop: true };
  }
  if (shellRoute.level === "setup" || !shellHasClient()) return { key: "firm", words: words.firm, icon: "sort", off: true };
  if (locked) return { key: "locked", words: words.locked, icon: "sort", off: true };
  return { key: "now", words: words.now, icon: "sort", off: false };
}

function drawSort() {
  const state = sortState();
  const button = $("sort");
  button.disabled = state.off;
  button.classList.toggle("is-stop", Boolean(state.stop));
  button.dataset.sortState = state.key;
  button.replaceChildren(icon(state.icon));
  button.setAttribute("aria-label", state.words);
  setTip(button, state.words);
  if (state.key === "now") button.setAttribute("aria-keyshortcuts", "F9");
  else button.removeAttribute("aria-keyshortcuts");
  $("find").disabled = shellRoute.level === "setup";
}

function sortClicked() {
  const state = sortState();
  if (state.off) return;
  if (state.stop) stopPass();
  else runScan();
}

// One place to say that something the shell shows has changed.
function shellChanged() {
  if (!vocab || !vocab.screen) return;
  drawLastSort();
  syncSortNotice();
  drawSort();
  drawCounts();
  shellEnable();
}

// A failed sort is also a notice at the top of the main area, on every page
// (ruling 20); the side panel's failed line stays. It has NO Retry and no
// action (ruling 28, superseding 26): the record it reads is the scheduled
// pass's, which the app's own Sort - one household at a time - never writes,
// so nothing on a page could clear it and nothing here may send a sort
// without a return chosen. It is the record's word, not an event's: it stays
// while the last scheduled sort failed, is left as it is while one runs, and
// goes when the next scheduled sort works.
function syncSortNotice() {
  if (scanning) return;
  const last = shellLastPass;
  if (last && last.when && last.ok === false) {
    keyedNotice("last-sort", { sentence: screenWords().last_sort.failed, kind: "failed" });
  } else {
    clearNotice("last-sort");
  }
}

function drawCounts() {
  const counts = shellCounts();
  const held = shellFirmUpdating();   // the counts shown are asked again: muted until the reply (P222)
  for (const node of document.querySelectorAll(".side-section[data-section]")) {
    const n = shellRoute.level === "setup" ? 0 : counts[node.dataset.section] || 0;
    const count = node.querySelector(".side-count");
    count.textContent = n > 0 ? String(n) : "";
    count.classList.toggle("is-held", held);
  }
}

// The search box's placeholder (pilot SPEC-lists 13, P173): Needs Review's
// names the files the box also finds there.
function drawFindWords() {
  const words = screenWords();
  $("find").setAttribute("placeholder", shellRoute.level === "needs-review" ? words.find_placeholder_files : words.find_placeholder);
}

// ── search (SPEC 8.2) ─────────────────────────────────────────────────
function fold(text) {
  return String(text).normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
}

// `files`: the waiting files the box also finds on Needs Review (P173), each
// noted with its return and year; choosing one opens Check on it.
function findOptions(query, files) {
  const needle = fold(query).trim();
  if (!needle) return [];
  const words = screenWords();
  const waiting = (files || []).filter((one) => fold(one.name).indexOf(needle) !== -1).map((one) => {
    const ret = shellReturn(one.return);
    return { name: one.name, note: `${ret ? ret.return_name : ""} ${one.year || ""}`.trim(), check: { ret: one.return, name: one.name, handle: one.handle } };
  });
  const people = households.filter((one) => fold(one.name).indexOf(needle) !== -1).map((one) => ({
    name: one.name,
    note: fill(shellOwnReturns(one.path).length === 1 ? words.counts.one_return : words.counts.returns, { n: shellOwnReturns(one.path).length }),
    route: { level: "household", household: one.path },
  }));
  const returns = engagements.filter((one) => fold(one.return_name).indexOf(needle) !== -1).map((one) => {
    const owner = shellHousehold(one.household);
    return {
      name: one.return_name,
      note: `${owner ? owner.name : ""} ${one.year}`.trim(),
      route: { level: "return", household: one.household, year: one.year, ret: one.path },
    };
  });
  return [...waiting, ...people, ...returns].slice(0, 8);
}

function drawFound() {
  hideTip();
  const list = $("find-list");
  const box = $("find");
  const query = box.value;
  const firm = shellFirmNow.data;
  shellFound = findOptions(query, shellRoute.level === "needs-review" && firm ? firm.files : []);
  if (!query.trim()) {
    hideFound();
    return;
  }
  const rows = shellFound.length ? shellFound.map((one, i) => h("li", {
    className: "find-option", role: "option", id: `find-option-${i}`, "aria-selected": i === 0 ? "true" : "false",
  }, h("span", { className: "find-name" }, one.name), h("span", { className: "find-note" }, one.note)))
    : [h("li", { className: "find-option", role: "option", "aria-disabled": "true" }, screenWords().find_none)];
  list.replaceChildren(...rows);
  shellFound.forEach((one, i) => rows[i].addEventListener("mousedown", (e) => {
    e.preventDefault();
    openFound(i);
  }));
  list.hidden = false;
  box.setAttribute("aria-expanded", "true");
  if (shellFound.length) box.setAttribute("aria-activedescendant", "find-option-0");
  else box.removeAttribute("aria-activedescendant");
}

function hideFound() {
  const list = $("find-list");
  list.hidden = true;
  list.replaceChildren();
  $("find").setAttribute("aria-expanded", "false");
  $("find").removeAttribute("aria-activedescendant");
  shellFound = [];
}

function moveFound(step) {
  if (!shellFound.length) return;
  const rows = [...$("find-list").children];
  const at = Math.max(0, rows.findIndex((row) => row.getAttribute("aria-selected") === "true"));
  const to = (at + step + rows.length) % rows.length;
  rows.forEach((row, i) => row.setAttribute("aria-selected", i === to ? "true" : "false"));
  $("find").setAttribute("aria-activedescendant", rows[to].id);
}

function openFound(index) {
  const one = shellFound[index];
  if (!one) return;
  $("find").value = "";
  hideFound();
  if (one.check) {
    openCheck(one.check.ret, one.check.name, one.check.handle);
    return;
  }
  shellGo(one.route);
}

function chosenFound() {
  const rows = [...$("find-list").children];
  const at = rows.findIndex((row) => row.getAttribute("aria-selected") === "true");
  return at === -1 ? 0 : at;
}

// ── the page (SPEC 6): pages.js, or the title alone ───────────────────
function routeTitle() {
  const route = shellRoute;
  const words = screenWords();
  if (FIRM_LEVELS.indexOf(route.level) !== -1) return "";   // firm pages have no H1 (SPEC 6, P75)
  const household = shellHousehold(route.household);
  if (route.level === "household") return household ? household.name : "";
  if (route.level === "year") return String(route.year);
  const ret = shellReturn(route.ret);
  return ret ? ret.return_name : "";
}

// The loading state every page shares: the title, then outline rows in the
// row grid; the word for a screen reader only (SPEC 6, states).
function shellSkeleton(count) {
  return Array.from({ length: count }, () => h("div", { className: "row-skeleton", "aria-hidden": "true" }, h("i"), h("i")));
}

// The outline stands in its own page's shape (P222): the Overview's three
// figures and its group head's line, a return page's caption line. No
// words, no numbers, no dots. A firm page whose wait has passed about 2 s
// says how many households `firm` has read, with a bar, where the hidden
// Loading was.
function shellLoading(title, level) {
  const words = screenWords();
  const reading = FIRM_LEVELS.indexOf(level) !== -1 ? shellReading() : null;
  const overview = level === "overview";
  const outline = () => h("i", { className: "outline-bar", "aria-hidden": "true" });
  return [
    ...(title ? [h("h1", { className: "page-title" }, title)] : []),
    ...(level === "return" ? [h("div", { className: "page-caption is-outline", "aria-hidden": "true" }, outline())] : []),
    ...(overview ? [h("div", { className: "figures", "aria-hidden": "true" }, [0, 1, 2].map(() => h("div", { className: "figure is-outline" }, outline())))] : []),
    h("div", { className: "group-head is-first" },
      reading ? shellReadingNodes(reading) : h("span", { className: "visually-hidden" }, words.loading),
      overview && !reading ? outline() : null),
    ...shellSkeleton(6),
  ];
}

// The first list could not be had: with no vocabulary nothing can draw the
// page, so the first paint's outline (index.html, P222) would wait, busy,
// for ever. It goes as a firm page's failed state does - its frame alone,
// not busy - and the failure's own notice says why, with Retry. A page
// already drawn from an earlier list keeps what it shows.
function shellStartFailed() {
  if (vocab) return;
  const page = $("page");
  page.setAttribute("aria-busy", "false");
  page.replaceChildren();
}

// The page's title alone; a firm page has none, so it draws only its frame.
function drawTitleOnly(page) {
  const title = routeTitle();
  page.replaceChildren(...(title ? [h("h1", { className: "page-title" }, title)] : []));
}

function drawPage() {
  const page = $("page");
  const route = shellRoute;
  if (route.level === "setup") {
    pagesLeave();
    page.setAttribute("aria-busy", "false");
    shellMarkUpdating(page, false);
    page.replaceChildren(...setupPage());
    return;
  }
  // A firm page waits for its counts: outline rows until they arrive; when
  // they cannot be had (the notice says so, with Retry) it shows its title.
  // A page drawn from counts held while they are asked again - a firm page,
  // a household's or a year's (shellFollowsCounts) - says Updating (P222);
  // its rows stay usable. The marker is set once per draw, never cleared and
  // set again, so its status is not read out on every redraw.
  const firmPage = FIRM_LEVELS.indexOf(route.level) !== -1;
  const waiting = firmPage && !shellFirmNow.data && shellFirmNow.status !== "failed";
  const busy = shellPageBusy || waiting;
  const updating = shellFollowsCounts() && !busy && shellFirmUpdating();
  page.setAttribute("aria-busy", busy || updating ? "true" : "false");
  shellMarkUpdating(page, updating);
  if (busy) {
    // The outline in its own page's grid: a return page borrows no list's (P222).
    page.dataset.list = pagesListOf(route);
    page.replaceChildren(...shellLoading(routeTitle(), route.level));
    return;
  }
  if ((firmPage && !shellFirmNow.data) || shellPageFailed) {
    drawTitleOnly(page);
    return;
  }
  pagesDraw(route, page);
}

// ── the setup page (SPEC 6.8) ─────────────────────────────────────────
// The path is app.js's setupDraft.root, kept for saveRoot(); what shows is the
// folder's own name, never its path.
function folderName(path) {
  return path.split(/[\\/]/).filter(Boolean).pop() || "";
}

function setupPage() {
  const words = screenWords().setup;
  const chosen = h("span", { id: "setup-chosen" }, folderName(setupDraft.root));
  const firm = h("input", { id: "setup-firm", type: "text", value: setupDraft.firm });
  const phone = h("input", { id: "setup-phone", type: "text", value: setupDraft.phone });
  const start = h("button", { id: "setup-start", type: "button", className: "btn btn-primary", disabled: !setupDraft.root.trim() }, words.start);
  const pick = h("button", { id: "setup-pick", type: "button", className: "btn" }, words.choose);
  pick.addEventListener("click", async () => {
    const picked = await window.tracker.pickFolder(words.title);
    if (!picked) return;
    setupDraft.root = picked;
    chosen.textContent = folderName(picked);
    start.disabled = false;
  });
  // While set-root runs the page shows the outline below the form (P222).
  const wait = h("div", { className: "setup-wait", "aria-hidden": "true" });
  start.addEventListener("click", async () => {
    setupDraft.firm = firm.value;
    setupDraft.phone = phone.value;
    start.disabled = true;
    wait.replaceChildren(...shellSkeleton(3));
    $("page").setAttribute("aria-busy", "true");
    try {
      await saveRoot();
    } finally {
      start.disabled = !setupDraft.root.trim();
      wait.replaceChildren();
      if (shellRoute.level === "setup") $("page").setAttribute("aria-busy", "false");
    }
  });
  const actions = [start];
  if (shellRootSet) {
    const cancel = h("button", { id: "setup-cancel", type: "button", className: "btn btn-subtle" }, vocab.editor.cancel);
    cancel.addEventListener("click", () => shellGo(shellBack || { level: "overview" }));
    actions.push(cancel);
  }
  return [
    h("h1", { className: "page-title" }, words.title),
    h("div", { className: "setup" },
      h("div", { className: "setup-pick" }, pick, chosen),
      h("label", { className: "setup-field" }, h("span", {}, vocab.settings.firm_label), firm),
      h("label", { className: "setup-field" }, h("span", {}, vocab.settings.phone_label), phone),
      h("div", { className: "setup-actions" }, ...actions)),
    wait,
  ];
}

// app.js: no clients folder is set (or it is now). `listed` is the reply.
function shellNeedsRoot(on, listed) {
  shellRootSet = !on && Boolean(listed && listed.root);
  if (on) {
    if (listed && listed.root_problem) notice({ sentence: screenWords().setup.missing, kind: "failed" });
    // The one page change that does not go through shellGo: its tip goes too (P202 review).
    hideTip();
    shellRoute = { level: "setup" };
    shellBack = null;
    shellDraw();
    return;
  }
  if (shellRoute.level === "setup" && !shellBack) shellGo({ level: "overview" });
}

// File › Change clients folder…
function shellChangeRoot() {
  // app.js fills these two only at first run; saveRoot() sends them, so keep the saved values.
  setupDraft.firm = vocab.firm || "";
  setupDraft.phone = vocab.settings.phone || "";
  shellGo({ level: "setup" });
}

// ── the menu channel, the page's side (SPEC 5.3, 5.4) ─────────────────
// The ids whose rule in 5.1 holds now. main.js sets `enabled` on the items
// whose ids it knows and ignores anything else.
// `at`: the route a row's menu stands for (a household or return row on a page
// that is not its own); the rules are the same, read for that route.
function shellEnabled(at) {
  const route = at || shellRoute;
  const client = ["household", "year", "return"].indexOf(route.level) !== -1;
  const isReturn = route.level === "return";
  const writable = !locked;
  const household = shellHousehold(route.household);
  const rollable = Boolean(household && (household.returns || []).some((one) => one.rollable));
  const own = lastState && lastState.household && lastState.household.path === route.household ? lastState.household : null;
  const shared = Boolean(own && own.shared_on);
  const paused = Boolean(own && own.pause && own.pause.sentence);   // while paused the pause is the work
  const ids = ["change_root", "refresh", "tour", "safeguards", "terms", "error_log", "about", "show_under_construction"];
  if (shellRootSet) {
    ids.push("new_household", "open_root", "overview", "needs_review", "reminders", "clients", "find", "schedule", "repair_schedule");
    ids.push("reset_columns");
  }
  if (client && writable) {
    ids.push("edit_household");
    if (!paused) ids.push("add_return");
    if (rollable) ids.push("roll_forward");
    if (!shared) ids.push("mark_shared");
  }
  if (isReturn && writable) ids.push("edit_list");
  if (isReturn) ids.push("draft_reminder", "open_working");
  if (client) ids.push("open_client_folder", "open_inbox");
  if (client && !scanning && writable) ids.push("sort_now");
  if (scanning) ids.push("stop_sorting");
  if (shellPaths.status) ids.push("firm_report");
  if (client && lockStale) ids.push("clear_lock");
  return ids;
}

// The menu channel is the window's other side: one that throws is said as a
// notice and the page goes on (a route change must not depend on it).
function shellEnable() {
  try {
    if (window.tracker.menu) window.tracker.menu.send({ enable: shellEnabled(), checked: shellChecked() });
  } catch (err) {
    failed(err);
  }
}

// Ask main.js for a native right-click menu: one of the six templates, at
// the pointer, with the ids that apply (the page's, or a row's own). The token
// is the page's own row key, echoed back (never a path).
function shellPopup(name, token, x, y, enable) {
  try {
    if (window.tracker.menu) window.tracker.menu.send({ popup: name, enable: enable || shellEnabled(), token, x, y });
  } catch (err) {
    failed(err);
  }
}

function unanswered(id) {
  notice({ sentence: fill(vocab.shell.page_error, { kind: id }), kind: "failed" });
  window.tracker.logError(`menu.${id}`);
}

// Open a path the API reported, or (`how` "reveal") show that file in File
// Explorer. The shell answers "" or the sentence for a path that is no longer
// what it was; that is a notice in the API's words, and what the operating
// system said goes to the error log.
async function openPath(path, how) {
  if (!path) return;
  try {
    const said = await window.tracker.open(path, how);
    if (said) {
      window.tracker.logError(String(said));
      notice({ sentence: vocab.shell.not_opened, kind: "warning" });
    }
  } catch (err) {
    failed(err);
  }
}

function clientFolder() {
  const household = shellHousehold(shellRoute.household);
  return household ? household.client_folder : paths && paths.client_folder;
}
function inboxFolder() {
  const household = shellHousehold(shellRoute.household);
  return household ? household.inbox : paths && paths.inbox;
}

async function shellRefresh() {
  forgetSortAnswers();   // app.js: a Sort's answer is not in the record read again (P131)
  try {
    adoptList(await call(["list"]));
    if (shellRoute.level === "return") await showReturn(shellRoute.ret);
  } catch (err) {
    failed(err, shellRefresh);
  }
  shellDraw();
}

// What each menu id does on the page. Every one goes through the function
// a click on the old button ran, so every existing check stays in place;
// no command reaches the tracker except through window.tracker.call.
const MENU_ANSWERS = {
  new_household: () => openNewHousehold(),
  change_root: () => shellChangeRoot(),
  open_root: () => openPath(shellPaths.clients_root),
  edit_household: () => openHouseholdEditor(),
  add_return: () => openAddReturn(shellHousehold(shellRoute.household) || (lastState && lastState.household)),
  mark_shared: () => markShared(),
  edit_list: () => openEditor(),
  open_client_folder: () => openPath(clientFolder()),
  open_inbox: () => openPath(inboxFolder()),
  open_working: () => openPath(paths && paths.engagement),
  overview: () => shellGo({ level: "overview" }),
  needs_review: () => shellGo({ level: "needs-review" }),
  reminders: () => shellGo({ level: "reminders" }),
  clients: () => shellGo({ level: "clients" }),
  find: () => $("find").focus(),
  refresh: () => shellRefresh(),
  reset_columns: () => pagesResetWidths(),
  show_under_construction: () => shellToggleSoon(),
  sort_now: () => sortClicked(),
  stop_sorting: () => stopPass(),
  schedule: () => openSchedule(),
  repair_schedule: () => repairSchedule(),
  firm_report: () => openPath(shellPaths.status),
  clear_lock: () => clearLock(),
  tour: () => PilotTour.start(),
  terms: () => PilotTerms.show(),
  roll_forward: () => openRoll(),
  draft_reminder: () => openReminder(),
  safeguards: () => openSafeguards(),
  about: () => openAbout(),
};

function shellAnswer(id) {
  const answer = MENU_ANSWERS[id];
  if (answer) answer();
  else unanswered(id);
}

function shellMenu(message) {
  if (message.missing) {
    toast(screenWords().notices.no_log);
    return;
  }
  const id = String(message.id);
  if (message.token && pagesMenu(id, message.token) !== false) return;
  shellAnswer(id);
}

// ── keyboard (SPEC 4.3): app.js's one keydown listener hands keys here ──
const F6_REGIONS = ["side", "bar", "page"];

function regionOf(node) {
  if (!node || !node.closest) return "page";
  if (node.closest("#side")) return "side";
  if (node.closest("#bar")) return "bar";
  return "page";
}

function focusRegion(name) {
  if (name === "side") {
    const here = document.querySelector('.side-section[aria-current="page"]:not(:disabled)');
    const first = document.querySelector(".side-section:not(:disabled)");
    (here || first || $("side")).focus();
  } else if (name === "bar") {
    const first = document.querySelector("#crumb-list button");
    (first && !$("find").disabled ? first : $("find")).focus();
  } else {
    $("page").focus();
  }
}

function shellKey(e) {
  tipKey(e);   // tooltip.js: Escape hides a showing tip first, and the key goes on (P130)
  if (e.key === "F6") {
    e.preventDefault();
    const at = F6_REGIONS.indexOf(regionOf(document.activeElement));
    focusRegion(F6_REGIONS[(at + (e.shiftKey ? F6_REGIONS.length - 1 : 1)) % F6_REGIONS.length]);
    return true;
  }
  if (e.target === $("find")) return findKey(e);
  if (e.key === "Escape") {
    if (dialogStack.length) return false;   // a dialog's own rule
    if (pagesPanelOpen()) {
      e.preventDefault();
      pagesClosePanel(true);
      return true;
    }
    if (!$("sheet").hidden) {
      e.preventDefault();
      closeSheet();
      return true;
    }
    if (!$("find-list").hidden) {
      $("find").value = "";
      hideFound();
      return true;
    }
    return false;
  }
  if (e.target.closest && e.target.closest('[role="listbox"]')) return pagesKey(e) === true;
  if (e.target.closest && e.target.closest(".col-head") && typeof pagesColumnKey === "function") return pagesColumnKey(e) === true;
  return false;
}

function findKey(e) {
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    moveFound(e.key === "ArrowDown" ? 1 : -1);
    return true;
  }
  if (e.key === "Enter") {
    e.preventDefault();
    openFound(chosenFound());
    return true;
  }
  if (e.key === "Escape") {
    e.preventDefault();
    $("find").value = "";
    hideFound();
    return true;
  }
  return false;
}

// ── wiring ────────────────────────────────────────────────────────────
for (const node of document.querySelectorAll(".side-section[data-section]")) {
  node.addEventListener("click", () => {
    if (node.dataset.section === "clients") pagesClientType = "";   // Clients itself: every type
    shellGo({ level: node.dataset.section });
  });
}
// A Client Type opens Clients filtered to it, from its first page (P153).
for (const node of document.querySelectorAll(".side-section[data-type]")) {
  node.addEventListener("click", () => {
    pagesClientType = node.dataset.type;
    delete pagesPageAt.clients;
    shellGo({ level: "clients" });
  });
}
// A stored "hidden" applies before the first paint, not when the words arrive (P197, review S1).
drawSoon();
// A page not built yet says so and does nothing else: no page, no command (P154).
for (const node of document.querySelectorAll(".side-section[data-soon]")) {
  node.addEventListener("click", () => toastWord("under_construction"));
}
// Settings: the settings the app already has, through the menu's own answer (P175).
$("side-settings").addEventListener("click", () => shellAnswer("change_root"));
$("sort").addEventListener("click", sortClicked);
$("find").addEventListener("input", drawFound);
$("find").addEventListener("focus", () => {
  if ($("find").value.trim()) drawFound();
});
document.addEventListener("click", (e) => {
  if (!e.target.closest("#find-wrap")) hideFound();
  // A click outside the Linked Households panel closes it (P171).
  if (!e.target.closest("#link-panel") && !e.target.closest(".link-mark")) pagesClosePanel(false);
});
$("sheet-close").addEventListener("click", () => closeSheet());
window.tracker.menu.onCommand(shellMenu);
