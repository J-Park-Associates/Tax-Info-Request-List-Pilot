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
// engine. A return's link reads its taxpayer (P194, P195): its name from the
// list less the recorded form it begins with; the year and the form are each
// their own column (Overview, Reminders), heading part or page title.
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

// The column headers of the four firm lists (pilot SPEC-lists; P135-P139):
// each list's columns by the vocabulary's word (vocab.screen.columns); a
// cell with no word has an empty header that orders nothing. A list's cells
// are its keys, left to right. The two lists of returns say each field once,
// in its own column (P194, P195): Tax Year, Taxpayer, Form Type, then the
// list's own status and date.
const PAGES_COLUMNS = {
  overview: { year: "tax_year", taxpayer: "taxpayer", form: "form_type", status: "status", end: "date" },
  needs_review: { name: "file", detail: "suggestion", status: "reason", end: "received" },
  reminders: { year: "tax_year", taxpayer: "taxpayer", form: "form_type", status: "stage", end: "drafted" },
  clients: { name: "client_name", detail: "returns", status: "status", end: "" },
};
// Every cell any list has: a list's widths set its own and clear the rest.
const PAGES_CELLS = ["year", "taxpayer", "form", "name", "detail", "status", "end"];
// Each column's least and most width in px (SPEC-lists 4). The usual widths
// are the stylesheet's tokens. Every column of a firm list is exactly its
// width (P199): none takes the window's slack, so widening a column moves
// its right edge, and the columns after it, to the right.
const PAGES_WIDTHS = { year: [64, 160], taxpayer: [160, 640], form: [64, 160], name: [160, 640], detail: [80, 400], status: [96, 320], end: [112, 240] };
// A list whose usual widths differ from the stylesheet's (SPEC-lists 4):
// Needs Review's reasons are the longest status words ("Looks Like Wrong
// Document"), and its suggestions are short request names, so 40px move
// from Suggestion to Reason. The sum is unchanged, so 1100px still fits.
const PAGES_USUAL = { needs_review: { detail: 160, status: 200 } };
const PAGES_WIDTH_STEP = 16;               // one Ctrl+Shift+Arrow: four grid steps
const PAGES_WIDTHS_KEY = "tracker.columns"; // this PC's own storage, never the record
const PAGES_ORDER_KEY = "tracker.order";    // the order each list was left in, kept the same way (P199)
// Urgency, the order the app already uses (SPEC-lists 3): a return that cannot
// be read or a paused household first, then what needs a person, what waits
// on the taxpayer, what is complete.
const PAGES_URGENCY = { problem: 0, needs: 1, waiting: 2, done: 3, plain: 4 };
let pagesOrder = null;         // list -> {cell, dir}: read once from this PC's storage (P199)
let pagesWidths = null;        // list -> {cell: px}: read once from this PC's storage (P139)
// Rows per page of a firm list (pilot SPEC-lists 14, P152, P174; owner question Q11).
const PAGES_PER_PAGE = 50;
// A reason's small icon on Needs Review (SPEC-lists 12, P149): every reason
// pill is the Need You amber, told apart by this icon and its words. A code
// not listed takes the plain alert.
const PAGES_REASON_ICONS = {
  unmatched: "question", ambiguous: "question", contested: "question", "between-returns": "question",
  "several-forms-unsorted": "question", "name-points-at": "question", "shows-form-number": "question",
  "name-absent": "person", "name-other": "person", "named-across": "person", "unnamed-across": "person",
  "no-room": "person", "no-people": "person", "issuer-not-named": "person",
  "no-request-accepts": "file", extension: "file", "not-a-document": "file", "too-small": "file", "too-large": "file",
  "no-pages": "file", "unreadable-pdf": "file", password: "file", "google-stub": "file", "ocr-only": "file",
  "opened-not-across": "box", "container-damaged": "box", "container-empty": "box", "container-limit": "box",
  "container-locked": "box", "file-moved": "hand", unfiled: "hand", "put-back-refused": "hand", "could-not-file": "hand",
};
// A return page's three sections in their status colour (SPEC-lists 6, P176).
const PAGES_SECTIONS = { needs_you: ["needs", "alert"], waiting: ["waiting", "clock"], received: ["done", "done"] };
let pagesPageAt = {};          // list -> the page shown (0 first); forgotten when the page is left (P174)
let pagesTab = "all";          // Overview's filter tab: all, need or waiting (P145)
let pagesReasonPick = "";      // Needs Review's reason card, a reason's code or "" for All (P149)
let pagesClientType = "";      // Households' Taxpayer Type, a key of vocab.screen.client_types or "" (P153)
let pagesPanel = null;         // the open Linked Households panel: {node, back} (P171)

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

// The taxpayer a return is for, as its name says it (P194, P195): the
// return's name without the "{form} - " the naming pattern puts first, and
// only when the record's form is what the name begins with. A return with no
// recorded form, or a name somebody typed another way, is shown whole: the
// form is read from the record, never from a name (P172), and a name is
// never cut by a guess. Letter case and a hyphen inside the form number are
// not differences (the catalog's own labels write a form number with a hyphen). The year is
// its own column, heading or title.
function pagesTaxpayer(name, form) {
  const pattern = vocab.layout ? vocab.layout.return_name_pattern : "";
  if (!pattern) throw new Error("layout.return_name_pattern");
  const at = pattern.indexOf("{client}");
  if (!form || pattern.indexOf("{form}") !== 0 || at === -1 || at + "{client}".length !== pattern.length) return name;
  const sep = pattern.slice("{form}".length, at);     // " - "
  const cut = sep ? name.indexOf(sep) : -1;
  const same = (text) => text.replace(/-/g, "").toLowerCase();
  const rest = cut > 0 && same(name.slice(0, cut)) === same(form) ? name.slice(cut + sep.length).trim() : "";
  return rest || name;
}

