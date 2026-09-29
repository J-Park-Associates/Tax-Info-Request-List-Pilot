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
// What this file offers the sheet (S5) and the right-click menus (S5):
//   pagesRowFor(token)  what a row is about ({menu, step, ...}), by the row's id
//   pagesFiles()        the Check steps on the page, in the order drawn
//   data-menu, data-token on every row and on the H1 of a household or
//                       return, which S5 wires to shellPopup()
// Steps that open the sheet call openCheck(ret, name, handle) and
// openReminder(ret) when they exist (S5); until then the shell says so.

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
    const name = typeof one === "string" ? one : one && (one.short_name || one.document || one.original_name || one.name || one.identifier || one.path);
    return String(name || "");
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
  const node = h("div", {
    className: `row${step ? " has-step" : ""}`, role: "option", id, "aria-selected": "false",
    "aria-description": words || undefined, dataset: { menu: spec.menu || "", token: id },
  },
  h("span", { className: "row-name" }, spec.name),
  h("span", { className: "row-detail" }, spec.detail || ""),
  h("span", { className: `row-status ${PAGES_TONES[spec.tone] || ""}` }, spec.status || ""),
  h("span", { className: "row-end" }, h("span", { className: "row-date" }, spec.date || ""), step));
  setTipIfCut(node.querySelector(".row-name"), spec.name);
  setTipIfCut(node.querySelector(".row-detail"), spec.detail);
  setTipIfCut(node.querySelector(".row-status"), spec.status);
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
    if (e.target.closest(".row-step")) pagesRunRow(row);
  });
  list.addEventListener("dblclick", (e) => {
    const row = e.target.closest(".row");
    if (row) pagesRunRow(row);
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
  const total = spec.blocks.reduce((n, block) => n + block.rows.length, 0);
  const meta = h("span", { className: "group-count" }, spec.caption !== undefined ? spec.caption : String(total));
  const title = h("h2", { className: "group-title", id: headId }, spec.heading);
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
  return h("h1", attrs, text);
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
    return { name: name(one), detail: one.household, status: said.text, tone: said.tone, date, menu: "return",
             step: { ...steps, route: pagesRoute(one.path) } };
  };
  return [...pagesEach(need, name, (one) => specOf(one, pagesDay(one.oldest))), ...pagesEach(wait, name, (one) => specOf(one, pagesDue(one.due)))];
}

function pagesOverview() {
  const words = screenWords();
  const firm = pagesFirm();
  const totals = firm.totals;
  const figures = h("div", { className: "figures" }, ...[[totals.need, words.figures.need], [totals.waiting, words.figures.waiting], [totals.complete, words.figures.complete]]
    .map(([n, label]) => h("div", { className: "figure" }, h("b", { className: "figure-number" }, String(n)), h("span", { className: "figure-label" }, label))));
  const rows = pagesEach(pagesWorkRows(firm.returns), (spec) => spec.name, pagesRow);
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
  return groups.flatMap((group, i) => pagesSafe(group.path, () => {
    const owner = pagesFirmReturn(group.path);
    const rows = pagesEach(group.files, (file) => file.name, (file) => pagesRow({
      name: file.name, detail: file.suggestion || "", status: pagesReason(file.code), tone: "needs", date: pagesDay(file.received),
      menu: "file", step: { kind: "check", ret: group.path, name: file.name, handle: file.handle },
    }));
    const household = owner ? owner.household : "";
    return pagesGroup({ heading: pagesReturnName(group.path), caption: household ? `${household} · ${rows.length}` : String(rows.length), first: i === 0, blocks: [{ rows }] });
  }) || []);
}

