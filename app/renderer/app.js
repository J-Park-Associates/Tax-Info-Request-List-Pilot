// Renderer logic — renders tracker state; every action round-trips through
// the Python API so the UI can never disagree with the real scanner.

let paths = null;          // paths of the active engagement
let engagements = [];      // [{name, path}]
let active = null;         // path of the active engagement
let forms = [];            // tax form catalog [{id, label, who, blurb}]
let templatesByForm = {};  // form id -> tailored request template items
let defaultYear = null;    // the tax year a new engagement is for (from the calendar)
let nameIsAuto = true;     // new-client name follows client + year + form until typed
let selectedForm = null;   // form id chosen on the wizard's first page
let templates = [];        // template items for the chosen form
let customItems = [];      // custom rows added in the wizard (plain objects keyed by column)
let editorRows = [];       // the request-list editor's rows (plain objects keyed by column)
let priors = [];           // engagements a new year can roll forward from
let selectedPrior = null;  // path of the prior engagement chosen on page 0

const $ = (id) => document.getElementById(id);

// Every word the app compares or shows comes from the API's vocabulary
// (tracker.api._vocab): statuses, overrides, decisions, defaults, patterns.
// Nothing here is typed twice; the CSS classes are derived from the keys.
let vocab = null;

function statusKey(status) {
  const entry = vocab.statuses.find((s) => s.value === status);
  return entry ? entry.key : vocab.unscanned_key;
}

// Every piece of the page is built from API data as DOM nodes, never as an
// HTML string: a client's file name, a keyword somebody typed into the
// request list or a folder name is text, whatever characters it contains.
// `el` is the one builder.
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "className") node.className = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (typeof value === "boolean") node[key] = value;   // checked, selected, disabled
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : String(child));
  }
  return node;
}

function show(id, nodes) {
  $(id).replaceChildren(...nodes);
}

// How a row's override is said to a person: a set-aside row carries the
// year the API gave the row (state.items[].year, from its own Period), in
// the API's label pattern; a row with no year is said with the bare value.
// The renderer reads nothing out of the Period's text.
function isSetAside(override) {
  return override === vocab.overrides.not_applicable;
}

function overrideLabel(override, year) {
  if (isSetAside(override) && year) return fill(vocab.not_applicable_label, { year });
  return override || "";
}

function chip(item) {
  if (isSetAside(item.manual_override)) {
    return el("span", { className: `chip chip-${vocab.unscanned_key}` },
      overrideLabel(item.manual_override, item.year));
  }
  const label = item.status || vocab.unscanned_label;
  return el("span", { className: `chip chip-${statusKey(item.status)}` }, label);
}

function fill(pattern, values) {
  return pattern.replace(/\{(\w+)\}/g, (_, key) => values[key] ?? "");
}

// The one button label the app owns; the docs that name it are pinned to it.
const SCAN_LABEL = "Sort & Scan";

function toast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.add("hidden"), 6000);
}

async function call(args, payload) {
  const result = await window.tracker.call(args, payload);
  if (result.error) throw new Error(result.error);
  return result;
}

const withEng = (cmd) => (active ? [cmd, vocab.engagement_flag, active] : [cmd]);

// ── rendering ───────────────────────────────────────────────────────────

function ruleTooltip(item) {
  const rules = [];
  if (item.allowed_extensions.length) rules.push(`Types: ${item.allowed_extensions.join(", ")}`);
  if (item.required_keywords.length) rules.push(`Must contain: ${item.required_keywords.join(", ")}`);
  if (item.any_keywords.length) rules.push(`Any of: ${item.any_keywords.join(", ")}`);
  if (item.expected_count > 1) rules.push(fill(vocab.expected_pattern, { n: item.expected_count }));
  return rules.join("  ·  ") || "No content rules";
}

function render(state) {
  paths = state.paths;

  show("rows", state.items.map((item) =>
    el("tr", { title: ruleTooltip(item) },
      el("td", { className: "col-id" }, el("span", { className: "req-id" }, item.identifier)),
      el("td", {},
        el("div", { className: "req-doc" }, item.document),
        el("div", { className: "req-period" },
          item.period,
          item.manual_override ? ` · override: ${overrideLabel(item.manual_override, item.year)}` : ""),
      ),
      el("td", { className: "col-num" },
        `${item.file_count ?? "–"}${item.expected_count > 1 ? ` / ${item.expected_count}` : ""}`),
      el("td", { className: "col-status" }, chip(item),
        // The reason the person gave beside the override: the judgment,
        // not only the fact that the rules were overridden.
        item.override_reason ? el("div", { className: "req-reason", title: item.override_reason }, item.override_reason) : null),
      el("td", { className: "col-recv" }, el("span", { className: "req-recv" }, item.received_date || "—")),
      el("td", {}, el("div", { className: "req-notes", title: item.validation_notes || "" },
        item.validation_notes || "—")),
    )));

  // The one count, from the same summarize() the run log and the reminder use.
  // Nothing waits for anything: the statuses and the request list are both
  // in the record (decisions 103 and 104).
  $("summary").textContent = state.summary ? state.summary.line : "";

  // One line when an ambiguous request holds this client's reminder
  // (decision 115): the API sorted the rows and owns the sentence; the
  // page shows the count and nothing more. The rows themselves are in the
  // table above with their notes.
  const held = state.reminder ? state.reminder.held || [] : [];
  $("reminder-held").textContent = held.length ? fill(vocab.reminder.held_line, { n: held.length }) : "";
  $("reminder-held").classList.toggle("hidden", held.length === 0);

  // The catalog the engagement was cut from, beside its name in the
  // toolbar. It is shown exactly as the record holds it — the catalog's
  // own key is how a person names the return — so the app carries no word
  // of its own for it, and an engagement made before it was recorded shows
  // nothing rather than a guess.
  const engForm = state.engagement ? state.engagement.form : "";
  $("eng-form").textContent = engForm;
  $("eng-form").classList.toggle("hidden", !engForm);

  // The engagement's own page beside it: current, behind, or unknown.
  // Both the label and the word are the API's — the page compares nothing
  // and names no state — and the class is derived from the word, the same
  // way a status chip's is.
  const viewState = state.view ? state.view.state : "";
  const chipEl = $("view-state");
  chipEl.textContent = viewState ? `${vocab.view.label}: ${viewState}` : "";
  chipEl.className = `eng-form view-${viewState}`;
  chipEl.classList.toggle("hidden", !viewState);

  renderMoved(state);
  renderReview(state);
  renderUnfileList(state);
  renderLock(state);
}

// ── A copy that wandered: the three answers, all of them a person's ─────

// A working copy that is not where the record put it (decision 109) gets
// its own card above the review queue, because it is the first question of
// the morning: nothing is guessed, and the person chooses one of three.
// The middle answer is offered only when the copy sits in some request's
// folder — the API says which — because keeping a file where it is means
// nothing in the review folder or loose under Prepared.
function renderMoved(state) {
  const moved = state.moved || [];
  $("moved-card").classList.toggle("hidden", moved.length === 0);
  $("moved-heading").textContent = fill(vocab.review_labels.moved_heading, { n: moved.length });
  $("moved-summary").textContent = vocab.review_labels.moved_summary;
  const choices = state.items.filter((i) => !isSetAside(i.manual_override));
  show("moved-list", moved.map((m) => movedRow(m, choices)));
}

