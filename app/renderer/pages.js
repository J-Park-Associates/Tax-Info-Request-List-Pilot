// The pages (pilot SPEC-shell.md sections 3.6 and 6; decisions P71, P75, P76).
//
// A classic script, loaded after app.js and tooltip.js and before shell.js,
// sharing their globals. shell.js decides which page and calls
// pagesDraw(route, page); this file draws it into #page from data it is
// handed and calls nothing itself but the steps a person takes: the API's
// `list` (households, engagements) and `firm` (the counts) replies, and the
// one `state` reply of the return on screen. It types no word of its own:
// every word is vocab.screen, vocab.menu or a word the vocabulary already
// held (a request's label, a stage's short name, a reason's short label),
// and a word the vocabulary lacks is a loud failure, never a guess (the
// draw catches it, says it as a notice and logs it).
//
// One row, one group, on every page (SPEC 3.6):
//   - a row is name, detail, status, and an end column that holds the date
//     and, on hover or focus, the row's one step;
//   - a group is an H2 with its count and a listbox of rows; the listbox is
//     one Tab stop and moves focus with aria-activedescendant; Up/Down,
//     Home/End, PageUp/PageDown move; Enter runs the row's step; a click
//     selects, a click on the step or a double click runs it.
//
// The grouping of a return's page is the API's `group` on each item of
// `state` (SPEC 9.1). A file's group follows the list it is in: parked and
// moved files are Needs you, files a person set aside are Set aside. An item
// with no `group` is not guessed at: it is set aside from the page (drawn in
// no group, counted in none) and named in a notice of its own, while every
// other row and group is drawn (pagesSafe; SPEC 6, "loud and safe").
//
// Three kinds of name are live links (SPEC 3.9; rulings 8-13), drawn as
// `.row-link` with the vocabulary's tooltip: a file name shows that exact
// working copy in File Explorer (`window.tracker.open(path, "reveal")`, the
// path looked up by the API's key in the map it came with, never drawn); a
// household name and a return name navigate in the app, with no call to the
// engine. A return's link reads "{Return Name} ({Year})": its name from the
// list and its year from the row's own record, never worked out here.
//
// What this file offers the sheet and the right-click menus:
//   pagesRowFor(token)  what a row is about ({menu, step, ...}), by the row's id
//   pagesFiles()        the Check steps on the page, in the order drawn
//   pagesDrafts()       the Draft reminder steps, in the order drawn
//   pagesWhere/pagesFocusAt  where focus sat in a row list, and back to it
//   pagesMenu(id, token)     a right-click item on a row (the crumbs' and the
//                            menu bar's ids are shell.js's)
//   data-menu, data-token on every row and on the H1 of a household or
//                       return; a right-click or Shift+F10 asks for the
//                       native menu of that template (shellPopup)
// Steps that open the sheet call openCheck(ret, name, handle) and
// openReminder(ret) (sheet.js).

"use strict";

const PAGES_GROUPS = ["needs_you", "waiting", "received", "set_aside"];
const PAGES_TONES = { needs: "is-attention", waiting: "is-waiting", done: "is-done", plain: "is-plain" };
const PAGES_LATE = "9999-99-99";

let pagesUid = 0;              // ids of the rows and headings of the page being drawn
const pagesTokens = new Map(); // a row's id -> what it is about (rebuilt with every draw)
let pagesFocus = null;         // where focus sat in a listbox before a redraw
let pagesLastLevel = "";       // the level drawn last, for the Clients switch
let pagesClientsAll = false;   // the Clients switch: false is Work waiting
let pagesSetAsideOpen = false;
let pagesBroken = [];          // the rows of the page being drawn that could not be built: {name, err}
let pagesDrawn = "";           // which route the page holds, so a failed draw keeps only its own

// ── small helpers ─────────────────────────────────────────────────────
function pagesDay(iso) {
  const parts = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
  if (!parts) return "";
  return new Date(Number(parts[1]), Number(parts[2]) - 1, Number(parts[3])).toLocaleDateString([], { month: "short", day: "numeric" });
}