// ── Reminders (SPEC 6.3) ──────────────────────────────────────────────
function pagesReminderSpecs(firm) {
  const ready = firm.returns.filter((one) => one.draft && one.draft.ready);
  return pagesEach(ready.sort((a, b) => pagesByName(pagesReturnName(a.path), pagesReturnName(b.path))), (one) => pagesReturnName(one.path), (one) => ({
    name: pagesReturnName(one.path), detail: one.household,
    status: one.draft.held > 0 ? screenWords().held : pagesStage(one.draft.stage),
    tone: one.draft.held > 0 ? "needs" : "waiting", date: pagesDay(one.draft.drafted), menu: "return",
    step: { kind: "draft", ret: one.path },
  }));
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
    return { work: need + wait > 0 || Boolean(problem), spec: {
      name: one.name, detail: returns.length ? fill(returns.length === 1 ? words.one_return : words.returns, { n: returns.length }) : "",
      status: said.text, tone: said.tone, date: "", menu: "household",
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
    return { name: one.return_name || one.label, detail, status: said.text, tone: said.tone, date: "", menu: "return",
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
  const parked = index.filter((one) => one.decision === decisions.needs_review).sort(oldestFirst);
  const parkedSpec = (entry) => {
    const first = ((triage.get(entry.handle) || {}).shortlist || [])[0];
    return { name: entry.original_name, detail: first ? nameOf(first.identifier) : "", status: pagesReason(entry.code), tone: "needs",
             date: pagesDay(entry.received), menu: "file", step: fileStep(entry) };
  };
  const parkedIn = (list, extra) => pagesEach(list, (one) => one.original_name, (one) => ({ ...parkedSpec(one), ...extra }));
  groups.needs_you.push(...parkedIn(parked.filter((one) => (one.bucket || plain) === plain), {}));
  const receivedOf = new Map(index.map((one) => [one.handle, one.received]));
  groups.needs_you.push(...pagesEach(state.moved || [], (one) => one.original_name, (one) => ({
    name: one.original_name, detail: nameOf(one.identifier || one.in_request), status: words.moved, tone: "needs",
    date: pagesDay(receivedOf.get(one.handle)), menu: "moved",
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
      const tone = { needs_you: "needs", waiting: "waiting", received: "done", set_aside: "plain" }[item.group];
      const spec = {
        name: pagesItemName(item), detail, status: pagesItemStatus(item), tone,
        date: item.group === "waiting" ? "" : pagesDay(item.received_date),
        menu: item.group === "received" ? "received" : "request",
        step: item.group === "needs_you" ? { kind: "edit", identifier: item.identifier }
          : item.group === "waiting" ? { kind: "draft", ret: state.paths.engagement } : null,
        identifier: item.identifier,
      };
      groups[item.group].push(spec);
    });
  }
  const dismissed = index.filter((one) => one.decision === decisions.dismissed).sort(oldestFirst);
  groups.set_aside.push(...pagesEach(dismissed, (one) => one.original_name, (entry) => ({
    name: entry.original_name, detail: "", status: vocab.review_labels.dismiss, tone: "plain", date: pagesDay(entry.received),
    menu: "file", step: fileStep(entry),
  })));
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
  const index = state.index || [];
  tally.needs_you += index.filter((one) => one.decision === vocab.decisions.needs_review).length + (state.moved || []).length;
  tally.set_aside += index.filter((one) => one.decision === vocab.decisions.dismissed).length;
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
    const pause = hh.pause || {};
    if (pause.sentence) {
      wanted.push({ key: "renamed", failure: { sentence: pause.sentence, kind: "warning" },
                    opts: pause.scope ? { action: { label: words.accept_folder_name, run: acceptFolderName, write: true } } : {} });
    }
    (hh.feeds || []).map((one) => one.warning).filter(Boolean).forEach((sentence, i) => {
      wanted.push({ key: `feed-${i}`, failure: { sentence, kind: "warning" } });
    });
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

function pagesRemember(page) {
  const here = document.activeElement;
  const list = here && here.closest ? here.closest('[role="listbox"]') : null;
  if (!list || !page.contains(list)) {
    pagesFocus = null;
    return;
  }
  const row = list.querySelector(".is-active");
  pagesFocus = { at: [...page.querySelectorAll('[role="listbox"]')].indexOf(list), row: row ? [...list.querySelectorAll('[role="option"]')].indexOf(row) : 0 };
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

// Every Check step on the page in the order drawn: the sheet's next arrow.
function pagesFiles() {
  return [...pagesTokens.entries()]
    .filter(([, spec]) => spec.step && spec.step.kind === "check")
    .sort((a, b) => Number(a[0].slice(4)) - Number(b[0].slice(4)))
    .map(([, spec]) => spec.step);
}
