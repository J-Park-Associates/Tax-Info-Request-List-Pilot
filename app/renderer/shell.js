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
// only, with its own builder `h`, which sets only the attributes it names
// (the pattern of app.js's `el`, decision 137).
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
// What this file calls in app.js: appRouteChanged(route), so the lock (a
// notice) follows the return on screen.
// What this file calls, if it exists (the pages are pages.js, the sheet S5's):
//   pagesDraw(route, page)   draw the route's page into #page
//   pagesLeave()             the setup page took the screen: the pages' notices go
//   pagesTally(state)        how many of each group a state holds
//   pagesKey(e)              a key on a row list (the one keydown listener
//                            stays in app.js and hands keys here)
//   pagesMenu(id, token)     a right-click menu item on a row
//   closeSheet(), openRoll(), openSafeguards(), openAbout(), openReminder()
// A menu id the page cannot answer yet is said as a notice and logged.

"use strict";

// ── one route (SPEC 4.1) ──────────────────────────────────────────────
// {level, household, year, ret}: `level` is one of LEVELS; household and
// ret are the paths the API reported; year is a number. No history and no
// back button: the path and the side panel are the way around (P75).

const LEVELS = ["overview", "needs-review", "reminders", "clients", "household", "year", "return", "setup"];
const FIRM_LEVELS = ["overview", "needs-review", "reminders", "clients"];
const SIDE_KEYS = ["overview", "needs-review", "reminders", "clients"];
const SCREEN_KEYS = { "needs-review": "needs_review" };

let shellRoute = { level: "overview" };
let shellBack = null;          // the route Cancel goes back to, from Change clients folder
let shellRootSet = false;      // a clients folder is set (the menu's "a clients folder is set")
let shellPaths = {};           // the list's `paths`: clients_root, status
let shellLastPass = null;      // the list's last_pass: {text, level, ok, when}
let shellProgressNow = null;   // the running pass's last line: {n, total}
let shellFirmNow = { status: "idle", data: null };   // idle, loading, ok, failed
let shellFirmAsked = false;    // a second ask arrived while one ran
let shellPageBusy = false;     // a return's state is on its way
let shellPageFailed = false;   // it could not be had (the notice says why, with Retry)
let shellFound = [];           // the search list's options

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

// ── a builder that sets only what it names ────────────────────────────
const H_ATTRIBUTES = new Set([
  "className", "id", "type", "disabled", "hidden", "tabindex", "role", "value", "dataset",
  "aria-label", "aria-current", "aria-selected", "aria-expanded", "aria-busy", "aria-hidden",
  "aria-labelledby", "aria-valuemin", "aria-valuemax", "aria-valuenow", "aria-live",
  "aria-controls", "aria-description", "aria-keyshortcuts", "aria-disabled", "aria-pressed",
]);

function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (!H_ATTRIBUTES.has(key)) throw new Error(`h.${key}`);
    if (value === undefined || value === null || value === false) continue;
    if (key === "className") node.className = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (typeof value === "boolean") node[key] = value;
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : String(child));
  }
  return node;
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
  for (const node of document.querySelectorAll(".side-section")) {
    const key = node.dataset.section;
    node.querySelector(".side-name").textContent = words.sections[SCREEN_KEYS[key] || key];
  }
  shellNameIcons();
  shellChanged();
  shellDraw();
}

// ── data the list and the firm command bring ──────────────────────────
function shellAdopt(listed) {
  // A write that changes the list carries the list half alone: what it does
  // not carry is kept.
  if (listed.paths) shellPaths = listed.paths;
  if (listed.last_pass) shellLastPass = listed.last_pass;
  shellRootSet = !listed.needs_root && Boolean(listed.root);
  if (shellRootSet) shellLoadFirm();
  shellChanged();
}