function pagesTime(clock) {
  const parts = /^(\d{1,2}):(\d{2})$/.exec(String(clock || ""));
  if (!parts) return String(clock || "");
  const at = new Date();
  at.setHours(Number(parts[1]), Number(parts[2]), 0, 0);
  return at.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function pagesDue(iso) {
  return iso ? fill(screenWords().due, { date: pagesDay(iso) }) : "";
}

// The firm reply the page is drawn from (shell.js keeps it; a page that
// needs it is only drawn once it has arrived).
function pagesFirm() {
  const data = shellFirm().data;
  if (!data) throw new Error("firm");
  return data;
}

function pagesFirmReturn(path) {
  const data = shellFirm().data;
  return data ? data.returns.find((one) => one.path === path) || null : null;
}

function pagesReturnName(path) {
  const one = shellReturn(path);
  return one ? one.return_name : folderName(path);
}

function pagesRoute(path) {
  const one = shellReturn(path);
  return { level: "return", household: one ? one.household : "", year: one ? one.year : 0, ret: path };
}

// ── links (SPEC 3.9; rulings 8-13) ────────────────────────────────────
const PAGES_LINK_WORDS = { file: "show_in_explorer", household: "navigate_client", return: "navigate_return" };

// A link's tooltip, the vocabulary's. A word it lacks is a loud failure (the
// row that would carry the link is left out and named), never a guess.
function pagesLinkWords(kind) {
  const key = PAGES_LINK_WORDS[kind];
  const said = key ? screenWords()[key] : "";
  if (!said) throw new Error(`screen.${key}`);
  return said;
}

// A return's link text, "{Return Name} ({Year})" (ruling 13): its name from
// the list, its year from the row's own record (or the list's), both the
// API's. A row the API gave no year for is its name alone, not a year of ours.
function pagesReturnText(path, year, named) {
  const name = named || pagesReturnName(path);
  const listed = shellReturn(path);
  const shown = year || (listed ? listed.year : 0);
  return shown ? `${name} (${shown})` : name;
}

function pagesHouseholdPath(name) {
  const one = households.find((other) => other.name === name);
  return one ? one.path : "";
}

// The absolute path the API reported under a key, from the map that came with
// the row (`state.paths`, `firm.paths`): a string, or {path, kind}. It goes to
// the shell's open and is never put in a node.
function pagesPathOf(map, key) {
  const found = map && key ? map[key] : "";
  return typeof found === "string" ? found : found && typeof found.path === "string" ? found.path : "";
}

function pagesFileLink(map, key) {
  return key ? { kind: "file", key, paths: map } : null;
}

function pagesRunLink(link) {
  if (link.kind === "household") shellGo({ level: "household", household: link.path });
  else if (link.kind === "return") shellGo(pagesRoute(link.path));
  else {
    const path = pagesPathOf(link.paths, link.key);
    if (path) openPath(path, "reveal");
    else unanswered("show_in_explorer");
  }
}

// A name that is a link: a node of its own in the cell, carrying the link's
// tooltip (which wins over the cut name's, whose full text is the page's
// heading or the sheet's title).
function pagesLinkNode(link, text, cell) {
  const node = h("span", { className: "row-link", dataset: { link: link.kind, cell } }, text);
  setTip(node, pagesLinkWords(link.kind));
  return node;
}

function pagesCell(className, cell, text, link) {
  const box = h("span", { className }, link ? pagesLinkNode(link, text, cell) : text);
  if (!link) setTipIfCut(box, text);
  return box;
}

// A short reason's label (SPEC 11.5): `vocab.reasons[code]`, a label or an
// object with `short`. A code the table lacks is a loud failure.
function pagesReason(code) {
  if (!code) return "";
  const said = vocab.reasons && vocab.reasons[code];
  const short = said && typeof said === "object" ? said.short : said;
  if (!short) throw new Error(`reasons.${code}`);
  return short;
}

// A stage's short name (SPEC 11.6): "Heads up", "Checking in", ...
function pagesStage(number) {
  const stage = ((vocab.reminder || {}).stages || []).find((one) => one.number === number);
  if (!stage || !stage.short) throw new Error(`stage.${number}`);
  return stage.short;
}

function pagesNextSort(firm) {
  return firm.next_sort ? fill(screenWords().empty.next_sort, { time: pagesTime(firm.next_sort) }) : "";
}

// A return's status word and tone from its counts (SPEC 6.1, 6.4).
function pagesCounts(counts, problem) {
  const words = screenWords().counts;
  if (problem) return { text: problem, tone: "needs" };
  if (counts.needs_you) return { text: fill(words.need, { n: counts.needs_you }), tone: "needs" };
  if (counts.waiting) return { text: fill(words.waiting, { n: counts.waiting }), tone: "waiting" };
  return { text: words.complete, tone: "done" };
}

// One row (or group) that cannot be built is set aside and named at the end
// of the draw (pagesReportBroken); every other row is still drawn. A page
// never blanks for one bad row, and nothing is guessed to fill its place.
function pagesLabel(one) {
  try {
    // Never a path: a row or group with no name of its own is left unnamed
    // rather than named by its folder (P63).
    const name = typeof one === "string" ? one : one && (one.short_name || one.document || one.original_name || one.name || one.identifier);
    return /[\\/]/.test(String(name || "")) ? "" : String(name || "");
  } catch (err) {
    return "";
  }
}

function pagesSafe(name, make) {
  try {
    return make();
  } catch (err) {
    pagesBroken.push({ name: pagesLabel(name), err });
    return null;
  }
}

// The specs (or rows) `make` builds from a list, the failed ones left out.
function pagesEach(list, nameOf, make) {
  return list.map((one, i) => pagesSafe(pagesSafeName(nameOf, one), () => make(one, i))).filter((one) => one !== null);
}

function pagesSafeName(nameOf, one) {
  try {
    return nameOf(one);
  } catch (err) {
    return pagesLabel(one);
  }
}

function pagesByName(a, b) {
  return a.localeCompare(b, undefined, { numeric: true });
}

// The name cell, and beside the name the row's marker when it has one (a
// household paused for two open years, ruling 21): the vocabulary's words.
function pagesNameCell(spec) {
  const box = pagesCell("row-name", "name", spec.name, spec.nameLink);
  if (spec.mark) box.append(h("span", { className: "row-mark is-attention" }, spec.mark));
  return box;
}

// The households the firm reply says are paused (`paused: true` on each of
// their returns, S6's field); an entry without the field is not paused, and
// nothing is drawn for it.
function pagesPaused(firm) {
  return new Set(firm.returns.filter((one) => one.paused === true).map((one) => one.household));
}

// ── the row and the group (SPEC 3.6) ──────────────────────────────────
// A spec: {name, detail, status, tone, date, step, menu}. `step` is data
// ({kind, ...}), run by pagesRunStep; `menu` names the right-click template.
function pagesRow(spec) {
  pagesUid += 1;
  const id = `row-${pagesUid}`;
  pagesTokens.set(id, spec);
  // The request list is a write: while a live lock holds the return its Edit
  // step is not offered (the menu's Edit request list is grey for the same reason).
  const stepOf = spec.step && !(spec.step.kind === "edit" && locked) ? spec.step : null;
  const words = stepOf ? pagesStepWords(stepOf) : "";
  const step = stepOf ? h("span", { className: "row-step", "aria-hidden": "true" }, words, icon("chev", true)) : null;
  // A return's or a household's row, and any row that carries a marker, may
  // wrap to two lines or more (rulings 21 and 27): the year after a return's
  // name and the words of a paused household are never cut away. A file's
  // name still ends in an ellipsis.
  const wraps = Boolean(spec.mark || (spec.nameLink && spec.nameLink.kind !== "file"));
  const node = h("div", {
    className: `row${step ? " has-step" : ""}${spec.child ? " row-child" : ""}${wraps ? " row-wrap" : ""}`, role: "option", id, "aria-selected": "false",
    "aria-description": words || undefined, dataset: { menu: spec.menu || "", token: id },
  },
  pagesNameCell(spec),
  pagesCell("row-detail", "detail", spec.detail || "", spec.detailLink),
  h("span", { className: `row-status ${PAGES_TONES[spec.tone] || ""}` }, spec.status || ""),
  h("span", { className: "row-end" }, h("span", { className: "row-date" }, spec.date || ""), step));
  // A status that is a tag for longer words (P116: `spec.reason` is its code,
  // `vocab.reason_tips` the words) shows them as its tooltip every time; any
  // other status shows its own words only when they are cut.
  const tips = spec.reason ? vocab.reason_tips : null;
  if (spec.reason && !tips) throw new Error("reason_tips");
  const tip = tips ? tips[spec.reason] || "" : "";
  if (tip) setTip(node.querySelector(".row-status"), tip);
  else setTipIfCut(node.querySelector(".row-status"), spec.status);
  return node;
}

function pagesStepWords(step) {
  const steps = screenWords().steps;
  return { open: steps.open, check: steps.check, draft: steps.draft, edit: steps.edit }[step.kind];
}

function pagesActivate(list, row) {
  for (const one of list.querySelectorAll(".is-active")) {
    one.classList.remove("is-active");
    one.setAttribute("aria-selected", "false");
  }
  row.classList.add("is-active");
  row.setAttribute("aria-selected", "true");
  list.setAttribute("aria-activedescendant", row.id);
  if (row.scrollIntoView) row.scrollIntoView({ block: "nearest" });
}

function pagesRunRow(row) {
  const spec = pagesTokens.get(row.id);
  if (spec && spec.step) pagesRunStep(spec.step);
}

// A click on a name link in a row: the link of that cell.
function pagesRunRowLink(row, node) {
  const spec = pagesTokens.get(row.id);
  const link = spec ? spec[`${node.dataset.cell}Link`] : null;
  if (link) pagesRunLink(link);
}

function pagesRunStep(step) {
  if (step.kind === "open") shellGo(step.route);
  else if (step.kind === "edit") {
    if (!locked) openEditor(step.identifier);
  } else if (step.kind === "check") {
    if (typeof openCheck === "function") openCheck(step.ret, step.name, step.handle);
    else unanswered("check");
  } else if (step.kind === "draft") {
    if (typeof openReminder === "function") openReminder(step.ret);
    else unanswered("draft_reminder");
  }
}

// One listbox: a Tab stop, named by its heading or by a label.
function pagesList(name, kids) {
  const attrs = { className: "rows", role: "listbox", tabindex: "0" };
  if (name.labelledby) attrs["aria-labelledby"] = name.labelledby;
  else attrs["aria-label"] = name.label;
  const list = h("div", attrs, ...kids);
  list.addEventListener("focus", () => {
    const first = list.querySelector('[role="option"]');
    if (first && !list.querySelector(".is-active")) pagesActivate(list, first);
  });
  list.addEventListener("click", (e) => {
    const row = e.target.closest(".row");
    if (!row) return;
    pagesActivate(list, row);
    list.focus({ preventScroll: true });
    const link = e.target.closest(".row-link");
    if (link) pagesRunRowLink(row, link);
    else if (e.target.closest(".row-step")) pagesRunRow(row);
  });
  list.addEventListener("dblclick", (e) => {
    const row = e.target.closest(".row");
    if (row && !e.target.closest(".row-link")) pagesRunRow(row);
  });
  list.addEventListener("contextmenu", (e) => {
    const row = e.target.closest(".row");
    if (!row) return;
    e.preventDefault();
    pagesActivate(list, row);
    list.focus({ preventScroll: true });
    pagesPopup(row, e.clientX, e.clientY);
  });
  return list;
}

// A group: the H2 with its count (or a caption), its rows, and - for a
// group with a step of its own - that step at the heading's end. `blocks`
// are runs of rows; a run with `sub` sits under a caption sub-heading.
// `fold` makes the group a closed `details` (Set aside).
function pagesGroup(spec) {
  pagesUid += 1;
  const headId = `group-${pagesUid}`;
  // A file's own row under its request (ruling 17) is not another request: not counted.
  const total = spec.blocks.reduce((n, block) => n + block.rows.filter((row) => !row.classList.contains("row-child")).length, 0);
  const meta = h("span", { className: "group-count" }, spec.caption !== undefined ? spec.caption : String(total));
  const title = h("h2", { className: "group-title", id: headId }, spec.headingLink ? pagesHeadLink(spec.headingLink, spec.heading) : spec.heading);
  const start = spec.step ? pagesGroupStep(spec.step) : null;
  const headClass = `group-head${spec.first ? " is-first" : ""}`;
  let body = null;
  if (total) {
    const kids = [];
    for (const block of spec.blocks) {
      if (!block.sub) {
        kids.push(...block.rows);
        continue;
      }
      pagesUid += 1;
      const subId = `sub-${pagesUid}`;
      kids.push(h("div", { role: "group", "aria-labelledby": subId },
        h("div", { className: "group-sub", id: subId }, block.sub), ...block.rows));
    }
    body = pagesList({ labelledby: headId }, kids);
  } else if (spec.none) {
    body = h("div", { className: "group-none" }, spec.none);
  }
  if (spec.fold) {
    const fold = h("details", { className: "group-fold" }, h("summary", { className: headClass }, title, meta), body);
    fold.open = Boolean(spec.open);
    if (spec.onToggle) fold.addEventListener("toggle", () => spec.onToggle(fold.open));
    return [fold];
  }
  return [h("div", { className: headClass }, title, meta, start), body].filter(Boolean);
}

// A link in a heading or a caption (a return's name, a household's): outside
// the row lists, so it takes its own click.
function pagesHeadLink(link, text) {
  const node = pagesLinkNode(link, text, "head");
  node.addEventListener("click", () => pagesRunLink(link));
  return node;
}

// The group heading's own step, shown on hover of the heading; the same
// step every row of the group runs, and reachable from the keyboard there.
function pagesGroupStep(step) {
  const node = h("button", { type: "button", className: "group-step", tabindex: "-1", "aria-hidden": "true" }, pagesStepWords(step), icon("chev", true));
  node.addEventListener("click", () => pagesRunStep(step));
  return node;
}

function pagesEmpty(line, note, ...more) {
  return h("div", { className: "page-empty" }, h("p", { className: "page-empty-line" }, line),
    note ? h("p", { className: "page-empty-note" }, note) : null, ...more);
}

function pagesTitle(text, menu, token) {
  pagesUid += 1;
  const attrs = { className: "page-title", id: `title-${pagesUid}` };
  if (menu) attrs.dataset = { menu, token };
  const node = h("h1", attrs, text);
  // The heading of a household or a return: its own native menu, acting on
  // the page it heads (the crumb tokens are shell.js's).
  if (menu) {
    node.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      shellPopup(menu, token, e.clientX, e.clientY);
    });
  }
  return node;
}