function movedRow(m, choices) {
  const where = m.now || vocab.review_labels.moved_nowhere;
  return el("li", { dataset: { original: m.pbc_location, seq: m.seq } },
    el("span", { className: "r-name" }, m.original_name),
    el("span", { className: "r-why" }, `${m.home} → ${where}`),
    // The picker is the same picker: a person may keep the copy where it
    // is and correct the request in one click, so it starts on the request
    // whose folder holds it.
    m.in_request && el("select", { "aria-label": `Request for ${m.original_name}` },
      choices.map((i) => requestOption(i, m.in_request))),
    m.in_request && el("input", {
      type: "text", className: "r-keyword", placeholder: "keyword to learn (optional)",
      "aria-label": "Keyword to add to the request",
      title: "A word this document contains that others like it will too. Taught to the request so the next one files itself; the editor shows it beside the row.",
    }),
    el("button", { className: "btn btn-primary r-restore" }, vocab.review_labels.restore),
    m.in_request && el("button", { className: "btn r-keep" }, vocab.review_labels.keep),
    el("button", { className: "btn r-review" }, vocab.review_labels.send_to_review),
  );
}

async function restoreMoved(li) {
  const btn = li.querySelector(".r-restore");
  btn.disabled = true;
  try {
    const result = await call(withEng("restore"), {
      original: li.dataset.original,
      seq: Number(li.dataset.seq),
    });
    render(result.state);
    const r = result.restored;
    const notes = [`${r.original_name}: ${r.decision}`, r.reason];
    if (r.scan_note) notes.push(r.scan_note);
    banner(notes.join(". ") + ".", r.parked_as || r.scan_note ? "warn" : "ok");
  } catch (err) {
    await refused(err, btn);
  }
}

// Keeping the copy where it is, is a filing, so it is the filing command,
// with the request the person left the picker on and the keyword they typed.
async function keepMoved(li) {
  const identifier = li.querySelector("select").value;
  if (!identifier) {
    toast("Pick the request this document belongs to first.");
    return;
  }
  const btn = li.querySelector(".r-keep");
  btn.disabled = true;
  try {
    await fileRow(li.dataset.original, identifier, Number(li.dataset.seq), typed(li, ".r-keyword"));
  } catch (err) {
    await refused(err, btn);
  }
}

// And send to review is an unfiling: the copy goes back under the client's
// own name and the row parks.
async function reviewMoved(li) {
  const btn = li.querySelector(".r-review");
  btn.disabled = true;
  try {
    const result = await call(withEng("unfile"), {
      original: li.dataset.original,
      seq: Number(li.dataset.seq),
    });
    render(result.state);
    const u = result.unfiled;
    const notes = [`${u.original_name}: ${u.decision}`];
    if (u.left_filed) notes.push(u.left_filed);
    if (u.scan_note) notes.push(u.scan_note);
    banner(notes.join(". ") + ".", u.left_filed || u.scan_note ? "warn" : "ok");
  } catch (err) {
    await refused(err, btn);
  }
}

// ── Needs review: a person's decision, carried out by the filer ──────────

function renderReview(state) {
  const rows = state.index || [];
  const parked = rows.filter((e) => e.decision === vocab.decisions.needs_review);
  // A document a person said nothing asks for keeps its copy and its row;
  // it is out of the way, not gone, and filing it undoes the decision.
  const dismissed = rows.filter((e) => e.decision === vocab.decisions.dismissed);
  $("review-card").classList.toggle("hidden", parked.length === 0 && dismissed.length === 0);
  const choices = state.items.filter((i) => !isSetAside(i.manual_override));
  const ids = new Set(state.items.map((i) => i.identifier));
  // The triage the API computed, by the same handle every review command
  // takes. Only a parked row has one; a set-aside row is not triaged.
  const triaged = new Map((state.review || []).map((t) => [t.pbc_location, t]));
  show("review-list", parked.map((e) =>
    reviewRow(e, choices, ids, true, triaged.get(e.pbc_location))));
  // The same queue drawn the other way (decision 114), from the same state:
  // both renderings are always drawn and the mode shows one of them.
  renderDeck(state);
  applyReviewMode();
  $("dismissed-card").classList.toggle("hidden", dismissed.length === 0);
  $("dismissed-heading").textContent =
    fill(vocab.review_labels.dismissed_heading, { n: dismissed.length });
  show("dismissed-list", dismissed.map((e) => reviewRow(e, choices, ids, false, null)));
}

// One entry of the picker: the identifier and the document, joined by the
// one separator a reason sentence uses between the same two things.
function requestOption(item, picked) {
  return el("option", { value: item.identifier, selected: item.identifier === picked },
    `${item.identifier}${vocab.triage.identifier_separator}${item.document}`);
}

// One row of the card. The question is the same whether the document is
// waiting or has been set aside - which request does this belong to - so it
// is asked the same way; only an open question offers the two boxes, the
// button that sets a document aside, and the shortlist.
//
// The shortlist is the picker's first entries, in the order the API ranked
// them, and the sentence behind each is listed beneath the row: an <option>
// can carry no second line, and the reason is the whole point - a person
// reads why before they pick. Everything below the divider is every other
// request, because a suggestion is a suggestion and nothing is taken away.
function reviewRow(e, choices, ids, open, triage) {
  const shortlist = (triage && triage.shortlist) || [];
  const suggested = shortlist.map((s) => s.identifier);
  const byId = new Map(choices.map((i) => [i.identifier, i]));
  const best = suggested.map((id) => byId.get(id)).filter(Boolean);
  const rest = choices.filter((i) => !suggested.includes(i.identifier));
  // The picker starts on the best suggestion; failing that, on the router's
  // own first candidate, which is what it started on before there was one.
  const guess = suggested[0] || (e.candidates || [])[0] || "";
  const picked = guess && ids.has(guess) ? guess : "";
  // The row's record version travels with the card and comes back with the
  // click, so the filer judges the decision against the row it was made on.
  return el("li", { dataset: { original: e.pbc_location, seq: e.seq } },
    el("span", { className: "r-name" }, e.original_name),
    el("span", { className: "r-why" }, e.reason),
    el("select", { "aria-label": `Request for ${e.original_name}` },
      el("option", { value: "" }, "Belongs to…"),
      best.length
        ? [el("optgroup", { label: vocab.review_labels.suggested },
            best.map((i) => requestOption(i, picked))),
           el("optgroup", { label: vocab.review_labels.other_requests },
            rest.map((i) => requestOption(i, picked)))]
        : rest.map((i) => requestOption(i, picked)),
    ),
    open && el("ul", { className: "r-reasons" },
      shortlist.length
        ? shortlist.map((s) => el("li", {}, s.reason))
        : el("li", { className: "r-nothing" }, vocab.triage.nothing_suggested),
      // A set-aside row the evidence points at is named, never offered:
      // the API's sentence, with the row's year label, one line each.
      ((triage && triage.set_aside) || []).map((s) =>
        el("li", { className: "r-set-aside" }, fill(vocab.triage.set_aside_note, s)))),
    open && el("input", {
      type: "text", className: "r-keyword", placeholder: "keyword to learn (optional)",
      "aria-label": "Keyword to add to the request",
      title: "A word this document contains that others like it will too. Taught to the request so the next one files itself; the editor shows it beside the row.",
    }),
    open && el("input", {
      type: "text", className: "r-note", placeholder: vocab.review_labels.dismiss_note,
      "aria-label": vocab.review_labels.dismiss_note,
    }),
    el("button", { className: "btn btn-primary r-file" },
      open ? vocab.review_labels.file : vocab.review_labels.file_anyway),
    open && el("button", { className: "btn r-dismiss" }, vocab.review_labels.dismiss),
  );
}

function typed(li, className) {
  const box = li.querySelector(className);
  return box ? box.value.trim() : "";
}

