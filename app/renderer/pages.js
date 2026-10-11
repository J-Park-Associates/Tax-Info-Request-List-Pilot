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
//     and, when the row has a step, a chevron at rest, the step's words
//     appearing before it on hover or focus (P270);
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
//   pagesVirtualMeasure(root) / pagesVirtualPlaceAll(root)  a long list's row height,
//                       and the rows in view (P279: only the drawn rows are
//                       in the document; every row stays registered)
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

let pagesUid = 0;              // ids of the rows and headings of the page being drawn
const pagesTokens = new Map(); // a row's id -> what it is about (rebuilt with every draw)
let pagesFocus = null;         // where focus sat in a listbox before a redraw
let pagesLastLevel = "";       // the level drawn last, for the Linked Households panel
let pagesEntered = "";         // the level whose choices (page, tab, card, switch) are held: they are forgotten when it is left (pagesEnter)
let pagesClientsAll = false;   // the Clients switch: false is Work waiting
let pagesSetAsideOpen = false;
let pagesBroken = [];          // the rows of the page being drawn that could not be built: {name, err}
let pagesDrawn = "";           // which route the page holds, so a failed draw keeps only its own
let pagesYearless = false;     // the list being drawn leaves out its Tax Year column: one year only (P268; the engine says so, `page.many_years`)

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
let pagesOrder = null;         // list -> {cell, dir}: read once from this PC's storage (P199)
let pagesWidths = null;        // list -> {cell: px}: read once from this PC's storage (P139)
// A list of more than this many rows draws only the rows in view (P279, SPEC-ui-menu-speed 2.1);
// one of this many or fewer is drawn whole, as it always was (Jason's question A). The editor reads it too.
const PAGES_VIRTUAL_FROM = 100;
const PAGES_VIRTUAL_OVER_LEAST = 15;   // rows kept either side of the view: a viewport's worth, at least this many
let pagesVirtualWired = false;         // the page's one scroll listener and resize observer are in place
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

// A return that needs a person says since when: the day its oldest waiting
// file arrived (P269, option c); the column's header stays "Date".
function pagesSince(iso) {
  return iso ? fill(screenWords().since, { date: pagesDay(iso) }) : "";
}

// The firm answer the page is drawn from (shell.js keeps it; a page that
// needs it is only drawn once it has arrived): the totals, the next sort and
// each return's counts of the newest reply of any list, and `replies`, the
// last reply of each firm list - one page of it (P278, SPEC-ui-menu-speed 4.3).
function pagesFirm() {
  const data = shellFirm().data;
  if (!data) throw new Error("firm");
  return data;
}

// One firm list's reply: its page, its counts and the paths its rows name.
// A list the answer holds no reply of is a loud failure, never an empty page.
function pagesReply(list) {
  const reply = pagesFirm().replies[list];
  if (!reply) throw new Error(`firm.${list}`);
  return reply;
}

// The page of a firm list the window holds (shown or on its way), or null.
function pagesHeldPage(list) {
  const data = shellFirm().data;
  return data && data.replies && data.replies[list] ? data.replies[list].page : null;
}