// The H1 of a household, year or return page (the frame that stays when the
// rest of the page cannot be built), or null on a page that has none.
function pagesTitleFor(route) {
  if (route.level === "return") return pagesTitle(pagesReturnName(route.ret), "return", "crumb-return");
  if (route.level === "year") return pagesTitle(String(route.year));
  const hh = route.level === "household" ? shellHousehold(route.household) : null;
  return hh ? pagesTitle(hh.name, "household", "crumb-household") : null;
}

function pagesCaption(text) {
  return text ? h("div", { className: "page-caption" }, text) : null;
}

// ── Overview (SPEC 6.1) ───────────────────────────────────────────────
function pagesWorkRows(returns) {
  const name = (one) => pagesReturnName(one.path);
  // A return whose record could not be read has no counts, and is the first
  // thing a person must see: it leads the first bucket, saying its problem.
  const soonest = (one) => (one.problem ? "" : one.oldest || PAGES_LATE);
  const need = returns.filter((one) => one.counts.needs_you > 0 || one.problem)
    .sort((a, b) => soonest(a).localeCompare(soonest(b)) || pagesByName(name(a), name(b)));
  const wait = returns.filter((one) => !one.problem && !one.counts.needs_you && one.counts.waiting > 0)
    .sort((a, b) => (a.due || PAGES_LATE).localeCompare(b.due || PAGES_LATE) || pagesByName(name(a), name(b)));
  const steps = { kind: "open" };
  const specOf = (one, date) => {
    const said = pagesCounts(one.counts, one.problem);
    const house = pagesHouseholdPath(one.household);
    return { name: pagesReturnText(one.path, one.year), detail: one.household, status: said.text, tone: said.tone, date, menu: "return",
             nameLink: { kind: "return", path: one.path }, detailLink: house ? { kind: "household", path: house } : null,
             step: { ...steps, route: pagesRoute(one.path) } };
  };
  return [...pagesEach(need, name, (one) => specOf(one, pagesDay(one.oldest))), ...pagesEach(wait, name, (one) => specOf(one, pagesDue(one.due)))];
}