// The Overview's counts (SPEC 4.2): after `list`, after a sort ends, after
// F5 and after a write that changes a count. While it runs the firm pages
// show their loading state; a failure is one notice with Retry and the
// pages keep what they last had.
async function shellLoadFirm() {
  if (shellFirmNow.status === "loading") {
    shellFirmAsked = true;
    return;
  }
  shellFirmNow = { status: "loading", data: shellFirmNow.data };
  shellChanged();
  try {
    if (!Array.isArray(vocab.commands) || vocab.commands.indexOf("firm") === -1) throw new Error("firm");
    shellFirmNow = { status: "ok", data: await call(["firm"]) };
  } catch (err) {
    failureSentence(err);
    shellFirmNow = { status: "failed", data: shellFirmNow.data };
    notice({ sentence: screenWords().notices.firm_failed, kind: "failed" }, { retry: shellLoadFirm });
  }
  if (shellFirmAsked) {
    shellFirmAsked = false;
    shellFirmNow = { status: "idle", data: shellFirmNow.data };
    shellLoadFirm();
    return;
  }
  shellChanged();
  if (FIRM_LEVELS.indexOf(shellRoute.level) !== -1) shellDraw();
}

// What pages.js reads (with shellRoute, shellLoading and shellGo).
function shellFirm() {
  return shellFirmNow;
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
  if (typeof closeSheet === "function") closeSheet();
  hideFound();
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
    if (own.length && !own.some((one) => one.path === shown)) path = (own.find((one) => one.path === active) || own[0]).path;
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
    if (typeof sheetStateArrived === "function") sheetStateArrived(state);   // sheet.js: the file answered leaves, the next comes
    const firm = shellFirmNow.data;
    const mine = firm && state.paths ? firm.returns.find((one) => one.path === state.paths.engagement) : null;
    if (!mine || typeof pagesTally !== "function") return;
    const tally = pagesTally(state);
    if (Object.keys(tally).some((key) => tally[key] !== mine.counts[key])) shellLoadFirm();
  } catch (err) {
    failed(err);
  }
}

function shellDraw() {
  drawSide();
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
  for (const node of document.querySelectorAll(".side-section")) {
    const key = node.dataset.section;
    node.disabled = off;
    if (key === shellSection()) node.setAttribute("aria-current", "page");
    else node.removeAttribute("aria-current");
    node.setAttribute("aria-keyshortcuts", `Control+${SIDE_KEYS.indexOf(key) + 1}`);
  }
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
  drawSort();
  drawCounts();
  shellEnable();
}

function drawCounts() {
  const counts = shellCounts();
  for (const node of document.querySelectorAll(".side-section")) {
    const n = shellRoute.level === "setup" ? 0 : counts[node.dataset.section] || 0;
    node.querySelector(".side-count").textContent = n > 0 ? String(n) : "";
  }
}

// ── search (SPEC 8.2) ─────────────────────────────────────────────────
function fold(text) {
  return String(text).normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
}

function findOptions(query) {
  const needle = fold(query).trim();
  if (!needle) return [];
  const words = screenWords();
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
  return [...people, ...returns].slice(0, 8);
}

function drawFound() {
  hideTip();
  const list = $("find-list");
  const box = $("find");
  const query = box.value;
  shellFound = findOptions(query);
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
function shellLoading(title) {
  const words = screenWords();
  const rows = Array.from({ length: 6 }, () => h("div", { className: "row-skeleton", "aria-hidden": "true" }, h("i"), h("i")));
  return [
    ...(title ? [h("h1", { className: "page-title" }, title)] : []),
    h("div", { className: "group-head is-first" }, h("span", { className: "visually-hidden" }, words.loading)),
    ...rows,
  ];
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
    if (typeof pagesLeave === "function") pagesLeave();
    page.setAttribute("aria-busy", "false");
    page.replaceChildren(...setupPage());
    return;
  }
  // A firm page waits for its counts: outline rows until they arrive; when
  // they cannot be had (the notice says so, with Retry) it shows its title.
  const firmPage = FIRM_LEVELS.indexOf(route.level) !== -1;
  const waiting = firmPage && !shellFirmNow.data && shellFirmNow.status !== "failed";
  const busy = shellPageBusy || waiting;
  page.setAttribute("aria-busy", busy ? "true" : "false");
  if (busy) {
    page.replaceChildren(...shellLoading(routeTitle()));
    return;
  }
  if ((firmPage && !shellFirmNow.data) || shellPageFailed) {
    drawTitleOnly(page);
    return;
  }
  if (typeof pagesDraw === "function") {
    pagesDraw(route, page);
    return;
  }
  drawTitleOnly(page);
}

// ── the setup page (SPEC 6.8) ─────────────────────────────────────────
// The path is app.js's #root-input, kept for saveRoot(); what shows is the
// folder's own name, never its path.
function folderName(path) {
  return path.split(/[\\/]/).filter(Boolean).pop() || "";
}