// The one place a document is filed. The list's button, the card's Accept
// and the answer that leaves a moved copy where it now sits are the same
// decision said three ways, so they are one call: the same command, the same
// record-version rule (decision 112), the same sentences afterwards. Two
// call sites could drift apart - one cannot, and a guard in
// tests/test_single_source.py keeps it the only one.
async function fileRow(original, identifier, seq, keyword) {
  const result = await call(withEng("assign"), { original, identifier, keyword, seq });
  render(result.state);
  const a = result.assigned;
  const notes = [`${a.original_name} filed as ${a.filed_as}`];
  if (a.keyword) notes.push(`"${a.keyword}" added to ${a.identifier} so the next one files itself`);
  if (a.keyword_note) notes.push(a.keyword_note);
  if (a.left_in_review) notes.push(a.left_in_review);
  // What the record now says about a pick the evidence did not point at:
  // the API's sentence, shown as it stands.
  if (a.overrode_shortlist) notes.push(a.overrode_shortlist);
  if (a.scan_note) notes.push(a.scan_note);
  banner(notes.join(". ") + ".",
    a.keyword_note || a.left_in_review || a.overrode_shortlist || a.scan_note ? "warn" : "ok");
}

async function assignParked(li) {
  const identifier = li.querySelector("select").value;
  if (!identifier) {
    toast("Pick the request this document belongs to first.");
    return;
  }
  const btn = li.querySelector(".r-file");
  btn.disabled = true;
  try {
    await fileRow(li.dataset.original, identifier, Number(li.dataset.seq), typed(li, ".r-keyword"));
  } catch (err) {
    await refused(err, btn);
  }
}

// A refusal a person has to look at again: the sentence is the API's, and
// the card is redrawn from the record so what they see next is what the
// record now holds rather than the row they acted on.
async function refused(err, btn) {
  toast(err.message);
  btn.disabled = false;
  await refresh();
}

// ── The same queue, one card at a time (decision 114) ────────────────────

// In March one client can hold a dozen parked rows, and the list makes a
// person read every row's whole picker to take the easy calls. The cards are
// a second rendering of state.review - never a second state: the deck is the
// API's order, and the only thing the page holds of its own is which rows a
// person sent to the back and which rendering they are on. After every
// action the deck is rebuilt from the state the API just returned, so a row
// filed or set aside anywhere else simply leaves it and the count is always
// the queue's.

// Which rendering the person is on, remembered on this machine alone. It is
// a preference and not a fact about the engagement, so nothing about it is
// recorded (decision 83), and the key is a key - no one reads it - so the
// renderer may type it where it may type no word. A store that refuses to
// answer (a locked profile, a private window) leaves the app on the list.
const REVIEW_MODE_STORAGE_KEY = "jpa.tracker.review-mode";
const MODE_LIST = "list";
const MODE_CARDS = "cards";

let reviewMode = storedReviewMode();
let skipped = [];          // pbc_locations sent to the back of the deck
let deckState = null;      // the state the deck was last drawn from

function storedReviewMode() {
  try {
    return localStorage.getItem(REVIEW_MODE_STORAGE_KEY) === MODE_CARDS ? MODE_CARDS : MODE_LIST;
  } catch (err) {
    return MODE_LIST;
  }
}

function setReviewMode(mode) {
  reviewMode = mode === MODE_CARDS ? MODE_CARDS : MODE_LIST;
  try {
    localStorage.setItem(REVIEW_MODE_STORAGE_KEY, reviewMode);
  } catch (err) {
    // A machine that will not remember it still shows what was asked for.
  }
  applyReviewMode();
}

// Both renderings are drawn; this shows one of them and says which button
// is the one in force.
function applyReviewMode() {
  const cards = reviewMode === MODE_CARDS;
  $("review-list").classList.toggle("hidden", cards);
  $("review-deck").classList.toggle("hidden", !cards);
  $("review-mode-cards").classList.toggle("on", cards);
  $("review-mode-list").classList.toggle("on", !cards);
  $("review-mode-cards").setAttribute("aria-pressed", String(cards));
  $("review-mode-list").setAttribute("aria-pressed", String(!cards));
}

// The deck: the API's order with the sent-back rows after it, in the order
// they were sent back. A row that has left the queue leaves the skip list
// with it, so nothing here outlives the row it was about.
function deckOrder(queue) {
  const here = new Set(queue.map((t) => t.pbc_location));
  skipped = skipped.filter((location) => here.has(location));
  const back = new Set(skipped);
  return [
    ...queue.filter((t) => !back.has(t.pbc_location)),
    ...skipped.map((location) => queue.find((t) => t.pbc_location === location)),
  ];
}

function renderDeck(state) {
  deckState = state;
  const rows = new Map((state.index || []).map((e) => [e.pbc_location, e]));
  const queue = (state.review || []).filter((t) => rows.has(t.pbc_location));
  const deck = deckOrder(queue);
  // The card on top is the one that gets answered; the position says how far
  // into the deck the person has walked, and the total is the queue's own -
  // sending a card to the back never changes it.
  const place = deck.length ? (skipped.length % deck.length) + 1 : 0;
  show("review-deck", deck.length
    ? [deckCard(deck[0], rows.get(deck[0].pbc_location), place, deck.length)]
    : []);
}

// One card: the document, why it parked, the top suggestion with the
// sentence behind it, the rows the evidence points at that are set aside,
// and the three answers. A card with nothing suggested has no Accept -
// there is nothing to accept - and says so in the API's words.
function deckCard(t, row, place, total) {
  const best = (t.shortlist || [])[0];
  // The suggestion Accept files to travels on the card, as the row's record
  // version does: what comes back with the click is what was on the screen.
  const identified = best ? { identifier: best.identifier } : {};
  return el("div", { className: "deck-card card",
                     dataset: { original: t.pbc_location, seq: t.seq, ...identified } },
    el("span", { className: "r-name" }, t.original_name),
    el("span", { className: "r-why" }, row ? row.reason : ""),
    best && el("span", { className: "deck-suggested" }, vocab.review_labels.suggested),
    el("ul", { className: "r-reasons" },
      best
        ? el("li", {}, best.reason)
        : el("li", { className: "r-nothing" }, vocab.triage.nothing_suggested),
      (t.set_aside || []).map((s) =>
        el("li", { className: "r-set-aside" }, fill(vocab.triage.set_aside_note, s)))),
    el("input", {
      type: "text", className: "r-keyword", placeholder: "keyword to learn (optional)",
      "aria-label": "Keyword to add to the request",
      title: "A word this document contains that others like it will too. Taught to the request so the next one files itself; the editor shows it beside the row.",
    }),
    el("span", { className: "deck-position" },
      fill(vocab.review_labels.card_position, { n: place, total })),
    best && el("button", { className: "btn btn-primary c-accept" }, vocab.review_labels.accept),
    el("button", { className: "btn c-open" }, vocab.review_labels.open_in_list),
    el("button", { className: "btn c-skip" }, vocab.review_labels.skip),
  );
}

// Accept is File it: the same call, made with the suggestion the card is
// showing and the keyword the person typed on it.
async function acceptCard(card) {
  const identifier = card.dataset.identifier;
  const btn = card.querySelector(".c-accept");
  btn.disabled = true;
  try {
    await fileRow(card.dataset.original, identifier, Number(card.dataset.seq),
                  typed(card, ".r-keyword"));
  } catch (err) {
    await refused(err, btn);
  }
}