// A household paused for two open years is work waiting for a person: one row
// on the Overview, first, worded by the vocabulary, opening the household
// (ruling 21). Nothing is hidden on its own pages.
function pagesPausedRows(firm) {
  const word = screenWords().notices.paused;
  return pagesEach([...pagesPaused(firm)].sort(pagesByName), (name) => name, (name) => {
    const path = pagesHouseholdPath(name);
    if (!path) throw new Error("household");
    return { name, detail: "", status: word, tone: "needs", date: "", menu: "household", nameLink: { kind: "household", path },
             step: { kind: "open", route: { level: "household", household: path } } };
  });
}

function pagesOverview() {
  const words = screenWords();
  const firm = pagesFirm();
  const totals = firm.totals;
  const figures = h("div", { className: "figures" }, ...[[totals.need, words.figures.need], [totals.waiting, words.figures.waiting], [totals.complete, words.figures.complete]]
    .map(([n, label]) => h("div", { className: "figure" }, h("b", { className: "figure-number" }, String(n)), h("span", { className: "figure-label" }, label))));
  const rows = pagesEach([...pagesPausedRows(firm), ...pagesWorkRows(firm.returns)], (spec) => spec.name, pagesRow);
  if (!rows.length) return [figures, pagesEmpty(words.empty.overview, pagesNextSort(firm))];
  return [figures, ...pagesGroup({ heading: words.work, first: true, blocks: [{ rows }] })];
}

// ── Needs review (SPEC 6.2) ───────────────────────────────────────────
function pagesReviewGroups(firm) {
  const byReturn = new Map();
  for (const file of firm.files) {
    if (!byReturn.has(file.return)) byReturn.set(file.return, []);
    byReturn.get(file.return).push(file);
  }
  const oldest = (list) => list.reduce((least, one) => (one.received < least ? one.received : least), PAGES_LATE);
  return [...byReturn.entries()]
    .map(([path, list]) => ({ path, files: list.slice().sort((a, b) => a.received.localeCompare(b.received) || pagesByName(a.name, b.name)) }))
    .sort((a, b) => oldest(a.files).localeCompare(oldest(b.files)) || pagesByName(pagesReturnName(a.path), pagesReturnName(b.path)));
}

function pagesNeedsReview() {
  const words = screenWords();
  const firm = pagesFirm();
  const groups = pagesReviewGroups(firm);
  if (!groups.length) return [pagesEmpty(words.empty.needs_review, pagesNextSort(firm))];
  return groups.flatMap((group, i) => pagesSafe(pagesReturnName(group.path), () => {
    const owner = pagesFirmReturn(group.path);
    // A file's name is a link to its working copy when the firm's reply names
    // one (`open_key` and the reply's `paths`, ruling 15); with none it is text.
    const rows = pagesEach(group.files, (file) => file.name, (file) => pagesRow({
      name: file.name, detail: file.suggestion || "", status: pagesReason(file.code), reason: file.code, tone: "needs", date: pagesDay(file.received),
      menu: "file", fileKind: "parked", nameLink: pagesFileLink(firm.paths, file.open_key),
      step: { kind: "check", ret: group.path, name: file.name, handle: file.handle },
    }));
    const household = owner ? owner.household : "";
    const house = pagesHouseholdPath(household);
    const caption = household
      ? [house ? pagesHeadLink({ kind: "household", path: house }, household) : household, ` · ${rows.length}`]
      : String(rows.length);
    return pagesGroup({ heading: pagesReturnText(group.path, owner ? owner.year : 0), headingLink: { kind: "return", path: group.path },
                        caption, first: i === 0, blocks: [{ rows }] });
  }) || []);
}

// ── Reminders (SPEC 6.3) ──────────────────────────────────────────────
function pagesReminderSpecs(firm) {
  const ready = firm.returns.filter((one) => one.draft && one.draft.ready);
  return pagesEach(ready.sort((a, b) => pagesByName(pagesReturnName(a.path), pagesReturnName(b.path))), (one) => pagesReturnName(one.path), (one) => {
    const house = pagesHouseholdPath(one.household);
    return {
      name: pagesReturnText(one.path, one.year), detail: one.household,
      status: one.draft.held > 0 ? screenWords().held : pagesStage(one.draft.stage),
      tone: one.draft.held > 0 ? "needs" : "waiting", date: pagesDay(one.draft.drafted), menu: "return",
      nameLink: { kind: "return", path: one.path }, detailLink: house ? { kind: "household", path: house } : null,
      step: { kind: "draft", ret: one.path },
    };
  });
}

function pagesReminders() {
  const words = screenWords();
  const specs = pagesReminderSpecs(pagesFirm());
  if (!specs.length) return [pagesEmpty(words.empty.reminders)];
  return [h("div", { className: "page-gap" }), pagesList({ label: words.sections.reminders }, pagesEach(specs, (spec) => spec.name, pagesRow))];
}

// ── Clients (SPEC 6.4) ────────────────────────────────────────────────
function pagesClientSpecs(firm, all) {
  const words = screenWords().counts;
  const own = (name) => firm.returns.filter((one) => one.household === name);
  const pausedNames = pagesPaused(firm);
  return pagesEach(households.slice().sort((a, b) => pagesByName(a.name, b.name)), (one) => one.name, (one) => {
    const returns = own(one.name);
    const need = returns.reduce((n, r) => n + r.counts.needs_you, 0);
    const wait = returns.reduce((n, r) => n + r.counts.waiting, 0);
    const problem = returns.find((r) => r.problem);
    // A household with a return whose record cannot be read is never
    // Complete: that return's problem is its status (as pagesCounts says it).
    const said = need ? { text: fill(words.need, { n: need }), tone: "needs" }
      : problem ? { text: problem.problem, tone: "needs" }
        : wait ? { text: fill(words.waiting, { n: wait }), tone: "waiting" }
          : returns.length ? { text: words.complete, tone: "done" } : { text: "", tone: "plain" };
    const paused = pausedNames.has(one.name);
    return { work: need + wait > 0 || Boolean(problem) || paused, spec: {
      name: one.name, detail: returns.length ? fill(returns.length === 1 ? words.one_return : words.returns, { n: returns.length }) : "",
      mark: paused ? screenWords().notices.paused : "",
      status: said.text, tone: said.tone, date: "", menu: "household", nameLink: { kind: "household", path: one.path },
      step: { kind: "open", route: { level: "household", household: one.path } },
    } };
  }).filter((one) => all || one.work).map((one) => one.spec);
}

function pagesSwitch() {
  const words = screenWords().filters;
  const option = (label, all) => {
    const node = h("button", { type: "button", className: "switch-option", "aria-pressed": pagesClientsAll === all ? "true" : "false" }, label);
    node.addEventListener("click", () => {
      pagesClientsAll = all;
      pagesDraw(shellRoute, $("page"));
    });
    return node;
  };
  return h("div", { className: "switch", role: "group", "aria-label": screenWords().sections.clients }, option(words.work, false), option(words.all, true));
}

