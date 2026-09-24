// Renderer logic — renders tracker state; every action round-trips through
// the Python API so the UI can never disagree with the real scanner.

let paths = null;          // paths of the active engagement
let engagements = [];      // [{name, path, household, year, return_name}]
let households = [];       // [{name, path, returns, open_years, ...}]
let misfits = [];          // [{path, sentence}] - the folders left alone
let chosenHousehold = null;  // the wizard's household: a path, or null for a new one
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
let rollFor = null;        // path of the household the returning-client page rolls
let lastState = null;      // the state the household card was drawn from

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
//
// It sets only the attributes this list names (decision 137): no `on...`
// handler, no `href`, no `src`, no `style` can reach a node through it, so
// a value that came from the API can never become code or an address, even
// if a later caller passes attributes built from data. A name not on the
// list is a programming error and throws.
const EL_ATTRIBUTES = new Set([
  "className", "dataset", "id", "type", "value", "title", "placeholder",
  "label", "rows", "checked", "selected", "disabled",
  "aria-label", "aria-pressed",
]);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (!EL_ATTRIBUTES.has(key)) throw new Error(`el(): attribute not allowed: ${key}`);
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

// Flattened, because half the callers build their list as "one fixed node,
// then a mapped array" and replaceChildren() turns an array it is handed
// into the text "[object HTMLOptionElement],..." rather than into its
// elements. That is how the wizard's list of existing households, and the
// rollover's list of form templates, came out holding one option and a
// line of noise.
function show(id, nodes) {
  $(id).replaceChildren(...nodes.flat(Infinity).filter((n) => n !== null && n !== undefined && n !== false));
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

// A row nobody asked for (decision 142) has the API's own word while
// nothing is in its folder - never the word for a request or for a gap,
// because nobody owes it. Once a document arrives it shows its real status,
// as any row does. The API says which (state.items[].status_label); the
// page compares.
function isIdleNotAsked(item) {
  return item.status_label === vocab.not_asked_label;
}

function chip(item) {
  if (isSetAside(item.manual_override)) {
    return el("span", { className: `chip chip-${vocab.unscanned_key}` },
      overrideLabel(item.manual_override, item.year));
  }
  if (isIdleNotAsked(item)) {
    return el("span", { className: `chip chip-${vocab.not_asked_key}` }, vocab.not_asked_label);
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
  lastState = state;

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
  // Decision 131: how far this return's working copies are short of room
  // under the clients root - information, not a warning (their names are
  // cut to fit and everything files). The API's sentence, or nothing.
  $("room-note").textContent = state.room_note || "";
  $("room-note").classList.toggle("hidden", !state.room_note);

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

  renderHousehold(state);
  renderMoved(state);
  renderReview(state);
  renderUnfileList(state);
  renderLock(state);
  renderReminder(state);
}

// ── The week's reminder (decision 118) ──────────────────────────────────

// The card is the one place a person sees the draft, moves it up or down
// the ladder, copies it and approves it. It is drawn from its own command
// rather than from `state`, because the letter is regenerated in memory at
// whatever stage the toggle stands on and `state` is the record as it is.
// Nothing here sends: there is no send button, no mail link and no form.
//
// Which rung the person moved the toggle to is the only thing the page
// holds of its own, and it is not a fact about the engagement (decision
// 83), so it is never recorded and it is dropped when the engagement
// changes - the next client's draft opens on the rung its own record gives.
let reminderStage = null;    // the stage a person picked, or null for the record's
let reminderFor = null;      // which engagement that choice belongs to
let reminderCard = null;     // the payload the card was last drawn from

function stageOf(number) {
  return vocab.reminder.stages.find((s) => s.number === number) || null;
}

function stageInk(number) {
  const stage = stageOf(number);
  return stage ? vocab.reminder.palette[stage.colour] : "";
}

// The two marks a stage can put on anything, as classes; which of them to
// put on what is the API's answer, never this file's.
function marked(colour, bold) {
  return `${colour ? "rem-em-colour" : ""} ${bold ? "rem-em-bold" : ""}`.trim();
}

function renderReminder(state) {
  if (reminderFor !== active) {
    reminderStage = null;
    reminderFor = active;
  }
  loadReminder();
}

async function loadReminder() {
  if (!active) {
    $("reminder-card").classList.add("hidden");
    return;
  }
  try {
    const result = await call(withEng("reminder"), { stage: reminderStage });
    drawReminder(result.reminder);
  } catch (err) {
    // An engagement nobody has scanned yet has no reminder to show, and
    // the request table above already says so row by row. The card is
    // simply not there until there is a draft to put in it.
    reminderCard = null;
    $("reminder-card").classList.add("hidden");
  }
}

function drawReminder(card) {
  reminderCard = card;
  const words = vocab.reminder;
  const rows = (card.held || []).length;
  const unsorted = card.unsorted || 0;
  // Held by a row (decision 115), or by files still waiting in the
  // household's inbox (decision 133): the same card either way.
  const held = rows > 0 || unsorted > 0;
  const quiet = !held && (card.asked || []).length === 0;
  $("reminder-card").classList.remove("hidden");
  // Held, the card is the hold, the rows holding it and the toggle, and
  // nothing else at all — not even what the record last drafted.
  $("reminder-status").textContent = held ? "" : reminderStatus(card);
  $("reminder-status").classList.toggle("hidden", held);

  // The hold, said once and here: the sentence, then the requests under it
  // with the reason each carries (decision 115's rows, in 118's card).
  const hold = $("reminder-hold");
  hold.classList.toggle("hidden", !held);
  hold.style.setProperty("--stage-ink", words.palette[words.hold_colour]);
  $("reminder-held").textContent = holdLine(rows, unsorted);
  show("reminder-held-rows", (card.held || []).map((row) =>
    el("li", {},
      el("span", { className: "rem-hold-id" }, row.identifier),
      ` ${row.document}`,
      el("span", { className: "rem-hold-why" }, row.reason))));

  // The four rungs, each in its own colour, the one in force pressed. Live
  // only when there is a generated letter to re-stage: a held reminder and
  // one somebody edited by hand both leave it standing but dead.
  $("reminder-stages").setAttribute("aria-label", words.stage_group);
  show("reminder-stages", words.stages.map((stage) => {
    const button = el("button", {
      type: "button",
      className: `rem-stage rem-stage-${stage.number}`,
      "aria-pressed": String(card.stage === stage.number),
      disabled: !card.editable,
      dataset: { stage: stage.number },
    }, el("span", { className: "rem-stage-n" }, stage.number), ` ${stage.name}`);
    button.style.setProperty("--stage-ink", vocab.reminder.palette[stage.colour]);
    return button;
  }));

  $("reminder-hint").textContent = quiet ? words.nothing_to_send : words.stage_toggle_hint;
  $("reminder-hint").classList.toggle("hidden", held || (!card.editable && !quiet));
  $("reminder-edited").textContent = words.edited_by_hand;
  $("reminder-edited").classList.toggle("hidden", held || !card.file.edited);
  // Why the letter has no link (decision 137, L5): the API's sentence.
  $("reminder-link-dropped").textContent = card.link_dropped || "";
  $("reminder-link-dropped").classList.toggle("hidden", !card.link_dropped);

  const subject = $("reminder-subject");
  const marks = (stageOf(card.stage) || {}).emphasis || {};
  subject.textContent = card.subject ? `${words.subject_prefix}${card.subject}` : "";
  subject.className = `rem-subject ${marked(marks.subject_colour, marks.subject_bold)}`.trim();
  subject.style.setProperty("--stage-ink", stageInk(card.stage));
  subject.classList.toggle("hidden", held || !card.subject);

  // The letter, drawn from its own shape as nodes - the page is built from
  // data and never from markup, so the body the clipboard carries is not
  // the body on screen even though both say exactly the same words.
  const preview = $("reminder-preview");
  preview.setAttribute("aria-label", words.heading);
  preview.style.setProperty("--stage-ink", stageInk(card.stage));
  preview.style.setProperty("--rem-ink", words.palette[words.letter_ink.body]);
  preview.style.setProperty("--rem-muted", words.palette[words.letter_ink.muted]);
  preview.style.setProperty("--rem-paper", words.palette[words.letter_ink.paper]);
  preview.classList.toggle("hidden", held);
  show("reminder-preview", held ? [] : letterNodes(card));

  // Held: the hold line, the rows and the toggle, and nothing that reads
  // like something to send. There is no file to open either.
  $("reminder-actions").classList.toggle("hidden", held);
  $("btn-open-draft").disabled = !card.file.exists;
}

// The hold, in the API's words: the rows' line, the inbox's line, or both.
function holdLine(rows, unsorted) {
  return [
    rows ? fill(vocab.reminder.held_line, { n: rows }) : "",
    unsorted ? fill(vocab.reminder.inbox_held_line, { n: unsorted }) : "",
  ].filter(Boolean).join(" · ");
}

function reminderStatus(card) {
  const words = vocab.reminder;
  if (card.approved) {
    return fill(words.approved_line, { date: card.approved.date, n: card.approved.stage });
  }
  if (card.last) return fill(words.last_drafted_line, { date: card.last.date, n: card.last.stage });
  return words.never_drafted_line;
}

// A line break inside a paragraph is a break, not a space: the quiet
// week's paragraph and the sign-off are written wrapped.
function lines(text) {
  const out = [];
  String(text).split("\n").forEach((line, i) => {
    if (i) out.push(el("br"));
    out.push(line);
  });
  return out;
}

function letterNodes(card) {
  const letter = card.letter || {};
  const marks = (stageOf(card.stage) || {}).emphasis || {};
  if (!letter.greeting) {
    // A draft somebody edited by hand: their own paragraphs, and no
    // stage's emphasis on words the machine did not write.
    return String(card.text || "").split("\n\n")
      .filter((block) => block.trim())
      .map((block) => el("p", {}, ...lines(block.replace(/^\n+|\n+$/g, ""))));
  }
  const nodes = [el("p", {}, ...lines(letter.greeting))];
  if (letter.progress) nodes.push(el("p", {}, letter.progress));
  if (letter.intro) nodes.push(el("p", {}, ...lines(letter.intro)));
  for (const section of letter.sections || []) {
    nodes.push(el("p", { className: "rem-sec" }, section.heading));
    nodes.push(el("ul", {}, section.items.map((line) =>
      el("li", { className: marked(marks.list_colour, marks.list_bold) }, line))));
  }
  if ((letter.drop || []).length) {
    // A span and never a link: an address the window followed would take
    // the app somewhere, and the client's own letter is where it is live.
    const drop = el("p", {}, letter.drop.join(" "));
    if (letter.link) drop.append(el("br"), el("span", { className: "rem-link" }, letter.link));
    nodes.push(drop);
  }
  if ((letter.deadline || []).length) {
    nodes.push(el("p", { className: marked(marks.deadline_colour, false) },
      letter.deadline.map((run) =>
        run.colour || run.bold
          ? el("span", { className: marked(run.colour, run.bold) }, run.text)
          : run.text)));
  }
  if (letter.close) nodes.push(el("p", {}, letter.close));
  if ((letter.signoff || []).length) {
    nodes.push(el("p", { className: "rem-sign" }, ...lines(letter.signoff.join("\n"))));
  }
  return nodes;
}

// The same words twice, so whichever one Outlook takes is the letter: the
// body as HTML it keeps, and the plain text beside it. The subject is not
// on the clipboard - it goes in Outlook's own box, and the card shows it
// as text a person selects.
async function copyReminder() {
  if (!reminderCard) return;
  const btn = $("btn-copy");
  btn.disabled = true;
  try {
    await navigator.clipboard.write([new ClipboardItem({
      "text/html": new Blob([reminderCard.html], { type: "text/html" }),
      "text/plain": new Blob([reminderCard.text], { type: "text/plain" }),
    })]);
    banner(vocab.reminder.copied, "ok");
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
}

// What you see is what you approve: the fingerprint of the text on screen
// goes with the click, and a panel the record has moved under is refused
// by the API and read again (decision 112's rule, on this card).
async function approveReminder() {
  if (!reminderCard) return;
  const btn = $("btn-approve");
  btn.disabled = true;
  try {
    const result = await call(withEng("approve"), {
      stage: reminderCard.stage,
      fingerprint: reminderCard.fingerprint,
    });
    drawReminder(result.reminder);
    const approved = result.reminder.approved;
    const said = approved
      ? fill(vocab.reminder.approved_line, { date: approved.date, n: approved.stage })
      : vocab.reminder.approve;
    banner(result.set_aside
      ? `${said}. ${fill(vocab.reminder.set_aside_line, { name: result.set_aside })}.`
      : said, "ok");
  } catch (err) {
    toast(err.message);
    await loadReminder();
  } finally {
    btn.disabled = false;
  }
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
  const people = (state.engagement || {}).people || [];
  show("review-list", parked.map((e) =>
    reviewRow(e, choices, ids, true, triaged.get(e.pbc_location), people)));
  // The same queue drawn the other way (decision 114), from the same state:
  // both renderings are always drawn and the mode shows one of them.
  renderDeck(state);
  applyReviewMode();
  $("dismissed-card").classList.toggle("hidden", dismissed.length === 0);
  $("dismissed-heading").textContent =
    fill(vocab.review_labels.dismissed_heading, { n: dismissed.length });
  show("dismissed-list", dismissed.map((e) => reviewRow(e, choices, ids, false, null, people)));
}

// The card's offer beside a page that named nobody on this return
// (decision 128): the person it belongs to, and the spelling this page
// prints. Offered only where the API said the name was absent - the app
// decides nothing about a name - and pre-filled with nothing, because the
// person types what the page shows.
function teachSpelling(triage, people) {
  const said = ((triage && triage.shortlist) || [])
    .map((s) => s.name).find(Boolean);
  if (!said || said.outcome !== vocab.people.outcomes.absent || !people.length) return null;
  const words = vocab.people;
  return el("div", { className: "r-teach" },
    el("span", { className: "tmpl-rules" }, words.teach),
    el("select", { className: "r-person", "aria-label": words.teach },
      people.map((p) => el("option", { value: p.name }, p.name))),
    el("input", {
      type: "text", className: "r-spelling", placeholder: words.teach_hint,
      "aria-label": words.teach_hint,
    }));
}

// What the card is sending about a spelling, or nothing at all.
function spellingFrom(node) {
  const box = node.querySelector(".r-spelling");
  const who = node.querySelector(".r-person");
  if (!box || !box.value.trim()) return null;
  return { person: who ? who.value : "", spelling: box.value.trim() };
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
function reviewRow(e, choices, ids, open, triage, people = []) {
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
    open && teachSpelling(triage, people),
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
    // And the answer that files it under a request of another return this
    // drop folder feeds (decision 129), offered only where there is one.
    fedReturns().length
      && el("button", { className: "btn r-hand-over" }, vocab.review_labels.hand_over),
  );
}

// Every return this drop folder feeds, as the picker offers them: the
// household's own open-year returns and the return lines a person extended
// it to, minus the one being looked at. The state carries both, so the
// page asks nothing of its own and can offer nothing the feed list does
// not already go to.
function fedReturns() {
  const hh = lastState && lastState.household;
  if (!hh) return [];
  const open = hh.open_years || [];
  const own = (hh.returns || [])
    .filter((r) => r.active && open.includes(r.year) && r.path !== active)
    .map((r) => ({ path: r.path, label: r.label }));
  const fed = (hh.feeds || []).filter((f) => f.path)
    .map((f) => ({ path: f.path, label: f.label }));
  return [...own, ...fed];
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
async function fileRow(original, identifier, seq, keyword, spelling) {
  const result = await call(withEng("assign"), { original, identifier, keyword, spelling, seq });
  render(result.state);
  const a = result.assigned;
  const notes = [`${a.original_name} filed as ${a.filed_as}`];
  if (a.keyword) notes.push(`"${a.keyword}" added to ${a.identifier} so the next one files itself`);
  if (a.keyword_note) notes.push(a.keyword_note);
  // A spelling taught with the filing (decision 128), in the API's words.
  if (a.spelling) notes.push(`"${a.spelling}" added so the next page that prints it confirms itself`);
  if (a.spelling_note) notes.push(a.spelling_note);
  if (a.left_in_review) notes.push(a.left_in_review);
  // What the record now says about a pick the evidence did not point at:
  // the API's sentence, shown as it stands.
  if (a.overrode_shortlist) notes.push(a.overrode_shortlist);
  if (a.scan_note) notes.push(a.scan_note);
  banner(notes.join(". ") + ".",
    a.keyword_note || a.spelling_note || a.left_in_review || a.overrode_shortlist || a.scan_note
      ? "warn" : "ok");
}

// ── File under another return (decision 129) ─────────────────────────────
//
// One decision the API carries out whole: the original moves where it must
// rest, the working copy is made in the taking return's request folder, the
// parked copy here goes, and this return's row closes. The page picks the
// return and the request and sends both; it decides nothing.

// The row being handed over while the modal is open.
let handingOver = null;

async function openHandOver(original, seq) {
  const words = vocab.review_labels;
  const offered = fedReturns();
  if (!offered.length) return;
  handingOver = { original, seq };
  $("ho-title").textContent = words.hand_over;
  $("ho-name").textContent = original;
  $("ho-return-label").textContent = words.hand_over_return;
  $("ho-request-label").textContent = words.hand_over_request;
  $("ho-file").textContent = words.file;
  show("ho-return", offered.map((one) => el("option", { value: one.path }, one.label)));
  $("handover-modal").classList.remove("hidden");
  await loadHandOverRequests();
}

// The taking return's own request list, read from its state - the same
// answer the editor and the pass read, so the picker can only offer a
// request that return really has.
async function loadHandOverRequests() {
  const target = $("ho-return").value;
  show("ho-request", [el("option", { value: "" }, "…")]);
  try {
    const state = await call(["state", vocab.engagement_flag, target]);
    show("ho-request", state.items.map((i) => requestOption(i, "")));
  } catch (err) {
    toast(err.message);
  }
}

async function fileHandOver() {
  const btn = $("ho-file");
  const identifier = $("ho-request").value;
  if (!handingOver || !identifier) {
    toast("Pick the request this document belongs to first.");
    return;
  }
  btn.disabled = true;
  try {
    const result = await call(withEng("assign"), {
      original: handingOver.original, identifier, target: $("ho-return").value,
      seq: handingOver.seq,
    });
    $("handover-modal").classList.add("hidden");
    render(result.state);
    const a = result.handed_over;
    const notes = [`${a.original_name}: ${fill(vocab.review_labels.handed_over,
      { label: a.label, identifier: a.identifier })}`];
    if (a.left_in_review) notes.push(a.left_in_review);
    if (a.scan_note) notes.push(a.scan_note);
    banner(notes.join(". ") + ".", a.left_in_review || a.scan_note ? "warn" : "ok");
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
    handingOver = null;
  }
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
    await fileRow(li.dataset.original, identifier, Number(li.dataset.seq),
                  typed(li, ".r-keyword"), spellingFrom(li));
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
    ? [deckCard(deck[0], rows.get(deck[0].pbc_location), place, deck.length,
                (state.engagement || {}).people || [])]
    : []);
}

// One card: the document, why it parked, the top suggestion with the
// sentence behind it, the rows the evidence points at that are set aside,
// and the three answers. A card with nothing suggested has no Accept -
// there is nothing to accept - and says so in the API's words.
function deckCard(t, row, place, total, people = []) {
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
    teachSpelling(t, people),
    el("input", {
      type: "text", className: "r-keyword", placeholder: "keyword to learn (optional)",
      "aria-label": "Keyword to add to the request",
      title: "A word this document contains that others like it will too. Taught to the request so the next one files itself; the editor shows it beside the row.",
    }),
    el("span", { className: "deck-position" },
      fill(vocab.review_labels.card_position, { n: place, total })),
    best && el("button", { className: "btn btn-primary c-accept" }, vocab.review_labels.accept),
    el("button", { className: "btn c-open" }, vocab.review_labels.open_in_list),
    // The deck offers what the list offers: a request of another return
    // this drop folder feeds (decision 129).
    fedReturns().length
      && el("button", { className: "btn c-hand-over" }, vocab.review_labels.hand_over),
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
                  typed(card, ".r-keyword"), spellingFrom(card));
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

// The picker is grouped by household (decision 125): a return is named by
// its household, its year and its own name, and two households may each
// hold a return of the same name. The names are the API's; the page
// only groups them.
function renderEngagements() {
  const byHousehold = new Map(households.map((h) => [h.path, []]));
  for (const e of engagements) {
    if (!byHousehold.has(e.household)) byHousehold.set(e.household, []);
    byHousehold.get(e.household).push(e);
  }
  const named = new Map(households.map((h) => [h.path, h.name]));
  show("eng-select", [...byHousehold]
    .filter(([, list]) => list.length)
    .map(([path, list]) =>
      el("optgroup", { label: named.get(path) || path },
        list.map((e) => el("option", { value: e.path, selected: e.path === active }, e.name)))));
}

// Every folder the walk left alone, with the one sentence saying why. The
// card is there only when there is one; nothing in a misfit is ever read,
// moved or renamed, and the app says so in the API's own words.
function renderMisfits() {
  const words = vocab.household;
  $("misfits-card").classList.toggle("hidden", misfits.length === 0);
  $("misfits-heading").textContent = `${words.misfits_heading} (${misfits.length})`;
  $("misfits-note").textContent = words.misfits_note;
  show("misfits-list", misfits.map((m) =>
    el("li", { className: "r-item" },
      el("div", { className: "r-name" }, relativeToRoot(m.path)),
      el("div", { className: "r-why" }, m.sentence))));
}

function relativeToRoot(path) {
  if (!clientsRoot || !path.startsWith(clientsRoot)) return path;
  return path.slice(clientsRoot.length).replace(/^[\\/]+/, "");
}

// The household this return belongs to: what the firm typed about it, the
// year's returns as buttons that switch the picker, and the one queue a
// person works across it. Every word is the API's.
function renderHousehold(state) {
  const words = vocab.household;
  const hh = state.household;
  $("household-card").classList.toggle("hidden", !hh);
  if (!hh) return;
  $("household-heading").textContent = words.heading;
  $("household-name").textContent = hh.name;
  $("household-members-label").textContent = words.members_label;
  $("household-members-label").title = words.members_help;
  $("household-members").textContent = hh.members.length ? hh.members.join(", ") : "—";
  $("household-contact-label").textContent = words.contact_label;
  $("household-contact-label").title = words.contact_help;
  $("household-contact").textContent = hh.contact || "—";
  $("household-link-label").textContent = words.link_label;
  $("household-link-label").title = words.link_help;
  $("household-link").textContent = hh.link || "—";
  const twoYears = hh.open_years.length > 1;
  $("household-two-years").classList.toggle("hidden", !twoYears);
  $("household-two-years").textContent = twoYears
    ? fill(words.two_open_years, { years: hh.open_years.join(", ") }) : "";
  $("household-returns-head").textContent = words.returns_heading;
  const open = hh.open_years.length === 1 ? hh.open_years[0] : null;
  // Each return of the open year, with its own reminder's state beside it
  // (decision 128), so the household's letters stand side by side. There
  // is still one letter per return and the Reminder card is still where a
  // person approves one: this is a line, never a send.
  show("household-returns", hh.returns
    .filter((r) => open === null || r.year === open)
    .map((r) => el("div", { className: "household-return" },
      el("button", {
        className: `btn btn-small${r.path === active ? " btn-primary" : ""}`,
        dataset: { path: r.path },
      }, r.label),
      r.reminder && el("span", { className: "wiz-note" }, returnReminderLine(r.reminder)))));
  $("household-queue").textContent = fill(words.queue_line, { n: hh.queue });
  $("btn-edit-household").textContent = words.edit;
  renderFeeds(hh);
  renderSharing(hh);
}

// What this drop folder also feeds, and whose drop folders feed a return
// here (decision 129). Labels and household names only: who is shared on
// another household is on that household's own card, never here. A feed
// that answers to no return this year says so in the API's sentence.
function renderFeeds(hh) {
  const words = vocab.household;
  const feeds = hh.feeds || [];
  const fed = hh.fed_by || [];
  const listed = feeds.filter((f) => f.label).map((f) => f.label);
  $("household-feeds").classList.toggle("hidden", !listed.length);
  $("household-feeds").textContent = listed.length
    ? fill(words.feeds_line, { listed: listed.join(", ") }) : "";
  $("household-fed-by").classList.toggle("hidden", !fed.length);
  $("household-fed-by").textContent = fed.length
    ? fill(words.fed_by_line, { listed: fed.map((h) => h.name).join(", ") }) : "";
  const said = feeds.map((f) => f.warning).filter(Boolean);
  $("household-feeds-unresolved").classList.toggle("hidden", !said.length);
  $("household-feeds-unresolved").textContent = said.join(" · ");
}

// One return's reminder, in the same words its own card uses: approved
// beats last-drafted beats never, and a hold is said after it. Every
// pattern is the API's (vocab.reminder) and the page types none of them.
function returnReminderLine(state) {
  const words = vocab.reminder;
  const said = state.approved
    ? fill(words.approved_line, { date: state.approved.date, n: state.approved.stage })
    : state.last
      ? fill(words.last_drafted_line, { date: state.last.date, n: state.last.stage })
      : words.never_drafted_line;
  const hold = holdLine(state.held || 0, state.unsorted || 0);
  return hold ? `${said} · ${hold}` : said;
}

// Whether the firm has said it shared this household, and the checklist
// until it does (decision 126). The tracker cannot see Drive's sharing:
// every line here, including the two grants and the note saying why they
// cannot be checked, arrives from the API already filled.
function renderSharing(hh) {
  const words = vocab.household;
  $("household-shared").textContent = hh.shared_on
    ? fill(words.shared_on_line, { day: hh.shared_on })
    : words.not_yet_shared_line;
  $("household-checklist").classList.toggle("hidden", !hh.checklist);
  if (hh.checklist) {
    $("household-checklist-heading").textContent = hh.checklist.heading;
    show("household-checklist-lines", hh.checklist.lines.map((line) => el("li", {}, line)));
    $("household-checklist-note").textContent = hh.checklist.note;
  }
  $("btn-mark-shared").textContent = words.mark_shared;
  $("btn-mark-shared").classList.toggle("hidden", Boolean(hh.shared_on));
}

// The firm's word, recorded once: one dated event on the household's
// record and nothing else. The API refuses it while the inbox link is
// blank, and its sentence is what the person reads.
async function markShared() {
  const btn = $("btn-mark-shared");
  btn.disabled = true;
  try {
    const result = await call(withEng("mark-shared"));
    render(result.state);
    banner(fill(vocab.household.shared_on_line, { day: result.shared_on }), "ok");
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
}

// The feed list as the editor holds it while the modal is open: a list a
// person built from the returns that already exist. Nothing is typed and
// nothing is inferred - a household is assembled by a person, and so is a
// feed (decision 129).
let editorFeeds = [];

// What the picker is offering right now, in the order it draws the options.
// An option's value is its index here and nothing else: a feed is two
// fields - a household name and a return line - and every one of them
// carries spaces, so a value that packed the pair into one string had to be
// taken apart again on a guess. The index is exact, and what is added is
// the object the option was drawn from, field for field.
let feedChoices = [];

// And where the two fields must be one key - the set of feeds already
// added, which is a lookup and not a value sent anywhere - the pair is
// keyed as the pair, rather than run together into one string with a
// separator a name might itself carry.
function feedKey(household, returnName) {
  return JSON.stringify([household, returnName]);
}

// The household's own fields, saved as one recorded event.
function openHouseholdEditor() {
  const words = vocab.household;
  const hh = lastState && lastState.household;
  if (!hh) return;
  $("hh-edit-title").textContent = words.edit;
  $("hh-edit-members-label").textContent = words.members_label;
  $("hh-edit-contact-label").textContent = words.contact_label;
  $("hh-edit-link-label").textContent = words.link_label;
  $("hh-edit-note").textContent = words.members_help;
  $("hh-edit-members").value = hh.members.join("\n");
  $("hh-edit-contact").value = hh.contact || "";
  $("hh-edit-link").value = hh.link || "";
  $("hh-edit-feeds-label").textContent = words.feeds_label;
  $("hh-edit-feeds-help").textContent = words.feeds_help;
  $("hh-edit-feed-add").textContent = words.add_feed;
  $("hh-edit-feed-warning").classList.add("hidden");
  editorFeeds = (hh.feeds || []).map((f) => ({ household: f.household, return_name: f.return_name,
                                               label: f.label }));
  renderEditorFeeds();
  $("household-modal").classList.remove("hidden");
}

// The return lines this drop folder feeds, and the picker of every other
// household's return lines it could. The picker is drawn from the same
// walk the pass uses (the `list` command), so a person can only pick a
// return the tracker already knows about.
function renderEditorFeeds() {
  const hh = lastState && lastState.household;
  const here = hh ? hh.name : "";
  show("hh-edit-feeds", editorFeeds.map((feed, at) => el("li", {},
    el("span", {}, feed.label || `${feed.household} ${feed.return_name}`),
    el("button", { className: "btn btn-small hh-feed-remove", dataset: { at: String(at) } },
      vocab.editor.remove_row))));
  const taken = new Set(editorFeeds.map((f) => feedKey(f.household, f.return_name)));
  const options = [];
  feedChoices = [];
  for (const other of households) {
    if (other.name === here) continue;
    const open = other.open_years || [];
    for (const one of other.returns || []) {
      if (!one.active || !open.includes(one.year)) continue;
      if (taken.has(feedKey(other.name, one.return_name))) continue;
      options.push(el("option", { value: String(feedChoices.length) }, one.label));
      feedChoices.push({ household: other.name, return_name: one.return_name,
                         label: one.label, members: other.members || [] });
    }
  }
  show("hh-edit-feed-pick", options.length ? options : [el("option", { value: "" }, "—")]);
  $("hh-edit-feed-add").disabled = !options.length;
}

// Every feed added is warned about, every time: anyone with access to this
// drop folder may drop for that return, and its documents will rest under
// the folder it lives in, shared with whoever that household's card says.
// The sentence and the stand-in for an untyped members list are the API's.
function addEditorFeed() {
  const picked = $("hh-edit-feed-pick").value;
  if (!picked) return;
  const chosen = feedChoices[Number(picked)];
  if (!chosen) return;
  const members = chosen.members.length ? chosen.members.join(", ")
    : vocab.household.nobody_typed;
  editorFeeds.push({ household: chosen.household, return_name: chosen.return_name,
                     label: chosen.label });
  renderEditorFeeds();
  const warning = $("hh-edit-feed-warning");
  warning.textContent = fill(vocab.household.feed_warning, { members });
  warning.classList.remove("hidden");
}

async function saveHousehold() {
  const btn = $("hh-edit-save");
  btn.disabled = true;
  try {
    const result = await call(withEng("edit-household"), {
      members: $("hh-edit-members").value.split("\n").map((one) => one.trim()).filter(Boolean),
      contact: $("hh-edit-contact").value.trim(),
      link: $("hh-edit-link").value.trim(),
      feeds: editorFeeds.map((f) => ({ household: f.household, return_name: f.return_name })),
    });
    $("household-modal").classList.add("hidden");
    render(result.state);
    const moved = result.saved.household;
    banner(moved.length ? `${vocab.household.heading}: ${moved.join(", ")}` : vocab.editor.nothing_changed, "ok");
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
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
  // The household's one inbox and its folder in the tree a client is
  // shared (decision 125): the labels are the API's, the paths are too.
  $("inbox-label").textContent = vocab.household.open_inbox;
  $("client-folder-label").textContent = vocab.household.open_client_folder;
  $("household-title").textContent = vocab.household.heading;
  $("hh-existing-head").textContent = vocab.household.existing;
  $("hh-existing-label").textContent = vocab.household.name_label;
  $("hh-new-head").textContent = vocab.household.new;
  $("hh-name-label").textContent = vocab.household.name_label;
  $("hh-contact-label").textContent = vocab.household.contact_label;
  $("hh-contact").title = vocab.household.contact_help;
  $("hh-members-label").textContent = vocab.household.members_label;
  $("hh-members").title = vocab.household.members_help;
  $("hh-link-label").textContent = vocab.household.link_label;
  $("hh-link").title = vocab.household.link_help;
  $("ne-name-label").textContent = vocab.household.return_name_label;
  $("ne-name").title = vocab.household.return_name_help;
  // What adding a return to a household shows, said every time on both
  // pages that add one (decision 129).
  $("hh-return-warning").textContent = vocab.household.return_warning;
  $("ne-return-warning").textContent = vocab.household.return_warning;
  $("ro-household-label").textContent = vocab.household.heading;
  $("view-label").textContent = vocab.view.open;
  $("edit-label").textContent = vocab.editor.open;
  // The two renderings of the review queue are named by the API too
  // (decision 114); the page carries no word for either of them.
  $("review-mode-cards").textContent = vocab.review_labels.card_mode;
  $("review-mode-list").textContent = vocab.review_labels.list_mode;
  // The Reminder card's heading and its three buttons (decision 118).
  // Nothing here sends, and none of these words is the page's.
  $("reminder-heading").textContent = vocab.reminder.heading;
  $("btn-copy").textContent = vocab.reminder.copy;
  $("btn-approve").textContent = vocab.reminder.approve;
  $("btn-open-draft").textContent = vocab.reminder.open_draft;
  $("root-input").placeholder = `e.g. ${vocab.example_root}`;
  // The firm's own telephone number, beside its name: the label, the
  // sentence under it and the number itself are all Python's.
  $("phone-input").placeholder = `${vocab.settings.phone_label} — ${vocab.settings.phone_help}`;
  $("phone-input").title = vocab.settings.phone_help;
  $("phone-input").setAttribute("aria-label", vocab.settings.phone_label);
  for (const id of ["ro-year", "ne-year"]) {
    $(id).min = vocab.year_min;
    $(id).max = vocab.year_max;
    $(id).title = vocab.year_note;
  }
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
  households = listed.households || [];
  misfits = listed.misfits || [];
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
  renderMisfits();
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
    renderShortOfRoom(result.short_of_room || []);
    await refresh();
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
}

// Decision 131: every return short of room under the root just set, one
// line each - the return's label and the API's own sentences - or nothing.
function renderShortOfRoom(shortOf) {
  $("room-card").classList.toggle("hidden", shortOf.length === 0);
  $("room-heading").textContent = `${vocab.room.heading} (${shortOf.length})`;
  show("room-list", shortOf.map((one) =>
    el("li", { className: "r-item" },
      el("div", { className: "r-name" }, one.engagement),
      el("div", { className: "r-why" }, one.sentences.join(" ")))));
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
  // The page opens on the active return's household (decision 126); the
  // picker is how a person moves to another one without switching it.
  rollFor = null;
  renderHouseholdStep();
  renderPriorPage();
  renderFormGrid();
  showStep("household");
  $("modal").classList.remove("hidden");
}

function showStep(step) {
  $("wiz-household").classList.toggle("hidden", step !== "household");
  $("wiz-prior").classList.toggle("hidden", step !== "prior");
  $("wiz-form").classList.toggle("hidden", step !== "form");
  $("wiz-items").classList.toggle("hidden", step !== "items");
}

// ── page 0: whose household ─────────────────────────────────────────────
// A return is made inside a household (decision 125): an existing one, by
// its folder, or a new one this call makes from the four fields.

function renderHouseholdStep() {
  show("hh-existing", [
    el("option", { value: "" }, vocab.household.new),
    households.map((h) => el("option", { value: h.path }, h.name)),
  ]);
  $("hh-existing").value = chosenHousehold || "";
  $("hh-name").value = "";
  $("hh-contact").value = "";
  $("hh-members").value = "";
  $("hh-link").value = "";
  syncHouseholdStep();
}

function syncHouseholdStep() {
  chosenHousehold = $("hh-existing").value || null;
  for (const id of ["hh-name", "hh-contact", "hh-members", "hh-link"]) {
    $(id).disabled = Boolean(chosenHousehold);
  }
  $("hh-existing-head").classList.toggle("hidden", households.length === 0);
  $("hh-existing").classList.toggle("hidden", households.length === 0);
}

// What every create and rollover sends about the household: the folder of
// the one that exists, or the four fields of the one being made.
function householdSpec() {
  if (chosenHousehold) return { household_path: chosenHousehold };
  return {
    household: $("hh-name").value.trim(),
    contact: $("hh-contact").value.trim(),
    members: $("hh-members").value.split("\n").map((one) => one.trim()).filter(Boolean),
    link: $("hh-link").value.trim(),
  };
}

// The household's own contact is the greeting a new return starts with.
function householdContact() {
  if (!chosenHousehold) return $("hh-contact").value.trim();
  const found = households.find((h) => h.path === chosenHousehold);
  return found ? found.contact : "";
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

// The household's returns for the open year, as the page ticks them: the
// priors the API listed, grouped by household, with a prior a rollover has
// already retired left out - it is not an open-year return any more.
function priorsOfHousehold(path) {
  return priors.filter((p) => p.household === path && !p.superseded_by);
}

// The household this page rolls: the one a person picked here, else the
// active return's, else the first household that has a prior at all.
function rollHousehold() {
  if (rollFor && priorsOfHousehold(rollFor).length) return rollFor;
  const here = lastState && lastState.household ? lastState.household.path : null;
  if (here && priorsOfHousehold(here).length) return here;
  const found = households.find((h) => priorsOfHousehold(h.path).length);
  return found ? found.path : null;
}

function renderPriorPage() {
  // **A household rolls as a household** (decision 126): the page shows
  // the open year's returns as a checklist, all ticked, and Roll Forward
  // rolls every ticked one and retires the rest. The picker is here so a
  // person can roll another household without switching the active
  // return first.
  rollFor = rollHousehold();
  show("ro-household", households
    .filter((h) => priorsOfHousehold(h.path).length)
    .map((h) => el("option", { value: h.path, selected: h.path === rollFor }, h.name)));
  const shown = rollFor ? priorsOfHousehold(rollFor) : [];
  show("prior-list", shown.map((p) =>
    el("div", { className: "prior-item roll-return" },
      el("label", { className: "prior-head" },
        el("input", { type: "checkbox", className: "roll-tick", checked: true,
                      dataset: { path: p.path } }),
        el("span", { className: "prior-name" }, p.label || p.name),
        el("span", { className: "prior-meta" }, priorMeta(p)),
      ),
      // The people the roll carries unchanged (decision 128), under the
      // return they belong to, with the way to look at them. Nothing
      // blocks on the look: strict parking is the safety net.
      el("div", { className: "prior-people" },
        el("span", { className: "prior-meta" },
          `${vocab.people.label}: ${(p.people || []).map((one) => one.name).join(", ") || "—"}`),
        el("button", { type: "button", className: "btn btn-small roll-review-people",
                       dataset: { path: p.path } }, vocab.people.review_people),
      ),
      el("label", { className: "field roll-form" },
        el("span", {}, "Form template (fills blanks, adds the rows this client never had as not asked)"),
        el("select", { className: "roll-form-pick", dataset: { path: p.path } },
          el("option", { value: "" }, "No template — carry last year's list as it is"),
          forms.map((f) => el("option", { value: f.id }, `${f.label} · ${f.who}`)),
        ),
      ),
    )));
  $("prior-list").classList.toggle("hidden", shown.length === 0);
  $("prior-empty").classList.toggle("hidden", shown.length > 0);
  $("ro-create").disabled = shown.length === 0;
  $("ro-household-field").classList.toggle("hidden", households.length < 2);
  syncPriorDefaults();
}

function syncPriorDefaults() {
  const shown = rollFor ? priorsOfHousehold(rollFor) : [];
  $("ro-year").value = shown.map((p) => p.next_year).find(Boolean) || "";
  syncUntickedNote();
}

// Said before anything is unticked, in the API's words: an unticked return
// is retired for the year, not merely skipped (decision 126).
function syncUntickedNote() {
  $("ro-unticked-note").textContent =
    fill(vocab.household.rollover_unticked, { year: $("ro-year").value || "" });
}

async function rollForward() {
  const ticked = [...$("prior-list").querySelectorAll(".roll-tick")].filter((b) => b.checked);
  const first = priorsOfHousehold(rollFor)[0];
  if (!first) {
    toast("Pick the engagement to roll forward, or start from a form template.");
    return;
  }
  const btn = $("ro-create");
  btn.disabled = true;
  try {
    const pick = (cls, path) =>
      $("prior-list").querySelector(`.${cls}[data-path="${CSS.escape(path)}"]`);
    const result = await call(
      ["roll-household", vocab.engagement_flag, first.path],
      {
        year: Number($("ro-year").value) || null,
        returns: ticked.map((box) => ({
          prior: box.dataset.path,
          form: pick("roll-form-pick", box.dataset.path).value,
        })),
      });
    $("modal").classList.add("hidden");
    await refresh(result.state.paths.engagement);
    // The banner: how many returns rolled into the year and how many were
    // retired, then each return's rows added as not asked (decision 142)
    // and last year's unfiled files - said here, once, because there is no
    // sheet to point at and a row a person wants asked is set in the editor.
    const lines = [
      `${result.rolled.length} return(s) rolled into ${result.target_year}; ` +
      `${result.retired.length} retired`,
      // The people carried unchanged and are worth one look (decision
      // 128), in the API's words.
      fill(vocab.people.rolled_note, { n: result.rolled.length }),
    ];
    for (const one of result.rolled) {
      const setAside = one.carried.filter((c) => c.origin === vocab.origin_not_applicable);
      const added = one.carried.filter((c) => c.origin === vocab.origin_new);
      const parts = [`${one.carried.length - setAside.length - added.length} request(s) carried`];
      if (setAside.length) parts.push(fill(vocab.not_applicable_carried, { n: setAside.length }));
      if (added.length) parts.push(fill(vocab.new_not_asked_carried, { n: added.length }));
      if (one.unfiled_last_year.length) {
        parts.push(`${one.unfiled_last_year.length} file(s) sent last year were never filed`);
      }
      lines.push(`• ${one.label}: ${parts.join("; ")}.`);
      // Decision 137: a link that was not a web address was left behind;
      // the sentence is the API's.
      if (one.link_dropped) lines.push(`  ${one.link_dropped}`);
    }
    for (const one of result.retired) lines.push(`• ${one}: retired.`);
    for (const one of result.skipped) lines.push(`• ${one.prior}: ${one.reason}`);
    const dropped = result.rolled.some((one) => one.link_dropped);
    banner(lines.join("\n"), result.skipped.length || dropped ? "warn" : "ok");
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
  $("tmpl-head-label").textContent = `${form.label} request list — ${vocab.ask_the_client}`;
  $("tmpl-note").textContent = vocab.ask_the_client_note;
  $("ne-name").value = "";
  nameIsAuto = true;
  $("ne-year").value = defaultYear || "";
  $("ne-client").value = householdContact();
  syncNameDefault();
  $("ne-due").value = "";
  // The return's people (decision 128): one taxpayer to start with, whose
  // name pre-fills from the household's contact, because that is who the
  // household said the return is for.
  wizardPeople = [{ ...blankPerson(), name: householdContact() }];
  labelPeopleBlock("wp-head", "wp-help", "wp-add");
  renderPeople("wp-people", wizardPeople, () => {});
  if (wizardPeople[0].name) refreshProposals(wizardPeople[0], () => renderPeople("wp-people", wizardPeople, () => {}));
  renderTemplateList();
  renderCustomRows();
  showStep("items");
  $("ne-client").focus();
}

// The return's name is the form and the client, form first (decision 125):
// the same name every year, so the return line can be followed. It follows
// the client field until the user types a name of their own.
function syncNameDefault() {
  if (!nameIsAuto) return;
  const client = $("ne-client").value.trim();
  $("ne-name").value = client
    ? fill(vocab.layout.return_name_pattern, { form: selectedForm || "", client }).trim()
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

// ── the People block (decision 128) ──────────────────────────────────────
// Who a return is for, with the spellings its documents use. Every label,
// every kind and both refusals are the API's; the proposals are the API's
// too (`propose-spellings`, a read that records nothing) and a person
// ticks them. Nothing here infers a person from a document, and no
// spelling is ever learned except by somebody typing it.

let wizardPeople = [];     // the wizard's list, before the return exists
let editorPeople = [];     // the editor's list, as the record holds it

function blankPerson() {
  return { kind: vocab.people.kinds[0].value, name: "", proposed: [], own: [] };
}

// One person as the API stores them: the ticked proposals and whatever
// spellings the person typed themselves, in that order.
function personSpec(person) {
  return {
    kind: person.kind,
    name: person.name,
    spellings: [...person.proposed.filter((p) => p.on).map((p) => p.text), ...person.own],
  };
}

// The record's people as the block edits them: every spelling it holds is
// a ticked one, because that is what it means for the record to hold it.
function personFromRecord(one) {
  return {
    kind: one.kind, name: one.name,
    proposed: (one.spellings || []).map((text) => ({ text, on: true })), own: [],
  };
}

// What the API would propose for this name, merged over what is there: a
// spelling somebody has already untick stays unticked, a new one arrives
// ticked, and a spelling they typed themselves is never touched.
async function refreshProposals(person, redraw) {
  if (!person.name.trim()) return;
  let result;
  try {
    result = await call(["propose-spellings"], { name: person.name, kind: person.kind });
  } catch (err) {
    toast(err.message);
    return;
  }
  const held = new Map(person.proposed.map((p) => [p.text, p.on]));
  person.proposed = result.spellings.map((text) => ({ text, on: held.get(text) !== false }));
  redraw();
}

function renderPeople(id, people, onChange) {
  const words = vocab.people;
  const redraw = () => { renderPeople(id, people, onChange); onChange(); };
  show(id, people.map((person, index) => {
    const kind = el("select", { "aria-label": words.kind_label },
      words.kinds.map((k) =>
        el("option", { value: k.value, selected: person.kind === k.value }, k.label)));
    kind.addEventListener("change", () => {
      person.kind = kind.value;
      refreshProposals(person, redraw);
      onChange();
    });
    const name = el("input", { type: "text", value: person.name, "aria-label": words.name_label });
    name.addEventListener("input", () => { person.name = name.value; onChange(); });
    // The proposals are fetched when the name is finished, not on every
    // keystroke: each call to the API is a process of its own, and a
    // half-typed name proposes half a spelling.
    name.addEventListener("change", () => { person.name = name.value; refreshProposals(person, redraw); });
    const ticks = person.proposed.map((spelling) => {
      const box = el("input", { type: "checkbox", checked: spelling.on });
      box.addEventListener("change", () => { spelling.on = box.checked; onChange(); });
      return el("label", { className: "wiz-check" }, box, el("span", {}, spelling.text));
    });
    // One spelling per line, never comma-separated: a comma is part of the
    // very form a document prints (`Park, John`), so splitting on one would
    // turn what a person typed into two one-word spellings and refuse both.
    const own = el("textarea", {
      className: "person-own", rows: 2, placeholder: words.own_spelling,
      "aria-label": words.own_spelling,
    });
    // A textarea's text is its content, not a `value` attribute: set after.
    own.value = person.own.join("\n");
    own.addEventListener("input", () => {
      person.own = own.value.split(/\r?\n/).map((one) => one.trim()).filter(Boolean);
      onChange();
    });
    const remove = el("button", { type: "button", className: "btn btn-small" }, words.remove);
    remove.addEventListener("click", () => {
      people.splice(index, 1);
      redraw();
    });
    return el("div", { className: "person" },
      el("label", { className: "field" }, el("span", {}, words.kind_label), kind),
      el("label", { className: "field" }, el("span", {}, words.name_label), name),
      el("div", { className: "person-spellings" },
        el("span", { className: "tmpl-rules", title: words.spellings_help }, words.spellings_label),
        ticks.length ? ticks : el("span", { className: "wiz-note" }, words.help),
        own),
      el("div", { className: "editor-actions" }, remove));
  }));
}

// The block's headings and its Add button, wherever it is drawn.
function labelPeopleBlock(headId, helpId, addId) {
  $(headId).textContent = vocab.people.label;
  $(helpId).textContent = vocab.people.help;
  $(addId).textContent = vocab.people.add;
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
  if (vocab.editor.yes_no_fields.includes(key)) {
    // Named and Asked: a pick of the two words, blank reading as yes.
    const current = row[key] === vocab.editor.no ? vocab.editor.no : vocab.editor.yes;
    const select = el("select", { "aria-label": column.label, title: column.help },
      [vocab.editor.yes, vocab.editor.no].map((value) =>
        el("option", { value, selected: current === value }, value)));
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

// What the learned cell holds for one row: the API's note that these words
// were taught by a filing rather than typed, and then each word with its
// own button that takes it back (decision 113). One event per word, so one
// button per word; the words and both labels are the API's.
function learnedCell(identifier, learned) {
  const taught = learned[identifier] || [];
  if (!taught.length) return [];
  return [
    el("span", { className: "ed-learned-note" }, fill(vocab.editor.learned_note, { keywords: "" })),
    ...taught.map((word) => el("span", { className: "ed-learned-word" }, word,
      el("button", {
        className: "btn btn-small ed-unlearn",
        dataset: { identifier, keyword: word },
        "aria-label": `${vocab.editor.unlearn_label} ${word}`,
        title: `${vocab.editor.unlearn_label} ${word}`,
      }, vocab.editor.unlearn_label))),
  ];
}

// The rows of a request list as a table of inputs: one column per entry of
// `columns`, a cell for the keywords a filing taught the row (the editor
// shows them as taught, never as typed, each with the button that takes
// it back),
// and a Remove button. Renders from
// plain objects keyed by column key; `onChange(rows)` is told about every
// edit, `onRemove(index)` about a removed row, and `onTakeBack(identifier,
// keyword)` about a word taken back. `keyed` shows each row's
// identifier as fixed text (the wizard assigns them); the editor passes
// the identifier as one of its columns instead, typed like the rest.
function requestRows(container, rows, { columns, onChange, onRemove, onTakeBack, learned = {}, keyed = true }) {
  const head = el("tr", {},
    keyed ? el("th", { className: "ed-id" }, columnsByKey(["identifier"])[0].label) : null,
    columns.map((c) => el("th", { title: c.help }, c.label)),
    Object.keys(learned).length ? el("th", {}, "") : null,
    el("th", {}, ""));
  const body = rows.map((row, index) => el("tr", {},
    keyed ? el("td", { className: "ed-id" }, el("span", { className: "req-id" }, row.identifier)) : null,
    columns.map((c) => el("td", { className: `ed-${c.key}` }, cellInput(row, c, () => onChange(rows)))),
    Object.keys(learned).length
      ? el("td", { className: "ed-learned", dataset: { identifier: row.identifier || "" } },
          learnedCell(row.identifier, learned))
      : null,
    el("td", { className: "ed-remove" },
      el("button", { className: "btn btn-small", dataset: { index: String(index) }, "aria-label": `${vocab.editor.remove_row} ${row.identifier || ""}` },
        vocab.editor.remove_row)),
  ));
  const table = el("table", { className: "editor-table" }, el("thead", {}, head), el("tbody", {}, body));
  table.addEventListener("click", (e) => {
    // Taking a keyword back is its own event and lands at once; removing a
    // row is part of the save, like every other edit.
    const word = e.target.closest("button.ed-unlearn");
    if (word) {
      if (onTakeBack) onTakeBack(word.dataset.identifier, word.dataset.keyword);
      return;
    }
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
  // Every catalog row goes on the return (decision 142), each carrying its
  // tick as `asked`: a ticked row is asked for and chased, an unticked one
  // is never chased but files what arrives for it. Custom rows are always
  // asked. A list with nothing asked is refused here and by the API.
  const catalog = [...$("tmpl-list").querySelectorAll("input[type=checkbox]")]
    .map((box) => ({ ...templates[Number(box.dataset.index)], asked: box.checked }));
  if (customItems.some((c) => !String(c.document || "").trim())) {
    toast("Give each custom request a document name first.");
    return;
  }
  const items = [...catalog, ...customItems.map((c) => ({ ...c, asked: true }))];
  const asked = items.filter((i) => i.asked).length;
  if (!asked) {
    toast("Select at least one request item.");
    return;
  }
  const btn = $("ne-create");
  btn.disabled = true;
  try {
    const result = await call(["create"], {
      ...householdSpec(),
      return_name: $("ne-name").value.trim(),
      form: selectedForm,
      items,
      people: wizardPeople.filter((p) => p.name.trim()).map(personSpec),
      client: $("ne-client").value.trim(),
      due: $("ne-due").value,
      year: Number($("ne-year").value) || null,
    });
    $("modal").classList.add("hidden");
    await refresh(result.state.paths.engagement);
    const lines = [
      `Engagement "${result.created}" created — ${asked} request folder(s) scaffolded, client README generated. Open the Client Folder to show it.`,
    ];
    // A household's first return comes back with the sharing checklist
    // (decision 126): the two grants a person makes in Drive, once, in
    // the API's own words. The household card carries the same lines
    // until somebody gives the firm's word on the card.
    if (result.checklist) {
      lines.push(result.checklist.heading);
      result.checklist.lines.forEach((line, n) => lines.push(`${n + 1}. ${line}`));
      lines.push(result.checklist.note);
    }
    // Decision 137: a household link that was not a web address was left
    // out of the new return; the sentence is the API's.
    if (result.link_dropped) lines.push(result.link_dropped);
    banner(lines.join("\n"), result.link_dropped ? "warn" : "ok");
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
    // The two yes/no marks, in the words the API reads them in. Left out,
    // a save sends none and a blank reads as yes, so every save turned a
    // named=no row into yes (decision 142 fixed it with the Asked mark).
    named: rule.named === false ? vocab.editor.no : vocab.editor.yes,
    asked: rule.asked === false ? vocab.editor.no : vocab.editor.yes,
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

// The key the rows nobody asked for fold under (decision 142): not a
// label, so it can never collide with a set-aside group's.
const NOT_ASKED_GROUP = "\u0001";

function editorGroupKey(row) {
  if (isSetAside(row.manual_override)) return overrideLabel(row.manual_override, editorRowYear(row));
  return row.asked === vocab.editor.no ? NOT_ASKED_GROUP : "";
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
    onTakeBack: unlearnKeyword,
  });
  const active = editorRows.filter((row) => !editorGroupKey(row));
  const groups = new Map();
  for (const row of editorRows) {
    const key = editorGroupKey(row);
    if (key) groups.set(key, [...(groups.get(key) || []), row]);
  }
  const activeBox = el("div", { className: "editor-rows" });
  requestRows(activeBox, active, options(active));
  // The rows nobody asked for first, in one group; then the set-aside
  // rows, one group per label. Setting Asked moves a row out before the save.
  const ordered = [...groups.entries()]
    .sort(([a], [b]) => (a === NOT_ASKED_GROUP ? -1 : b === NOT_ASKED_GROUP ? 1 : 0));
  const folded = ordered.map(([label, rows]) => {
    const box = el("div", { className: "editor-rows" });
    requestRows(box, rows, options(rows));
    const heading = label === NOT_ASKED_GROUP
      ? fill(vocab.editor.not_asked_heading, { n: rows.length })
      : fill(vocab.editor.set_aside_heading, { label, n: rows.length });
    return el("details", { className: label === NOT_ASKED_GROUP ? "ed-not-asked" : "ed-set-aside" },
      el("summary", {}, heading), box);
  });
  $("ed-rows").replaceChildren(activeBox, ...folded);
}

// Only the learned column, drawn again from the state the API just sent.
// Nothing else is touched: an unlearn lands on its own, and whatever the
// person has typed into the rows and not saved is theirs to keep.
function renderLearnedCells(learned) {
  for (const cell of $("ed-rows").querySelectorAll("td.ed-learned")) {
    cell.replaceChildren(...learnedCell(cell.dataset.identifier, learned));
  }
}

// One keyword taken back: one event, recorded at once, and the request
// re-scanned by the API in the same breath because its rules just moved.
async function unlearnKeyword(identifier, keyword) {
  let result;
  try {
    result = await call(withEng("unlearn"), { identifier, keyword });
  } catch (err) {
    editorNote(err.message, "err");
    return;
  }
  editorState.learned = result.state.learned || {};
  renderLearnedCells(editorState.learned);
  const said = fill(vocab.editor.unlearned_note, result.unlearned);
  editorNote(result.unlearned.scan_note ? `${said}\n${result.unlearned.scan_note}` : said,
             result.unlearned.scan_note ? "warn" : "ok");
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
// `people` is laid out by its own block below these (decision 128): a
// person is a kind, a name and a list of ticked spellings, which is not a
// box, so it is drawn where it can be edited rather than shown as one.
function renderEngagementFields(info) {
  show("ed-fields", vocab.editor.engagement_fields
    .filter((f) => f.key !== "name" && f.key !== "people")
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
  // The people travel with the rest of the details, as one edit
  // (decision 128): a person with no name yet is a row somebody started
  // and is not sent.
  details.people = editorPeople.filter((p) => p.name.trim()).map(personSpec);
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
  // The return's people, as the record holds them (decision 128): edited
  // here and nowhere else, and saved with the rest of the details.
  editorPeople = ((editorState.engagement || {}).people || []).map(personFromRecord);
  labelPeopleBlock("ep-head", "ep-help", "ep-add");
  renderPeople("ep-people", editorPeople, () => {});
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
$("btn-inbox").addEventListener("click", () => paths && window.tracker.open(paths.inbox));
$("btn-client-folder").addEventListener("click", () => paths && window.tracker.open(paths.client_folder));
$("btn-edit-household").addEventListener("click", openHouseholdEditor);
$("btn-mark-shared").addEventListener("click", markShared);
$("hh-edit-cancel").addEventListener("click", () => $("household-modal").classList.add("hidden"));
$("hh-edit-save").addEventListener("click", saveHousehold);
$("hh-edit-feed-add").addEventListener("click", addEditorFeed);
$("hh-edit-feeds").addEventListener("click", (e) => {
  const remove = e.target.closest("button.hh-feed-remove");
  if (!remove) return;
  editorFeeds.splice(Number(remove.dataset.at), 1);
  renderEditorFeeds();
});
$("ho-cancel").addEventListener("click", () => {
  $("handover-modal").classList.add("hidden");
  handingOver = null;
});
$("ho-return").addEventListener("change", loadHandOverRequests);
$("ho-file").addEventListener("click", fileHandOver);
$("household-returns").addEventListener("click", (e) => {
  const button = e.target.closest("button[data-path]");
  if (!button) return;
  active = button.dataset.path;
  refresh(active);
});
$("btn-edit").addEventListener("click", openEditor);
$("btn-view").addEventListener("click", () => paths && window.tracker.open(paths.view));
$("btn-status").addEventListener("click", () => paths && window.tracker.open(paths.status));
$("btn-copy").addEventListener("click", copyReminder);
$("btn-approve").addEventListener("click", approveReminder);
$("btn-open-draft").addEventListener("click", () => paths && window.tracker.open(paths.draft));
$("reminder-stages").addEventListener("click", (e) => {
  const button = e.target.closest(".rem-stage");
  if (!button || button.disabled) return;
  reminderStage = Number(button.dataset.stage);
  loadReminder();
});
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
$("wh-cancel").addEventListener("click", () => $("modal").classList.add("hidden"));
$("wh-next").addEventListener("click", () => {
  renderPriorPage();
  showStep("prior");
});
$("hh-existing").addEventListener("change", () => {
  syncHouseholdStep();
  renderPriorPage();
});
$("wf-cancel").addEventListener("click", () => $("modal").classList.add("hidden"));
$("wp-cancel").addEventListener("click", () => $("modal").classList.add("hidden"));
$("wp-new-client").addEventListener("click", () => showStep("form"));
$("ro-household").addEventListener("change", (e) => {
  rollFor = e.target.value || null;
  renderPriorPage();
});
$("ro-create").addEventListener("click", rollForward);
$("ro-year").addEventListener("keydown", (e) => e.key === "Enter" && rollForward());
$("ro-year").addEventListener("input", syncUntickedNote);
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
// The People block's one button, in the wizard and in the editor
// (decision 128); the rows wire their own controls as they are drawn.
$("wp-add").addEventListener("click", () => {
  wizardPeople.push(blankPerson());
  renderPeople("wp-people", wizardPeople, () => {});
});
$("ep-add").addEventListener("click", () => {
  editorPeople.push(blankPerson());
  renderPeople("ep-people", editorPeople, () => {});
});
// The returning-client page's button for looking at a return's people
// opens the editor on that return, which is where the block lives and the
// only place a person is added, changed or removed.
$("prior-list").addEventListener("click", async (e) => {
  const button = e.target.closest("button.roll-review-people");
  if (!button) return;
  $("modal").classList.add("hidden");
  active = button.dataset.path;
  await refresh(active);
  openEditor();
});
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
  const over = e.target.closest(".r-hand-over");
  if (over) {
    const li = over.closest("li");
    openHandOver(li.dataset.original, Number(li.dataset.seq));
  }
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
  const over = e.target.closest(".c-hand-over");
  if (over) {
    const card = over.closest(".deck-card");
    openHandOver(card.dataset.original, Number(card.dataset.seq));
  }
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