// The hard calls belong to the full picker, where every request is offered
// (decision 84): the card hands the row over rather than growing a picker of
// its own.
function openCardInList(card) {
  setReviewMode(MODE_LIST);
  const wanted = card.dataset.original;
  for (const li of $("review-list").children) {
    const hit = li.dataset.original === wanted;
    li.classList.toggle("focused", hit);
    if (hit) li.scrollIntoView({ block: "center" });
  }
}

// Skip is a reorder and nothing else: the card goes to the back, the queue
// is the same length, and nothing is sent anywhere.
function skipCard(card) {
  const location = card.dataset.original;
  skipped = [...skipped.filter((one) => one !== location), location];
  if (deckState) renderDeck(deckState);
}

// ── The way back, so nobody corrects a filing in Explorer ────────────────

// Folded away by default. It is a list of what is already right, there for
// the one row that is not, and the index is the only thing that knows where
// a working copy went: a correction made in Explorer is one it never learns.
// One original can have a copy in more than one request folder (a page that
// carried two forms), so each destination is named; Unfile still takes the
// one original, because the row is one row and every copy goes back with it.
function renderUnfileList(state) {
  const filed = (state.index || []).filter((e) => e.decision === vocab.decisions.filed);
  $("filed-card").classList.toggle("hidden", filed.length === 0);
  $("filed-heading").textContent = fill(vocab.review_labels.filed_heading, { n: filed.length });
  show("filed-list", filed.map((e) =>
    el("li", { dataset: { original: e.pbc_location, seq: e.seq } },
      el("span", { className: "r-name" }, e.original_name),
      el("span", { className: "r-why" }, `${e.identifier} — ${e.filed_names.join(", ")}`),
      el("input", {
        type: "text", className: "r-note", placeholder: vocab.review_labels.unfile_note,
        "aria-label": vocab.review_labels.unfile_note,
      }),
      el("button", { className: "btn r-unfile" }, vocab.review_labels.unfile),
    )));
}

// Nothing is deleted and nothing is moved: the row is rewritten, so the
// banner says what the row now reads and the file is still where it was.
async function dismissParked(li) {
  const btn = li.querySelector(".r-dismiss");
  btn.disabled = true;
  try {
    const result = await call(withEng("dismiss"), {
      original: li.dataset.original,
      note: typed(li, ".r-note"),
      seq: Number(li.dataset.seq),
    });
    render(result.state);
    const d = result.dismissed;
    const notes = [`${d.original_name}: ${d.decision}`, d.reason];
    banner(notes.join(". ") + ".", "ok");
  } catch (err) {
    await refused(err, btn);
  }
}

// The copy goes back under the client's own name and the request reverts in
// the same breath, so the banner says where the document is now, not what
// it stopped being.
async function unfileDocument(li) {
  const btn = li.querySelector(".r-unfile");
  btn.disabled = true;
  try {
    const result = await call(withEng("unfile"), {
      original: li.dataset.original,
      note: typed(li, ".r-note"),
      seq: Number(li.dataset.seq),
    });
    render(result.state);
    const u = result.unfiled;
    const notes = [`${u.original_name}: ${u.decision}`];
    if (u.left_filed) notes.push(u.left_filed);
    if (u.scan_note) notes.push(u.scan_note);
    banner(notes.join(". ") + ".", u.left_filed || u.scan_note ? "warn" : "ok");
  } catch (err) {
    await refused(err, btn);
  }
}

function renderEngagements() {
  show("eng-select", engagements.map((e) =>
    el("option", { value: e.path, selected: e.path === active }, e.name)));
}

function banner(text, cls) {
  const el = $("banner");
  el.textContent = text;
  el.className = `banner ${cls}${text.includes("\n") ? " multi" : ""}`;
}

// ── the engagement lock, shown instead of left as a mystery file ─────────

function renderLock(state) {
  const lock = state.lock;
  const notice = $("lock-notice");
  notice.classList.toggle("hidden", !lock);
  if (!lock) return;
  const since = lock.started ? ` started at ${lock.started.replace("T", " ").slice(0, 16)}` : "";
  if (lock.stale) {
    $("lock-text").textContent =
      `A run${since} left its lock behind (${lock.age_minutes} min old) — it has most likely died. The next ${SCAN_LABEL} or scheduled pass will replace it; clear it here to tidy up now.`;
    notice.className = "banner warn";
    $("btn-unlock").classList.remove("hidden");
  } else {
    $("lock-text").textContent =
      `A run${since} is still going (${lock.age_minutes} min). ${SCAN_LABEL} will wait for it; a lock older than ${lock.stale_after_minutes} minutes can be cleared here.`;
    notice.className = "banner ok";
    $("btn-unlock").classList.add("hidden");
  }
}