function pagesClients() {
  const words = screenWords();
  const firm = pagesFirm();
  if (!households.length) {
    const start = h("button", { type: "button", className: "btn" }, vocab.menu.new_household);
    start.addEventListener("click", () => openNewHousehold());
    return [pagesEmpty(words.empty.clients, "", start)];
  }
  const specs = pagesClientSpecs(firm, pagesClientsAll);
  const rows = document.createDocumentFragment();
  for (const row of pagesEach(specs, (spec) => spec.name, pagesRow)) rows.append(row);
  return [pagesSwitch(), specs.length ? pagesList({ label: words.sections.clients }, [rows]) : pagesEmpty(words.empty.work)];
}

// ── Household and year (SPEC 6.5, 6.6) ────────────────────────────────
function pagesHouseholdCaption(route) {
  const hh = shellHousehold(route.household);
  const state = lastState && lastState.household && lastState.household.path === route.household ? lastState.household : null;
  const words = screenWords();
  const parts = [];
  if (hh && hh.contact) parts.push(fill(words.contact, { name: hh.contact }));
  if (state) parts.push(state.shared_on ? words.shared : words.not_shared);
  return parts.join(" · ");
}

function pagesReturnSpecs(returns) {
  const words = screenWords();
  return pagesEach(returns.slice().sort((a, b) => pagesByName(a.return_name || a.label, b.return_name || b.label)), (one) => one.return_name || one.label, (one) => {
    const firm = pagesFirmReturn(one.path);
    const said = firm ? pagesCounts(firm.counts, firm.problem) : { text: "", tone: "plain" };
    const detail = one.superseded_by ? words.rolled : one.active === false ? words.inactive : "";
    return { name: pagesReturnText(one.path, one.year, one.return_name), detail, status: said.text, tone: said.tone, date: "", menu: "return",
             nameLink: { kind: "return", path: one.path },
             step: { kind: "open", route: { level: "return", household: shellRoute.household, year: one.year, ret: one.path } } };
  });
}

function pagesHousehold(route) {
  const words = screenWords();
  const hh = shellHousehold(route.household);
  if (!hh) return [];
  const head = [pagesTitleFor(route), pagesCaption(pagesHouseholdCaption(route))];
  if (!hh.returns.length) {
    const add = h("button", { type: "button", className: "btn" }, vocab.menu.add_return);
    add.addEventListener("click", () => openAddReturn(hh));
    return [...head, pagesEmpty(words.empty.returns, "", add)];
  }
  const years = [...new Set(hh.returns.map((one) => one.year))].sort((a, b) => b - a);
  return [...head, ...years.flatMap((year, i) => pagesSafe(String(year), () => pagesGroup({
    heading: String(year), first: i === 0,
    blocks: [{ rows: pagesEach(pagesReturnSpecs(hh.returns.filter((one) => one.year === year)), (spec) => spec.name, pagesRow) }],
  })) || [])];
}

function pagesYear(route) {
  const hh = shellHousehold(route.household);
  if (!hh) return [];
  const title = pagesTitleFor(route);
  const specs = pagesReturnSpecs(hh.returns.filter((one) => one.year === route.year));
  return [title, h("div", { className: "page-gap" }), pagesList({ labelledby: title.id }, pagesEach(specs, (spec) => spec.name, pagesRow))];
}

// ── Return (SPEC 6.7) ─────────────────────────────────────────────────
function pagesItemName(item) {
  return item.short_name || item.document;
}

// A request row's status word: the preparer's word for the record's, or
// the set-aside label with its year (the API's patterns, decision 200).
function pagesItemStatus(item) {
  if (isSetAside(item.manual_override)) return overrideLabel(item.manual_override, item.year);
  const shown = vocab.labels[item.status_key];
  if (!shown) throw new Error(`labels.${item.status_key}`);
  return shown.label;
}

// A request row's detail: "1 of 2" while partly in, else its period when
// that is not the return's year.
function pagesItemDetail(item, year) {
  if (item.file_count > 0 && item.expected_count > item.file_count) {
    return fill(screenWords().partly, { n: item.file_count, total: item.expected_count });
  }
  if (item.period && item.year !== year) return item.period;
  return "";
}