// A form's order key (P195): the order the app already lists forms in, the
// side panel's Client Types (vocab.client_type_forms), then any other form
// by its name; a blank form is blank, so it goes last both ways.
function pagesFormKey(form) {
  if (!form) return "";
  if (!vocab.client_type_forms) throw new Error("client_type_forms");
  const known = Object.values(vocab.client_type_forms).flat();
  const at = known.indexOf(form);
  return [at === -1 ? known.length : at, form];
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
// `link.tip`: a link's own tooltip, where it says more than its kind's
// words (a taxpayer's return also names its household, P195).
function pagesLinkNode(link, text, cell) {
  const node = h("span", { className: "row-link", dataset: { link: link.kind, cell } }, text);
  setTip(node, link.tip || pagesLinkWords(link.kind));
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
  // The form tag (P145) comes first where the row has no Form Type column
  // of its own (the household and year pages); the name no longer begins
  // with the form (P195), so a screen reader reads the tag too.
  const tag = spec.form && !spec.returnRow ? h("span", { className: "form-tag" }, spec.form) : null;
  const first = tag || (spec.fileIcon ? h("span", { className: "row-icon" }, icon("file", true)) : null);
  const box = h("span", { className: "row-name" }, first, spec.nameLink ? pagesLinkNode(spec.nameLink, spec.name, "name") : spec.name);
  if (!spec.nameLink) setTipIfCut(box, spec.name);
  if (spec.mark) box.append(h("span", { className: "row-mark is-attention" }, spec.mark));
  if (spec.linksIn === "name") pagesLinkMarkIn(box, spec.links, true, spec.linkOwner || spec.name);
  return box;
}

// A return row's Form Type cell: the form tag, or nothing when the record has no form.
function pagesFormCell(spec) {
  return h("span", { className: "row-form" }, spec.form ? h("span", { className: "form-tag" }, spec.form) : null);
}

// A return's heading on Needs Review (P195): the year, the taxpayer (the
// link to the return) and the form tag, each once, in the columns' order.
function pagesReturnHeading(path, year, form) {
  return [year ? h("span", { className: "head-year" }, String(year)) : null,
    pagesHeadLink({ kind: "return", path }, pagesTaxpayer(pagesReturnName(path), form)),
    form ? h("span", { className: "form-tag" }, form) : null];
}

// ── linked households (pilot SPEC-lists 10; P141, P171) ────────────────
// The icon beside a household's name when it has links, in --st-linked.
// Inside a row list it is not a Tab stop (the list is one, SPEC-shell
// 3.6): the list's own click and Space on the active row open its panel.
// Outside a list it is an ordinary button.
// `owner`: the household whose links these are, so a redraw can find the
// same mark again and keep its panel open (the review's S2).
function pagesLinkMark(links, inList, owner) {
  const words = screenWords().linked;
  if (!words || !words.tip) throw new Error("linked.tip");
  const mark = h("button", { type: "button", className: "link-mark", "aria-label": words.tip, "aria-haspopup": "dialog",
                             tabindex: inList ? "-1" : undefined, dataset: { owner: owner || "" } }, icon("link", true));
  mark.linked = links;
  setTip(mark, words.tip);
  if (!inList) {
    mark.addEventListener("click", (e) => {
      e.stopPropagation();
      pagesShowPanel(mark, links, mark);
    });
  }
  return mark;
}

function pagesLinkMarkIn(box, links, inList, owner) {
  if (links && links.length) box.append(pagesLinkMark(links, inList, owner));
}

// The small panel naming each linked household and its kind, each name a
// link to that client. Escape (shellKey), a click outside (shell.js) or
// leaving it closes it, and focus goes back where it was opened from.
function pagesShowPanel(anchor, links, back) {
  pagesClosePanel(false);
  const words = screenWords();
  const lines = links.map((one) => {
    const kind = words.linked[one.kind];
    if (!kind) throw new Error(`linked.${one.kind}`);
    const name = one.path ? h("button", { type: "button", className: "link-to" }, one.name) : h("span", { className: "link-name" }, one.name);
    if (one.path) {
      setTip(name, pagesLinkWords("household"));
      name.addEventListener("click", () => {
        pagesClosePanel(false);
        shellGo({ level: "household", household: one.path });
      });
    }
    return h("li", { className: "link-line" }, name, h("span", { className: "link-kind" }, kind));
  });
  const node = h("div", { id: "link-panel", role: "dialog", "aria-label": words.linked.tip, tabindex: "-1" }, h("ul", { className: "link-list" }, ...lines));
  document.body.append(node);
  pagesPanel = { node, back, owner: anchor.dataset ? anchor.dataset.owner || "" : "" };
  node.addEventListener("focusout", (e) => {
    if (pagesPanel && pagesPanel.node === node && !node.contains(e.relatedTarget)) pagesClosePanel(false);
  });
  FloatingUIDOM.computePosition(anchor, node, {
    strategy: "fixed", placement: "bottom-start",
    middleware: [FloatingUIDOM.offset(TIP_GAP), FloatingUIDOM.flip({ padding: TIP_MARGIN }), FloatingUIDOM.shift({ padding: TIP_MARGIN })],
  }).then(({ x, y }) => {
    node.style.setProperty("left", `${Math.round(x)}px`);
    node.style.setProperty("top", `${Math.round(y)}px`);
  });
  const first = node.querySelector(".link-to");
  (first || node).focus();
}

function pagesPanelOpen() {
  return pagesPanel !== null;
}

// `back`: focus returns to where the panel was opened from (the icon, or
// the row list whose active row opened it).
function pagesClosePanel(back) {
  if (!pagesPanel) return;
  const was = pagesPanel;
  pagesPanel = null;
  was.node.remove();
  if (back && was.back && was.back.isConnected) was.back.focus();
}

// A row's panel: its links, under its icon, focus back to its list.
function pagesOpenRowLinks(list, row) {
  const spec = pagesTokens.get(row.id);
  const mark = row.querySelector(".link-mark");
  if (!spec || !spec.links || !spec.links.length || !mark) return false;
  pagesShowPanel(mark, spec.links, list);
  return true;
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
  // A file's own name is an item, not a heading: ordinary weight (P136).
  const file = Boolean(spec.fileKind || (spec.nameLink && spec.nameLink.kind === "file"));
  // A row with linked households says so to a screen reader: its icon is
  // not a Tab stop inside the list (P171).
  const linked = spec.links && spec.links.length ? screenWords().linked.tip : "";
  // A status that is a tag for longer words (P116) carries them for the
  // keyboard and a screen reader, since focus rests on the list (lane 2);
  // a return row names its household there too, as its tooltip does (P195).
  const described = [words, pagesReasonTip(spec), spec.household, linked].filter(Boolean).join(", ");
  // A row of a list of returns (Overview, Reminders) is five cells, one field
  // each: Tax Year, Taxpayer, Form Type, then status and date (P194, P195).
  const lead = spec.returnRow
    ? [h("span", { className: "row-year" }, spec.year ? String(spec.year) : ""), pagesNameCell(spec), pagesFormCell(spec)]
    : [pagesNameCell(spec), pagesDetailCell(spec)];
  const node = h("div", {
    className: `row${spec.returnRow ? " row-return" : ""}${step ? " has-step" : ""}${spec.child ? " row-child" : ""}${wraps ? " row-wrap" : ""}${file ? " row-file" : ""}`,
    role: "option", id, "aria-selected": "false",
    "aria-description": described || undefined, dataset: { menu: spec.menu || "", token: id },
  },
  ...lead,
  pagesStatusCell(spec),
  h("span", { className: "row-end" }, h("span", { className: "row-date" }, spec.date || ""), step));
  return node;
}

// The detail cell: a link, plain words, or (Needs Review's suggestion) a
// muted tag with its full title as the tooltip. (The link mark sits in the
// name cell: no list shows a household in its detail column since P195.)
function pagesDetailCell(spec) {
  if (spec.detailTag && spec.detail) {
    const tag = h("span", { className: "request-tag" }, spec.detail);
    setTip(tag, spec.detailTip || spec.detail);
    return h("span", { className: "row-detail" }, tag);
  }
  return pagesCell("row-detail", "detail", spec.detail || "", spec.detailLink);
}

// The longer words a status is a tag for (P116: `spec.reason` is its code,
// `vocab.reason_tips` the words), or "". A reason code with no tips table is
// a loud failure, never a silent missing tooltip.
function pagesReasonTip(spec) {
  const tips = spec.reason ? vocab.reason_tips : null;
  if (spec.reason && !tips) throw new Error("reason_tips");
  return tips ? tips[spec.reason] || "" : "";
}

// The status cell: the status word, or on a firm list a pill - a dot (or a
// reason's icon) and the words - in the status's colour on its tint (P145,
// P149). The tooltip is the full words, shown when they are cut.
function pagesStatusCell(spec) {
  // A status still on its way: an outline bar, never a pill and never a blank (P222).
  if (spec.waiting) return h("span", { className: "row-status is-waiting-counts", "aria-hidden": "true" }, h("i", { className: "outline-bar" }));
  const tone = PAGES_TONES[spec.tone] || "";
  // A status that is a tag for longer words (P116) shows them as its tooltip
  // every time; any other status shows its own words only when they are cut.
  const tip = pagesReasonTip(spec);
  if (!spec.pill || !spec.status) {
    const box = h("span", { className: `row-status ${tone}` }, spec.status || "");
    if (tip) setTip(box, tip);
    else setTipIfCut(box, spec.status);
    return box;
  }
  const word = h("span", { className: "pill-word" }, spec.status);
  if (tip) setTip(word, tip);
  else setTipIfCut(word, spec.status);
  const lead = spec.reasonIcon ? icon(spec.reasonIcon, true) : h("span", { className: "pill-dot", "aria-hidden": "true" });
  return h("span", { className: `row-status ${tone}` }, h("span", { className: "pill" }, lead, word));
}

function pagesStepWords(step) {
  const steps = screenWords().steps;
  return { open: steps.open, check: steps.check, draft: steps.draft, edit: steps.edit }[step.kind];
}

// `byKey`: the keyboard made the row active, so its status's tooltip - the
// full words - shows at once, as a hover would (P178); any other way hides it.
function pagesActivate(list, row, byKey) {
  for (const one of list.querySelectorAll(".is-active")) {
    one.classList.remove("is-active");
    one.setAttribute("aria-selected", "false");
  }
  row.classList.add("is-active");
  row.setAttribute("aria-selected", "true");
  list.setAttribute("aria-activedescendant", row.id);
  if (row.scrollIntoView) row.scrollIntoView({ block: "nearest" });
  if (typeof showTipNow !== "function") return;
  hideTip();
  const status = byKey ? row.querySelector(".row-status [data-tip], .row-status[data-tip]") : null;
  if (status) showTipNow(status);
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
function pagesList(name, kids, edge) {
  // `edge`: a return section's tone, drawn as a faint edge down its rows (P176).
  const attrs = { className: edge ? `rows edge-${edge}` : "rows", role: "listbox", tabindex: "0" };
  if (name.labelledby) attrs["aria-labelledby"] = name.labelledby;
  else attrs["aria-label"] = name.label;
  const list = h("div", attrs, ...kids);
  list.addEventListener("focus", () => {
    const first = list.querySelector('[role="option"]');
    const byKey = typeof list.matches === "function" && list.matches(":focus-visible");
    if (first && !list.querySelector(".is-active")) pagesActivate(list, first, byKey);
  });
  list.addEventListener("click", (e) => {
    const row = e.target.closest(".row");
    if (!row) return;
    pagesActivate(list, row);
    list.focus({ preventScroll: true });
    const link = e.target.closest(".row-link");
    if (e.target.closest(".link-mark")) pagesOpenRowLinks(list, row);
    else if (link) pagesRunRowLink(row, link);
    else if (e.target.closest(".row-step")) pagesRunRow(row);
  });
  list.addEventListener("dblclick", (e) => {
    const row = e.target.closest(".row");
    if (row && !e.target.closest(".row-link") && !e.target.closest(".link-mark")) pagesRunRow(row);
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
  // A return section's tone (P176): its icon before the heading, a bar at
  // its edge and a tinted count badge, in the section's status colour.
  const section = spec.key ? PAGES_SECTIONS[spec.key] : null;
  const tone = section ? PAGES_TONES[section[0]] : "";
  const meta = h("span", { className: `group-count${section ? ` is-badge ${tone}` : ""}` }, spec.caption !== undefined ? spec.caption : String(total));
  // `heading`: words, or the nodes of a return's heading (pagesReturnHeading).
  const title = h("h2", { className: "group-title", id: headId }, spec.heading);
  const start = spec.step ? pagesGroupStep(spec.step) : null;
  const lead = section ? h("span", { className: `group-icon ${tone}` }, icon(section[1])) : spec.lead || null;
  const headClass = `group-head${spec.first ? " is-first" : ""}${section ? ` is-section section-${section[0]}` : ""}`;
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
    body = pagesList({ labelledby: headId }, kids, section ? section[0] : "");
  } else if (spec.none) {
    body = h("div", { className: "group-none" }, spec.none);
  }
  if (spec.fold) {
    const fold = h("details", { className: "group-fold" }, h("summary", { className: headClass }, lead, title, meta), body);
    fold.open = Boolean(spec.open);
    if (spec.onToggle) fold.addEventListener("toggle", () => spec.onToggle(fold.open));
    return [fold];
  }
  // `heads`: a list's column headers, between its heading and its rows;
  // `tools`: what sits at the heading's end (Overview's tabs, a Needs
  // Review group's count and More Actions).
  return [h("div", { className: headClass }, lead, title, meta, spec.tools || null, start), body ? spec.heads : null, body].filter(Boolean);
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

// ── column headers: order and width (pilot SPEC-lists; P135-P139) ─────
// A header's tooltip is "Sort by {Column}" (Jason, P180); the column word
// itself and the header's name never say Sort, which also names the filing pass.
// A header orders its list by its column: the first click in the column's
// natural direction, the second the reverse, the third back to the list's
// usual order. The order is a view of the rows the engine already sent, so
// it is worked out here and nowhere else; a list keeps it while the app is
// open. A width is this PC's: kept in its own storage across restarts,
// forgotten by View › Reset Column Widths.

// The firm list a route draws, or "" for a page with no column headers.
function pagesListOf(route) {
  return { overview: "overview", "needs-review": "needs_review", reminders: "reminders", clients: "clients" }[route.level] || "";
}

// A status's order key: its urgency, then the larger count first, then its words.
function pagesUrgent(rank, count, text) {
  return text ? [rank, -(count || 0), text] : "";
}

function pagesIsBlank(value) {
  return value === "" || value === null || value === undefined;
}

function pagesCompareKeys(x, y) {
  if (Array.isArray(x)) {
    for (let i = 0; i < x.length; i += 1) {
      const by = pagesCompareKeys(x[i], y[i]);
      if (by) return by;
    }
    return 0;
  }
  if (typeof x === "number" && typeof y === "number") return x - y;
  return pagesByName(String(x), String(y));
}

// Compares two {spec, at} entries by one column: blanks always last, in
// either direction; a tie keeps the usual order (`at`).
function pagesCompare(cell, dir) {
  return (a, b) => {
    const x = a.spec.keys ? a.spec.keys[cell] : "";
    const y = b.spec.keys ? b.spec.keys[cell] : "";
    if (pagesIsBlank(x) || pagesIsBlank(y)) {
      if (pagesIsBlank(x) && pagesIsBlank(y)) return a.at - b.at;
      return pagesIsBlank(x) ? 1 : -1;
    }
    return dir * pagesCompareKeys(x, y) || a.at - b.at;
  };
}

// A list's specs in the order its header asks for, or as they came.
function pagesOrdered(list, specs) {
  const order = pagesStoredOrder()[list];
  if (!order) return specs;
  const by = pagesCompare(order.cell, order.dir);
  return specs.map((spec, at) => ({ spec, at })).sort(by).map((entry) => entry.spec);
}

// A header was pressed: the next order in its cycle, the list drawn again,
// and focus back on the same header so it can be pressed again.
function pagesOrderBy(list, cell) {
  const held = pagesStoredOrder();
  const now = held[list];
  if (!now || now.cell !== cell) held[list] = { cell, dir: 1 };
  else if (now.dir > 0) held[list] = { cell, dir: -1 };
  else delete held[list];
  pagesSaveOrder();
  delete pagesPageAt[list];      // any change of order returns to page 1 (P174)
  const page = $("page");
  pagesDraw(shellRoute, page);
  const again = page.querySelector(`.col-head[data-cell="${cell}"]`);
  if (again) again.focus();
}

// The header row of a list: one `role="columnheader"` cell per column in the
// rows' own grid, each a button (a Tab stop; Enter and Space press it) with
// the vocabulary's word, the drawn arrow of its order and a grip on its
// right edge. `aria-sort` says which column orders the list and which way.
function pagesColumnHeads(list) {
  const words = screenWords();
  const said = words.columns;
  const order = pagesStoredOrder()[list];
  const cells = Object.keys(PAGES_COLUMNS[list]).map((cell) => {
    const key = PAGES_COLUMNS[list][cell];
    if (!key) return h("div", { className: "col-cell", role: "columnheader", dataset: { cell } }, pagesGrip(list, cell));
    const word = said[key];
    if (!word) throw new Error(`columns.${key}`);
    const sort = order && order.cell === cell ? (order.dir > 0 ? "ascending" : "descending") : "none";
    const arrow = icon("chev", true);
    arrow.classList.add("col-arrow");
    const button = h("button", { type: "button", className: "col-head", dataset: { cell, list } }, h("span", { className: "col-word" }, word), arrow);
    setTip(button, fill(said.sort_by, { column: word }));
    button.addEventListener("click", () => pagesOrderBy(list, cell));
    return h("div", { className: "col-cell", role: "columnheader", "aria-sort": sort, dataset: { cell } }, button, pagesGrip(list, cell));
  });
  return h("div", { className: "col-table", role: "table", "aria-label": words.sections[list], dataset: { list } },
    h("div", { className: "col-heads", role: "row" }, ...cells));
}

// The grip on a header's right edge: drag to set the width, double-click to
// fit the widest entry. The keyboard's way is Ctrl+Shift+Arrow on the header.
function pagesGrip(list, cell) {
  const grip = h("span", { className: "col-grip", "aria-hidden": "true", dataset: { cell } });
  grip.addEventListener("pointerdown", (e) => pagesGripStart(list, cell, grip, e));
  grip.addEventListener("dblclick", () => pagesFit(list, cell));
  return grip;
}

function pagesGripStart(list, cell, grip, e) {
  if (e.button !== 0) return;
  e.preventDefault();
  const from = grip.parentNode.getBoundingClientRect().width;
  const start = e.clientX;
  grip.setPointerCapture(e.pointerId);
  grip.classList.add("is-dragging");
  const move = (m) => pagesSetWidth(list, cell, from + m.clientX - start);
  const done = () => {
    grip.removeEventListener("pointermove", move);
    grip.removeEventListener("pointerup", done);
    grip.removeEventListener("pointercancel", done);
    grip.classList.remove("is-dragging");
    pagesSaveWidths();
  };
  grip.addEventListener("pointermove", move);
  grip.addEventListener("pointerup", done);
  grip.addEventListener("pointercancel", done);
}

// Fit a column to its widest entry on the page and its header's own word:
// every cell is measured on one line (`is-measuring`), then let go.
function pagesFit(list, cell) {
  const page = $("page");
  const parts = { year: ".row-year", taxpayer: ".row-name", form: ".row-form", name: ".row-name", detail: ".row-detail", status: ".row-status", end: ".row-end" }[cell];
  page.classList.add("is-measuring");
  let widest = 0;
  for (const one of page.querySelectorAll(`${parts}, .col-cell[data-cell="${cell}"] .col-head`)) widest = Math.max(widest, one.scrollWidth);
  page.classList.remove("is-measuring");
  pagesSetWidth(list, cell, widest);
  pagesSaveWidths();
}

// Ctrl+Shift+Right widens and Ctrl+Shift+Left narrows the focused header's
// column by one step, and the width it lands on is said to a screen reader
// (shell.js hands a key on a header here; true = handled). Not Alt+Arrow:
// Alt+Left is Back in Windows, and Alt shows the hidden menu bar (P137).
function pagesColumnKey(e) {
  const head = e.target.closest(".col-head");
  if (!head || !e.ctrlKey || !e.shiftKey || e.altKey || (e.key !== "ArrowLeft" && e.key !== "ArrowRight")) return false;
  e.preventDefault();
  const box = head.parentNode;
  pagesSetWidth(head.dataset.list, head.dataset.cell, box.getBoundingClientRect().width + (e.key === "ArrowRight" ? PAGES_WIDTH_STEP : -PAGES_WIDTH_STEP));
  pagesSaveWidths();
  $("page-say").textContent = fill(screenWords().columns.width, {
    column: head.querySelector(".col-word").textContent, n: Math.round(box.getBoundingClientRect().width),
  });
  return true;
}

// The order each list was left in on this PC, read once (P199, replacing
// P139's "while the app is open"): kept per list as its widths are. Only an
// order a header can give survives the read - a list this app draws, one of
// its columns with a word, a direction of 1 or -1 - so a damaged or old
// value leaves that list (or every list) in its usual order and says
// nothing, as an unreadable width does.
function pagesStoredOrder() {
  if (pagesOrder) return pagesOrder;
  pagesOrder = {};
  try {
    const held = JSON.parse(window.localStorage.getItem(PAGES_ORDER_KEY) || "{}");
    if (held && typeof held === "object" && !Array.isArray(held)) {
      for (const [list, one] of Object.entries(held)) {
        const columns = PAGES_COLUMNS[list];
        if (columns && one && typeof one === "object" && Object.prototype.hasOwnProperty.call(columns, one.cell)
            && columns[one.cell] && (one.dir === 1 || one.dir === -1)) pagesOrder[list] = { cell: one.cell, dir: one.dir };
      }
    }
  } catch (err) {
    // Unreadable or not JSON: every list in its usual order, which pagesOrder now holds.
  }
  return pagesOrder;
}

// Kept on this PC; a profile that refuses the write keeps the order while
// the app is open.
function pagesSaveOrder() {
  try {
    window.localStorage.setItem(PAGES_ORDER_KEY, JSON.stringify(pagesStoredOrder()));
  } catch (err) {
    // Not kept past a restart; the order holds while the app is open.
  }
}

// The widths this PC holds, read once. Storage that cannot be read (a locked
// profile) leaves the usual widths: a width is a comfort of this screen, not
// a fact about a return, and the page works the same without it.
function pagesStoredWidths() {
  if (pagesWidths) return pagesWidths;
  pagesWidths = {};
  try {
    const held = JSON.parse(window.localStorage.getItem(PAGES_WIDTHS_KEY) || "{}");
    if (held && typeof held === "object" && !Array.isArray(held)) pagesWidths = held;
  } catch (err) {
    // Unreadable or not JSON: the usual widths, which pagesWidths now holds.
  }
  return pagesWidths;
}

// One column's width in a list: the held one, within its limits; else the
// list's own usual width (PAGES_USUAL); else null, the stylesheet's. A cell
// the list does not have is null: a width kept for a column a list no longer
// draws (Overview's old Return column, P195) never reaches its new layout.
function pagesWidthOf(list, cell) {
  if (!(cell in PAGES_COLUMNS[list])) return null;
  const held = (pagesStoredWidths()[list] || {})[cell];
  if (typeof held !== "number" || !Number.isFinite(held)) return (PAGES_USUAL[list] || {})[cell] || null;
  const [least, most] = PAGES_WIDTHS[cell];
  return Math.round(Math.min(most, Math.max(least, held)));
}

function pagesSetWidth(list, cell, px) {
  const [least, most] = PAGES_WIDTHS[cell];
  const held = pagesStoredWidths();
  // Only the list's own columns are kept: the next save drops a width of a column it no longer has.
  const own = Object.entries(held[list] || {}).filter(([one]) => one in PAGES_COLUMNS[list]);
  held[list] = { ...Object.fromEntries(own), [cell]: Math.round(Math.min(most, Math.max(least, px))) };
  pagesApplyWidths($("page"), list);
}

// Kept on this PC; a profile that refuses the write keeps the width while
// the app is open, as the read above does.
function pagesSaveWidths() {
  try {
    window.localStorage.setItem(PAGES_WIDTHS_KEY, JSON.stringify(pagesStoredWidths()));
  } catch (err) {
    // Not kept past a restart; the width holds while the app is open.
  }
}

// The list's widths on the page (the tokens the rows' grid reads), or the
// usual ones on a page with no list.
function pagesApplyWidths(page, list) {
  for (const cell of PAGES_CELLS) {
    const px = list ? pagesWidthOf(list, cell) : null;
    if (px === null) page.style.removeProperty(`--size-col-${cell}`);
    else page.style.setProperty(`--size-col-${cell}`, `${px}px`);
  }
}

// View › Reset Column Widths: every list back to the usual widths.
function pagesResetWidths() {
  pagesWidths = {};
  try {
    window.localStorage.removeItem(PAGES_WIDTHS_KEY);
  } catch (err) {
    // Nothing held to forget: the usual widths are what the page now shows.
  }
  pagesApplyWidths($("page"), pagesListOf(shellRoute));
}

// ── page buttons (pilot SPEC-lists 14; P152, P174) ────────────────────
// A list's items divided into pages after its order, tabs and filters: the
// part shown and its footer. `sizeOf` counts an item (Needs Review counts a
// return group by its files, and never splits one); a page holds items
// while their count stays within PAGES_PER_PAGE, and an item larger than a
// page is a page of its own.
function pagesPaged(list, items, sizeOf) {
  const size = sizeOf || (() => 1);
  const pages = [];
  let part = [];
  let held = 0;
  for (const one of items) {
    const n = size(one);
    if (part.length && held + n > PAGES_PER_PAGE) {
      pages.push(part);
      part = [];
      held = 0;
    }
    part.push(one);
    held += n;
  }
  if (part.length) pages.push(part);
  const at = Math.min(pagesPageAt[list] || 0, Math.max(0, pages.length - 1));
  pagesPageAt[list] = at;
  const count = (group) => group.reduce((n, one) => n + size(one), 0);
  const before = pages.slice(0, at).reduce((n, group) => n + count(group), 0);
  const shown = pages[at] || [];
  const total = count(items);
  return { part: shown, foot: total ? pagesFoot(list, before + 1, before + count(shown), total, at, pages.length) : null };
}

// "Showing 1-50 of 750 Returns", with Previous and Next (disabled at the ends).
function pagesFoot(list, from, to, total, at, count) {
  const words = screenWords().paging;
  const noun = words.nouns[list];
  if (!noun) throw new Error(`paging.nouns.${list}`);
  const step = (by, key) => {
    const button = h("button", { type: "button", className: "btn btn-small page-step", disabled: by < 0 ? at === 0 : at >= count - 1, dataset: { step: key } }, words[key]);
    button.addEventListener("click", () => pagesTurn(list, by, key));
    return button;
  };
  return h("div", { className: "page-foot" }, h("span", { className: "page-count" }, fill(words.showing, { from, to, total, noun })),
    h("span", { className: "page-steps" }, step(-1, "previous"), step(1, "next")));
}

// Previous or Next: the page drawn again at its top, focus kept on the
// button pressed, or on the other one once this one is disabled.
function pagesTurn(list, by, key) {
  pagesPageAt[list] = Math.max(0, (pagesPageAt[list] || 0) + by);
  const page = $("page");
  pagesDraw(shellRoute, page);
  page.scrollTop = 0;
  const same = page.querySelector(`.page-step[data-step="${key}"]`);
  const other = page.querySelector(`.page-step[data-step="${key === "next" ? "previous" : "next"}"]`);
  const to = same && !same.disabled ? same : other;
  if (to) to.focus();
}

// A choice that narrows a list (a tab, a reason card, a Client Type): the
// list starts again at its first page, is drawn again, and focus goes back
// to the control that was pressed (found by its data-pick).
function pagesPick(list, set, pick) {
  set();
  delete pagesPageAt[list];
  const page = $("page");
  pagesDraw(shellRoute, page);
  const again = page.querySelector(`[data-pick="${pick}"]`);
  if (again) again.focus();
}

// Overview's filter tabs: All, Need You (n), Waiting (n) (P145).
function pagesTabs(need, waiting) {
  const words = screenWords();
  const tab = (key, label) => {
    const node = h("button", { type: "button", className: "switch-option", "aria-pressed": pagesTab === key ? "true" : "false", dataset: { pick: `tab-${key}` } }, label);
    node.addEventListener("click", () => pagesPick("overview", () => { pagesTab = key; }, `tab-${key}`));
    return node;
  };
  return h("div", { className: "switch is-tabs", role: "group", "aria-label": words.work },
    tab("all", words.filters.all), tab("need", fill(words.tabs.need, { n: need })), tab("waiting", fill(words.tabs.waiting, { n: waiting })));
}

// ── a firm return's row (P194, P195) ──────────────────────────────────
// The first three cells of a return's row on Overview and Reminders, one
// field each: its year, its taxpayer - the link to the return, whose tooltip
// and screen-reader description name the household, which has no column of
// its own, and after which the household's link mark sits - and its form.
function pagesReturnCells(one) {
  const said = screenWords().columns;
  if (!said.taxpayer_tip) throw new Error("columns.taxpayer_tip");
  const tip = one.household ? fill(said.taxpayer_tip, { action: pagesLinkWords("return"), household: one.household }) : "";
  return { returnRow: true, year: one.year || "", name: pagesTaxpayer(pagesReturnName(one.path), one.form || ""), form: one.form || "",
           household: one.household || "", links: one.links || [], linksIn: "name", linkOwner: one.household || "",
           nameLink: { kind: "return", path: one.path, tip } };
}

// What those three cells order by: the year's number, the taxpayer as shown,
// the form's place in the app's order of forms.
function pagesReturnKeys(cells) {
  return { year: cells.year, taxpayer: cells.name, form: pagesFormKey(cells.form) };
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
  // `keys`: what each column orders by (SPEC-lists 3) - the year, the shown
  // taxpayer, the form's place, the urgency and the ISO date the row was
  // drawn from, never the drawn "Mar 3".
  const specOf = (one, date, iso) => {
    const said = pagesCounts(one.counts, one.problem);
    const rank = one.problem ? PAGES_URGENCY.problem : PAGES_URGENCY[said.tone];
    const cells = pagesReturnCells(one);
    return { ...cells, status: said.text, tone: said.tone, date, menu: "return", pill: true,
             step: { ...steps, route: pagesRoute(one.path) },
             keys: { ...pagesReturnKeys(cells), status: pagesUrgent(rank, one.counts.needs_you || one.counts.waiting, said.text), end: iso || "" } };
  };
  return [...pagesEach(need, name, (one) => specOf(one, pagesDay(one.oldest), one.oldest)), ...pagesEach(wait, name, (one) => specOf(one, pagesDue(one.due), one.due))];
}

// A household paused for two open years is work waiting for a person: one row
// on the Overview, first, worded by the vocabulary, opening the household
// (ruling 21). Nothing is hidden on its own pages.
function pagesPausedRows(firm) {
  const word = screenWords().notices.paused;
  return pagesEach([...pagesPaused(firm)].sort(pagesByName), (name) => name, (name) => {
    const path = pagesHouseholdPath(name);
    if (!path) throw new Error("household");
    // A household's row in the return columns: no year and no form of its
    // own; its name stands in the Taxpayer column (P195).
    return { returnRow: true, year: "", name, form: "", status: word, tone: "needs", date: "", menu: "household", pill: true, nameLink: { kind: "household", path },
             step: { kind: "open", route: { level: "household", household: path } },
             keys: { year: "", taxpayer: name, form: "", status: pagesUrgent(PAGES_URGENCY.problem, 0, word), end: "" } };
  });
}

function pagesOverview() {
  const words = screenWords();
  const firm = pagesFirm();
  const totals = firm.totals;
  // The three counts, each in a raised card with its status's icon (P145).
  const figures = h("div", { className: "figures" }, ...[[totals.need, words.figures.need, "needs", "alert"], [totals.waiting, words.figures.waiting, "waiting", "clock"],
    [totals.complete, words.figures.complete, "done", "done"]]
    .map(([n, label, tone, name]) => h("div", { className: "figure" },
      h("span", { className: "figure-top" }, h("span", { className: "figure-label" }, label), h("span", { className: `figure-icon ${PAGES_TONES[tone]}` }, icon(name))),
      h("b", { className: "figure-number" }, String(n)))));
  const all = [...pagesPausedRows(firm), ...pagesWorkRows(firm.returns)];
  if (!all.length) return [figures, pagesEmpty(words.empty.overview, pagesNextSort(firm))];
  // The tab narrows the whole list, then the order and the pages apply.
  const need = all.filter((spec) => spec.tone === "needs");
  const waiting = all.filter((spec) => spec.tone === "waiting");
  const shown = pagesTab === "need" ? need : pagesTab === "waiting" ? waiting : all;
  const { part, foot } = pagesPaged("overview", pagesOrdered("overview", shown));
  const rows = pagesEach(part, (spec) => spec.name, pagesRow);
  return [figures, ...pagesGroup({ heading: words.work, caption: String(shown.length), first: true, tools: pagesTabs(need.length, waiting.length),
                                   heads: pagesColumnHeads("overview"), none: words.empty.work, blocks: [{ rows }] }), foot];
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

// One waiting file's row. A file's name is a link to its working copy when the
// firm's reply names one (`open_key` and the reply's `paths`, ruling 15);
// with none it is text.
function pagesReviewSpec(firm, group, file) {
  const reason = pagesReason(file.code);
  return {
    name: file.name, detail: file.suggestion_short || file.suggestion || "", detailTip: file.suggestion || "", detailTag: true,
    status: reason, reason: file.code, tone: "needs", date: pagesDay(file.received), pill: true, reasonIcon: PAGES_REASON_ICONS[file.code] || "alert", fileIcon: true,
    menu: "file", fileKind: "parked", nameLink: pagesFileLink(firm.paths, file.open_key),
    step: { kind: "check", ret: group.path, name: file.name, handle: file.handle },
    keys: { name: file.name, detail: file.suggestion || "", status: pagesUrgent(PAGES_URGENCY.needs, 0, reason), end: file.received || "" },
  };
}

// The returns of Needs Review in the chosen order (SPEC-lists 3): each
// return's files ordered among themselves, and the returns following their
// first file; with no order chosen, today's order.
function pagesOrderedGroups(planned) {
  const order = pagesStoredOrder().needs_review;
  if (!order) return planned;
  const by = pagesCompare(order.cell, order.dir);
  return planned.map((one, at) => ({ one, at }))
    .sort((a, b) => {
      const x = a.one.specs[0];
      const y = b.one.specs[0];
      if (!x || !y) return x === y ? a.at - b.at : (x ? -1 : 1);
      return by({ spec: x, at: a.at }, { spec: y, at: b.at });
    })
    .map((entry) => entry.one);
}

// "13 Files", "1 File": the count beside a title (P149).
function pagesFileCount(n) {
  const words = screenWords().counts;
  return n === 1 ? words.one_file : fill(words.files, { n });
}

// The reason cards across the top of Needs Review (P149): All, then one per
// reason present with its count, each a filter (aria-pressed).
function pagesReasonCards(counts, total) {
  const words = screenWords();
  const card = (code, label, n, name) => {
    const node = h("button", { type: "button", className: "reason-card", "aria-pressed": pagesReasonPick === code ? "true" : "false", dataset: { pick: `reason-${code || "all"}` } },
      h("span", { className: "reason-card-top" }, name ? h("span", { className: "reason-card-icon is-attention" }, icon(name, true)) : null, h("span", { className: "reason-card-word" }, label)),
      h("b", { className: "reason-card-number" }, String(n)));
    node.addEventListener("click", () => pagesPick("needs_review", () => { pagesReasonPick = code; }, `reason-${code || "all"}`));
    return node;
  };
  const reasons = [...counts.entries()].map(([code, n]) => [code, pagesReason(code), n]).sort((a, b) => b[2] - a[2] || pagesByName(a[1], b[1]));
  return h("div", { className: "reason-cards", role: "group", "aria-label": words.sections.needs_review },
    card("", words.filters.all, total, ""), ...reasons.map(([code, label, n]) => card(code, label, n, PAGES_REASON_ICONS[code] || "alert")));
}

// A return group's heading on Needs Review (P149): its folder icon, the
// return's name, the household as the small secondary link with its link
// mark, the count of its documents, and More Actions, which opens the same
// native menu as a right-click on the heading (the return's; no new action).
function pagesReviewGroup(group, specs) {
  const words = screenWords();
  const owner = pagesFirmReturn(group.path);
  const rows = pagesEach(specs, (spec) => spec.name, pagesRow);
  const household = owner ? owner.household : "";
  const house = pagesHouseholdPath(household);
  const caption = household ? [house ? pagesHeadLink({ kind: "household", path: house }, household) : household] : [];
  if (owner && owner.links && owner.links.length) caption.push(pagesLinkMark(owner.links, false, household));
  pagesUid += 1;
  const token = `row-${pagesUid}`;
  const route = pagesRoute(group.path);
  pagesTokens.set(token, { menu: "return", nameLink: { kind: "return", path: group.path }, step: { kind: "open", route } });
  const more = h("button", { type: "button", className: "icon-button group-more", "aria-label": words.icons.more_actions, "aria-haspopup": "menu" }, icon("more"));
  setTip(more, words.icons.more_actions);
  const popup = (x, y) => shellPopup("return", token, x, y, pagesEnableFor(pagesTokens.get(token)));
  more.addEventListener("click", () => {
    const box = more.getBoundingClientRect();
    popup(box.left, box.bottom);
  });
  const count = h("span", { className: "group-docs" }, rows.length === 1 ? words.documents.one : fill(words.documents.many, { n: rows.length }));
  const nodes = pagesGroup({ heading: pagesReturnHeading(group.path, owner ? owner.year : 0, owner ? owner.form : ""),
                             caption, lead: h("span", { className: "group-icon" }, icon("folder")), tools: [count, more], blocks: [{ rows }] });
  nodes[0].addEventListener("contextmenu", (e) => {
    e.preventDefault();
    popup(e.clientX, e.clientY);
  });
  return [h("div", { className: "return-card" }, ...nodes)];
}

function pagesNeedsReview() {
  const words = screenWords();
  const firm = pagesFirm();
  const all = pagesReviewGroups(firm);
  if (!all.length) return [pagesEmpty(words.empty.needs_review, pagesNextSort(firm))];
  // The reason cards count the whole page; a card narrows it, then the
  // order and the pages apply (P149, P174).
  const counts = new Map();
  for (const group of all) for (const file of group.files) counts.set(file.code, (counts.get(file.code) || 0) + 1);
  if (pagesReasonPick && !counts.has(pagesReasonPick)) pagesReasonPick = "";
  const groups = pagesReasonPick
    ? all.map((group) => ({ ...group, files: group.files.filter((file) => file.code === pagesReasonPick) })).filter((group) => group.files.length)
    : all;
  const total = groups.reduce((n, group) => n + group.files.length, 0);
  const planned = pagesOrderedGroups(groups.map((group) => ({
    group, specs: pagesOrdered("needs_review", pagesEach(group.files, (file) => file.name, (file) => pagesReviewSpec(firm, group, file))),
  })));
  const { part, foot } = pagesPaged("needs_review", planned, (one) => one.specs.length);
  const head = h("div", { className: "group-head is-first page-head" }, h("h2", { className: "list-title" }, words.sections.needs_review),
    h("span", { className: "list-count" }, pagesFileCount(total)));
  const allFiles = all.reduce((n, group) => n + group.files.length, 0);
  return [head, pagesReasonCards(counts, allFiles), pagesColumnHeads("needs_review"),
    ...part.flatMap(({ group, specs }) => pagesSafe(pagesReturnName(group.path), () => pagesReviewGroup(group, specs)) || []), foot];
}

// ── Reminders (SPEC 6.3) ──────────────────────────────────────────────
function pagesReminderSpecs(firm) {
  const ready = firm.returns.filter((one) => one.draft && one.draft.ready);
  return pagesEach(ready.sort((a, b) => pagesByName(pagesReturnName(a.path), pagesReturnName(b.path))), (one) => pagesReturnName(one.path), (one) => {
    const held = one.draft.held > 0;
    const status = held ? screenWords().held : pagesStage(one.draft.stage);
    const cells = pagesReturnCells(one);
    return {
      ...cells,
      status, tone: held ? "needs" : "waiting", date: pagesDay(one.draft.drafted), menu: "return", pill: true,
      step: { kind: "draft", ret: one.path },
      // Held first (a person must act), then the later stage first: a later
      // reminder is the more overdue taxpayer (SPEC-lists 3).
      keys: { ...pagesReturnKeys(cells), status: pagesUrgent(held ? PAGES_URGENCY.needs : PAGES_URGENCY.waiting, held ? 0 : one.draft.stage, status),
              end: one.draft.drafted || "" },
    };
  });
}

function pagesReminders() {
  const words = screenWords();
  const specs = pagesOrdered("reminders", pagesReminderSpecs(pagesFirm()));
  if (!specs.length) return [pagesEmpty(words.empty.reminders)];
  const { part, foot } = pagesPaged("reminders", specs);
  return [h("div", { className: "page-gap" }), pagesColumnHeads("reminders"),
    pagesList({ label: words.sections.reminders }, pagesEach(part, (spec) => spec.name, pagesRow)), foot];
}

// ── Clients (SPEC 6.4) ────────────────────────────────────────────────
function pagesClientSpecs(firm, all) {
  const words = screenWords().counts;
  const own = (name) => firm.returns.filter((one) => one.household === name);
  const pausedNames = pagesPaused(firm);
  const kind = pagesClientType ? (vocab.client_type_forms || {})[pagesClientType] : null;
  if (pagesClientType && !kind) throw new Error(`client_type_forms.${pagesClientType}`);
  // A Client Type keeps the households with a return of one of its forms,
  // by the form each return's record holds - never read from a name (P153).
  const ofType = (one) => !kind || (one.returns || []).some((ret) => kind.indexOf(ret.form) !== -1);
  return pagesEach(households.filter(ofType).sort((a, b) => pagesByName(a.name, b.name)), (one) => one.name, (one) => {
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
    const rank = !need && problem ? PAGES_URGENCY.problem : PAGES_URGENCY[said.tone];
    return { work: need + wait > 0 || Boolean(problem) || paused, spec: {
      name: one.name, detail: returns.length ? fill(returns.length === 1 ? words.one_return : words.returns, { n: returns.length }) : "",
      mark: paused ? screenWords().notices.paused : "",
      status: said.text, tone: said.tone, date: "", menu: "household", pill: true, links: one.links || [], linksIn: "name",
      nameLink: { kind: "household", path: one.path },
      step: { kind: "open", route: { level: "household", household: one.path } },
      keys: { name: one.name, detail: returns.length || "", status: pagesUrgent(rank, need || wait, said.text), end: "" },
    } };
  }).filter((one) => all || one.work).map((one) => one.spec);
}

// The Clients switch: Work Waiting (with its count, P153) and All.
function pagesSwitch(work) {
  const words = screenWords().filters;
  const option = (label, all, count) => {
    const node = h("button", { type: "button", className: "switch-option", "aria-pressed": pagesClientsAll === all ? "true" : "false", dataset: { pick: all ? "all" : "work" } },
      label, count === undefined ? null : h("span", { className: "switch-count" }, String(count)));
    node.addEventListener("click", () => pagesPick("clients", () => { pagesClientsAll = all; }, all ? "all" : "work"));
    return node;
  };
  return h("div", { className: "switch", role: "group", "aria-label": screenWords().sections.clients }, option(words.work, false, work), option(words.all, true));
}

// The Client Type filter on Clients, with its dismiss (P153; SPEC-lists 15.3).
function pagesTypeFilter() {
  if (!pagesClientType) return null;
  const words = screenWords();
  const label = (words.client_types || {})[pagesClientType];
  if (!label) throw new Error(`client_types.${pagesClientType}`);
  const dismiss = h("button", { type: "button", className: "icon-button type-dismiss", "aria-label": words.icons.remove_filter, dataset: { pick: "type" } }, icon("dismiss", true));
  setTip(dismiss, words.icons.remove_filter);
  dismiss.addEventListener("click", () => pagesPick("clients", () => { pagesClientType = ""; }, "all"));
  return h("span", { className: "type-filter" }, h("span", { className: "type-filter-word" }, label), dismiss);
}

function pagesClients() {
  const words = screenWords();
  const firm = pagesFirm();
  if (!households.length) {
    const start = h("button", { type: "button", className: "btn" }, vocab.menu.new_household);
    start.addEventListener("click", () => openNewHousehold());
    return [pagesEmpty(words.empty.clients, "", start)];
  }
  // One order for both tabs of the switch (SPEC-lists 3); the type and the
  // tab narrow the whole list, then the order and the pages apply.
  const work = pagesClientSpecs(firm, false).length;
  const specs = pagesOrdered("clients", pagesClientSpecs(firm, pagesClientsAll));
  const bar = h("div", { className: "clients-bar" }, pagesSwitch(work), pagesTypeFilter());
  if (!specs.length) return [bar, pagesEmpty(words.empty.work)];
  const { part, foot } = pagesPaged("clients", specs);
  const rows = document.createDocumentFragment();
  for (const row of pagesEach(part, (spec) => spec.name, pagesRow)) rows.append(row);
  return [bar, pagesColumnHeads("clients"), pagesList({ label: words.sections.clients }, [rows]), foot];
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
  // While the firm's counts are on their way with none held, a row's status
  // is an outline until they arrive (P222); when they could not be had it is
  // empty, and the notice says so.
  const counts = shellFirm();
  const waiting = counts.status === "loading" && !counts.data;
  return pagesEach(returns.slice().sort((a, b) => pagesByName(a.return_name || a.label, b.return_name || b.label)), (one) => one.return_name || one.label, (one) => {
    const firm = pagesFirmReturn(one.path);
    const said = firm ? pagesCounts(firm.counts, firm.problem) : { text: "", tone: "plain" };
    const detail = one.superseded_by ? words.rolled : one.active === false ? words.inactive : "";
    // The form tag and the taxpayer, each once; the year is the heading
    // above the rows or the page's title (P195).
    return { name: pagesTaxpayer(one.return_name || pagesReturnName(one.path), one.form || ""), form: one.form || "", detail, status: said.text, tone: said.tone, date: "", menu: "return",
             waiting: waiting && !firm,
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
      if (one.fold) delete spec.key;        // Set aside keeps its plain fold (P176)
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
  // A firm page's pages, tab and reason card are forgotten when it is left;
  // a Client Type when another firm page is opened (P174, P145, P149, P153).
  if (route.level !== pagesLastLevel) {
    pagesPageAt = {};
    pagesTab = "all";
    pagesReasonPick = "";
    if (["overview", "needs-review", "reminders"].indexOf(route.level) !== -1) pagesClientType = "";
  }
  // An open Linked Households panel outlives a redraw of the same page (the
  // review's S2): it is opened again on the same household's mark, or, when
  // that mark is gone, focus goes to the page's list rather than be lost.
  const panel = pagesPanel && route.level === pagesLastLevel ? { owner: pagesPanel.owner } : null;
  if (typeof pagesClosePanel === "function") pagesClosePanel(false);
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
  page.replaceChildren(...nodes.filter(Boolean));
  page.dataset.list = pagesListOf(route);   // a firm list's rows are shaded in turn (P145)
  pagesApplyWidths(page, pagesListOf(route));
  pagesDrawn = key;
  pagesRestore(page);
  if (panel) pagesReopenPanel(page, panel.owner);
}

// The panel again, on the redrawn mark of the household it was open for;
// with no such mark, focus goes to the page's first list (or the page).
function pagesReopenPanel(page, owner) {
  const mark = [...page.querySelectorAll(".link-mark")].find((one) => one.dataset.owner === owner && one.linked);
  if (mark) {
    pagesShowPanel(mark, mark.linked, mark.closest('[role="listbox"]') || mark);
    return;
  }
  (page.querySelector('[role="listbox"]') || page).focus();
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
    pagesActivate(list, rows[Math.min(Math.max(moves[e.key], 0), rows.length - 1)], true);
    return true;
  }
  // Space: the active row's Linked Households panel, when it has one (P171).
  if (e.key === " " && pagesOpenRowLinks(list, rows[at])) {
    e.preventDefault();
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