async function clearLock() {
  const btn = $("btn-unlock");
  btn.disabled = true;
  try {
    const result = await call(withEng("unlock"));
    render(result.state);
    banner(`Stale lock cleared (${result.age_minutes} min old). Run ${SCAN_LABEL} when ready.`, "ok");
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
}

// ── data flows ──────────────────────────────────────────────────────────

// Everything static on the page that names a Python-owned fact is filled
// here, once, from the vocabulary: the product, the rules, the folder the
// originals go to, the year bounds, the example root, the button label.
function applyVocabulary() {
  document.title = vocab.firm ? `${vocab.product} — ${vocab.firm}` : vocab.product;
  $("brand-product").textContent = vocab.product;
  $("scan-label").textContent = SCAN_LABEL;
  $("view-label").textContent = vocab.view.open;
  $("edit-label").textContent = vocab.editor.open;
  // The two renderings of the review queue are named by the API too
  // (decision 114); the page carries no word for either of them.
  $("review-mode-cards").textContent = vocab.review_labels.card_mode;
  $("review-mode-list").textContent = vocab.review_labels.list_mode;
  $("root-input").placeholder = `e.g. ${vocab.example_root}`;
  // The firm's own telephone number, beside its name: the label, the
  // sentence under it and the number itself are all Python's.
  $("phone-input").placeholder = `${vocab.settings.phone_label} — ${vocab.settings.phone_help}`;
  $("phone-input").title = vocab.settings.phone_help;
  $("phone-input").setAttribute("aria-label", vocab.settings.phone_label);
  $("ro-include-note").textContent =
    "Also add checklist rows this client has never had (otherwise they are offered, once, when the rollover is done, and added later in the editor)";
  for (const id of ["ro-year", "ne-year"]) {
    $(id).min = vocab.year_min;
    $(id).max = vocab.year_max;
    $(id).title = vocab.year_note;
  }
  $("ro-client").placeholder = vocab.origin_prior;
  $("cu-add").textContent = vocab.editor.add_row;
  // The editor's every word: the two titles, the buttons, the paste hint.
  $("ed-title").textContent = vocab.editor.title;
  $("ed-engagement-title").textContent = vocab.editor.engagement_title;
  $("ed-list-title").textContent = vocab.editor.title;
  $("ed-add").textContent = vocab.editor.add_row;
  $("ed-paste-title").textContent = vocab.editor.paste;
  $("ed-paste-hint").textContent = vocab.editor.paste_hint;
  $("ed-paste-btn").textContent = vocab.editor.paste;
  $("ed-cancel").textContent = vocab.editor.cancel;
  $("ed-save").textContent = vocab.editor.save;
  const cards = document.querySelectorAll("#assurances .assure div");
  vocab.rules.forEach((rule, i) => {
    if (!cards[i]) return;
    cards[i].querySelector("strong").textContent = rule.headline;
    cards[i].querySelector("span").textContent = rule.detail;
  });
}

let clientsRoot = "";      // the one folder every engagement sits under

async function loadEngagements(preferPath) {
  const listed = await call(["list"]);
  vocab = listed.vocab;
  applyVocabulary();
  engagements = listed.engagements;
  clientsRoot = listed.root || "";
  $("setup-card").classList.toggle("hidden", !listed.needs_root);
  if (listed.needs_root) {
    $("root-input").value = clientsRoot;
    $("firm-input").value = vocab.firm || "";
    $("phone-input").value = vocab.settings.phone || "";
    $("setup-note").textContent = clientsRoot
      ? `${clientsRoot} is not a folder any more. Point the app at the right one.`
      : "The scheduled job walks this same folder, so this is the only place it is set.";
    return false;
  }
  if (!engagements.length) return false;
  active =
    (preferPath && engagements.find((e) => e.path === preferPath)?.path) ||
    (active && engagements.find((e) => e.path === active)?.path) ||
    engagements[0].path;
  renderEngagements();
  return true;
}

async function refresh(preferPath) {
  try {
    if (!(await loadEngagements(preferPath))) {
      if (!$("setup-card").classList.contains("hidden")) return;   // waiting for the folder
      banner(`No engagements under ${clientsRoot} yet — click ${$("btn-new").textContent.trim()} to create the first.`, "ok");
      show("rows", []);
      return;
    }
    render(await call(withEng("state")));
  } catch (err) {
    toast(err.message);
  }
}

async function saveRoot() {
  const btn = $("btn-save-root");
  btn.disabled = true;
  try {
    const result = await call(["set-root"], {
      root: $("root-input").value.trim(),
      firm: $("firm-input").value.trim(),
      phone: $("phone-input").value.trim(),
    });
    banner(`Clients folder set to ${result.root} (written to ${result.settings_path}).`, "ok");
    await refresh();
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
}

async function installSchedule() {
  const sched = vocab.schedule;
  if (!confirm(`Register the daily job with Task Scheduler for this clients folder?\n\nIt files, scans and (on ${sched.draft_day}s) drafts reminders. Nothing is ever sent.`)) return;
  const btn = $("btn-schedule");
  btn.disabled = true;
  try {
    const result = await call(["install-schedule"], {});
    if (result.installed) {
      banner(`Scheduled: every day from ${result.start}, repeating every ${result.every} minutes, over ${result.root}. Re-run this to change it.`, "ok");
    } else {
      banner(`Not Windows here. On the scheduling machine run:  ${result.command.join(" ")}`, "warn");
    }
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
}

async function runScan() {
  const btn = $("btn-scan");
  btn.disabled = true;
  btn.classList.add("spinning");
  $("scan-label").textContent = "Scanning…";
  try {
    const result = await call(withEng("scan"));
    render(result.state);
    const run = result.run;
    const summary = result.state.summary ? result.state.summary.line : "";
    if (run.skipped) {
      banner(`Nothing done: ${run.skipped}.`, "warn");
      return;
    }
    if (run.error) {
      banner(`The pass reported a problem: ${run.error}`, "err");
      return;
    }
    const did = [`filed ${run.filed}`];
    if (run.review) did.push(`${run.review} to review`);
    if (run.waiting) did.push(`${run.waiting} still syncing`);
    const problems = [];
    if (run.file_errors.length) problems.push(`${run.file_errors.length} file(s) could not be sorted`);
    const lines = [`Pass complete — ${did.join(", ")}.   ${summary}`];
    if (problems.length) lines.push(`But ${problems.join("; ")}.`);
    for (const w of run.warnings) lines.push(`• ${w}`);
    banner(lines.join("\n"), problems.length ? "warn" : run.warnings.length ? "warn" : "ok");
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
    btn.classList.remove("spinning");
    $("scan-label").textContent = SCAN_LABEL;
  }
}

// ── New Engagement wizard ───────────────────────────────────────────────
// Opens on the returning-client page — rolling last year forward is the
// default action. Behind it: pick a tax form type, then trim its list.

async function openWizard() {
  try {
    if (!forms.length) {
      const result = await call(["templates"]);
      forms = result.forms;
      templatesByForm = result.templates;
      defaultYear = result.default_year || null;
    }
    priors = (await call(["priors"])).priors;
  } catch (err) {
    toast(err.message);
    return;
  }
  selectedForm = null;
  const open = priors.filter((p) => !p.superseded_by);
  selectedPrior = open.length ? open[open.length - 1].path : priors.length ? priors[priors.length - 1].path : null;
  renderPriorPage();
  renderFormGrid();
  showStep("prior");
  $("modal").classList.remove("hidden");
}

function showStep(step) {
  $("wiz-prior").classList.toggle("hidden", step !== "prior");
  $("wiz-form").classList.toggle("hidden", step !== "form");
  $("wiz-items").classList.toggle("hidden", step !== "items");
}

// ── page 0: returning client ────────────────────────────────────────────

function priorMeta(p) {
  const bits = [];
  if (p.superseded_by) bits.push(`already rolled forward into ${p.superseded_by}`);
  if (p.year) bits.push(fill(vocab.period_pattern, { year: p.year }));
  bits.push(`${p.requests} request${p.requests === 1 ? "" : "s"}`);
  if (p.requests) bits.push(`${p.received} received`);
  return bits.join(" · ");
}

function renderPriorPage() {
  show("prior-list", priors.map((p) =>
    el("label", { className: "prior-item" },
      el("input", { type: "radio", name: "prior", value: p.path, checked: p.path === selectedPrior }),
      el("span", { className: "prior-name" }, p.name),
      el("span", { className: "prior-meta" }, priorMeta(p)),
    )));
  $("prior-list").classList.toggle("hidden", priors.length === 0);
  $("prior-empty").classList.toggle("hidden", priors.length > 0);
  $("ro-create").disabled = priors.length === 0;

  show("ro-form", [
    el("option", { value: "" }, "No template — carry last year's list as it is"),
    forms.map((f) => el("option", { value: f.id }, `${f.label} · ${f.who}`)),
  ]);
  syncPriorDefaults();
}

function syncPriorDefaults() {
  const prior = priors.find((p) => p.path === selectedPrior);
  const year = prior && prior.next_year ? prior.next_year : "";
  $("ro-year").value = year;
  $("ro-name").value = "";
  $("ro-client").value = prior ? prior.client || "" : "";
  $("ro-link").value = "";
  $("ro-due").value = "";
  $("ro-name").placeholder = prior
    ? fill(vocab.rollover_name_pattern, { prior: prior.name, year: year || vocab.unknown_year_label })
    : "defaults to last year's name and the new year";
}

async function rollForward() {
  if (!selectedPrior) {
    toast("Pick the engagement to roll forward, or start from a form template.");
    return;
  }
  const btn = $("ro-create");
  btn.disabled = true;
  try {
    const result = await call(["rollover"], {
      prior: selectedPrior,
      name: $("ro-name").value.trim(),
      form: $("ro-form").value,
      year: Number($("ro-year").value) || null,
      include_new: $("ro-include-new").checked,
      client: $("ro-client").value.trim(),
      link: $("ro-link").value.trim(),
      due: $("ro-due").value,
    });
    $("modal").classList.add("hidden");
    await refresh(result.state.paths.engagement);
    const r = result.rollover;
    // The reply carries every rolled row with its origin; last year's
    // set-aside rows are grouped on the API's origin value and said in
    // the API's one line, apart from the carried count.
    const setAside = r.carried.filter((c) => c.origin === vocab.origin_not_applicable);
    const carried = r.carried.length - setAside.length;
    const parts = [`${carried} request(s) carried from ${r.prior}`];
    if (setAside.length) parts.push(fill(vocab.not_applicable_carried, { n: setAside.length }));
    // The offers and last year's unfiled files are said here, once: there
    // is no sheet to point at, and an offer a person wants is added in the
    // editor (decision 104).
    if (r.offered.length) {
      const offered = r.offered.map((o) => `${o.identifier}${vocab.triage.identifier_separator}${o.document}`).join(", ");
      parts.push(`${r.offered.length} template row(s) offered but not added: ${offered}`);
    }
    if (r.unfiled_last_year.length) parts.push(`${r.unfiled_last_year.length} file(s) sent last year were never filed`);
    banner(`Engagement "${result.created}" rolled forward: ${parts.join("; ")}.`, "ok");
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
}

function renderFormGrid() {
  show("form-grid", forms.map((f) =>
    el("button", { className: "form-card", dataset: { form: f.id } },
      el("span", { className: "form-num" }, f.label),
      el("span", { className: "form-who" }, f.who),
      el("span", { className: "form-blurb" }, f.blurb),
    )));
}

function chooseForm(formId) {
  const form = forms.find((f) => f.id === formId);
  if (!form) return;
  selectedForm = formId;
  templates = templatesByForm[formId] || [];
  customItems = [];
  $("items-title").textContent = `New ${form.label} Engagement`;
  $("chosen-form").textContent = `${form.label} · ${form.who}`;
  $("tmpl-head-label").textContent = `${form.label} request list — tick what applies`;
  $("ne-name").value = "";
  nameIsAuto = true;
  $("ne-year").value = defaultYear || "";
  $("ne-name").placeholder = fill(vocab.name_pattern, { client: vocab.new_client_placeholder, year: $("ne-year").value, form: form.label });
  $("ne-client").value = "";
  $("ne-link").value = "";
  $("ne-due").value = "";
  renderTemplateList();
  renderCustomRows();
  showStep("items");
  $("ne-client").focus();
}

// The engagement name is what the client, the year and the form already
// say. It follows the client field until the user types a name of their own.
function syncNameDefault() {
  if (!nameIsAuto) return;
  const client = $("ne-client").value.trim();
  const form = forms.find((f) => f.id === selectedForm);
  const year = Number($("ne-year").value) || defaultYear;
  $("ne-name").value = client
    ? fill(vocab.name_pattern, { client, year, form: form ? form.label : "" }).replace(/\s+/g, " ").trim()
    : "";
}

function templateSummary(t) {
  const bits = [];
  if (t.extensions) bits.push(t.extensions);
  if (t.required_keywords) bits.push(`must contain "${t.required_keywords}"`);
  if (t.any_keywords) bits.push(`any of: ${t.any_keywords}`);
  if (t.expected_count > 1) bits.push(fill(vocab.expected_pattern, { n: t.expected_count }));
  return bits.join(" · ");
}

function renderTemplateList() {
  show("tmpl-list", templates.map((t, i) =>
    el("label", { className: "tmpl-item" },
      el("input", { type: "checkbox", dataset: { index: String(i) }, checked: Boolean(t.core) }),
      el("span", { className: "tmpl-id" }, t.identifier),
      el("span", { className: "tmpl-doc" }, t.document, " ",
        el("span", { className: "tmpl-rules" }, templateSummary(t))),
    )));
}

// ── the one row component: the wizard's custom rows and the editor's ─────

// A column of the request list, as the API describes it: its key in the
// record, its heading, and the sentence under the heading. The wizard shows
// three of the eleven; the editor shows them all.
function columnsByKey(keys) {
  return keys.map((key) => vocab.columns.find((c) => c.key === key)).filter(Boolean);
}

// One input for one cell. The two numbers take their floor from the
// vocabulary (never typed here); the override is a pick of the API's two
// values or nothing; everything else is text. Typing writes straight into
// the row object, so the rows are always what the inputs say.
function cellInput(row, column, onChange) {
  const key = column.key;
  const minimum = vocab.editor.minimums[key];
  if (key === "manual_override") {
    const select = el("select", { "aria-label": column.label },
      el("option", { value: "", selected: !row[key] }, ""),
      Object.values(vocab.overrides).map((value) =>
        el("option", { value, selected: row[key] === value }, value)));
    select.addEventListener("change", () => { row[key] = select.value; onChange(); });
    return select;
  }
  if (key === "override_reason") {
    // A pick from the API's reasons, and a box for the person's own words
    // when they pick the last entry. What is saved is the text: one of
    // the reasons, or what was typed - never the word that opened the box.
    const current = row[key] || "";
    const listed = vocab.override_reasons.includes(current);
    const ownWords = vocab.override_reason_other;
    const select = el("select", { "aria-label": column.label, title: column.help },
      el("option", { value: "", selected: !current }, ""),
      vocab.override_reasons.map((value) =>
        el("option", { value, selected: current === value }, value)),
      el("option", { value: ownWords, selected: Boolean(current) && !listed }, ownWords));
    const typed = el("input", {
      type: "text", className: "ed-reason-typed", value: listed ? "" : current,
      "aria-label": `${column.label} (${ownWords})`, placeholder: ownWords,
    });
    typed.classList.toggle("hidden", !(Boolean(current) && !listed));
    select.addEventListener("change", () => {
      const picked = select.value;
      const typing = picked === ownWords;
      typed.classList.toggle("hidden", !typing);
      row[key] = typing ? typed.value : picked;
      if (typing) typed.focus();
      onChange();
    });
    typed.addEventListener("input", () => { row[key] = typed.value; onChange(); });
    return el("span", { className: "ed-reason" }, select, typed);
  }
  const input = el("input", {
    type: minimum === undefined ? "text" : "number",
    value: row[key] === undefined || row[key] === null ? "" : String(row[key]),
    "aria-label": column.label,
    title: column.help,
  });
  if (minimum !== undefined) input.min = minimum;
  input.addEventListener("input", () => { row[key] = input.value; onChange(); });
  return input;
}

// The rows of a request list as a table of inputs: one column per entry of
// `columns`, a note for the keywords a filing taught the row (the editor
// shows them as taught, never as typed), and a Remove button. Renders from
// plain objects keyed by column key; `onChange(rows)` is told about every
// edit, and `onRemove(index)` about a removed row. `keyed` shows each row's
// identifier as fixed text (the wizard assigns them); the editor passes
// the identifier as one of its columns instead, typed like the rest.
function requestRows(container, rows, { columns, onChange, onRemove, learned = {}, keyed = true }) {
  const head = el("tr", {},
    keyed ? el("th", { className: "ed-id" }, columnsByKey(["identifier"])[0].label) : null,
    columns.map((c) => el("th", { title: c.help }, c.label)),
    Object.keys(learned).length ? el("th", {}, "") : null,
    el("th", {}, ""));
  const body = rows.map((row, index) => el("tr", {},
    keyed ? el("td", { className: "ed-id" }, el("span", { className: "req-id" }, row.identifier)) : null,
    columns.map((c) => el("td", { className: `ed-${c.key}` }, cellInput(row, c, () => onChange(rows)))),
    Object.keys(learned).length
      ? el("td", { className: "ed-learned" },
          learned[row.identifier] && learned[row.identifier].length
            ? fill(vocab.editor.learned_note, { keywords: learned[row.identifier].join(", ") })
            : "")
      : null,
    el("td", { className: "ed-remove" },
      el("button", { className: "btn btn-small", dataset: { index: String(index) }, "aria-label": `${vocab.editor.remove_row} ${row.identifier || ""}` },
        vocab.editor.remove_row)),
  ));
  const table = el("table", { className: "editor-table" }, el("thead", {}, head), el("tbody", {}, body));
  table.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-index]");
    if (btn) onRemove(Number(btn.dataset.index));
  });
  table.addEventListener("keydown", (e) => {
    // Enter on the last row adds another, the way the wizard always did.
    if (e.key === "Enter" && e.target.closest("tr") === table.querySelector("tbody tr:last-child")) {
      e.preventDefault();
      container.dispatchEvent(new CustomEvent("addrow", { bubbles: true }));
    }
  });
  container.replaceChildren(table);
}

// ── the wizard's custom requests ────────────────────────────────────────

// Blank fields are sent blank: the catalog's item_from_spec() fills the
// file types and the keyword (the document name) by the one rule, and the
// editor shows the result afterwards.
const CUSTOM_COLUMNS = ["document", "allowed_extensions", "required_keywords"];

function customIdentifier(position) {
  return `X${String(position).padStart(2, "0")}`;
}

function renumberCustom() {
  customItems.forEach((c, i) => (c.identifier = customIdentifier(i + 1)));
}

function renderCustomRows() {
  requestRows($("cu-rows"), customItems, {
    columns: columnsByKey(CUSTOM_COLUMNS),
    onChange: () => {},
    onRemove: (index) => {
      customItems.splice(index, 1);
      renumberCustom();
      renderCustomRows();
    },
  });
}

function addCustomItem() {
  customItems.push({ identifier: "", document: "", allowed_extensions: "", required_keywords: "" });
  renumberCustom();
  renderCustomRows();
  const inputs = $("cu-rows").querySelectorAll("tbody tr:last-child input");
  if (inputs.length) inputs[0].focus();
}

async function createEngagement() {
  const checked = [...$("tmpl-list").querySelectorAll("input:checked")]
    .map((box) => templates[Number(box.dataset.index)]);
  if (customItems.some((c) => !String(c.document || "").trim())) {
    toast("Give each custom request a document name first.");
    return;
  }
  const items = [...checked, ...customItems];
  if (!items.length) {
    toast("Select at least one request item.");
    return;
  }
  const btn = $("ne-create");
  btn.disabled = true;
  try {
    const result = await call(["create"], {
      name: $("ne-name").value.trim(),
      form: selectedForm,
      items,
      client: $("ne-client").value.trim(),
      link: $("ne-link").value.trim(),
      due: $("ne-due").value,
      year: Number($("ne-year").value) || null,
    });
    $("modal").classList.add("hidden");
    await refresh(result.state.paths.engagement);
    banner(
      `Engagement "${result.created}" created — ${items.length} request folder(s) scaffolded, client README generated. Open the Client Folder to show it.`,
      "ok"
    );
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
}

// ── the request-list editor (decision 104) ──────────────────────────────
// The list and the engagement's details are edited here and nowhere else.
// Rows open from state.rules - the person's rows as stored, without the
// keywords filings taught, which are shown beside each row as taught - and
// a save is one `edit` call: refused with the row and the column named, or
// recorded as one event of exactly what changed.

let editorState = null;    // the state the editor opened on

function editorRow(rule) {
  return {
    identifier: rule.identifier,
    document: rule.document,
    period: rule.period,
    expected_count: rule.expected_count,
    allowed_extensions: rule.allowed_extensions.length
      ? rule.allowed_extensions.join(", ") : vocab.editor.any_extension,
    min_size_kb: rule.min_size_kb,
    required_keywords: rule.required_keywords.join(", "),
    any_keywords: rule.any_keywords.join(", "),
    // A blank pattern that is not derived is the no-date-check mark the person
    // typed: shown and sent back as that mark, the round trip the file types column makes.
    date_pattern: rule.date_pattern_derived ? "" : (rule.date_pattern || vocab.editor.no_date_check),
    manual_override: rule.manual_override,
    override_reason: rule.override_reason || "",
  };
}

function blankEditorRow() {
  return Object.fromEntries(vocab.columns.map((c) => [c.key, ""]));
}

// The year a row's Period gives, as the API computed it for the row the
// editor opened on (state.items[].year); a row typed since has none, and
// is labelled with the bare value until it is saved and read back.
function editorRowYear(row) {
  const known = ((editorState && editorState.items) || []).find((i) => i.identifier === row.identifier);
  return known ? known.year : null;
}

function editorGroupKey(row) {
  return isSetAside(row.manual_override) ? overrideLabel(row.manual_override, editorRowYear(row)) : "";
}

// The active rows in one table; the rows set aside as not applicable in a
// folded group per label below it, headed as the Status Report heads its
// own folded block. Removal is by the row's place in editorRows whichever
// group it is drawn in, and a row whose override changes moves between
// the groups before anything is saved.
function renderEditorRows() {
  const grouping = () => editorRows.map(editorGroupKey).join("\u0000");
  const drawn = grouping();
  const options = (rows) => ({
    columns: vocab.columns,
    keyed: false,
    learned: (editorState && editorState.learned) || {},
    onChange: () => { if (grouping() !== drawn) renderEditorRows(); },
    onRemove: (index) => {
      editorRows.splice(editorRows.indexOf(rows[index]), 1);
      renderEditorRows();
    },
  });
  const active = editorRows.filter((row) => !editorGroupKey(row));
  const groups = new Map();
  for (const row of editorRows) {
    const key = editorGroupKey(row);
    if (key) groups.set(key, [...(groups.get(key) || []), row]);
  }
  const activeBox = el("div", { className: "editor-rows" });
  requestRows(activeBox, active, options(active));
  const folded = [...groups.entries()].map(([label, rows]) => {
    const box = el("div", { className: "editor-rows" });
    requestRows(box, rows, options(rows));
    return el("details", { className: "ed-set-aside" },
      el("summary", {}, fill(vocab.editor.set_aside_heading, { label, n: rows.length })), box);
  });
  $("ed-rows").replaceChildren(activeBox, ...folded);
}

function addEditorRow() {
  editorRows.push(blankEditorRow());
  renderEditorRows();
  const inputs = $("ed-rows").querySelectorAll("tbody tr:last-child input");
  if (inputs.length) inputs[0].focus();
}

// The engagement's details, laid out from the vocabulary: a text box, a
// date or a yes/no box for each field a person may change, and the value
// as plain text for the ones they may not (the folder is the name; the
// rollover writes Rolled From; the form was recorded once). Which fields
// take a date box is Python's answer too (vocab.editor.date_fields), so
// the page names no detail of its own.
function renderEngagementFields(info) {
  show("ed-fields", vocab.editor.engagement_fields
    .filter((f) => f.key !== "name")
    .map((f) => {
      const value = info[f.key];
      if (!f.editable) {
        return el("label", { className: "field" }, el("span", {}, f.label),
          el("span", { className: "ed-readonly", title: f.help }, value === true ? vocab.editor.yes : value === false ? vocab.editor.no : value || "—"));
      }
      if (typeof value === "boolean") {
        return el("label", { className: "wiz-check" },
          el("input", { type: "checkbox", checked: value, dataset: { field: f.key } }),
          el("span", {}, `${f.label} — ${f.help}`));
      }
      return el("label", { className: "field" }, el("span", { title: f.help }, f.label),
        el("input", { type: vocab.editor.date_fields.includes(f.key) ? "date" : "text", value: value || "", dataset: { field: f.key }, title: f.help }));
    }));
}

function engagementFromFields() {
  const details = {};
  for (const box of $("ed-fields").querySelectorAll("[data-field]")) {
    details[box.dataset.field] = box.type === "checkbox" ? box.checked : box.value.trim();
  }
  return details;
}

function editorNote(text, cls) {
  const note = $("ed-note");
  note.textContent = text;
  note.className = `banner ${cls}${text.includes("\n") ? " multi" : ""}`;
  note.classList.toggle("hidden", !text);
}

async function openEditor() {
  if (!active) return;
  try {
    editorState = await call(withEng("state"));
  } catch (err) {
    toast(err.message);
    return;
  }
  editorRows = (editorState.rules || []).map(editorRow);
  renderEngagementFields(editorState.engagement || {});
  renderEditorRows();
  $("ed-paste").value = "";
  editorNote("", "ok");
  $("editor").classList.remove("hidden");
}

function closeEditor() {
  $("editor").classList.add("hidden");
}

// A small RFC 4180 reader: quoted fields, doubled quotes, commas inside
// quotes. Used only when the pasted block holds no tab.
function csvFields(line) {
  const fields = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"') {
        if (line[i + 1] === '"') { field += '"'; i++; } else quoted = false;
      } else field += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") { fields.push(field); field = ""; }
    else field += ch;
  }
  fields.push(field);
  return fields;
}