// The grouping of one return's `state` into the four groups of SPEC 6.7,
// as row specs in the order drawn. Each item's group is the API's `group`;
// a file's is the list it is in. Buckets ("Emails and zips", "Not
// documents") mark parked files with a `sub` and sit last in the group, so
// a sub-heading never captions a row that is not its own.
function pagesReturnGroups(state, year) {
  const words = screenWords();
  const decisions = vocab.decisions;
  const index = state.index || [];
  const items = state.items || [];
  const triage = new Map((state.review || []).map((one) => [one.handle, one]));
  const byId = new Map(items.map((one) => [one.identifier, one]));
  const nameOf = (identifier) => (byId.has(identifier) ? pagesItemName(byId.get(identifier)) : identifier || "");
  const groups = { needs_you: [], waiting: [], received: [], set_aside: [] };
  const fileStep = (entry) => ({ kind: "check", ret: state.paths.engagement, name: entry.original_name, handle: entry.handle });
  const oldestFirst = (a, b) => String(a.received).localeCompare(String(b.received)) || pagesByName(a.original_name, b.original_name);

  const bucketOrder = vocab.review_labels.bucket_order;
  const plain = bucketOrder[0];
  // A file's group is the engine's (`index[].group`, SPEC 9.1: the same the firm's counts use), never
  // worked out here from its decision; a file with none is set aside and named, as an item is.
  for (const entry of index) {
    pagesSafe(entry, () => {
      if (PAGES_GROUPS.indexOf(entry.group) === -1) throw new Error("group");
    });
  }
  const filesIn = (group) => index.filter((one) => one.group === group);
  const parked = filesIn("needs_you").filter((one) => one.decision === decisions.needs_review).sort(oldestFirst);
  // A file's name is a link to its working copy when the state names one:
  // `shown_key` on a parked or set-aside row, `open_key` on a moved one, and
  // `open_keys[0]` on the one copy a filed row has (SPEC 3.9, 5.7). A row with
  // no key is text.
  const linkOf = (key) => pagesFileLink(state.paths, key);
  const parkedSpec = (entry) => {
    const first = ((triage.get(entry.handle) || {}).shortlist || [])[0];
    return { name: entry.original_name, detail: first ? nameOf(first.identifier) : "", status: pagesReason(entry.code), reason: entry.code, tone: "needs",
             date: pagesDay(entry.received), menu: "file", fileKind: "parked", nameLink: linkOf(entry.shown_key), step: fileStep(entry) };
  };
  const parkedIn = (list, extra) => pagesEach(list, (one) => one.original_name, (one) => ({ ...parkedSpec(one), ...extra }));
  groups.needs_you.push(...parkedIn(parked.filter((one) => (one.bucket || plain) === plain), {}));
  const receivedOf = new Map(index.map((one) => [one.handle, one.received]));
  groups.needs_you.push(...pagesEach(state.moved || [], (one) => one.original_name, (one) => ({
    name: one.original_name, detail: nameOf(one.identifier || one.in_request), status: words.moved, tone: "needs",
    date: pagesDay(receivedOf.get(one.handle)), menu: "moved", canKeep: Boolean(one.in_request && !one.gone), gone: Boolean(one.gone), nameLink: linkOf(one.open_key),
    step: { kind: "check", ret: state.paths.engagement, name: one.original_name, handle: one.handle },
  })));

  const filedBy = (identifier) => index.filter((one) => one.decision === decisions.filed
    && (one.identifier === identifier || (one.answered || []).indexOf(identifier) !== -1));
  // An item with no known group is not guessed at and not drawn: it is set
  // aside (pagesSafe) and named in a notice at the end of the draw, while
  // every other row is drawn (SPEC 6, loud and safe).
  for (const item of items) {
    pagesSafe(item, () => {
      if (PAGES_GROUPS.indexOf(item.group) === -1) throw new Error("group");
      const filed = filedBy(item.identifier);
      const detail = item.group === "received"
        ? (filed.length > 1 ? fill(words.counts.files, { n: filed.length }) : filed.length ? filed[0].original_name : "")
        : pagesItemDetail(item, year);
      // One filed file is a link to its copy under this very request: the
      // first of its copies, which is the one the record's `prepared_location`
      // names and the filer files under the row's own `identifier` (decision
      // 94's other copies follow it). A file that only answers the request
      // (decision 146) has no copy here, so no link. Several files are a
      // count, and a count is not a name. Unfile is offered for the one
      // original filed under this request, Mark missing for the request a
      // consolidated statement answered without a copy (decision 146).
      const single = filed.length === 1 ? filed[0] : null;
      const direct = filed.filter((one) => one.identifier === item.identifier);
      const answering = filed.find((one) => (one.answered || []).indexOf(item.identifier) !== -1);
      const tone = { needs_you: "needs", waiting: "waiting", received: "done", set_aside: "plain" }[item.group];
      const spec = {
        name: pagesItemName(item), detail, status: pagesItemStatus(item), tone,
        date: item.group === "waiting" ? "" : pagesDay(item.received_date),
        menu: item.group === "received" ? "received" : "request",
        step: item.group === "needs_you" ? { kind: "edit", identifier: item.identifier }
          : item.group === "waiting" ? { kind: "draft", ret: state.paths.engagement } : null,
        identifier: item.identifier,
      };
      if (item.group === "received") {
        spec.detailLink = single && single.identifier === item.identifier && (single.open_keys || []).length >= 1 ? linkOf(single.open_keys[0]) : null;
        // Several files answer the request: the request keeps its count and each file
        // gets its own row under it (ruling 17), with its own link and its own Unfile.
        spec.unfile = filed.length === 1 && direct.length === 1 ? { original: direct[0].handle, seq: direct[0].seq, name: direct[0].original_name } : null;
        spec.missing = answering ? { original: answering.handle, seq: answering.seq, identifier: item.identifier } : null;
      }
      groups[item.group].push(spec);
      if (item.group === "received" && filed.length > 1) {
        for (const one of filed) {
          const here = one.identifier === item.identifier;
          groups.received.push({
            name: one.original_name, detail: "", status: "", tone: "done", date: pagesDay(one.received), child: true,
            menu: "received", identifier: item.identifier,
            nameLink: here && (one.open_keys || []).length >= 1 ? linkOf(one.open_keys[0]) : null,
            unfile: here ? { original: one.handle, seq: one.seq, name: one.original_name } : null, missing: null,
          });
        }
      }
    });
  }
  // Set aside: files a person set aside (Not requested) and moved files a person marked missing. The
  // second has no copy to check, so it has no step.
  groups.set_aside.push(...pagesEach(filesIn("set_aside").sort(oldestFirst), (one) => one.original_name, (entry) => {
    const missing = entry.decision === decisions.file_moved;
    return {
      name: entry.original_name, detail: "", status: missing ? words.moved : vocab.review_labels.dismiss, tone: "plain",
      date: pagesDay(entry.received), menu: "file", fileKind: missing ? "missing" : "aside", nameLink: linkOf(entry.shown_key),
      step: missing ? null : fileStep(entry),
    };
  }));
  for (const bucket of bucketOrder.slice(1)) {
    groups.needs_you.push(...parkedIn(parked.filter((one) => one.bucket === bucket), { sub: vocab.review_labels.buckets[bucket] }));
  }
  return groups;
}

// A group's blocks: consecutive rows with the same sub-heading run together.
function pagesBlocks(specs) {
  const blocks = [];
  for (const spec of specs) {
    const row = pagesSafe(spec.name, () => pagesRow(spec));
    if (row === null) continue;
    const last = blocks[blocks.length - 1];
    if (last && (last.sub || "") === (spec.sub || "")) last.rows.push(row);
    else blocks.push({ sub: spec.sub || "", rows: [row] });
  }
  return blocks;
}

// Which groups a return's page draws, in order (SPEC 6.7): Needs you, Waiting
// on client (with the group's own step), Received (always, so a return with
// nothing received says so) and the closed fold of set-aside rows. A group with no
// rows is left out but Received.
function pagesReturnPlan(groups, route) {
  const words = screenWords();
  const plan = [];
  if (groups.needs_you.length) plan.push({ key: "needs_you", heading: words.groups.needs_you });
  if (groups.waiting.length) plan.push({ key: "waiting", heading: words.groups.waiting, step: { kind: "draft", ret: route.ret } });
  plan.push({ key: "received", heading: words.groups.received, none: words.empty.received });
  if (groups.set_aside.length) plan.push({ key: "set_aside", heading: words.groups.set_aside, fold: true });
  return plan;
}

function pagesReturn(route) {
  if (!lastState || !lastState.paths || lastState.paths.engagement !== route.ret) return [];
  const state = lastState;
  const title = pagesTitleFor(route);
  const due = state.engagement && state.engagement.due ? pagesDue(state.engagement.due) : "";
  const groups = pagesReturnGroups(state, route.year);
  const out = [title, pagesCaption(due)];
  pagesReturnPlan(groups, route).forEach((one, i) => {
    pagesSafe(one.heading, () => {
      const spec = { ...one, first: i === 0, blocks: pagesBlocks(groups[one.key]) };
      if (one.fold) {
        // Shut each time the page opens (pagesDraw resets it); kept across redraws of this page.
        spec.open = pagesSetAsideOpen;
        spec.onToggle = (open) => { pagesSetAsideOpen = open; };
      }
      out.push(...pagesGroup(spec));
    });
  });
  return out.filter(Boolean);
}