function setupPage() {
  const words = screenWords().setup;
  const chosen = h("span", { id: "setup-chosen" }, folderName($("root-input").value));
  const firm = h("input", { id: "setup-firm", type: "text", value: $("firm-input").value });
  const phone = h("input", { id: "setup-phone", type: "text", value: $("phone-input").value });
  const start = h("button", { id: "setup-start", type: "button", className: "btn btn-primary", disabled: !$("root-input").value.trim() }, words.start);
  const pick = h("button", { id: "setup-pick", type: "button", className: "btn" }, words.choose);
  pick.addEventListener("click", async () => {
    const picked = await window.tracker.pickFolder(words.title);
    if (!picked) return;
    $("root-input").value = picked;
    chosen.textContent = folderName(picked);
    start.disabled = false;
  });
  start.addEventListener("click", async () => {
    $("firm-input").value = firm.value;
    $("phone-input").value = phone.value;
    start.disabled = true;
    try {
      await saveRoot();
    } finally {
      start.disabled = !$("root-input").value.trim();
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
  ];
}

// app.js: no clients folder is set (or it is now). `listed` is the reply.
function shellNeedsRoot(on, listed) {
  shellRootSet = !on && Boolean(listed && listed.root);
  if (on) {
    if (listed && listed.root_problem) notice({ sentence: screenWords().setup.missing, kind: "failed" });
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
  $("firm-input").value = vocab.firm || "";
  $("phone-input").value = vocab.settings.phone || "";
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
  const ids = ["change_root", "refresh", "tour", "safeguards", "terms", "error_log", "about"];
  if (shellRootSet) {
    ids.push("new_household", "open_root", "overview", "needs_review", "reminders", "clients", "find", "schedule", "repair_schedule");
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
    if (window.tracker.menu) window.tracker.menu.send({ enable: shellEnabled() });
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
  sort_now: () => sortClicked(),
  stop_sorting: () => stopPass(),
  schedule: () => openSchedule(),
  repair_schedule: () => repairSchedule(),
  firm_report: () => openPath(shellPaths.status),
  clear_lock: () => clearLock(),
  tour: () => PilotTour.start(),
  terms: () => PilotTerms.show(),
  roll_forward: () => (typeof openRoll === "function" ? openRoll() : unanswered("roll_forward")),
  draft_reminder: () => (typeof openReminder === "function" ? openReminder() : unanswered("draft_reminder")),
  safeguards: () => (typeof openSafeguards === "function" ? openSafeguards() : unanswered("safeguards")),
  about: () => (typeof openAbout === "function" ? openAbout() : unanswered("about")),
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
  if (message.token && typeof pagesMenu === "function" && pagesMenu(id, message.token) !== false) return;
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
  if (e.key === "F6") {
    e.preventDefault();
    const at = F6_REGIONS.indexOf(regionOf(document.activeElement));
    focusRegion(F6_REGIONS[(at + (e.shiftKey ? F6_REGIONS.length - 1 : 1)) % F6_REGIONS.length]);
    return true;
  }
  if (e.target === $("find")) return findKey(e);
  if (e.key === "Escape") {
    if (dialogStack.length) return false;   // a dialog's own rule
    if (!$("sheet").hidden && typeof closeSheet === "function") {
      e.preventDefault();
      closeSheet();
      return true;
    }
    if (!$("find-list").hidden) {
      $("find").value = "";
      hideFound();
      return true;
    }
    if (tipShowing()) {
      hideTip();
      return true;
    }
    return false;
  }
  if (e.target.closest && e.target.closest('[role="listbox"]') && typeof pagesKey === "function") return pagesKey(e) === true;
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
for (const node of document.querySelectorAll(".side-section")) {
  node.addEventListener("click", () => shellGo({ level: node.dataset.section }));
}
$("sort").addEventListener("click", sortClicked);
$("find").addEventListener("input", drawFound);
$("find").addEventListener("focus", () => {
  if ($("find").value.trim()) drawFound();
});
document.addEventListener("click", (e) => {
  if (!e.target.closest("#find-wrap")) hideFound();
});
$("sheet-close").addEventListener("click", () => {
  if (typeof closeSheet === "function") closeSheet();
});
if (window.tracker.menu) window.tracker.menu.onCommand(shellMenu);