// Rows pasted from a spreadsheet, appended by position: a tab on any line
// makes every line tab-separated, otherwise the lines are CSV; a first
// line that repeats the headings is skipped; missing trailing cells are
// blank. Returns how many rows were added. Nothing is recorded here.
function pasteRows(block) {
  const lines = block.split(/\r?\n/).filter((line) => line.trim() !== "");
  if (!lines.length) return 0;
  const tabbed = lines.some((line) => line.includes("\t"));
  let rows = lines.map((line) => (tabbed ? line.split("\t") : csvFields(line)).map((cell) => cell.trim()));
  const labels = vocab.columns.map((c) => c.label.toLowerCase());
  // The heading line is recognised by its first ten cells, so one copied
  // with a trailing tab is still skipped.
  const first = rows[0].slice(0, labels.length).map((cell) => cell.toLowerCase());
  if (first.length === labels.length && first.every((cell, i) => cell === labels[i])
      && rows[0].slice(labels.length).every((cell) => cell === "")) rows = rows.slice(1);
  for (const cells of rows) {
    const row = blankEditorRow();
    vocab.columns.forEach((c, i) => { row[c.key] = cells[i] === undefined ? "" : cells[i]; });
    editorRows.push(row);
  }
  renderEditorRows();
  return rows.length;
}