// How many of each group a `state` holds, counted the way `firm` counts
// (SPEC 9.1, 9.2): shell.js asks for the firm's counts again when they differ.
function pagesTally(state) {
  const tally = { needs_you: 0, waiting: 0, received: 0, set_aside: 0 };
  for (const item of state.items || []) {
    // An item with no known group is counted in none (the draw names it).
    if (PAGES_GROUPS.indexOf(item.group) !== -1) tally[item.group] += 1;
  }
  // Files count where the engine put them (`index[].group`): parked and moved-by-hand files are Needs you,
  // files set aside and moved files marked missing are Set aside; filed files count in no group (their
  // request does).
  for (const entry of state.index || []) {
    if (entry.group === "needs_you" || entry.group === "set_aside") tally[entry.group] += 1;
  }
  return tally;
}

// ── notices that belong to a household's pages (SPEC 6.5) ─────────────
function pagesHouseholdNotices(route) {
  const wanted = [];
  const client = ["household", "year", "return"].indexOf(route.level) !== -1;
  const hh = client && lastState && lastState.household && lastState.household.path === route.household ? lastState.household : null;
  if (hh) {
    const words = vocab.household;
    if ((hh.open_years || []).length > 1) {
      wanted.push({ key: "two-years", failure: { sentence: fill(words.two_open_years, { years: hh.open_years.join(", ") }), kind: "warning" } });
    }
    // The pause and the feeds are the API's long sentences: each is shown as
    // its short line and the sentence goes to the error log (SPEC 11.1). A
    // pause a person can accept (it names a scope) is the renamed folder, with
    // Accept; a year's pause has no Accept.
    const pause = hh.pause || {};
    if (pause.sentence) {
      wanted.push({ key: "renamed", failure: { sentence: shortNotice(pause.scope ? "renamed" : "paused"), kind: "warning" },
                    detail: pause.sentence,
                    opts: pause.scope ? { action: { label: words.accept_folder_name, run: acceptFolderName, write: true } } : {} });
    }
    const feeds = (hh.feeds || []).map((one) => one.warning).filter(Boolean);
    if (feeds.length) wanted.push({ key: `feeds:${feeds.join("\n")}`, failure: { sentence: shortNotice("feed"), kind: "warning" }, detail: feeds.join("\n") });
  }
  syncNotices("household", wanted);
}

// The shell left the household's pages (the setup page): its notices go.
function pagesLeave() {
  syncNotices("household", []);
  syncNotices("rows", []);
  pagesDrawn = "";
}

// ── the page ──────────────────────────────────────────────────────────
function pagesBuild(route) {
  const builders = {
    overview: pagesOverview, "needs-review": pagesNeedsReview, reminders: pagesReminders, clients: pagesClients,
    household: pagesHousehold, year: pagesYear, return: pagesReturn,
  };
  return builders[route.level](route);
}

// Where focus sits in a row list of the page: which list and which row, or
// null when it sits anywhere else.
function pagesWhere(page) {
  const here = document.activeElement;
  const list = here && here.closest ? here.closest('[role="listbox"]') : null;
  if (!list || !page.contains(list)) return null;
  const row = list.querySelector(".is-active");
  return { at: [...page.querySelectorAll('[role="listbox"]')].indexOf(list), row: row ? [...list.querySelectorAll('[role="option"]')].indexOf(row) : 0 };
}

function pagesRemember(page) {
  pagesFocus = pagesWhere(page);
}

// Focus back on the row it was on (or the nearest), after the page was drawn
// again: the sheet's way back to the row that opened it.
function pagesFocusAt(where) {
  pagesFocus = where;
  pagesRestore($("page"));
}

function pagesRestore(page) {
  if (!pagesFocus) return;
  const list = page.querySelectorAll('[role="listbox"]')[pagesFocus.at];
  const rows = list ? list.querySelectorAll('[role="option"]') : [];
  if (rows.length) {
    pagesActivate(list, rows[Math.min(Math.max(pagesFocus.row, 0), rows.length - 1)]);
    list.focus({ preventScroll: true });
  }
  pagesFocus = null;
}

// The notices for rows and groups that could not be built: one each, naming
// the row (user data) in the app's own error sentence; the detail, with the
// error's own message, goes to the error log (SPEC 11.1, 2.2 E30).
function pagesReportBroken() {
  const wanted = pagesBroken.map((one, i) => {
    const kind = (one.err && one.err.name) || "Error";
    const said = fill(vocab.shell.page_error, { kind });
    return {
      key: `${i}:${one.name}`,
      failure: { sentence: one.name ? fill(vocab.notices.about, { label: one.name, sentence: said }) : said, kind: "failed" },
      detail: `${one.name}: ${kind}: ${String((one.err && one.err.message) || one.err)}\n${(one.err && one.err.stack) || ""}`,
    };
  });
  syncNotices("rows", wanted);
}

function pagesRouteKey(route) {
  return [route.level, route.household || "", route.year || "", route.ret || ""].join("|");
}

// shell.js: draw the route's page into #page. A page that cannot be built
// whole keeps what it held (the same page) or draws its frame, its H1, and
// says so; it is never emptied for one bad row (SPEC 6, failed read).
function pagesDraw(route, page) {
  if (route.level === "clients" && pagesLastLevel !== "clients") pagesClientsAll = false;
  pagesLastLevel = route.level;
  const key = pagesRouteKey(route);
  if (pagesDrawn !== key) pagesSetAsideOpen = false;   // Set aside is shut each time the page opens
  pagesRemember(page);
  const before = new Map(pagesTokens);
  pagesUid = 0;
  pagesTokens.clear();
  pagesBroken = [];
  let nodes = null;
  try {
    pagesHouseholdNotices(route);
  } catch (err) {
    failed(err);
  }
  try {
    nodes = pagesBuild(route);
  } catch (err) {
    failed(err);
  }
  try {
    pagesReportBroken();
  } catch (err) {
    failed(err);
  }
  if (nodes === null && pagesDrawn === key && page.childNodes && page.childNodes.length) {
    for (const [id, spec] of before) pagesTokens.set(id, spec);
    return;
  }
  if (nodes === null) {
    try {
      nodes = [pagesTitleFor(route)].filter(Boolean);
    } catch (err) {
      nodes = [];
    }
  }
  page.replaceChildren(...nodes);
  pagesDrawn = key;
  pagesRestore(page);
}

// ── keys on a row list (SPEC 3.6, 4.3) ────────────────────────────────
// shell.js hands a key from inside a `role="listbox"` here; true = handled.
// The right-click key (Shift+F10, the menu key) is the right-click menu's,
// wired with it.
function pagesKey(e) {
  const list = e.target.closest('[role="listbox"]');
  if (!list) return false;
  const rows = [...list.querySelectorAll('[role="option"]')];
  if (!rows.length) return false;
  const at = Math.max(0, rows.findIndex((one) => one.classList.contains("is-active")));
  // Shift+F10 and the menu key: the row's native menu, under the row.
  if (e.key === "ContextMenu" || (e.key === "F10" && e.shiftKey)) {
    e.preventDefault();
    const box = rows[at].getBoundingClientRect();
    pagesPopup(rows[at], box.left + box.width / 2, box.bottom);
    return true;
  }
  const size = rows[0].offsetHeight || 1;
  const page = Math.max(1, Math.floor(($("page").clientHeight || size) / size) - 1);
  const moves = {
    ArrowDown: at + 1, ArrowUp: at - 1, Home: 0, End: rows.length - 1, PageDown: at + page, PageUp: at - page,
  };
  if (e.key in moves) {
    e.preventDefault();
    pagesActivate(list, rows[Math.min(Math.max(moves[e.key], 0), rows.length - 1)]);
    return true;
  }
  if (e.key === "Enter") {
    e.preventDefault();
    pagesRunRow(rows[at]);
    return true;
  }
  return false;
}