// The firm's returns by path, built once for the reply on screen and read by
// every row that needs a return's counts (a scan per call made a sort of n
// returns n log n scans). The index belongs to the `return_counts` array it was
// built from, so a reply adopted later has its own; the first return with a
// path answers, as the scan did.
function pagesFirmReturn(path) {
  const data = shellFirm().data;
  if (!data) return null;
  if (pagesFirmReturn.from !== data.return_counts) {
    pagesFirmReturn.from = data.return_counts;
    pagesFirmReturn.byPath = new Map();
    for (const one of data.return_counts) if (!pagesFirmReturn.byPath.has(one.path)) pagesFirmReturn.byPath.set(one.path, one);
  }
  return pagesFirmReturn.byPath.get(path) || null;
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

// While the launch's last counts stand (P229), the Overview says their time
// in its own Work line (Jason, 2026-10-08: "Time on Overview page"): a line
// the page always draws, whose height the words never change, so no row
// moves when they come or go, and the path row's slot keeps its 8 ch.
function pagesAsOf() {
  const asOf = shellFirm().asOf;
  return asOf ? fill(screenWords().updating_as_of, { time: pagesTime(asOf) }) : "";
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

// One collator for every name sort: `localeCompare` with options builds a
// collator on each call, and a sort of a few hundred names calls it thousands
// of times. The options are the ones the sorts always used (numbers inside a
// name compare as numbers, "Client 2" before "Client 10"), the sensitivity the
// default: "base" would make "Okafor" and "okafor" equal and so change an order
// the people have always seen.
const PAGES_COLLATOR = new Intl.Collator(undefined, { numeric: true });

function pagesByName(a, b) {
  return PAGES_COLLATOR.compare(a, b);
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

// ── the row and the group (SPEC 3.6) ──────────────────────────────────
// A row's id, assigned at draw time and registered with what it is about, so the right-click menus, the
// sheet's next arrow and Shift+F10 see every row of a list whether its node is made yet or not (P279).
function pagesRegister(spec) {
  pagesUid += 1;
  const id = `row-${pagesUid}`;
  pagesTokens.set(id, spec);
  return id;
}

// A spec: {name, detail, status, tone, date, step, menu}. `step` is data
// ({kind, ...}), run by pagesRunStep; `menu` names the right-click template.
function pagesRow(spec) {
  return pagesRowNode(spec, pagesRegister(spec), null);
}

// The row's node. `place`: a row of a long list ({pos, size, sub}) made when it comes into view - its id was
// registered at draw time, it is one line (a long name ends in an ellipsis, with its tooltip), and it says its place
// in the list and the sub-heading it sits under.
function pagesRowNode(spec, id, place) {
  // The request list is a write: while a live lock holds the return its Edit
  // step is not offered (the menu's Edit request list is grey for the same reason).
  const stepOf = spec.step && !(spec.step.kind === "edit" && locked) ? spec.step : null;
  const words = stepOf ? pagesStepWords(stepOf) : "";
  // At rest the step is a quiet chevron; its words come before it on hover or on the
  // keyboard's active row (P270). Both are aria-hidden: the words are in `described`.
  const step = stepOf ? h("span", { className: "row-step", "aria-hidden": "true" }, h("span", { className: "row-step-words" }, words), icon("chev", true)) : null;
  // A return's or a household's row, and any row that carries a marker, may
  // wrap to two lines or more (rulings 21 and 27): the year after a return's
  // name and the words of a paused household are never cut away. A file's
  // name still ends in an ellipsis.
  const wraps = !place && Boolean(spec.mark || (spec.nameLink && spec.nameLink.kind !== "file"));
  // A file's own name is an item, not a heading: ordinary weight (P136).
  const file = Boolean(spec.fileKind || (spec.nameLink && spec.nameLink.kind === "file"));
  // A row with linked households says so to a screen reader: its icon is
  // not a Tab stop inside the list (P171).
  const linked = spec.links && spec.links.length ? screenWords().linked.tip : "";
  // A status that is a tag for longer words (P116) carries them for the
  // keyboard and a screen reader, since focus rests on the list (lane 2);
  // a return row names its household there too, as its tooltip does (P195).
  // A list that holds one year leaves out its Tax Year column, and the year is said here (P268).
  const yearSaid = spec.returnRow && pagesYearless && spec.year ? String(spec.year) : "";
  const described = [place ? place.sub : "", words, pagesReasonTip(spec), spec.household, linked, yearSaid].filter(Boolean).join(", ");
  // A row of a list of returns (Overview, Reminders) is five cells, one field
  // each: Tax Year, Taxpayer, Form Type, then status and date (P194, P195) -
  // four when the list holds only one year (P268).
  const lead = spec.returnRow
    ? [...(pagesYearless ? [] : [h("span", { className: "row-year" }, spec.year ? String(spec.year) : "")]), pagesNameCell(spec), pagesFormCell(spec)]
    : [pagesNameCell(spec), pagesDetailCell(spec)];
  // The household and year pages put the status right after the name (P275): name, status, detail, end.
  const status = pagesStatusCell(spec);
  const cells = spec.statusNext ? [lead[0], status, ...lead.slice(1)] : [...lead, status];
  const node = h("div", {
    className: `row${spec.returnRow ? " row-return" : ""}${step ? " has-step" : ""}${spec.child ? " row-child" : ""}${wraps ? " row-wrap" : ""}${file ? " row-file" : ""}`,
    role: "option", id, "aria-selected": "false",
    "aria-posinset": place ? String(place.pos) : undefined, "aria-setsize": place ? String(place.size) : undefined,
    "aria-description": described || undefined, dataset: { menu: spec.menu || "", token: id },
  },
  ...cells,
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
  return screenWords().steps[step.kind];
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
  const model = list.pagesModel;
  if (model) {
    // A long list: the active row is pinned in the document, and brought into view by the page's own scroll.
    model.active = model.index.get(row.id);
    pagesVirtualReveal(list, model.slot[model.active]);
    pagesVirtualPlace(list);
  } else if (row.scrollIntoView) row.scrollIntoView({ block: "nearest" });
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
    openCheck(step.ret, step.name, step.handle);
  } else if (step.kind === "draft") {
    openReminder(step.ret);
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
    const byKey = typeof list.matches === "function" && list.matches(":focus-visible");
    if (list.pagesModel) {
      if (list.pagesModel.active < 0) pagesActivateAt(list, 0, byKey);
      return;
    }
    const first = list.querySelector('[role="option"]');
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
  const total = spec.blocks.reduce((n, block) => n + block.rows.filter((row) => !pagesIsChild(row)).length, 0);
  // A return section's tone (P176): its icon before the heading, a bar at
  // its edge and a tinted count badge, in the section's status colour.
  const section = spec.key ? PAGES_SECTIONS[spec.key] : null;
  const tone = section ? PAGES_TONES[section[0]] : "";
  const meta = h("span", { className: `group-count${section ? ` is-badge ${tone}` : ""}` }, spec.caption !== undefined ? spec.caption : String(total));
  // `heading`: words, or the nodes of a return's heading (pagesReturnHeading).
  const title = h("h2", { className: "group-title", id: headId }, spec.heading);
  const start = spec.step ? pagesGroupStep(spec.step) : null;
  const lead = section ? h("span", { className: `group-icon ${tone}` }, icon(section[1])) : null;
  const headClass = `group-head${spec.first ? " is-first" : ""}${section ? ` is-section section-${section[0]}` : ""}`;
  let body = null;
  if (total && spec.blocks.lazy) {
    body = pagesVirtualList({ labelledby: headId }, spec.blocks, section ? section[0] : "");
  } else if (total) {
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
    // A long list inside the fold draws nothing until it is opened (P279).
    if (spec.blocks.lazy) fold.addEventListener("toggle", () => { if (fold.open) pagesVirtualMeasureSaid(fold); });
    return [fold];
  }
  // `heads`: a list's column headers, between its heading and its rows;
  // `note`: words after the count on the heading's own line (the
  // Overview's "Updating, as of {time}", P229); `tools`: what sits at the
  // heading's end (Overview's tabs, a Needs Review group's More Actions; its
  // count is in the caption).
  return [h("div", { className: headClass }, lead, title, meta, spec.note || null, spec.tools || null, start), body ? spec.heads : null, body].filter(Boolean);
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
// usual order. The engine works the order out (tracker/firm_pages.py, P278)
// and sends the page in it; this file only keeps the choice, on this PC, and
// asks. A width is this PC's: kept in its own storage across restarts,
// forgotten by View › Reset Column Widths.

// The firm list a route draws, or "" for a page with no column headers.
function pagesListOf(route) {
  return { overview: "overview", "needs-review": "needs_review", reminders: "reminders", clients: "clients" }[route.level] || "";
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
  pagesRedraw(list, `.col-head[data-cell="${cell}"]`);   // any change of order returns to page 1 (P174)
}

// The header row of a list: one `role="columnheader"` cell per column in the
// rows' own grid, each a button (a Tab stop; Enter and Space press it) with
// the vocabulary's word, the drawn arrow of its order and a grip on its
// right edge. `aria-sort` says which column orders the list and which way:
// the order of the page drawn (`order`, as the engine echoed it), not the one
// just asked for.
function pagesColumnHeads(list, order = pagesStoredOrder()[list]) {
  const words = screenWords();
  const said = words.columns;
  const cells = Object.keys(PAGES_COLUMNS[list]).filter((cell) => !(pagesYearless && cell === "year")).map((cell) => {
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
  // A pointer moves many times a frame, and each width written restyles the
  // page's grid: the latest position is written once per frame, and the
  // release writes whatever is waiting, so the width saved is the last one.
  let frame = 0;
  let latest = null;
  const apply = () => {
    frame = 0;
    if (latest === null) return;
    pagesSetWidth(list, cell, latest);
    latest = null;
  };
  const move = (m) => {
    latest = from + m.clientX - start;
    if (!frame) frame = requestAnimationFrame(apply);
  };
  const done = () => {
    cancelAnimationFrame(frame);
    apply();
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
  const held = storeRead(PAGES_ORDER_KEY, true);   // nothing held: every list in its usual order
  if (held && typeof held === "object" && !Array.isArray(held)) {
    for (const [list, one] of Object.entries(held)) {
      const columns = PAGES_COLUMNS[list];
      if (columns && one && typeof one === "object" && Object.prototype.hasOwnProperty.call(columns, one.cell)
          && columns[one.cell] && (one.dir === 1 || one.dir === -1)) pagesOrder[list] = { cell: one.cell, dir: one.dir };
    }
  }
  return pagesOrder;
}

// Kept on this PC; a profile that refuses the write keeps the order while
// the app is open.
function pagesSaveOrder() {
  storeWrite(PAGES_ORDER_KEY, JSON.stringify(pagesStoredOrder()));
}

// The widths this PC holds, read once. Storage that cannot be read (a locked
// profile) leaves the usual widths: a width is a comfort of this screen, not
// a fact about a return, and the page works the same without it.
function pagesStoredWidths() {
  if (pagesWidths) return pagesWidths;
  const held = storeRead(PAGES_WIDTHS_KEY, true);
  pagesWidths = held && typeof held === "object" && !Array.isArray(held) ? held : {};
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
  storeWrite(PAGES_WIDTHS_KEY, JSON.stringify(pagesStoredWidths()));
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
  storeWrite(PAGES_WIDTHS_KEY, null);
  pagesApplyWidths($("page"), pagesListOf(shellRoute));
}

// ── page buttons (pilot SPEC-lists 14; P152, P174; P278) ──────────────
// The engine divides a list into pages after its filter and its order (50 a
// page; Needs Review by whole returns) and sends one: `page` says where it
// is. The footer is the count line and, past one page, Previous and Next.
function pagesFootOf(list, page) {
  return page.total ? pagesFoot(list, page.from, page.to, page.total, page.at, page.pages) : null;
}

// "Showing 1-50 of 750 Returns", with Previous and Next (disabled at the ends).
// A list of one page has nowhere to turn to, so it is the count line alone:
// two buttons that can only be grey are not offered.
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
    count > 1 ? h("span", { className: "page-steps" }, step(-1, "previous"), step(1, "next")) : null);
}

// Previous or Next: the page after this one asked of the engine; when it
// lands it is drawn at its top, focus kept on the button pressed, or on the
// other one once this one is disabled. The turn counts from the page last asked
// for, else the page drawn.
function pagesTurn(list, by, key) {
  // Counted from the page last asked for (so Next then a quick Previous asks for the page it started from), else from the page drawn.
  const held = pagesHeldPage(list);
  pagesPageAt[list] = Math.max(0, (list in pagesPageAt ? pagesPageAt[list] : held ? held.at : 0) + by);
  shellTurnFirm(list, () => {
    const page = $("page");
    page.scrollTop = 0;
    const same = page.querySelector(`.page-step[data-step="${key}"]`);
    const other = page.querySelector(`.page-step[data-step="${key === "next" ? "previous" : "next"}"]`);
    const to = same && !same.disabled ? same : other;
    if (to) to.focus();
  });
}

// A choice that narrows a list (a tab, a reason card, a Client Type): the
// list starts again at its first page, the engine is asked for it, and focus
// goes back to the control that was pressed (found by its data-pick) when it lands.
function pagesPick(list, set, pick) {
  set();
  pagesRedraw(list, `[data-pick="${pick}"]`);
}

// The list starts again at its first page and the engine is asked for it;
// when it lands, focus goes back to the control (`selector`) that was pressed.
function pagesRedraw(list, selector) {
  pagesPageAt[list] = 0;   // asked for, not forgotten: a Next pressed before it lands counts from it
  shellTurnFirm(list, () => {
    const again = $("page").querySelector(selector);
    if (again) again.focus();
  });
}

// A button that is pressed or not and picks one choice of a list's filter
// (a tab, a reason card, a switch option): `set` makes the choice and the
// redraw puts focus back on the button by its data-pick.
function pagesPickButton(list, className, pressed, pick, set, ...children) {
  const node = h("button", { type: "button", className, "aria-pressed": pressed ? "true" : "false", dataset: { pick } }, ...children);
  node.addEventListener("click", () => pagesPick(list, set, pick));
  return node;
}

// Overview's filter tabs: All, Need You (n), Waiting (n) (P145); the counts
// and the pressed tab are the page's (`page.counts`, `page.filter.tab`).
function pagesTabs(page) {
  const words = screenWords();
  const tab = (key, label) => pagesPickButton("overview", "switch-option", page.filter.tab === key, `tab-${key}`, () => { pagesTab = key; }, label);
  return h("div", { className: "switch is-tabs", role: "group", "aria-label": words.work },
    tab("all", words.filters.all), tab("need", fill(words.tabs.need, { n: page.counts.need })), tab("waiting", fill(words.tabs.waiting, { n: page.counts.waiting })));
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

// ── Overview (SPEC 6.1) ───────────────────────────────────────────────
// The page's rows as the engine sent them (P278), each worded and given its
// step. A household paused for two open years is one row, first, worded by the
// vocabulary, opening the household (ruling 21); a return needing a person or
// waiting on the taxpayer is a row of its bucket, saying since when or due when.
// The page's own order is the engine's: nothing is sorted here.
function pagesWorkRows(rows) {
  const steps = { kind: "open" };
  const paused = (row) => {
    // A household in the return columns: no year and no form of its own; its
    // name stands in the Taxpayer column (P195).
    if (!row.household_path) throw new Error("household");
    return { returnRow: true, year: "", name: row.household, form: "", status: screenWords().notices.paused, tone: "needs", date: "", menu: "household", pill: true,
             nameLink: { kind: "household", path: row.household_path }, step: { kind: "open", route: { level: "household", household: row.household_path } } };
  };
  const made = (one) => {
    const said = pagesCounts(one.counts, one.problem);
    return { ...pagesReturnCells(one), status: said.text, tone: said.tone, date: one.bucket === "wait" ? pagesDue(one.due) : pagesSince(one.oldest), menu: "return", pill: true,
             step: { ...steps, route: pagesRoute(one.path) } };
  };
  return pagesEach(rows, (row) => (row.kind === "paused" ? row.household : pagesReturnName(row.path)), (row) => (row.kind === "paused" ? paused(row) : made(row)));
}

function pagesOverview() {
  const words = screenWords();
  const firm = pagesFirm();
  const { page } = pagesReply("overview");
  const totals = firm.totals;
  // The three counts, each in a raised card with its status's icon (P145).
  const figures = h("div", { className: "figures" }, ...[[totals.need, words.figures.need, "needs", "alert"], [totals.waiting, words.figures.waiting, "waiting", "clock"],
    [totals.complete, words.figures.complete, "done", "done"]]
    .map(([n, label, tone, name]) => h("div", { className: "figure" },
      h("span", { className: "figure-top" }, h("span", { className: "figure-label" }, label), h("span", { className: `figure-icon ${PAGES_TONES[tone]}` }, icon(name))),
      h("b", { className: "figure-number" }, String(n)))));
  pagesYearless = !page.many_years;   // the engine counted over the whole list, before its tab and its pages (P268)
  const asOf = pagesAsOf();
  // An Overview with no work says the time under its empty line: no row is below it.
  if (!page.counts.all) return [figures, pagesEmpty(words.empty.overview, pagesNextSort(firm), asOf ? h("p", { className: "page-empty-note page-as-of" }, asOf) : null)];
  const rows = pagesEach(pagesWorkRows(page.rows), (spec) => spec.name, pagesRow);
  return [figures, ...pagesGroup({ heading: words.work, caption: String(page.total), first: true, tools: pagesTabs(page),
                                   note: asOf ? h("span", { className: "page-as-of" }, asOf) : null,
                                   heads: pagesColumnHeads("overview", page.order), none: words.empty.work, blocks: [{ rows }] }), pagesFootOf("overview", page)];
}

// ── Needs review (SPEC 6.2) ───────────────────────────────────────────
// One waiting file's row. A file's name is a link to its working copy when the
// reply names one (`open_key` and the reply's `paths`, ruling 15); with none it
// is text.
function pagesReviewSpec(reply, group, file) {
  const reason = pagesReason(file.code);
  return {
    name: file.name, detail: file.suggestion_short || file.suggestion || "", detailTip: file.suggestion || "", detailTag: true,
    status: reason, reason: file.code, tone: "needs", date: pagesDay(file.received), pill: true, reasonIcon: PAGES_REASON_ICONS[file.code] || "alert", fileIcon: true,
    menu: "file", fileKind: "parked", nameLink: pagesFileLink(reply.paths, file.open_key),
    step: { kind: "check", ret: group.path, name: file.name, handle: file.handle },
  };
}

// "13 Files", "1 File": the count beside a title (P149).
function pagesFileCount(n) {
  const words = screenWords().counts;
  return n === 1 ? words.one_file : fill(words.files, { n });
}

// The reason cards across the top of Needs Review (P149): All, then one per
// reason present with its count, most files first (the engine's order), each a
// filter (aria-pressed).
function pagesReasonCards(reasons, total, pick) {
  const words = screenWords();
  const card = (code, label, n, name) => pagesPickButton("needs_review", "reason-card", pick === code, `reason-${code || "all"}`, () => { pagesReasonPick = code; },
    h("span", { className: "reason-card-top" }, name ? h("span", { className: "reason-card-icon is-attention" }, icon(name, true)) : null, h("span", { className: "reason-card-word" }, label)),
    h("b", { className: "reason-card-number" }, String(n)));
  return h("div", { className: "reason-cards", role: "group", "aria-label": words.sections.needs_review },
    card("", words.filters.all, total, ""), ...reasons.map(([code, n]) => card(code, pagesReason(code), n, PAGES_REASON_ICONS[code] || "alert")));
}

// A return group's heading on Needs Review (P149, P272): an ordinary group,
// as on a return's own page - no card, no pill, no folder icon. The return's
// name, the household as the small secondary link with its link mark, then
// the count of its documents in the same caption, and More Actions after the
// count, which opens the same native menu as a right-click on the heading
// (the return's; no new action). `first` is the page's first group.
function pagesReviewGroup(group, specs, first) {
  const words = screenWords();
  const rows = pagesEach(specs, (spec) => spec.name, pagesRow);
  // The heading needs nothing else of the firm: the group carries its household, its household's folder and links, its year and form (P278).
  const household = group.household;
  const house = group.household_path;
  const caption = household ? [house ? pagesHeadLink({ kind: "household", path: house }, household) : household] : [];
  if (group.links && group.links.length) caption.push(pagesLinkMark(group.links, false, household));
  const count = rows.length === 1 ? words.documents.one : fill(words.documents.many, { n: rows.length });
  caption.push(household ? ` \u00b7 ${count}` : count);
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
  const nodes = pagesGroup({ heading: pagesReturnHeading(group.path, group.year, group.form),
                             caption, first, tools: [more], blocks: [{ rows }] });
  nodes[0].addEventListener("contextmenu", (e) => {
    e.preventDefault();
    popup(e.clientX, e.clientY);
  });
  return nodes;
}

function pagesNeedsReview() {
  const words = screenWords();
  const firm = pagesFirm();
  const reply = pagesReply("needs_review");
  const { page } = reply;
  if (!page.counts.all) return [pagesEmpty(words.empty.needs_review, pagesNextSort(firm))];
  const head = h("div", { className: "group-head is-first page-head" }, h("h2", { className: "list-title" }, words.sections.needs_review),
    h("span", { className: "list-count" }, pagesFileCount(page.total)));
  // The first heading drawn sits 24px under the column headers; a group that
  // cannot be built is named in a notice and the next one is the first.
  let first = true;
  const groupNodes = page.rows.flatMap((group) => {
    const specs = pagesEach(group.files, (file) => file.name, (file) => pagesReviewSpec(reply, group, file));
    const nodes = pagesSafe(pagesReturnName(group.path), () => pagesReviewGroup(group, specs, first));
    if (nodes) first = false;
    return nodes || [];
  });
  return [head, pagesReasonCards(page.counts.reasons, page.counts.all, page.filter.reason), pagesColumnHeads("needs_review", page.order), ...groupNodes, pagesFootOf("needs_review", page)];
}

// ── Reminders (SPEC 6.3) ──────────────────────────────────────────────
// The page's rows as the engine sent them (P278): the returns whose draft is
// ready, worded; the order is the engine's.
function pagesReminderSpecs(rows) {
  return pagesEach(rows, (one) => pagesReturnName(one.path), (one) => {
    const held = one.draft.held > 0;
    const status = held ? screenWords().held : pagesStage(one.draft.stage);
    return {
      ...pagesReturnCells(one),
      status, tone: held ? "needs" : "waiting", date: pagesDay(one.draft.drafted), menu: "return", pill: true,
      step: { kind: "draft", ret: one.path },
    };
  });
}

function pagesReminders() {
  const words = screenWords();
  const { page } = pagesReply("reminders");
  pagesYearless = !page.many_years;   // over every ready draft (P268)
  if (!page.total) return [pagesEmpty(words.empty.reminders)];
  return [h("div", { className: "page-gap" }), pagesColumnHeads("reminders", page.order),
    pagesList({ label: words.sections.reminders }, pagesEach(pagesReminderSpecs(page.rows), (spec) => spec.name, pagesRow)), pagesFootOf("reminders", page)];
}

// ── Clients (SPEC 6.4) ────────────────────────────────────────────────
// The page's households as the engine sent them (P278), which grouped the
// firm's returns by household once, from the same walk: a household's count of
// returns, what needs a person, what waits and the first return that could not
// be read, and whether it is paused. Worded here, in the order given.
function pagesClientSpecs(rows) {
  const words = screenWords().counts;
  return pagesEach(rows, (one) => one.name, (one) => {
    // A household with a return whose record cannot be read is never
    // Complete: that return's problem is its status (as pagesCounts says it).
    const said = one.need ? { text: fill(words.need, { n: one.need }), tone: "needs" }
      : one.problem ? { text: one.problem, tone: "needs" }
        : one.wait ? { text: fill(words.waiting, { n: one.wait }), tone: "waiting" }
          : one.returns ? { text: words.complete, tone: "done" } : { text: "", tone: "plain" };
    return {
      name: one.name, detail: one.returns ? fill(one.returns === 1 ? words.one_return : words.returns, { n: one.returns }) : "",
      mark: one.paused ? screenWords().notices.paused : "",
      status: said.text, tone: said.tone, date: "", menu: "household", pill: true, links: one.links || [], linksIn: "name",
      nameLink: { kind: "household", path: one.path },
      step: { kind: "open", route: { level: "household", household: one.path } },
    };
  });
}

// The Clients switch: Work Waiting (with its count, P153) and All; the pressed
// one is the page's (`page.filter.all`).
function pagesSwitch(work, everyone) {
  const words = screenWords().filters;
  const option = (label, all, count) => pagesPickButton("clients", "switch-option", everyone === all, all ? "all" : "work", () => { pagesClientsAll = all; },
    label, count === undefined ? null : h("span", { className: "switch-count" }, String(count)));
  return h("div", { className: "switch", role: "group", "aria-label": screenWords().sections.clients }, option(words.work, false, work), option(words.all, true));
}

// The Client Type filter on Clients, with its dismiss (P153; SPEC-lists 15.3).
function pagesTypeFilter(type) {
  if (!type) return null;
  const words = screenWords();
  const label = (words.client_types || {})[type];
  if (!label) throw new Error(`client_types.${type}`);
  const dismiss = h("button", { type: "button", className: "icon-button type-dismiss", "aria-label": words.icons.remove_filter, dataset: { pick: "type" } }, icon("dismiss", true));
  setTip(dismiss, words.icons.remove_filter);
  dismiss.addEventListener("click", () => pagesPick("clients", () => { pagesClientType = ""; }, "all"));
  return h("span", { className: "type-filter" }, h("span", { className: "type-filter-word" }, label), dismiss);
}

function pagesClients() {
  const words = screenWords();
  if (!households.length) {
    const start = h("button", { type: "button", className: "btn" }, vocab.menu.new_household);
    start.addEventListener("click", () => openNewHousehold());
    return [pagesEmpty(words.empty.clients, "", start)];
  }
  // The engine narrowed the whole list by the type and the tab, ordered it and
  // cut the page; both tabs of the switch share one order (SPEC-lists 3).
  const { page } = pagesReply("clients");
  const bar = h("div", { className: "clients-bar" }, pagesSwitch(page.counts.work, page.filter.all), pagesTypeFilter(page.filter.type));
  if (!page.total) return [bar, pagesEmpty(words.empty.work)];
  const rows = document.createDocumentFragment();
  for (const row of pagesEach(pagesClientSpecs(page.rows), (spec) => spec.name, pagesRow)) rows.append(row);
  return [bar, pagesColumnHeads("clients", page.order), pagesList({ label: words.sections.clients }, [rows]), pagesFootOf("clients", page)];
}

// ── Household and year (SPEC 6.5, 6.6) ────────────────────────────────
// The household card (P275): who to talk to, who the household is shared with
// and whether its inbox link is saved, in a card beside the returns (above them
// in a narrow page). A fact with nothing to say is left out; the Inbox Link is
// always there. The link itself is the client's share link: it is never drawn
// and never opened (an app that opened it would reach the network) - "Saved"
// tells a person whether Mark as Shared will be accepted. Opening the inbox
// folder stays a menu item, and More Actions opens the household's menu: the
// token is the H1's own, so it acts on the page's household with the page's
// enable rules.
function pagesHouseholdCard(route, hh) {
  const words = screenWords();
  if (!words.household_card) throw new Error("vocab.screen.household_card");
  const card = words.household_card;
  const state = lastState && lastState.household && lastState.household.path === route.household ? lastState.household : null;
  const members = (hh.members || []).filter(Boolean);
  const fact = (term, ...values) => h("div", { className: "card-fact" }, h("dt", {}, term), ...values);
  const facts = [];
  if (hh.contact) facts.push(fact(card.contact, h("dd", {}, hh.contact)));
  if (members.length || state) {
    facts.push(fact(card.shared_with, members.length ? h("dd", {}, members.join(", ")) : null,
      state ? h("dd", { className: "card-shared" }, state.shared_on ? words.shared : words.not_shared) : null));
  }
  facts.push(fact(card.inbox_link, h("dd", {}, hh.link ? card.link_saved : card.no_link)));
  const more = h("button", { type: "button", className: "icon-button card-more", "aria-label": words.icons.more_actions, "aria-haspopup": "menu" }, icon("more"));
  setTip(more, words.icons.more_actions);
  const popup = (x, y) => shellPopup("household", "crumb-household", x, y);
  more.addEventListener("click", () => {
    const box = more.getBoundingClientRect();
    popup(box.left, box.bottom);
  });
  const node = h("div", { className: "household-card" }, h("dl", { className: "card-facts" }, ...facts), more);
  node.addEventListener("contextmenu", (e) => {
    e.preventDefault();
    popup(e.clientX, e.clientY);
  });
  return node;
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
             statusNext: true,
             waiting: waiting && !firm,
             nameLink: { kind: "return", path: one.path },
             step: { kind: "open", route: { level: "return", household: shellRoute.household, year: one.year, ret: one.path } } };
  });
}

function pagesHousehold(route) {
  const words = screenWords();
  const hh = shellHousehold(route.household);
  if (!hh) return [];
  // The H1, then the body: the card first (read first, in both forms), then the
  // returns' list. The card and each year are built on their own, so one that
  // cannot be built is named in a notice and the rest is drawn (P275).
  const card = pagesSafe(hh.name, () => pagesHouseholdCard(route, hh));
  let list;
  if (!hh.returns.length) {
    const add = h("button", { type: "button", className: "btn" }, vocab.menu.add_return);
    add.addEventListener("click", () => openAddReturn(hh));
    list = h("div", { className: "returns-list" }, pagesEmpty(words.empty.returns, "", add));
  } else {
    const years = [...new Set(hh.returns.map((one) => one.year))].sort((a, b) => b - a);
    list = h("div", { className: "returns-list" }, ...years.flatMap((year, i) => pagesSafe(String(year), () => pagesGroup({
      heading: String(year), first: i === 0,
      blocks: pagesBlocks(pagesReturnSpecs(hh.returns.filter((one) => one.year === year))),
    })) || []));
  }
  return [pagesTitleFor(route), h("div", { className: "household-body" }, h("div", { className: "household-layout" }, card, list))];
}

function pagesYear(route) {
  const hh = shellHousehold(route.household);
  if (!hh) return [];
  const title = pagesTitleFor(route);
  const specs = pagesReturnSpecs(hh.returns.filter((one) => one.year === route.year));
  const blocks = pagesBlocks(specs);
  const list = blocks.lazy ? pagesVirtualList({ labelledby: title.id }, blocks, "") : pagesList({ labelledby: title.id }, blocks.flatMap((block) => block.rows));
  return [title, h("div", { className: "page-gap" }), h("div", { className: "returns-list" }, list)];
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

  // The files filed under each request, in index order, read once from the
  // index: a file counts under its own identifier and under each request it
  // answered (decision 146), once under each.
  const filedUnder = new Map();
  for (const one of index) {
    if (one.decision !== decisions.filed) continue;
    for (const identifier of new Set([one.identifier, ...(one.answered || [])])) {
      if (!filedUnder.has(identifier)) filedUnder.set(identifier, []);
      filedUnder.get(identifier).push(one);
    }
  }
  const filedBy = (identifier) => filedUnder.get(identifier) || [];
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
//
// A list of more than PAGES_VIRTUAL_FROM rows is registered whole but its nodes are made as they come into view
// (P279): its rows are {id, spec} here, not nodes, and `blocks.lazy` says so.
function pagesBlocks(specs) {
  const blocks = [];
  blocks.lazy = specs.length > PAGES_VIRTUAL_FROM;
  for (const spec of specs) {
    const row = blocks.lazy ? { id: pagesRegister(spec), spec } : pagesSafe(spec.name, () => pagesRow(spec));
    if (row === null) continue;
    const last = blocks[blocks.length - 1];
    if (last && (last.sub || "") === (spec.sub || "")) last.rows.push(row);
    else blocks.push({ sub: spec.sub || "", rows: [row] });
  }
  return blocks;
}

// A row of a group, drawn or only registered: one of several files under a request (ruling 17)?
function pagesIsChild(row) {
  return row.spec ? Boolean(row.spec.child) : row.classList.contains("row-child");
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
    // its short line, and the sentence is under Details and in the error log
    // (SPEC 11.1; P259 Q3, SPEC-mac-check-fixes 4.2: `shown`). A
    // pause a person can accept (it names a scope) is the renamed folder, with
    // Accept; a year's pause has no Accept.
    const pause = hh.pause || {};
    if (pause.sentence) {
      wanted.push({ key: "renamed", failure: { sentence: shortNotice(pause.scope ? "renamed" : "paused"), kind: "warning" },
                    detail: pause.sentence, shown: true,
                    opts: pause.scope ? { action: { label: words.accept_folder_name, run: acceptFolderName, write: true } } : {} });
    }
    const feeds = (hh.feeds || []).map((one) => one.warning).filter(Boolean);
    if (feeds.length) wanted.push({ key: `feeds:${feeds.join("\n")}`, failure: { sentence: shortNotice("feed"), kind: "warning" }, detail: feeds.join("\n"), shown: true });
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
  // A long list names the active row by its place in the whole list, not among the drawn nodes (P279).
  const place = list.pagesModel ? Math.max(0, list.pagesModel.active) : row ? [...list.querySelectorAll('[role="option"]')].indexOf(row) : 0;
  return { at: [...page.querySelectorAll('[role="listbox"]')].indexOf(list), row: place };
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
  if (list && list.pagesModel) {
    const count = list.pagesModel.ids.length;
    if (count) {
      pagesActivateAt(list, Math.min(Math.max(pagesFocus.row, 0), count - 1));
      list.focus({ preventScroll: true });
    }
    pagesFocus = null;
    return;
  }
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

// A firm page's pages, tab and reason card are forgotten when it is left, the
// Clients switch when Clients is entered, and a Client Type when another firm
// page is opened (P174, P145, P149, P153). The shell enters a firm list before
// it asks the engine for its first page (P278), the draw enters it again: the
// second time nothing changes.
function pagesEnter(route) {
  if (route.level === pagesEntered) return;
  if (route.level === "clients") pagesClientsAll = false;
  pagesPageAt = {};
  pagesTab = "all";
  pagesReasonPick = "";
  if (["overview", "needs-review", "reminders"].indexOf(route.level) !== -1) pagesClientType = "";
  pagesEntered = route.level;
}

// A reply has landed for a list (P278). Two things the engine corrects of what
// was asked, and only these: a page past the end is the last page, and a
// reason card whose reason is no longer among the files is All. Everything else
// the person has since chosen stays chosen. Only for the firm page on screen:
// the choices of a list that was left are already forgotten.
function pagesAdopt(reply) {
  const { list, at, pages, counts } = reply.page;
  if (pagesListOf(shellRoute) !== list) return;
  if (at < (pagesPageAt[list] || 0) && at === Math.max(0, pages - 1)) pagesPageAt[list] = at;
  if (list === "needs_review" && pagesReasonPick && !counts.reasons.some(([code]) => code === pagesReasonPick)) pagesReasonPick = "";
}

// shell.js: draw the route's page into #page. A page that cannot be built
// whole keeps what it held (the same page) or draws its frame, its H1, and
// says so; it is never emptied for one bad row (SPEC 6, failed read).
function pagesDraw(route, page) {
  pagesEnter(route);
  // An open Linked Households panel outlives a redraw of the same page (the
  // review's S2): it is opened again on the same household's mark, or, when
  // that mark is gone, focus goes to the page's list rather than be lost.
  const panel = pagesPanel && route.level === pagesLastLevel ? { owner: pagesPanel.owner } : null;
  pagesClosePanel(false);
  pagesLastLevel = route.level;
  const key = pagesRouteKey(route);
  if (pagesDrawn !== key) pagesSetAsideOpen = false;   // Set aside is shut each time the page opens
  pagesRemember(page);
  const before = new Map(pagesTokens);
  const keepTop = pagesDrawn === key ? page.scrollTop : 0;   // a redraw of the same page keeps its place (P279)
  pagesUid = 0;
  pagesTokens.clear();
  pagesBroken = [];
  let nodes = null;
  pagesYearless = false;
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
  page.classList.toggle("is-yearless", pagesYearless);   // one year: no Tax Year column (P268)
  pagesApplyWidths(page, pagesListOf(route));
  pagesDrawn = key;
  try {
    pagesVirtualMeasure(page, keepTop);
  } catch (err) {
    failed(err);
  }
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

// ── long lists draw only the rows in view (P279, SPEC-ui-menu-speed 2) ──
// A list of more than PAGES_VIRTUAL_FROM rows registers every row at draw time (pagesTokens, so the menus, the
// sheet's next arrow and Shift+F10 see every row) but makes a node only for the rows in view, one screen either
// side of it, and the active row. The listbox is as tall as the whole list and each drawn row sits at its place in
// it; the listbox itself is never removed, so focus stays put however far the page scrolls. The row height is
// never typed here: it is a drawn row's own, which the stylesheet gives by the density (--size-row, or
// --size-row-compact under Compact Rows), so it is measured, and a list that is not laid out is loud.

// The items - rows and the sub-headings between them (a slot of the same height each) - the view meets, and `over`
// either side: {first, last}, an empty list or a list far from the view {first: 0, last: -1}. Pure.
function pagesWindow(count, H, listTop, viewTop, viewHeight, over) {
  if (!(count > 0) || !(H > 0)) return { first: 0, last: -1 };
  const first = Math.max(0, Math.floor((viewTop - listTop) / H) - over);
  const last = Math.min(count - 1, Math.ceil((viewTop + viewHeight - listTop) / H) - 1 + over);
  return first > last ? { first: 0, last: -1 } : { first, last };
}

// How many rows either side of the view: a viewport's worth, at least PAGES_VIRTUAL_OVER_LEAST.
function pagesOver(viewHeight, H) {
  return Math.max(PAGES_VIRTUAL_OVER_LEAST, H > 0 ? Math.ceil(viewHeight / H) : 0);
}

// The list as the page's scroller sees it: where its top is in the scrolled content.
function pagesListTop(list, page) {
  return list.getBoundingClientRect().top - page.getBoundingClientRect().top + page.scrollTop;
}

// A long list's listbox. `blocks`: the rows ({id, spec}, registered) and the sub-headings they sit under, in order.
function pagesVirtualList(name, blocks, edge) {
  const list = pagesList(name, [], edge);
  list.classList.add("is-virtual");
  const items = [];
  const ids = [];
  const specs = [];
  const slot = [];
  for (const block of blocks) {
    if (block.sub) items.push({ head: block.sub });
    for (const row of block.rows) {
      slot.push(items.length);
      items.push({ row: ids.length, sub: block.sub || "" });
      ids.push(row.id);
      specs.push(row.spec);
    }
  }
  list.pagesModel = { items, ids, specs, slot, index: new Map(ids.map((id, i) => [id, i])), H: 0, active: -1, nodes: new Map(), broken: new Set() };
  return list;
}

// The node of item `i`, made now: a sub-heading's slot, or a row that says its place (aria-posinset, aria-setsize)
// and, for a row under a sub-heading, that sub-heading's words at the front of its description. A row that cannot
// be made is an empty row of the same height and is said once, by the page's notice - never a silent gap.
function pagesVirtualMake(list, i) {
  const model = list.pagesModel;
  const item = model.items[i];
  let node = null;
  if (item.head !== undefined) {
    node = h("div", { className: "group-sub", role: "presentation" }, item.head);
    node.style.setProperty("height", `${model.H}px`);
  } else {
    const spec = model.specs[item.row];
    const id = model.ids[item.row];
    if (!model.broken.has(i)) node = pagesSafe(spec.name, () => pagesRowNode(spec, id, { pos: item.row + 1, size: model.ids.length, sub: item.sub }));
    if (node === null) {
      model.broken.add(i);
      node = h("div", { className: "row", role: "option", id, "aria-selected": "false", "aria-posinset": String(item.row + 1), "aria-setsize": String(model.ids.length), dataset: { menu: "", token: id } });
    }
    if (item.row === model.active) {
      node.classList.add("is-active");
      node.setAttribute("aria-selected", "true");
    }
    // The list's last row has no hairline under it, as the last row of a list drawn whole has none.
    if (item.row === model.ids.length - 1) node.classList.add("is-last");
  }
  node.style.setProperty("top", `${i * model.H}px`);
  return node;
}

// Item `i` in the document (made if it is not), in its place among the drawn ones.
function pagesVirtualNode(list, i) {
  const model = list.pagesModel;
  if (model.nodes.has(i)) return model.nodes.get(i);
  const node = pagesVirtualMake(list, i);
  let next = null;
  let nextAt = Infinity;
  for (const [at, other] of model.nodes) {
    if (at > i && at < nextAt) {
      next = other;
      nextAt = at;
    }
  }
  list.insertBefore(node, next);
  model.nodes.set(i, node);
  return node;
}

// The rows the view meets, a screen either side of it, and the active row are in the document; the others are not.
// A row already drawn is kept as it is, never rebuilt.
function pagesVirtualPlace(list) {
  const model = list.pagesModel;
  const page = $("page");
  if (!model.H || !page) return;
  const over = pagesOver(page.clientHeight, model.H);
  const win = pagesWindow(model.items.length, model.H, pagesListTop(list, page), page.scrollTop, page.clientHeight, over);
  const active = model.active >= 0 ? model.slot[model.active] : -1;
  for (const [i, node] of [...model.nodes]) {
    if ((i >= win.first && i <= win.last) || i === active) continue;
    list.removeChild(node);
    model.nodes.delete(i);
  }
  const broken = pagesBroken.length;
  for (let i = win.first; i <= win.last; i += 1) pagesVirtualNode(list, i);
  if (active >= 0) pagesVirtualNode(list, active);
  if (pagesBroken.length !== broken) {
    try {
      pagesReportBroken();
    } catch (err) {
      failed(err);
    }
  }
}

// The row's own height, measured from a drawn row, and the listbox sized to the whole list. The first row is made,
// laid out, and read; anything else than a positive number is a list that was not laid out, and a failure the
// page says (decision 193) - never a guessed height. A list inside a fold that is shut is not laid out and is
// left until the fold opens.
function pagesVirtualSize(list) {
  const model = list.pagesModel;
  const fold = list.closest ? list.closest("details") : null;
  if (fold && !fold.open) return;
  for (const node of model.nodes.values()) list.removeChild(node);
  model.nodes.clear();
  model.H = 0;
  const first = model.items.findIndex((item) => item.head === undefined);
  if (first === -1) return;
  const probe = pagesVirtualMake(list, first);
  list.append(probe);
  const height = probe.offsetHeight;
  list.removeChild(probe);
  if (!(height > 0)) throw new Error("row_height");
  model.H = height;
  list.style.setProperty("height", `${model.items.length * height}px`);
}

// Every long list under `root` (the page, or a fold just opened): measured and drawn. A redraw of the same page
// asks for its scroll position back (`keepTop`), which the browser lost while the lists had no height.
function pagesVirtualMeasure(root, keepTop) {
  const lists = [...root.querySelectorAll(".rows.is-virtual")];
  if (!lists.length) return;
  pagesVirtualWire();
  const broken = pagesBroken.length;
  for (const list of lists) pagesVirtualSize(list);
  const page = $("page");
  if (keepTop) page.scrollTop = keepTop;
  for (const list of lists) pagesVirtualPlace(list);
  if (pagesBroken.length !== broken) pagesReportBroken();   // a row that could not be made, said once
}

// pagesVirtualMeasure for a caller outside pagesDraw (a fold opened, the density switched): a throw is the
// page's failure notice, as it is when the draw measures (decision 193), never a console line only.
function pagesVirtualMeasureSaid(root) {
  try {
    pagesVirtualMeasure(root);
  } catch (err) {
    // The failed size took the lists' rows out of the document: no list names a row that is gone.
    for (const list of root.querySelectorAll(".rows.is-virtual")) {
      if (list.pagesModel && !list.pagesModel.nodes.size) list.removeAttribute("aria-activedescendant");
    }
    failed(err);
  }
}

// Every long list on the page, after a scroll or a resize.
function pagesVirtualPlaceAll(root) {
  for (const list of root.querySelectorAll(".rows.is-virtual")) pagesVirtualPlace(list);
}

// One passive scroll listener on the page and one resize observer, each coalesced to one animation frame.
function pagesVirtualWire() {
  if (pagesVirtualWired) return;
  pagesVirtualWired = true;
  const page = $("page");
  let queued = false;
  const again = () => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      pagesVirtualPlaceAll(page);
    });
  };
  page.addEventListener("scroll", again, { passive: true });
  if (typeof ResizeObserver === "function") new ResizeObserver(again).observe(page);
}

// The page scrolled just far enough that item `i` is whole in view (`block: "nearest"`'s rule), by the page's own
// scroll position: the row may not be in the document yet.
function pagesVirtualReveal(list, i) {
  const model = list.pagesModel;
  const page = $("page");
  if (!model.H) return;
  const top = pagesListTop(list, page) + i * model.H;
  const bottom = top + model.H;
  if (top < page.scrollTop) page.scrollTop = top;
  else if (bottom > page.scrollTop + page.clientHeight) page.scrollTop = bottom - page.clientHeight;
}

// Row `at` of a long list made active: drawn if it is not, then brought into view.
function pagesActivateAt(list, at, byKey) {
  const model = list.pagesModel;
  if (!model.H) return;
  pagesActivate(list, pagesVirtualNodeSaid(list, model.slot[at]), byKey);
}

// Item `i` in the document, as pagesVirtualNode makes it, and a row that cannot be made, reached by a key or by a
// restore, named once (pagesReportBroken) as a row reached by scrolling is: the baseline is taken before the node.
function pagesVirtualNodeSaid(list, i) {
  const broken = pagesBroken.length;
  const node = pagesVirtualNode(list, i);
  if (pagesBroken.length !== broken) {
    try {
      pagesReportBroken();
    } catch (err) {
      failed(err);
    }
  }
  return node;
}

// The keys of a long list: the model's rows, drawn or not (the arrow keys, Home, End, PageUp and PageDown move the
// active index over every row), Space, Enter and Shift+F10 on the active one.
function pagesKeyLong(e, list) {
  const model = list.pagesModel;
  const count = model.ids.length;
  if (!count || !model.H) return false;
  const at = Math.max(0, model.active);
  if (e.key === "ContextMenu" || (e.key === "F10" && e.shiftKey)) {
    e.preventDefault();
    const node = pagesVirtualNodeSaid(list, model.slot[at]);
    const box = node.getBoundingClientRect();
    pagesPopup(node, box.left + box.width / 2, box.bottom);
    return true;
  }
  const page = Math.max(1, Math.floor(($("page").clientHeight || model.H) / model.H) - 1);
  const moves = { ArrowDown: at + 1, ArrowUp: at - 1, Home: 0, End: count - 1, PageDown: at + page, PageUp: at - page };
  if (e.key in moves) {
    e.preventDefault();
    pagesActivateAt(list, Math.min(Math.max(moves[e.key], 0), count - 1), true);
    return true;
  }
  if (e.key === " " && pagesOpenRowLinks(list, pagesVirtualNodeSaid(list, model.slot[at]))) {
    e.preventDefault();
    return true;
  }
  if (e.key === "Enter") {
    e.preventDefault();
    pagesRunRow(pagesVirtualNodeSaid(list, model.slot[at]));
    return true;
  }
  return false;
}

// ── keys on a row list (SPEC 3.6, 4.3) ────────────────────────────────
// shell.js hands a key from inside a `role="listbox"` here; true = handled.
// The right-click key (Shift+F10, the menu key) is the right-click menu's,
// wired with it.
function pagesKey(e) {
  const list = e.target.closest('[role="listbox"]');
  if (!list) return false;
  if (list.pagesModel) return pagesKeyLong(e, list);
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