async function saveEditor() {
  const btn = $("ed-save");
  btn.disabled = true;
  try {
    const result = await call(withEng("edit"), {
      items: editorRows,
      engagement: engagementFromFields(),
    });
    render(result.state);
    closeEditor();
    const saved = result.saved;
    const lines = [saved.recorded
      ? fill(vocab.editor.saved, { changed: saved.changed.length, removed: saved.removed.length })
      : vocab.editor.nothing_changed];
    if (result.warnings.length) {
      lines.push(`${vocab.editor.warnings_heading}:`);
      for (const w of result.warnings) lines.push(`• ${w}`);
    }
    banner(lines.join("\n"), result.warnings.length ? "warn" : "ok");
  } catch (err) {
    editorNote(err.message, "err");
  } finally {
    btn.disabled = false;
  }
}

// ── wiring ──────────────────────────────────────────────────────────────

$("btn-scan").addEventListener("click", runScan);
$("btn-new").addEventListener("click", openWizard);
$("btn-shared").addEventListener("click", () => paths && window.tracker.open(paths.shared));
$("btn-edit").addEventListener("click", openEditor);
$("btn-view").addEventListener("click", () => paths && window.tracker.open(paths.view));
$("btn-status").addEventListener("click", () => paths && window.tracker.open(paths.status));
$("eng-select").addEventListener("change", (e) => {
  active = e.target.value;
  refresh(active);
});
$("form-grid").addEventListener("click", (e) => {
  const card = e.target.closest(".form-card");
  if (card) chooseForm(card.dataset.form);
});
$("wi-back").addEventListener("click", () => showStep("form"));
$("wf-back").addEventListener("click", () => showStep("prior"));
$("wf-cancel").addEventListener("click", () => $("modal").classList.add("hidden"));
$("wp-cancel").addEventListener("click", () => $("modal").classList.add("hidden"));
$("wp-new-client").addEventListener("click", () => showStep("form"));
$("prior-list").addEventListener("change", (e) => {
  if (e.target.name === "prior") {
    selectedPrior = e.target.value;
    syncPriorDefaults();
  }
});
$("ro-create").addEventListener("click", rollForward);
$("ro-name").addEventListener("keydown", (e) => e.key === "Enter" && rollForward());
$("btn-schedule").addEventListener("click", installSchedule);
$("btn-save-root").addEventListener("click", saveRoot);
$("root-input").addEventListener("keydown", (e) => e.key === "Enter" && saveRoot());
$("btn-browse").addEventListener("click", async () => {
  const picked = await window.tracker.pickFolder($("setup-title").textContent);
  if (picked) $("root-input").value = picked;
});
$("btn-unlock").addEventListener("click", clearLock);
$("ne-client").addEventListener("input", syncNameDefault);
$("ne-year").addEventListener("input", syncNameDefault);
$("ne-name").addEventListener("input", () => {
  nameIsAuto = $("ne-name").value.trim() === "";
  syncNameDefault();
});
$("cu-add").addEventListener("click", addCustomItem);
$("cu-rows").addEventListener("addrow", addCustomItem);
$("ed-add").addEventListener("click", addEditorRow);
$("ed-rows").addEventListener("addrow", addEditorRow);
$("ed-paste-btn").addEventListener("click", () => {
  const added = pasteRows($("ed-paste").value);
  if (added) $("ed-paste").value = "";
});
$("ed-save").addEventListener("click", saveEditor);
$("ed-cancel").addEventListener("click", closeEditor);
$("editor").addEventListener("click", (e) => {
  if (e.target === $("editor")) closeEditor();
});
$("ne-create").addEventListener("click", createEngagement);
$("ne-cancel").addEventListener("click", () => $("modal").classList.add("hidden"));
$("modal").addEventListener("click", (e) => {
  if (e.target === $("modal")) $("modal").classList.add("hidden");
});
$("moved-list").addEventListener("click", (e) => {
  const restore = e.target.closest(".r-restore");
  if (restore) restoreMoved(restore.closest("li"));
  const keep = e.target.closest(".r-keep");
  if (keep) keepMoved(keep.closest("li"));
  const send = e.target.closest(".r-review");
  if (send) reviewMoved(send.closest("li"));
});
$("review-list").addEventListener("click", (e) => {
  const file = e.target.closest(".r-file");
  if (file) assignParked(file.closest("li"));
  const dismiss = e.target.closest(".r-dismiss");
  if (dismiss) dismissParked(dismiss.closest("li"));
});
$("review-mode").addEventListener("click", (e) => {
  if (e.target.closest("#review-mode-cards")) setReviewMode(MODE_CARDS);
  if (e.target.closest("#review-mode-list")) setReviewMode(MODE_LIST);
});
$("review-deck").addEventListener("click", (e) => {
  const accept = e.target.closest(".c-accept");
  if (accept) acceptCard(accept.closest(".deck-card"));
  const open = e.target.closest(".c-open");
  if (open) openCardInList(open.closest(".deck-card"));
  const skip = e.target.closest(".c-skip");
  if (skip) skipCard(skip.closest(".deck-card"));
});
$("dismissed-list").addEventListener("click", (e) => {
  const btn = e.target.closest(".r-file");
  if (btn) assignParked(btn.closest("li"));
});
$("filed-list").addEventListener("click", (e) => {
  const btn = e.target.closest(".r-unfile");
  if (btn) unfileDocument(btn.closest("li"));
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    $("modal").classList.add("hidden");
    closeEditor();
  }
});

refresh();