// What a row is about, by its id (a right-click's token).
function pagesRowFor(token) {
  return pagesTokens.get(token) || null;
}

// The steps of one kind on the page in the order drawn: the sheet's next arrow.
function pagesSteps(kind, wanted) {
  return [...pagesTokens.entries()]
    .filter(([, spec]) => spec.step && spec.step.kind === kind && (!wanted || wanted(spec)))
    .sort((a, b) => Number(a[0].slice(4)) - Number(b[0].slice(4)))
    .map(([, spec]) => spec.step);
}

// Every Check step of the files a person must look at, in the order drawn
// (SPEC 7.1): the parked and moved-by-hand files, not the ones already set
// aside, which are checked one at a time when a person opens them.
function pagesFiles() {
  return pagesSteps("check", (spec) => spec.fileKind !== "aside");
}

// Every Draft reminder step on the page (the Reminders page's drafts).
function pagesDrafts() {
  return pagesSteps("draft");
}

// ── the right-click menu of a row (SPEC 5.2, 5.3) ─────────────────────
// A row asks for the native menu of its template with the ids that apply to
// it now (a live lock greys the writing items); the id chosen comes back
// with the row's token to pagesMenu. The client rows (household, return) act
// on that row's household or return: the app goes there first, then answers
// the item as if the person had chosen it on that page.

// The route a household or return row stands for.
function pagesRowRoute(spec) {
  if (spec.step && spec.step.route) return spec.step.route;
  const link = spec.nameLink;
  if (link && link.kind === "return") return pagesRoute(link.path);
  if (link && link.kind === "household") return { level: "household", household: link.path };
  return shellRoute;
}

// Another Return is on the sheet only for a parked document of a return whose
// household has another return to hand it to (app.js's fedReturns, read from
// the state the sheet draws from). A file of a return that is not on screen
// cannot be known here, so its item stays grey rather than opening a sheet
// that has no such button (SPEC 5.3: "the ids whose rule holds now").
function pagesCanHandOver(spec) {
  const state = lastState;
  if (!state || !spec.step || !state.paths || state.paths.engagement !== spec.step.ret) return false;
  const entry = (state.index || []).find((one) => one.handle === spec.step.handle);
  return Boolean(entry) && !notADocument(entry) && fedReturns().length > 0;
}

function pagesEnableFor(spec) {
  const ids = [];
  const write = !locked;
  if (spec.menu === "file") {
    if (spec.step) ids.push("check");
    if (write && spec.fileKind === "parked") {
      ids.push("not_requested");
      if (pagesCanHandOver(spec)) ids.push("another_return");
    }
  } else if (spec.menu === "moved") {
    ids.push("check");
    // A copy whose original is gone has only Mark Missing on the sheet.
    if (write && !spec.gone) ids.push("put_back");
    if (write && spec.canKeep) ids.push("keep_here");
  } else if (spec.menu === "request") {
    if (write) ids.push("edit_request");
  } else if (spec.menu === "received") {
    if (write && spec.unfile && !writeBusy("unfile", spec.unfile.original)) ids.push("unfile");
    if (write && spec.missing && !writeBusy("mark-missing", spec.missing.original, spec.missing.identifier)) ids.push("mark_missing");
    if (spec.detailLink || spec.nameLink) ids.push("show_in_explorer");
  } else if (spec.menu === "household" || spec.menu === "return") {
    ids.push(...shellEnabled(pagesRowRoute(spec)));
  }
  if ((spec.menu === "file" || spec.menu === "moved") && spec.nameLink) ids.push("show_in_explorer");
  return ids;
}

function pagesPopup(row, x, y) {
  const spec = pagesTokens.get(row.id);
  if (spec && spec.menu) shellPopup(spec.menu, row.id, x, y, pagesEnableFor(spec));
}

// Open the sheet on a file, then press the button the menu item stands for:
// the write is the sheet's own, with everything the sheet checks.
async function pagesCheckThen(spec, button, id) {
  await openCheck(spec.step.ret, spec.step.name, spec.step.handle);
  if (sheetNow && !sheetPress(button)) unanswered(id);
}

async function pagesClientMenu(spec, id) {
  if (id === "draft_reminder" && spec.step && spec.step.kind === "draft") {
    openReminder(spec.step.ret);
    return;
  }
  const route = pagesRowRoute(spec);
  const here = route.level === shellRoute.level && (route.level === "household" ? route.household === shellRoute.household : route.ret === shellRoute.ret);
  if (!here) {
    await shellGo(route);
    if (shellRoute !== route) return;   // the person went on elsewhere while it loaded
  }
  // The item was enabled from the page the row was on; the page it went to
  // has its own lock and its own rules (SPEC 5.2). Answer only if they hold.
  if (!shellEnabled().includes(id)) return;
  shellAnswer(id);
}

const PAGES_ROW_ANSWERS = {
  check: (spec) => pagesRunStep(spec.step),
  not_requested: (spec) => pagesCheckThen(spec, "r-dismiss", "not_requested"),
  another_return: (spec) => pagesCheckThen(spec, "r-hand-over", "another_return"),
  put_back: (spec) => pagesCheckThen(spec, "r-restore", "put_back"),
  keep_here: (spec) => pagesCheckThen(spec, "r-keep", "keep_here"),
  edit_request: (spec) => pagesRunStep({ kind: "edit", identifier: spec.identifier }),
  unfile: (spec) => openUnfile(spec.unfile),
  mark_missing: (spec) => withdrawAnswer(spec.missing),
  show_in_explorer: (spec) => pagesRunLink(spec.nameLink || spec.detailLink),
};

// shell.js asks first for every menu message that carries a token. False:
// not a row's (the crumbs' tokens, the menu bar), so the shell answers.
function pagesMenu(id, token) {
  const spec = pagesTokens.get(token);
  if (!spec) return false;
  const answer = PAGES_ROW_ANSWERS[id];
  // An answer is asynchronous; a failure of the page's own in it is a notice
  // like any other, never an unhandled rejection.
  if (answer) {
    Promise.resolve().then(() => answer(spec)).catch((err) => failed(err));
    return true;
  }
  if (spec.menu === "household" || spec.menu === "return") {
    pagesClientMenu(spec, id).catch((err) => failed(err));
    return true;
  }
  return false;
}
