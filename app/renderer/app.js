// Renderer logic — renders tracker state; every action round-trips through
// the Python API so the UI can never disagree with the real scanner.

let paths = null;          // paths of the active engagement
let engagements = [];      // [{name, path, household, year, return_name}]
let households = [];       // [{name, path, returns, open_years, ...}]
let misfits = [];          // [{path, sentence}] - the folders left alone
let addingTo = null;       // the household a new return is added to: a path its card reported, or null for a new household
let active = null;         // path of the active engagement
let forms = [];            // tax form catalog [{id, label, who, blurb}]
let templatesByForm = {};  // form id -> tailored request template items
let formsUnloaded = "";    // why the catalog could not be loaded, said in the roll fold's form pick
let defaultYear = null;    // the tax year a new engagement is for (from the calendar)
let nameIsAuto = true;     // new-client name follows client + year + form until typed
let selectedForm = null;   // form id chosen on the dialog's form step
let templates = [];        // template items for the chosen form
let customItems = [];      // custom rows added in the new return's request list (plain objects keyed by column)
let editorRows = [];       // the request-list editor's rows (plain objects keyed by column)
let rollChoice = null;     // the roll fold's unticks and form picks, for the household on screen
let lastState = null;      // the state the household card was drawn from

const $ = (id) => document.getElementById(id);

// Every word the app compares or shows comes from the API's vocabulary
// (tracker.api._vocab): statuses, overrides, decisions, defaults, patterns.
// Nothing here is typed twice; the CSS classes are derived from the keys.
let vocab = null;

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
  "className", "dataset", "id", "type", "value", "placeholder",
  "label", "rows", "checked", "selected", "disabled",
  "aria-label", "aria-pressed", "aria-expanded",
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

// A node with its tooltip (tooltip.js): the replacement for every title
// attribute (SPEC 13). A blank word sets none.
function tipped(node, words) {
  setTip(node, words || "");
  return node;
}

// Flattened, because half the callers build their list as "one fixed node,
// then a mapped array" and replaceChildren() turns an array it is handed
// into the text "[object HTMLOptionElement],..." rather than into its
// elements. That is how the old list of existing households, and the
// rollover's list of form templates, came out holding one option and a
// line of noise; the flatten stays for any caller.
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
  if (isSetAside(override) && year) {
    return fill(vocab.labels[vocab.overrides.not_applicable].label, { year });
  }
  return override || "";
}

// The rows nobody waits on, grouped for the one set-aside fold (decision
// 200): the rows nobody asked for with nothing in first, then one group per
// not-applicable label, oldest year first - the Status Report's
// order. Each group carries its label and that label's sentence from the
// API's table. `idle` says which rows are not asked and idle, `yearOf`
// what year a row's Period gives. `name` is what a group's table is
// called to a screen reader.
function setAsideGroups(rows, idle, yearOf) {
  const notAsked = vocab.labels[vocab.not_asked_label];
  const notApplicable = vocab.labels[vocab.overrides.not_applicable];
  const groups = new Map();
  const add = (label, sentence, order, name, row) => {
    if (!groups.has(label)) groups.set(label, { label, sentence, order, name, rows: [] });
    groups.get(label).rows.push(row);
  };
  for (const row of rows) {
    if (isSetAside(row.manual_override)) {
      const label = overrideLabel(row.manual_override, yearOf(row));
      add(label, notApplicable.sentence, yearOf(row) || 0, label, row);
    } else if (idle(row)) {
      add(notAsked.label, notAsked.sentence, -1, vocab.not_asked_table_label, row);
    }
  }
  return [...groups.values()].sort((a, b) => a.order - b.order || a.label.localeCompare(b.label));
}

// One group's heading inside the set-aside fold: its label and count in
// bold, and the label's sentence beside it as text.
function setAsideHeading(group) {
  return el("div", { className: "req-side" },
    el("span", { className: "side" }, fill(vocab.set_aside.group, { label: group.label, n: group.rows.length })),
    " ", group.sentence);
}

function fill(pattern, values) {
  return pattern.replace(/\{(\w+)\}/g, (_, key) => values[key] ?? "");
}

// A toast is the API's word (vocab.screen.notices), never a sentence typed
// here. A word the vocabulary lacks is a failure said loudly, not a blank.
function toastWord(key) {
  const said = vocab && vocab.screen && vocab.screen.notices ? vocab.screen.notices[key] : "";
  if (!said) {
    failed(new Error(`vocab.screen.notices.${key}`));
    return;
  }
  toast(said);
}

function toast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.add("hidden"), 6000);
}

// A failure the tracker answered with (decision 193): its envelope, and the
// call that met it, so Retry can make the same call again.
class TrackerError extends Error {
  constructor(result, args, payload) {
    super(result.error);
    this.result = result;
    this.failure = result.failure || { sentence: result.error, kind: "failed", seq: null, identifier: null };
    this.args = args;
    this.payload = payload;
  }
}

// Every reply's warnings become notices, and an error throws its envelope.
// `ofAnother`: the reply is a read of a return other than the one shown
// (the hand-over picker's), so its warnings are said under that return's
// label (decision 194's review, S1), never as if about the return shown.
async function call(args, payload, { ofAnother = false } = {}) {
  const result = await window.tracker.call(args, payload);
  if (result && Array.isArray(result.warnings) && result.warnings.length) {
    warningNotices(ofAnother ? result.warnings.map((sentence) =>
      fill(vocab.notices.about, { label: labelOfState(result), sentence })) : result.warnings);
  }
  if (result.error) throw new TrackerError(result, args, payload);
  return result;
}

// ── notices: a failure or a warning stays until a person dismisses it ────
// (decision 193). A failure offers Retry (a stale one too: the same read
// again), a notice may carry one action of its own (Show, Accept), and every
// one ends in the dismiss icon; the row a notice names is outlined on every
// redraw until it is dismissed. The buttons come from index.html's template,
// so a notice works before any vocabulary has arrived (a failed first start).

const notices = [];   // [{sentence, kind, identifier, count, retry, action, node}]

function noticeButton(act) {
  return $("notice-buttons").content.querySelector(`[data-act="${act}"]`).cloneNode(true);
}

// What Retry does for a notice: the call that failed, or - for a stale one,
// whose row moved - the read of the return again.
function retryOf(entry) {
  if (entry.kind === "stale") return entry.retry || (() => showReturn(active));
  return entry.kind === "failed" ? entry.retry : null;
}

function drawNotice(entry) {
  const text = entry.count > 1 && vocab
    ? `${entry.sentence} ${fill(vocab.notices.repeated, { n: entry.count })}`
    : entry.sentence;
  const buttons = [];
  if (entry.action) {
    const act = noticeButton("retry");
    act.dataset.act = "action";
    act.textContent = entry.action.label;
    if (entry.action.write) {
      act.dataset.write = "1";
      if (locked) {
        act.disabled = true;
        act.dataset.lockGreyed = "1";
      }
    }
    buttons.push(act);
  } else if (retryOf(entry)) {
    buttons.push(noticeButton("retry"));
  }
  const dismiss = noticeButton("dismiss");
  if (vocab && vocab.screen) {
    dismiss.setAttribute("aria-label", vocab.screen.icons.dismiss);
    setTip(dismiss, vocab.screen.icons.dismiss);
  }
  entry.node.replaceChildren(el("span", { className: "notice-text" }, text), ...buttons, dismiss);
}

function notice(failure, { retry, action } = {}) {
  if (!failure || !failure.sentence) return null;
  const kind = failure.kind || "failed";
  // A keyed notice is its own line even when another says the same short words.
  let entry = notices.find((one) => one.sentence === failure.sentence && one.kind === kind && one.key === (failure.key || null));
  if (entry) {
    entry.count += 1;
    entry.retry = retry || entry.retry;
    entry.action = action || entry.action;
  } else {
    entry = { sentence: failure.sentence, kind, identifier: failure.identifier || null, key: failure.key || null, count: 1, retry, action };
    entry.node = el("div", { className: `notice notice-${kind}` });
    notices.push(entry);
    $("notices").append(entry.node);
  }
  drawNotice(entry);
  outlineRefused();
  if (kind === "locked" && failure.lock) showLock(failure.lock);
  return entry;
}

// A notice that belongs to a state of the page, not to an event: the lock,
// the reader's warning, a household's two open years. One per key. It is
// said once for a sentence: dismissed, it does not come back on the next
// draw; it goes when the state does (clearNotice) and returns if the state
// does (a different sentence, or the same one after it cleared).
const keyedNotices = new Map();   // key -> {sentence, kind, entry}

function keyedNotice(key, failure, opts) {
  const kind = failure.kind || "failed";
  const had = keyedNotices.get(key);
  if (had && had.sentence === failure.sentence && had.kind === kind) return false;
  if (had && notices.indexOf(had.entry) !== -1) dismissNotice(had.entry);
  keyedNotices.set(key, { sentence: failure.sentence, kind, entry: notice({ ...failure, key }, opts) });
  return true;
}

function clearNotice(key) {
  const had = keyedNotices.get(key);
  if (had && notices.indexOf(had.entry) !== -1) dismissNotice(had.entry);
  keyedNotices.delete(key);
}

// A set of keyed notices under one prefix: those wanted are shown, the rest
// are cleared. `wanted` is [{key, failure, opts}].
function syncNotices(prefix, wanted) {
  const keep = new Set(wanted.map((one) => `${prefix}:${one.key}`));
  for (const key of [...keyedNotices.keys()]) {
    if (key.indexOf(`${prefix}:`) === 0 && !keep.has(key)) clearNotice(key);
  }
  for (const one of wanted) {
    // Its detail (the long sentence, the error's own message) goes to the
    // error log when the notice first shows, never on screen (SPEC 11.1).
    if (keyedNotice(`${prefix}:${one.key}`, one.failure, one.opts) && one.detail) window.tracker.logError(one.detail);
  }
}

// What a write said (SPEC 2.2, P63 rule 6): what went well shows in the
// rows themselves, so it says nothing - or, where its effect is off screen,
// a toast; what did not go well is a notice per line, and stays.
function outcome(text, cls, { toasted = false } = {}) {
  if (cls === "ok") {
    if (toasted && text) toast(text);
    return;
  }
  for (const line of String(text).split("\n")) {
    const said = line.replace(/^•\s*/, "").trim();
    if (said) notice({ sentence: said, kind: cls === "err" ? "failed" : "warning" });
  }
}

// The label a state reply gives its own return, from its household's list.
function labelOfState(state) {
  const here = state.paths ? state.paths.engagement : "";
  const own = ((state.household || {}).returns || []).find((one) => one.path === here);
  return own ? own.label : here;
}

function warningNotices(list) {
  for (const sentence of list) notice({ sentence, kind: "warning" });
}

// What a caught error is said as, wherever it is said: the tracker's own
// sentence from its envelope, or - for an error of the page's own - its
// class alone, in the API's sentence; that message goes to the error log
// through the shell, never on screen (principle 7; the review's S5).
function failureSentence(err) {
  if (err && err.failure) return err.failure.sentence;
  const kind = (err && err.name) || "Error";
  window.tracker.logError(`${kind}: ${String((err && err.message) || err)}\n${(err && err.stack) || ""}`);
  return vocab ? fill(vocab.shell.page_error, { kind }) : kind;
}

// A caught error, said as a notice: the tracker's envelope, or a failure
// of the page's own in failureSentence's words. Returns the sentence, for
// a caller that also says it where the person is reading (decision 201).
function failed(err, retry) {
  if (err && err.failure) {
    notice(err.failure, { retry });
    return err.failure.sentence;
  }
  const sentence = failureSentence(err);
  notice({ sentence, kind: "failed", seq: null, identifier: null }, { retry });
  return sentence;
}

function dismissNotice(entry) {
  const at = notices.indexOf(entry);
  if (at >= 0) notices.splice(at, 1);
  entry.node.remove();
  outlineRefused();
}

function outlineRefused() {
  const named = new Set(notices.map((one) => one.identifier).filter(Boolean));
  for (const row of document.querySelectorAll("[data-row]")) {
    row.classList.toggle("refused", named.has(row.dataset.row));
  }
}

// ── the view generation (D6): a late reply never paints another return ──

let viewGeneration = 0;

// The one way the shown return changes: every reply started before it is
// dropped when it arrives.
function select(path) {
  active = path;
  stopLockWatch();   // the lock shown next starts its own watch (the review's M1)
  return ++viewGeneration;
}

// Every draw after an await: only while the view it was asked for is
// still the one shown.
function renderFor(view, state) {
  if (view !== viewGeneration) return false;
  render(state);
  applyLock();
  outlineRefused();
  return true;
}

const withEng = (cmd) => (active ? [cmd, vocab.engagement_flag, active] : [cmd]);

// ── rendering ───────────────────────────────────────────────────────────

// The state of one return has arrived (a read or a write's reply): the
// reminder's letter is drawn into the side sheet, and the shell draws the
// page (pages.js groups it by the API's `group`) and moves the sheet on
// (sheet.js). Nothing after the assignment can throw into the write that
// brought the state: an error of the page's own is a notice, and the write
// stands (review 2 of S4, note 1).
function render(state) {
  paths = state.paths;
  lastState = state;
  if (state.household && rollChoice && rollChoice.household !== state.household.path) rollChoice = null;
  try {
    renderLock(state);
    renderReminder(state);
  } catch (err) {
    failed(err);
  }
  shellStateArrived(state);   // shell.js: the page, the sheet, and the firm's counts if they moved
}

// ── The week's reminder (decision 118) ──────────────────────────────────

// The card is the one place a person sees the draft, moves it up or down
// the ladder, copies it and approves it. It arrives with the state
// (`state.reminder_card`, decision 194): exactly what the `reminder`
// command answers at the record's stage, so a switch or a write is one
// reply and the card cannot disagree with the table. The `reminder`
// command is the stage toggle's: it regenerates the letter in memory at
// the rung a person moved to, and redraws the card after a refused approve.
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
  drawReminderReply(state.reminder_card || { reminder: null, not_yet: "" });
  // A rung a person moved the toggle to on this return survives a write
  // by one call, and only then (decision 194, R3): the state's card is at
  // the record's stage.
  if (reminderStage !== null && reminderCard && reminderCard.editable
      && reminderCard.stage !== reminderStage) loadReminder();
}

// One card from either source - the state's `reminder_card` or the
// `reminder` command's reply, which are the same shape: the card, the
// not-yet line (D7), or the sentence saying why it could not be composed
// (its notice comes from the reply's warnings).
function drawReminderReply(reply) {
  if (reply.reminder) {
    drawReminder(reply.reminder);
    return;
  }
  reminderCard = null;
  drawReminderLine(reply.unreadable || reply.not_yet);
}

async function loadReminder() {
  if (!active) return;
  const view = viewGeneration;
  try {
    const result = await call(withEng("reminder"), { stage: reminderStage });
    if (view !== viewGeneration) return;
    drawReminderReply(result);
  } catch (err) {
    // A reminder that cannot be read is said, and the card stays (D7).
    if (view !== viewGeneration) return;
    failed(err, loadReminder);
    reminderCard = null;
    drawReminderLine(vocab.reminder.unreadable);
  }
}

// The sheet's reminder with one line and nothing to copy or approve
// (decision 193): the sheet stays, whatever the read said.
function drawReminderLine(line) {
  $("sheet-reminder").classList.add("line-only");
  $("reminder-actions").classList.add("hidden");
  $("reminder-status").textContent = line;
  $("reminder-status").classList.remove("hidden");
}

function drawReminder(card) {
  reminderCard = card;
  $("sheet-reminder").classList.remove("line-only");
  const words = vocab.reminder;
  const rows = (card.held || []).length;
  const unsorted = card.unsorted || 0;
  // Held by a row (decision 115), or by files still waiting in the
  // household's inbox (decision 133): the same card either way.
  const held = rows > 0 || unsorted > 0;
  // Held, the sheet is the hold, the rows holding it and the toggle, and
  // nothing else at all — not even what the record last drafted.
  $("reminder-status").textContent = held ? "" : reminderStatus(card);
  $("reminder-status").classList.toggle("hidden", held);

  // The hold, said once and here: the sentence, then the requests under it
  // with the reason each carries (decision 115's rows, in 118's card).
  const hold = $("reminder-hold");
  hold.classList.toggle("hidden", !held);
  hold.style.setProperty("--stage-ink", words.palette[words.hold_colour]);
  $("reminder-held").textContent = card.held_too_long
    ? `${holdLine(rows, unsorted)}\n${card.held_too_long}`
    : holdLine(rows, unsorted);
  // A held row is named by its document alone: never its request code, and
  // the engine's long hold sentence (row.reason) is the status page's, not
  // the sheet's (SPEC 7.2, 11.1).
  show("reminder-held-rows", (card.held || []).map((row) => el("li", {}, row.document)));

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
    }, el("span", { className: "rem-stage-n" }, stage.number), ` ${pagesStage(stage.number)}`);
    button.style.setProperty("--stage-ink", vocab.reminder.palette[stage.colour]);
    return button;
  }));

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
  // like something to send. There is no file to open at all (SPEC 7.2).
  $("reminder-actions").classList.toggle("hidden", held);
}

// The hold, in the API's words: the rows' line, the inbox's line, or both.
function holdLine(rows, unsorted) {
  return [
    rows ? fill(vocab.reminder.held_line, { n: rows }) : "",
    unsorted ? fill(vocab.reminder.inbox_held_line, { n: unsorted }) : "",
  ].filter(Boolean).join(" · ");
}

// The sheet's caption (SPEC 7.2): the approval the record holds, or when the
// letter was drafted and at which stage - all the API's words, the dates as
// the pages say them.
function reminderStatus(card) {
  const words = vocab.reminder;
  if (card.approved) {
    return fill(words.approved_line, { date: card.approved.date, n: card.approved.stage });
  }
  if (card.lapsed) return words.approved_then_edited;
  if (card.last) return fill(screenWords().sheet.drafted, { date: pagesDay(card.last.date), n: card.last.stage });
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
    outcome(vocab.reminder.copied, "ok", { toasted: true });
  } catch (err) {
    failed(err, copyReminder);
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
    outcome(result.set_aside
      ? `${said}. ${fill(vocab.reminder.set_aside_line, { name: result.set_aside })}.`
      : said, "ok");
  } catch (err) {
    failed(err, approveReminder);
    await loadReminder();
  } finally {
    btn.disabled = false;
  }
}

// ── A copy that wandered: the answers, all of them a person's ───────────
//
// A working copy that is not where the record put it (decision 109) is the
// first question of the morning: nothing is guessed, and the person chooses.
// The sheet (sheet.js) draws one such row (movedRow) beside the file's name
// and its request: Put back, or - offered only when the copy sits in some
// request's folder, which the API says - Keep here.

// The keyword box, one builder for its three places - a moved copy's
// keep-it-here and the review row (decision 201, D11): a
// visible label that stays while the person types, and the sentence
// saying what the word does as its title. Every word is the API's.
function keywordBox() {
  const words = vocab.review_labels;
  return el("label", { className: "field r-keyword-box" },
    el("span", {}, words.keyword),
    el("input", { type: "text", className: "r-keyword" }));
}

// A note a person may leave when setting a document aside or unfiling it, labelled with the
// words that were its placeholder (decision 201): a placeholder is gone
// the moment somebody types, and a box must keep its name.
function noteBox(words) {
  return el("label", { className: "field r-note-box" },
    el("span", {}, words),
    el("input", { type: "text", className: "r-note" }));
}

function movedRow(m, choices, items = choices) {
  // Decision 157: a copy whose original is gone too has nothing to put
  // back or keep - each would refuse - so the one answer offered is the
  // person's Mark missing on the row's own request, which puts the document
  // back on the client's letter.
  // The button names the request by its name, never its code (SPEC 11.1).
  if (m.gone) {
    const asked = m.identifier ? items.find((i) => i.identifier === m.identifier) : null;
    if (m.identifier && !asked) throw new Error(`items.${m.identifier}`);
    return el("li", { className: "sheet-row", dataset: { original: m.handle, row: m.handle, seq: m.seq } },
      asked && el("button", { className: "btn btn-primary r-withdraw", dataset: { identifier: m.identifier } },
        fill(vocab.review_labels.mark_missing, { identifier: pagesItemName(asked) })),
    );
  }
  return el("li", { className: "sheet-row", dataset: { original: m.handle, row: m.handle, seq: m.seq } },
    // The picker is the same picker: a person may keep the copy where it
    // is and correct the request in one click, so it starts on the request
    // whose folder holds it.
    m.in_request && el("select", { "aria-label": vocab.review_labels.hand_over_request },
      choices.map((i) => requestOption(i, m.in_request))),
    m.in_request && keywordBox(),
    el("button", { className: "btn btn-primary r-restore" }, vocab.review_labels.restore),
    m.in_request && el("button", { className: "btn r-keep" }, vocab.review_labels.keep),
  );
}

async function restoreMoved(li, btn) {
  const view = viewGeneration;   // drawn only if this return is still the one shown (D6)
  btn.disabled = true;
  try {
    const result = await call(withEng("restore"), {
      original: li.dataset.original,
      seq: Number(li.dataset.seq),
    });
    renderFor(view, result.state);
    const r = result.restored;
    const notes = [`${r.original_name}: ${r.decision}`, r.reason];
    if (r.scan_note) notes.push(r.scan_note);
    outcome(notes.join(". ") + ".", r.parked_as || r.scan_note ? "warn" : "ok");
  } catch (err) {
    await refused(err, btn);
  }
}

// Keeping the copy where it is, is a filing, so it is the filing command,
// with the request the person left the picker on and the keyword they typed.
async function keepMoved(li, btn) {
  const identifier = li.querySelector("select").value;
  if (!identifier) {
    toastWord("pick_request");
    return;
  }
  btn.disabled = true;
  try {
    await fileRow(li.dataset.original, identifier, Number(li.dataset.seq), typed(li, ".r-keyword"));
  } catch (err) {
    await refused(err, btn);
  }
}

// ── Needs review: a person's decision, carried out by the filer ──────────

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
    el("label", { className: "field r-spelling-box" },
      el("span", {}, words.teach_hint),
      el("input", { type: "text", className: "r-spelling" })));
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
  // The request is named by its document; the code is only the value.
  return el("option", { value: item.identifier, selected: item.identifier === picked }, item.document);
}

// One file's answers, as the side sheet draws them (sheet.js places the parts
// of this row in the sheet's body, its More fold and its footer). The
// question is the same whether the document is waiting or has been set aside
// - which request does this belong to - so it is asked the same way; only an
// open question offers the reasons, the two boxes, the button that sets a
// document aside, and the shortlist.
//
// The shortlist is the picker's first entries, in the order the API ranked
// them, and the sentence behind each is listed beneath the picker: an <option>
// can carry no second line, and the reason is the whole point - a person
// reads why before they pick. Everything below the divider is every other
// request, because a suggestion is a suggestion and nothing is taken away.
// A row that is not a document (decision 190) is never filed: it says its
// true type, and offers only the answer that sets it aside. The open icon
// offers the review copy only where the API named a key for it (decision
// 190, following 184: a document the tracker read and parked, never an email
// or a zip, nor a file whose reading was refused), and opens it by that key
// in state.paths - never a path of ours.
const BELONGS_TO = "Belongs To…";

function notADocument(row) {
  return Boolean(row) && row.bucket === vocab.review_labels.not_a_document;
}

function trueType(row) {
  return notADocument(row)
    ? el("span", { className: "r-type" },
        fill(vocab.review_labels.true_type, { extension: row.extension }))
    : null;
}

function reviewRow(e, choices, ids, open, triage, people = []) {
  const attrs = { className: "sheet-row", dataset: { original: e.handle, row: e.handle, seq: e.seq } };
  if (notADocument(e)) {
    return el("li", attrs,
      trueType(e),
      open && el("div", { className: "sheet-more hidden" }, noteBox(vocab.review_labels.dismiss_note)),
      open && el("button", { className: "btn r-dismiss" }, vocab.review_labels.dismiss),
    );
  }
  const shortlist = (triage && triage.shortlist) || [];
  const suggested = shortlist.map((s) => s.identifier);
  const byId = new Map(choices.map((i) => [i.identifier, i]));
  const best = suggested.map((id) => byId.get(id)).filter(Boolean);
  const rest = choices.filter((i) => !suggested.includes(i.identifier));
  // The picker starts on the best suggestion; failing that, on the router's
  // own first candidate, which is what it started on before there was one.
  const guess = suggested[0] || (e.candidates || [])[0] || "";
  const picked = guess && ids.has(guess) ? guess : "";
  // The row's record version travels with the sheet and comes back with the
  // click, so the filer judges the decision against the row it was made on.
  return el("li", attrs,
    el("select", { "aria-label": BELONGS_TO },
      el("option", { value: "" }, BELONGS_TO),
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
    open && issuerBox(triage),
    // And the one click (decision 204), on a row that names another
    // household's person: what it will file, then the button.
    waitsFor(triage, "r-where-it-waits"),
    // The rarely used answers fold under More (SPEC 7.1): the keyword, the
    // spelling to teach, the reason, and the answer that files it under a
    // request of another return this drop folder feeds (decision 129),
    // offered only where there is one.
    open && el("div", { className: "sheet-more hidden" },
      keywordBox(),
      teachSpelling(triage, people),
      noteBox(vocab.review_labels.dismiss_note),
      fedReturns().length
        ? el("button", { className: "btn btn-subtle r-hand-over" }, vocab.review_labels.hand_over) : null),
    el("button", { className: "btn btn-primary r-file" },
      open ? vocab.review_labels.file : vocab.review_labels.file_anyway),
    open && el("button", { className: "btn r-dismiss" }, vocab.review_labels.dismiss),
  );
}

// Decision 204's one click: a parked row that names the person of a return
// in another household carries what that return's list accepted, resolved by
// the API against the feed list. Everything the click does is on the screen -
// the requests it files under, as the picker names them, and the Also
// Answers - and the button sends nothing but the row and its version. Where
// the claim no longer resolves, the API's own sentence stands in its place.
function waitsFor(triage, className) {
  if (!triage) return null;
  if (triage.waits_for_refused) {
    return el("span", { className: "r-why" }, triage.waits_for_refused);
  }
  const w = triage.waits_for;
  if (!w) return null;
  return el("div", { className: "where-it-waits" },
    el("ul", { className: "r-reasons" },
      w.requests.map((r) => el("li", {}, r.document)),
      w.answers.length
        ? el("li", {}, `${vocab.review_labels.also_answers} ${w.answers.join(", ")}`) : null),
    el("button", { className: `btn btn-primary ${className}` },
      fill(vocab.review_labels.file_where_it_waits, { label: w.label })));
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
  const view = viewGeneration;   // drawn only if this return is still the one shown (D6)
  const result = await call(withEng("assign"), { original, identifier, keyword, spelling, seq });
  renderFor(view, result.state);
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
  outcome(notes.join(". ") + ".",
    a.keyword_note || a.spelling_note || a.left_in_review || a.overrode_shortlist || a.scan_note
      ? "warn" : "ok");
}

// ── An unnamed issuer: one box, one button (decision 201) ───────────────
// A K-1 parked because it names none of the list's issuers carries the row
// the API will add - the next free one in F's block, named before anything
// is pressed - one box for the issuer's name as the K-1 prints it, and one
// button. The page sends the row, its version, the list's version the card
// was drawn from and the typed name: no identifier and no row, so it names
// no column value of its own. The API builds the row, checks it by the
// editor's own rules and files the document under it, in one step.
function issuerBox(triage) {
  const offer = triage && triage.issuer;
  if (!offer) return null;
  const words = vocab.review_labels;
  return el("div", { className: "r-issuer", dataset: { head: (lastState && lastState.list_head) || "" } },
    el("label", { className: "field" },
      el("span", {}, words.issuer_label),
      el("input", { type: "text", className: "r-issuer-name" })),
    el("button", { className: "btn r-add-issuer" }, words.issuer_add),
    el("p", { className: "wiz-note" }, fill(words.issuer_help, { identifier: offer.identifier })));
}

// The one place the issuer is added and the document filed. The list's
// row reaches it; a refusal is said the way a filing's is, and the row is
// drawn again from the record.
async function addIssuerAndFile(node, btn) {
  const box = btn.closest(".r-issuer");
  const view = viewGeneration;   // drawn only if this return is still the one shown (D6)
  btn.disabled = true;
  try {
    const result = await call(withEng("add-issuer-and-file"), {
      original: node.dataset.original, seq: Number(node.dataset.seq),
      head: box.dataset.head, issuer: typed(box, ".r-issuer-name"),
    });
    renderFor(view, result.state);
    const done = result.added_and_filed;
    const notes = [done.said];
    if (done.assigned.scan_note) notes.push(done.assigned.scan_note);
    outcome(notes.join("\n"), done.assigned.scan_note ? "warn" : "ok");
  } catch (err) {
    await refused(err, btn);
  }
}

// ── File under another return (decision 129) ─────────────────────────────
//
// One decision the API carries out whole: the original moves where it must
// rest, the working copy is made in the taking return's Prepared folder, the
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
  openDialog("handover-modal");
  await loadHandOverRequests();
}

// The taking return's own request list, read from its state - the same
// answer the editor and the pass read, so the picker can only offer a
// request that return really has.
async function loadHandOverRequests() {
  const target = $("ho-return").value;
  show("ho-request", [el("option", { value: "" }, "…")]);
  try {
    const state = await call(["state", vocab.engagement_flag, target], undefined, { ofAnother: true });
    show("ho-request", state.items.map((i) => requestOption(i, "")));
  } catch (err) {
    failed(err, loadHandOverRequests);
  }
}

async function fileHandOver() {
  const btn = $("ho-file");
  const identifier = $("ho-request").value;
  if (!handingOver || !identifier) {
    toastWord("pick_request");
    return;
  }
  btn.disabled = true;
  try {
    await handOver({
      original: handingOver.original, identifier, target: $("ho-return").value,
      seq: handingOver.seq,
    });
    closeDialog("handover-modal");
  } catch (err) {
    failed(err);
  } finally {
    btn.disabled = false;
    handingOver = null;
  }
}

// The one place a document is handed over (decisions 132 and 204): the
// picker's answer and the one click are one decision, so they are one call
// and one set of sentences afterwards.
async function handOver(spec) {
  const view = viewGeneration;   // drawn only if this return is still the one shown (D6)
  const result = await call(withEng("assign"), spec);
  renderFor(view, result.state);
  const a = result.handed_over;
  const notes = [`${a.original_name}: ${fill(vocab.review_labels.handed_over,
    { label: a.label, identifier: a.identifier })}`];
  if (a.left_in_review) notes.push(a.left_in_review);
  if (a.scan_note) notes.push(a.scan_note);
  outcome(notes.join(". ") + ".", a.left_in_review || a.scan_note ? "warn" : "ok");
}

// The one click (decision 204): the row and its version, and nothing
// picked here - the API reads what the row waits for and hands it over.
async function fileWhereItWaits(original, seq, btn) {
  btn.disabled = true;
  try {
    await handOver({ original, seq, waiting: true });
  } catch (err) {
    await refused(err, btn);
  }
}

async function assignParked(li, btn) {
  const identifier = li.querySelector("select").value;
  if (!identifier) {
    toastWord("pick_request");
    return;
  }
  btn.disabled = true;
  try {
    await fileRow(li.dataset.original, identifier, Number(li.dataset.seq),
                  typed(li, ".r-keyword"), spellingFrom(li));
  } catch (err) {
    await refused(err, btn);
  }
}

// A refusal a person has to look at again: the sentence is the API's, and
// the page is drawn again from the record so what they see next is what the
// record now holds rather than the row they acted on.
async function refused(err, btn) {
  failed(err);
  if (btn) btn.disabled = false;
  await showReturn(active);
}

// Open is the review copy the API named under this key in state.paths
// (decision 190): the shell opens only the paths the API reported, so a
// key the state does not hold opens nothing. The sheet's open icon calls it.
function openReviewCopy(btn) {
  const target = paths && paths[btn.dataset.key];
  if (target) openPath(target);
}

// ── The way back, so nobody corrects a filing in Explorer ────────────────

// A filed original is unfiled, or one request it answered is marked missing,
// from the right-click menu of a request already answered (SPEC 5.2, the
// `received` template); the index is the only thing that knows where a working copy
// went, and a correction made in Explorer is one it never learns. One
// original can have a copy under more than one request (a page that carried
// two forms); Unfile still takes the one original, because the row is one row
// and every copy goes back with it. Each takes the row's handle and its
// record version (`seq`) and no button: the menu has none.

// A menu item has no button to grey, so the write in flight is remembered by
// what it writes: a second Unfile of the same original before the reply would
// carry the same `seq`, be refused, and be reported as a failure although the
// first worked. writeBusy() lets the row's menu grey the item meanwhile.
const writesInFlight = new Set();
function writeKey(command, original, identifier) {
  return `${command} ${original} ${identifier || ""}`;
}
function writeBusy(command, original, identifier) {
  return writesInFlight.has(writeKey(command, original, identifier));
}
function writeStart(key) {
  if (writesInFlight.has(key)) return false;
  writesInFlight.add(key);
  return true;
}
function writeDone(key) {
  writesInFlight.delete(key);
}

// The statement stays filed; only the one request comes off what it
// answers, and the re-scan puts that request back to what its folder holds.
async function withdrawAnswer(spec, btn) {
  const view = viewGeneration;   // drawn only if this return is still the one shown (D6)
  const busy = writeKey("mark-missing", spec.original, spec.identifier);
  if (!writeStart(busy)) return;
  if (btn) btn.disabled = true;
  try {
    const result = await call(withEng("mark-missing"), {
      original: spec.original,
      identifier: spec.identifier,
      note: spec.note || "",
      seq: Number(spec.seq),
    });
    renderFor(view, result.state);
    const m = result.marked_missing;
    const notes = [`${m.original_name}: ${m.reason}`];
    if (m.scan_note) notes.push(m.scan_note);
    outcome(notes.join(". ") + ".", m.scan_note ? "warn" : "ok");
  } catch (err) {
    await refused(err, btn);
  } finally {
    writeDone(busy);
  }
}

// Nothing is deleted and nothing is moved: the row is rewritten, so the
// banner says what the row now reads and the file is still where it was.
// From the sheet's set-aside button, or the row's right-click menu (the
// sheet presses it), with the note the person left in More.
async function dismissParked(li, btn) {
  const view = viewGeneration;   // drawn only if this return is still the one shown (D6)
  btn.disabled = true;
  try {
    const result = await call(withEng("dismiss"), {
      original: li.dataset.original,
      note: typed(li, ".r-note"),
      seq: Number(li.dataset.seq),
    });
    renderFor(view, result.state);
    const d = result.dismissed;
    const notes = [`${d.original_name}: ${d.decision}`, d.reason];
    outcome(notes.join(". ") + ".", "ok");
  } catch (err) {
    await refused(err, btn);
  }
}

// A right-click Unfile asks first, in a small box (ruling 16): the file's
// name, the optional reason the old list's Unfile carried, Cancel and the
// confirm. The reason goes to the write as `note`; it is never required.
let unfiling = null;
function openUnfile(spec) {
  const words = vocab.review_labels;
  unfiling = spec;
  $("uf-title").textContent = words.unfile;
  $("uf-name").textContent = spec.name || "";
  $("uf-note-label").textContent = words.unfile_note;
  $("uf-note").value = "";
  $("uf-cancel").textContent = vocab.editor.cancel;
  $("uf-confirm").textContent = words.unfile;
  $("uf-confirm").disabled = false;
  openDialog("unfile-modal");
}

async function confirmUnfile() {
  if (!unfiling) return;
  const btn = $("uf-confirm");
  btn.disabled = true;   // the write is in flight: one press, one write
  try {
    await unfileDocument({ ...unfiling, note: $("uf-note").value.trim() });
  } finally {
    btn.disabled = false;
    closeDialog("unfile-modal");
  }
}

// The copy goes back under the client's own name and the request reverts in
// the same breath, so the banner says where the document is now, not what
// it stopped being.
async function unfileDocument(spec) {
  const view = viewGeneration;   // drawn only if this return is still the one shown (D6)
  const busy = writeKey("unfile", spec.original);
  if (!writeStart(busy)) return;
  try {
    const result = await call(withEng("unfile"), {
      original: spec.original,
      note: spec.note || "",
      seq: Number(spec.seq),
    });
    renderFor(view, result.state);
    const u = result.unfiled;
    const notes = [`${u.original_name}: ${u.decision}`];
    if (u.left_filed) notes.push(u.left_filed);
    if (u.scan_note) notes.push(u.scan_note);
    outcome(notes.join(". ") + ".", u.left_filed || u.scan_note ? "warn" : "ok");
  } catch (err) {
    await refused(err, null);
  } finally {
    writeDone(busy);
  }
}

// Every folder the walk left alone, with the one sentence saying why: a
// notice with the count and Show, which opens the dialog of names (S5's
// #misfits-modal). Nothing in a misfit is ever read, moved or renamed. The
// list itself goes to the dialog; the notice carries no path.
function renderMisfits() {
  if (!misfits.length) {
    clearNotice("misfits");
    return;
  }
  const words = vocab.screen.notices;
  keyedNotice("misfits", { sentence: fill(words.skipped, { n: misfits.length }), kind: "warning" },
    { action: { label: words.show, run: () => (typeof openMisfits === "function" ? openMisfits() : unanswered("misfits")) } });
}

// ── the household's roll dialog (decisions 126 and 196) ────────────────────
// A household rolls as a household, from the Client menu's Roll forward…, and
// only when the API names the year (state.household.roll_year: one open year,
// not paused, and that year has ended). Every return the roll carries is
// ticked; an unticked one is retired, which the API's sentence says before
// anything is unticked. The year is named, never typed, and which returns
// the roll carries is the API's word too (each return's rollable). The
// ticks and picks belong to the household they were made on (decision 196):
// another household's leftover choice is dropped when its state arrives.

// The dialog (SPEC 2.7, E92): the menu opens it on the household whose state
// is on screen; a household with nothing to roll never gets here (the menu
// item is grey) and is said if it does.
function openRoll() {
  const hh = lastState && lastState.household;
  if (!hh || !hh.roll_year) {
    unanswered("roll_forward");
    return;
  }
  renderRollFold(hh);
  openDialog("roll-modal");
}

function renderRollFold(hh) {
  const words = vocab.household;
  const year = hh.roll_year;
  const choice = rollChoice && rollChoice.household === hh.path ? rollChoice : null;
  $("roll-title").textContent = fill(words.roll_forward_to, { year });
  $("roll-cancel").textContent = vocab.editor.cancel;
  $("btn-roll").textContent = fill(words.roll_ticked, { year });
  show("roll-body", [
    hh.returns.filter((r) => r.rollable).map((r) => {
      const picked = choice && choice.forms.has(r.path) ? choice.forms.get(r.path) : r.form;
      const known = forms.some((f) => f.id === picked);
      return el("div", { className: "prior-item roll-return" },
        el("label", { className: "prior-head" },
          el("input", { type: "checkbox", className: "roll-tick",
                        checked: !(choice && choice.unticked.has(r.path)),
                        dataset: { path: r.path } }),
          el("span", { className: "prior-name" }, r.label),
        ),
        // The people the roll carries unchanged (decision 128), under the
        // return they belong to, with the way to look at them. Nothing
        // blocks on the look: strict parking is the safety net.
        el("div", { className: "prior-people" },
          el("span", { className: "prior-meta" },
            `${vocab.people.label}: ${(r.people || []).join(", ") || "—"}`),
          el("button", { type: "button", className: "btn btn-small roll-review-people",
                         dataset: { path: r.path } }, vocab.people.review_people),
        ),
        el("label", { className: "field roll-form" },
          el("span", {}, vocab.roll_template_label),
          // The return's own recorded form is picked by default (decision
          // 142's review, R2), so the catalog rows it never had arrive as
          // not asked without anybody choosing; "no template" is the
          // default only for a return that never recorded one. A catalog
          // that could not be loaded is said here, where the pick is read,
          // and no pick is drawn: the roll keeps each recorded form rather
          // than sending "no template" for all of them.
          formsUnloaded
            ? el("span", { className: "wiz-note" },
              fill(words.roll_forms_unloaded, { reason: formsUnloaded }))
            : el("select", { className: "roll-form-pick", dataset: { path: r.path } },
              el("option", { value: "", selected: !known }, words.roll_no_template),
              forms.map((f) => el("option", { value: f.id, selected: f.id === picked },
                `${f.label} · ${f.who}`)),
            ),
        ),
      );
    }),
    el("p", { className: "wiz-note" }, fill(words.rollover_unticked, { year })),
  ]);
}

// The one roll call, built from the household on screen and nothing else:
// a pure function of the card's household and the fold's choices, which a
// test runs under node (decision 196). Another household's leftover choice
// is ignored; null when the API offers no roll.
function rollHouseholdCall(hh, choice) {
  if (!hh || !hh.roll_year) return null;
  const rollable = hh.returns.filter((r) => r.rollable);
  if (!rollable.length) return null;
  const mine = choice && choice.household === hh.path ? choice : null;
  const unticked = mine ? mine.unticked : new Set();
  const picks = mine ? mine.forms : new Map();
  return [
    ["roll-household", vocab.engagement_flag, rollable[0].path],
    {
      year: hh.roll_year,
      returns: rollable
        .filter((r) => !unticked.has(r.path))
        .map((r) => ({ prior: r.path, form: picks.has(r.path) ? picks.get(r.path) : (r.form || "") })),
    },
  ];
}

// The fold's ticks and picks, held for the household on screen so a redraw
// (looking at a return's people switches the return) brings back what the
// person chose.
// Display state only: nothing about it is recorded (decision 83).
function rollChoiceFor(path) {
  if (!rollChoice || rollChoice.household !== path) {
    rollChoice = { household: path, unticked: new Set(), forms: new Map() };
  }
  return rollChoice;
}

function gatherRollChoice(hh) {
  const choice = rollChoiceFor(hh.path);
  for (const box of $("roll-body").querySelectorAll(".roll-tick")) {
    if (box.checked) choice.unticked.delete(box.dataset.path);
    else choice.unticked.add(box.dataset.path);
  }
  for (const pick of $("roll-body").querySelectorAll(".roll-form-pick")) {
    choice.forms.set(pick.dataset.path, pick.value);
  }
  return choice;
}

async function rollFromCard() {
  const words = vocab.household;
  const hh = lastState && lastState.household;
  if (!hh) return;
  const built = rollHouseholdCall(hh, gatherRollChoice(hh));
  if (!built) return;
  const btn = $("btn-roll");
  btn.disabled = true;
  try {
    const result = await call(...built);
    rollChoice = null;
    closeDialog("roll-modal");
    // The list this write changed arrives with it (decision 194).
    if (result.list) adoptList(result.list);
    renderFor(select(result.state.paths.engagement), result.state);
    // The banner: how many returns rolled into the year and how many were
    // retired, then each return's rows added as not asked (decision 142)
    // and last year's unfiled files - said here, once, because there is no
    // sheet to point at and a row a person wants asked is set in the editor.
    const lines = [
      fill(words.roll_done, { rolled: result.rolled.length, year: result.target_year,
                             retired: result.retired.length }),
      // The people carried unchanged and are worth one look (decision
      // 128), in the API's words.
      fill(vocab.people.rolled_note, { n: result.rolled.length }),
    ];
    for (const one of result.rolled) {
      const setAside = one.carried.filter((c) => c.origin === vocab.origin_not_applicable);
      const added = one.carried.filter((c) => c.origin === vocab.origin_new);
      const parts = [fill(words.roll_carried, { n: one.carried.length - setAside.length - added.length })];
      if (setAside.length) parts.push(fill(vocab.not_applicable_carried, { n: setAside.length }));
      if (added.length) parts.push(fill(vocab.new_not_asked_carried, { n: added.length }));
      if (one.unfiled_last_year.length) {
        parts.push(fill(words.roll_unfiled, { n: one.unfiled_last_year.length }));
      }
      lines.push(`• ${one.label}: ${parts.join("; ")}.`);
      // Decision 137: a link that was not a web address was left behind;
      // the sentence is the API's.
      if (one.link_dropped) lines.push(`  ${one.link_dropped}`);
      // Decision 201: a same-name issuer pair last year's list held, carried
      // as it was; the sentence is the API's.
      for (const warning of one.warnings) lines.push(`  ${warning}`);
    }
    for (const one of result.retired) lines.push(`• ${fill(words.roll_retired_line, { label: one })}`);
    for (const one of result.skipped) lines.push(`• ${one.prior}: ${one.reason}`);
    // Decision 159: every return rolled but a retirement failed - the
    // API's own sentence says what was rolled, retired and left open.
    if (result.warning) lines.push(result.warning);
    const dropped = result.rolled.some((one) => one.link_dropped || one.warnings.length);
    outcome(lines.join("\n"),
      result.skipped.length || result.warning || dropped ? "warn" : "ok");
  } catch (err) {
    // A refused roll lands in the notices area and stays until dismissed
    // (decision 193); the fold keeps the person's ticks and picks.
    failed(err);
  } finally {
    btn.disabled = false;
  }
}

// A person's word that the folder's name is the name (decision 188): the
// API writes one dated line per record that claimed another and moves
// nothing. The seq is the household record's as its page was drawn, so a
// page drawn before somebody else acted is refused, not applied. The action
// is the notice's (pages.js draws "Folder renamed" with Accept).
async function acceptFolderName() {
  const view = viewGeneration;   // drawn only if this return is still the one shown (D6)
  const pause = lastState && lastState.household && lastState.household.pause;
  if (!pause || !pause.engagement) return;
  try {
    const result = await call(["accept-folder-name", vocab.engagement_flag, pause.engagement],
                              { seq: pause.seq, scope: pause.scope });
    if (result.list) adoptList(result.list);   // the list this write changed (decision 194)
    renderFor(view, result.state);
  } catch (err) {
    failed(err, acceptFolderName);
  }
}

// The firm's word, recorded once: one dated event on the household's
// record and nothing else. The API refuses it while the inbox link is
// blank, and its sentence is what the person reads. The household's page
// says "Shared" afterwards, so this says nothing.
async function markShared() {
  const view = viewGeneration;   // drawn only if this return is still the one shown (D6)
  try {
    const result = await call(withEng("mark-shared"));
    renderFor(view, result.state);
  } catch (err) {
    failed(err);
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
  $("hh-edit-members").value = hh.members.join("\n");
  $("hh-edit-contact").value = hh.contact || "";
  $("hh-edit-link").value = hh.link || "";
  $("hh-edit-feeds-label").textContent = words.feeds_label;
  $("hh-edit-feed-add").textContent = words.add_feed;
  $("hh-edit-feed-warning").classList.add("hidden");
  editorFeeds = (hh.feeds || []).map((f) => ({ household: f.household, return_name: f.return_name,
                                               label: f.label }));
  renderEditorFeeds();
  openDialog("household-modal");
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
  const view = viewGeneration;   // drawn only if this return is still the one shown (D6)
  const btn = $("hh-edit-save");
  btn.disabled = true;
  try {
    const result = await call(withEng("edit-household"), {
      members: $("hh-edit-members").value.split("\n").map((one) => one.trim()).filter(Boolean),
      contact: $("hh-edit-contact").value.trim(),
      link: $("hh-edit-link").value.trim(),
      feeds: editorFeeds.map((f) => ({ household: f.household, return_name: f.return_name })),
    });
    closeDialog("household-modal");
    if (result.list) adoptList(result.list);   // the list this write changed (decision 194)
    renderFor(view, result.state);
    const moved = result.saved.household;
    outcome(moved.length ? `${vocab.household.heading}: ${moved.join(", ")}` : vocab.editor.nothing_changed, "ok");
  } catch (err) {
    failed(err);
  } finally {
    btn.disabled = false;
  }
}

// ── the engagement lock, shown instead of left as a mystery file ─────────

function renderLock(state) {
  showLock(state.lock);
}

// Every word is the API's (vocab.lock, decision 193): when the pass started,
// on which machine and - on this machine - the household and file it is on.
// The lock is one notice. A live lock greys this return's writes and is
// watched until it goes; a lock left behind is Tools > Clear stuck lock.
let locked = false;
let lockStale = false;    // the lock shown was left behind (the menu's Clear stuck lock)
let lockWatch = null;
let lockWatched = null;   // the folder the running watch asks about

function lockStarted(lock) {
  return (lock.started || "").replace("T", " ").slice(0, 16);
}

function showLock(lock) {
  lockStale = Boolean(lock && lock.stale);
  if (!lock || lock.stale) stopLockWatch();
  if (!lock) {
    clearNotice("lock");
    setLocked(false);
    return;
  }
  const words = vocab.lock;
  const started = lockStarted(lock);
  if (lock.stale) {
    keyedNotice("lock", { sentence: fill(words.left_behind, { started, host: lock.host, minutes: lock.age_minutes }), kind: "warning" });
    setLocked(false);
    return;
  }
  // The lock it was given, named by the API's label; the sentence for the
  // shown return only when it is the shown return (the review's S1).
  // One short line (SPEC 2.2 E31): the API's running / running_other words and
  // nothing else; its `on` and `greyed` sentences are not shown.
  const said = lock.engagement && lock.engagement !== active
    ? fill(words.running_other, { started, host: lock.host, label: lock.label })
    : fill(words.running, { started, host: lock.host });
  keyedNotice("lock", { sentence: said, kind: "locked" });
  setLocked(true);
  watchLock(lock);
}

// The controls that send a write for the shown return: greyed while a live
// pass holds it, and again after every redraw draws them anew. Only what
// this greyed is given back, so a control the sheet drew disabled stays so.
// (The menu and the sort icon follow `locked` through shellChanged.)
const LOCKED_CARDS = ["sheet-body", "sheet-foot"];

function applyLock() {
  const controls = [
    ...LOCKED_CARDS.flatMap((id) => ($(id) ? [...$(id).querySelectorAll("button, select, input")] : [])),
    ...$("notices").querySelectorAll("button[data-write]"),
  ];
  for (const control of controls) {
    if (locked && !control.disabled) {
      control.disabled = true;
      control.dataset.lockGreyed = "1";
    } else if (!locked && control.dataset.lockGreyed) {
      control.disabled = false;
      delete control.dataset.lockGreyed;
    }
  }
}

function setLocked(on) {
  locked = on;
  applyLock();
  shellChanged();   // shell.js: the sort icon and the menu's enable list
}

function stopLockWatch() {
  clearInterval(lockWatch);
  lockWatch = null;
  lockWatched = null;
}

// The shell moved to another page (shell.js): the lock belongs to the return
// on screen, so a page that is not a return's, or is another return's, shows
// none until that return's state says so.
function appRouteChanged(route) {
  const own = lastState && lastState.paths ? lastState.paths.engagement : "";
  const here = route.level === "return" ? own === route.ret
    : (route.level === "household" || route.level === "year")
      && engagements.some((one) => one.household === route.household && one.path === own);
  if (here) {
    showLock(lastState.lock);
    return;
  }
  stopLockWatch();
  clearNotice("lock");
  lockStale = false;
  setLocked(false);
}

// Asks, every few seconds and only while a live lock shows, whether it has
// gone (ruling 10): no timed wait, and nothing retried for the person. It
// stops on a switch of return, and brings the buttons back the moment the
// lock goes.
// It watches the folder the lock is in - the one the API reported, a
// return or a household - and a watch already running is kept only while it
// is that folder's and this view's (the review's M1 and S1).
function watchLock(lock) {
  const target = lock.engagement || active;
  if (lockWatch && lockWatched === target) return;
  stopLockWatch();
  lockWatched = target;
  const view = viewGeneration;
  let asking = false;
  lockWatch = setInterval(async () => {
    if (view !== viewGeneration) {
      stopLockWatch();
      return;
    }
    if (asking) return;
    asking = true;
    try {
      const result = await call(["watch", vocab.engagement_flag, target]);
      if (view !== viewGeneration) return;
      if (result.lock) {
        showLock(result.lock);
        return;
      }
      stopLockWatch();
      clearNotice("lock");
      setLocked(false);
      notice({ sentence: vocab.lock.buttons_back, kind: "warning" });
      showReturn(active);
    } catch (err) {
      stopLockWatch();
      failed(err);
    } finally {
      asking = false;
    }
  }, vocab.lock.watch_seconds * 1000);
}

async function clearLock() {
  const view = viewGeneration;   // drawn only if this return is still the one shown (D6)
  try {
    const result = await call(withEng("unlock"));
    renderFor(view, result.state);
    outcome(fill(vocab.lock.cleared, { minutes: result.age_minutes }), "ok");
  } catch (err) {
    failed(err);
  }
}

// ── data flows ──────────────────────────────────────────────────────────

// Everything static on the page that names a Python-owned fact is filled
// here, once, from the vocabulary: the product, the rules, the folder the
// originals go to, the year bounds, the example root, the button label.
function applyVocabulary() {
  document.querySelector("title").textContent = vocab.firm ? `${vocab.product} — ${vocab.firm}` : vocab.product;
  applyScheduleVocabulary(vocab.schedule);
  $("household-title").textContent = vocab.household.new;
  // Add a return and New household (decision 196): the household step, the
  // form step and the request list, with no help line of their own (SPEC
  // 2.7). The menu owns the words that open them (File > New household…).
  $("wi-back").textContent = `\u2190 ${vocab.household.change_form}`;
  $("wi-household").textContent = `\u2190 ${vocab.household.change_household}`;
  $("ne-create").textContent = vocab.household.create_return;
  $("hh-name-label").textContent = vocab.household.name_label;
  $("hh-contact-label").textContent = vocab.household.contact_label;
  $("hh-members-label").textContent = vocab.household.members_label;
  $("hh-link-label").textContent = vocab.household.link_label;
  $("ne-name-label").textContent = vocab.household.return_name_label;
  // What adding a return to a household shows, said every time on both
  // pages that add one (decision 129).
  $("hh-return-warning").textContent = vocab.household.return_warning;
  $("ne-return-warning").textContent = vocab.household.return_warning;
  // The reminder's two buttons (decision 118; the draft file is not opened
  // from here, SPEC 7.2). Nothing here sends, and none of these words is the page's.
  $("btn-copy").textContent = vocab.reminder.copy;
  $("btn-approve").textContent = vocab.reminder.approve;
  for (const id of ["ne-year"]) {
    $(id).min = vocab.year_min;
    $(id).max = vocab.year_max;
  }
  $("cu-add").textContent = vocab.editor.add_row;
  // The editor's every word: the two titles, the buttons, the paste hint.
  $("ed-title").textContent = vocab.editor.title;
  $("ed-engagement-title").textContent = vocab.editor.engagement_title;
  $("ed-add").textContent = vocab.editor.add_row;
  $("ed-paste-title").textContent = vocab.editor.paste;
  $("ed-paste-btn").textContent = vocab.editor.paste;
  $("ed-rename-title").textContent = vocab.editor.rename_title;
  $("ed-rename-from").setAttribute("aria-label", vocab.editor.rename_from);
  $("ed-rename-to").setAttribute("aria-label", vocab.editor.rename_to);
  $("ed-rename-to").placeholder = vocab.editor.rename_to;
  $("ed-rename-btn").textContent = vocab.editor.rename;
  $("ed-cancel").textContent = vocab.editor.cancel;
  $("ed-save").textContent = vocab.editor.save;
  shellVocabulary();   // shell.js: the side panel's, path row's and sort icon's words
}

let clientsRoot = "";      // the one folder every engagement sits under

async function loadEngagements(preferPath, asked) {
  const listed = await call(["list"]);
  // Another return was chosen while the list was on its way (D6).
  if (asked !== undefined && asked !== viewGeneration) return null;
  vocab = listed.vocab;
  applyVocabulary();
  adoptList(listed);
  renderMachineNotices(listed);
  renderAfterInstall(listed.after_install);
  if (listed.needs_root) {
    $("root-input").value = clientsRoot;
    $("firm-input").value = vocab.firm || "";
    $("phone-input").value = vocab.settings.phone || "";
    shellNeedsRoot(true, listed);   // shell.js: the setup page, and its "Folder not found" notice
    return false;
  }
  shellNeedsRoot(false, listed);
  if (!engagements.length) return false;
  const chosen =
    (preferPath && engagements.find((e) => e.path === preferPath)?.path) ||
    (active && engagements.find((e) => e.path === active)?.path) ||
    engagements[0].path;
  if (chosen !== active) select(chosen);
  return true;
}

// Sticky notices: nothing dismisses them but a person, and they return only
// when the sentence changes. The reader's (the app sits too deep for its
// reader, decision 169, until it is moved), and the machine's own problems,
// each said until it is fixed (decision 186). The last pass is not a
// notice: the last-sort line says "Sort failed" (SPEC 8.3). Each is shown as
// its short line; the API's sentence (which can name a folder) goes to the
// error log when the notice first shows (SPEC 2.2 E28, E30; 11.1).
function renderMachineNotices(listed) {
  if (listed.reader_warning) {
    if (keyedNotice("reader", { sentence: shortNotice("reader"), kind: "warning" })) window.tracker.logError(listed.reader_warning);
  } else clearNotice("reader");
  const machine = listed.machine_warnings || [];
  syncNotices("machine", machine.length
    ? [{ key: machine.join("\n"), failure: { sentence: shortNotice("machine"), kind: "warning" }, detail: machine.join("\n") }] : []);
}

// The list half of a `list` reply, without the vocabulary (decision 194):
// start-up's, or the one a write that changes the list carries (`create`,
// `rollover`, `roll-household`, `edit-household`, `accept-folder-name`,
// `edit` when it changed `active`), or the `list` asked once when a Sort &
// Scan pass ends (decision 203). Showing
// a return never reads the list again: the path, the search and the pages
// are as the app last walked the root, which is display (UX 1); every write
// is still judged under the lock.
function adoptList(listed) {
  engagements = listed.engagements || [];
  households = listed.households || [];
  misfits = listed.misfits || [];
  clientsRoot = listed.root || "";
  renderMisfits();
  shellAdopt(listed);   // shell.js: paths, the last sort, the firm's counts
}

// Show one return: one `state`, and nothing else (decision 194). The page,
// the hidden cards and the household all arrive in that one reply, and a
// reply that lands after another return was chosen is dropped (D6). True
// only when this read drew the page.
async function showReturn(path) {
  const view = select(path);
  try {
    renderFor(view, await call(["state", vocab.engagement_flag, path]));
    return view === viewGeneration;
  } catch (err) {
    if (view === viewGeneration) failed(err, () => showReturn(path));
    return false;
  }
}

// Start-up: the list and the vocabulary, once. The app opens on the
// Overview and reads no return until a page asks for one (SPEC 4.2); at
// first run the shell draws the setup page. Run again only when the clients
// folder is set (decision 194, R8), since the vocabulary depends on the
// settings that writes.
async function bootstrap(preferPath) {
  try {
    const listed = await loadEngagements(preferPath, viewGeneration);
    if (!listed) return;   // a later choice owns the page now, or no folder or return yet
    // The catalog is for the roll fold's form pick: a failure to load it
    // is said there, and the page is drawn all the same.
    try {
      await loadForms();
    } catch (err) {
      formsUnloaded = failureSentence(err);   // never a page error's own text (principle 7)
    }
  } catch (err) {
    failed(err, () => bootstrap(preferPath));
  }
}

async function saveRoot() {
  try {
    const result = await call(["set-root"], {
      root: $("root-input").value.trim(),
      firm: $("firm-input").value.trim(),
      phone: $("phone-input").value.trim(),
    });
    // What the after-install step did with the schedule (decision 209): a
    // step that could not run is the setup notice, with its lines in the
    // error log; a return short of room is one notice (decision 131).
    renderAfterInstall(noticeOf(result.after_install));
    if (result.after_install.failed.length) window.tracker.logError(`${result.after_install.schedule_sentence}\n${result.after_install.failed.join("\n")}`);
    renderShortOfRoom(result.short_of_room || []);
    await bootstrap();
  } catch (err) {
    failed(err, saveRoot);
  }
}

// Decision 131: the returns short of room under the root just set. One
// notice, in the API's heading; each return's label and sentences go to the
// error log, and every return's rows say it too.
function renderShortOfRoom(shortOf) {
  if (!shortOf.length) {
    clearNotice("room");
    return;
  }
  window.tracker.logError(shortOf.map((one) => `${one.engagement}: ${one.sentences.join(" ")}`).join("\n"));
  keyedNotice("room", { sentence: vocab.room.heading, kind: "warning" });
}

// Decision 209: what the last after-install run left for a person - the
// record check's findings, or a step that could not run - is one notice in
// the API's heading until a later run finds nothing; its lines go to the
// error log. Nothing is ever a person's to press once: the step runs itself.
function renderAfterInstall(left) {
  if (!left) {
    clearNotice("after-install");
    return;
  }
  const lines = [...left.failed, ...left.findings];
  if (keyedNotice("after-install", { sentence: vocab.after_install.heading, kind: "failed" })) {
    window.tracker.logError([left.wait, ...lines].filter(Boolean).join("\n"));
  }
}

// What one run of the step left, as the notice shows it, or nothing.
function noticeOf(done) {
  return done && (done.findings.length || done.failed.length)
    ? { ...done, wait: done.findings.length ? vocab.after_install.wait : "" }
    : null;
}

// The deliberate re-run of the after-install step (decision 209): the
// schedule registers itself, and this is for one deleted or broken. The
// banner says the API's sentence for what happened, as it is. When another
// computer runs the schedule, the page offers to move it here (the
// review's S5) - the packaged app's only way to, in the API's words with
// that computer's name filled in - and moves it only on yes.
// The question before the schedule moves, with its warning under it (SPEC
// 11.2, P77): a risky act keeps its warning, said in the API's words.
function moveScheduleQuestion(host) {
  return `${vocab.schedule.move_confirm}\n\n${vocab.schedule.move_warning}`.split("{host}").join(host);
}

async function repairSchedule() {
  if (!confirm(vocab.schedule.repair_confirm)) return;
  try {
    let result = await call(["install-schedule"], {});
    outcome(result.sentence, result.installed ? "ok" : "warn", { toasted: true });
    renderAfterInstall(noticeOf(result.after_install));
    if (result.host && confirm(moveScheduleQuestion(result.host))) {
      result = await call(["move-schedule-here"], {});
      outcome(result.moved ? `${result.sentence} ${result.schedule_sentence}` : result.sentence,
             result.installed ? "ok" : "warn", { toasted: true });
      if (result.moved) renderAfterInstall(noticeOf(result.after_install));
    }
  } catch (err) {
    failed(err, repairSchedule);
  }
}

// ── the Schedule dialog (pilot P21) ──────────────────────────────────────
// On or off, the first run's time and how often, kept per computer. Read
// from `settings`, saved by `set-schedule`; every word is the API's
// (vocab.schedule), and the API's sentence is what the banner says.

function applyScheduleVocabulary(words) {
  $("sc-title").textContent = words.title;
  $("sc-enabled-label").textContent = words.enabled_label;
  $("sc-on-label").textContent = words.on;
  $("sc-off-label").textContent = words.off;
  $("sc-start-label").textContent = words.start_label;
  $("sc-every-label").textContent = words.every_label;
  $("sc-save").textContent = words.save;
  $("sc-cancel").textContent = words.cancel;
  $("sc-every").replaceChildren(
    ...words.every_choices.map((one) => el("option", { value: String(one.minutes) }, one.label)));
}

// Off greys the two fields: there is nothing to choose while it does not run.
function greyScheduleFields() {
  const off = $("sc-off").checked;
  $("sc-start").disabled = off;
  $("sc-every").disabled = off;
}

function scheduleError(text) {
  $("sc-error").textContent = text;
  $("sc-error").classList.toggle("hidden", !text);
}

// The dialog opens at once on its loading line and fills when `settings`
// answers; a failed read closes it and says why, as any failed read does.
async function openSchedule() {
  scheduleError("");
  // The read is on its way: outline rows, and the one word for a screen reader.
  $("sc-loading").replaceChildren(h("span", { className: "visually-hidden" }, screenWords().loading), ...shellSkeleton(3));
  $("sc-loading").classList.remove("hidden");
  $("sc-form").classList.add("hidden");
  $("sc-save").disabled = true;
  openDialog("schedule-modal");
  try {
    const current = await call(["settings"], {});
    // A saved choice the file cannot be trusted for is said, and the dialog
    // starts from the API's defaults for the person to choose again.
    const chosen = current.schedule
      || { enabled: true, start: vocab.schedule.start, every: vocab.schedule.every };
    $("sc-on").checked = chosen.enabled;
    $("sc-off").checked = !chosen.enabled;
    $("sc-start").value = chosen.start;
    $("sc-every").value = String(chosen.every);
    $("sc-next").textContent = current.next_run;
    scheduleError(current.schedule_problem);
    greyScheduleFields();
    // What "Next run" says is true of the saved choice only (hidden again on any change, below).
    $("sc-next").classList.remove("hidden");
    $("sc-loading").classList.add("hidden");
    $("sc-form").classList.remove("hidden");
    $("sc-save").disabled = false;
    rebaseline("schedule-modal", ["enabled", "start", "every"]);
    $("sc-start").focus();
  } catch (err) {
    closeDialog("schedule-modal");
    failed(err, openSchedule);
  }
}

async function saveSchedule() {
  const btn = $("sc-save");
  btn.disabled = true;
  scheduleError("");
  try {
    const result = await call(["set-schedule"], {
      enabled: $("sc-on").checked,
      start: $("sc-start").value,
      every: Number($("sc-every").value),
    });
    closeDialog("schedule-modal");
    const worked = result.after_install.exit === 0 && (result.installed || !result.enabled);
    outcome(result.next_run ? `${result.sentence} ${result.next_run}` : result.sentence, worked ? "ok" : "warn", { toasted: true });
    renderAfterInstall(noticeOf(result.after_install));
    try {
      await loadEngagements();     // the last-pass line follows the new choice
    } catch (err) {
      failed(err);
    }
  } catch (err) {
    scheduleError(failureSentence(err));   // a refusal stays in the dialog, which stays open
  } finally {
    btn.disabled = false;
  }
}

// The shell's launch step ran in the background and finished (decision
// 209, the review's S7): ask again for what it left, and show only that -
// the rest of the page, and anything a person is editing, is left alone.
if (window.tracker.onAfterInstallDone) {
  window.tracker.onAfterInstallDone(async () => {
    try {
      renderAfterInstall((await call(["list"])).after_install);
    } catch (err) {
      failed(err);        // said by the one rule (decision 193), never its message
    }
  });
}

// A failed sort as the banner says it (rulings 25 and 29): the API's failure word and
// a short reason from the API by the kind of failure the pass reported, five
// words at most; the run's own sentence stays in the error log.
function scanFailed(run) {
  const words = vocab.scan;
  const reason = words.reasons[run.code] || words.reasons.other;
  return reason ? fill(words.problem_reason, { reason }) : words.problem;
}

// What a Sort & Scan pass said, as the banner's lines and its colour: the
// asked return's run from the pass's final line, the household's other
// returns, and the summary line of the state drawn after it.
function scanSummary(run, others, summary) {
  // What the pass said beyond the asked return (decision 189): the
  // household's other returns' problems, shown the way this return's
  // warnings are - the API's words, each under the return's own label.
  // The pass's own warnings are notices (decision 193), which stay.
  const also = [];
  for (const other of others) {
    for (const said of [other.error, other.skipped, ...other.warnings]) {
      if (said) also.push(`• ${other.label}: ${said}`);
    }
  }
  // Every word is the API's (vocab.scan, decision 42; the review's S4).
  const words = vocab.scan;
  if (run.skipped) return { text: [fill(words.nothing_done, { why: run.skipped }), ...also].join("\n"), cls: "warn" };
  if (run.error) return { text: [scanFailed(run), ...also].join("\n"), cls: "err" };
  const did = [fill(words.filed, { n: run.filed })];
  if (run.review) did.push(fill(words.review, { n: run.review }));
  if (run.waiting) did.push(fill(words.syncing, { n: run.waiting }));
  const problems = [];
  if (run.file_errors.length) problems.push(fill(words.not_sorted, { n: run.file_errors.length }));
  const lines = [fill(words.complete, { did: did.join(", "), summary })];
  if (problems.length) lines.push(fill(words.but, { problems: problems.join("; ") }));
  for (const w of run.warnings) lines.push(`• ${w}`);
  lines.push(...also);
  return { text: lines.join("\n"),
           cls: problems.length || run.warnings.length || also.length || run.cancelled ? "warn" : "ok" };
}

// The one Sort & Scan running from this window (decision 203): its command
// line, the pass id its first progress line gave (what Stop names), and
// the return it was asked for. The pass runs on in its own process after
// the click is answered; the shell sends its lines and then its ending on
// the progress channel.
let scanning = null;

// Everything the shell says about the running pass: a progress line, or -
// once, when its process closes - its ending. Only the running pass's.
function onPassMessage(m) {
  if (!scanning || JSON.stringify(m.args) !== JSON.stringify(scanning.args)) return;
  if (m.reply !== undefined) {
    passEnded(m);
    return;
  }
  drawProgress(m);
}

// Where the pass is (decision 193): the household it is on, as `n` of `of`.
// The last-sort line in the side panel says it (shell.js); the pass id is
// what Stop names.
function drawProgress(m) {
  const said = m.progress || {};
  shellProgress(said);
  if (said.pass) scanning.pass = said.pass;
  shellChanged();
}

// Stop: only this app's own pass, at its next file (decision 193). What was
// done is recorded and the rest waits; the pass's ending says so. The sort
// icon is the button (it shows Stop while this runs).
async function stopPass() {
  if (!scanning || !scanning.pass || scanning.stopping) return;
  scanning.stopping = true;
  shellChanged();
  try {
    await call(["cancel-pass"], { pass: scanning.pass });
  } catch (err) {
    failed(err);
  }
}

// The sort icon back as Sort now. It follows `scanning` and `locked`
// (decision 203's review, M2): a lock the shown return met during the pass
// greys it through the lock's own mark, which the lock going gives back.
function scanDone() {
  scanning = null;
  applyLock();
  shellProgress({});
  shellChanged();
}

// Sort now starts the scheduled runner for this return's household and
// is answered as soon as the pass has begun (decision 203). Every other
// return and every read keep working while it runs; the household's own
// returns show the lock the pass holds, as any lock shows (decision 193).
async function runScan() {
  const args = withEng(vocab.pass_command);
  const mine = { args, pass: null, stopping: false, asked: active };
  scanning = mine;
  shellChanged();
  try {
    const started = await call(args);
    if (scanning !== mine) return;   // it has already ended, and said so
    mine.pass = started.pass;
    if (started.started) drawProgress({ progress: started.started });
  } catch (err) {
    // It never started: refused, or a pass already holds the household
    // (the lock notice, and its watch), or the tracker could not start.
    if (scanning === mine) scanDone();
    failed(err, runScan);
  }
}

// The pass has ended (decision 203): its final line, or the shell's own
// failure when it gave none or was killed. The counts come from the final
// line, and then the page is redrawn from the record - the list once, then
// the shown return's state (the lane's ruling on 194's Q5) - behind the
// view generation, so a return chosen since is the one drawn.
async function passEnded({ reply }) {
  const asked = scanning.asked;
  scanDone();
  const ended = reply || {};
  if (ended.error) {
    notice(ended.failure || { sentence: ended.error, kind: "failed" }, { retry: runScan });
  } else {
    warningNotices(ended.pass_warnings || []);
  }
  const runs = Array.isArray(ended.runs) ? ended.runs : [];
  const run = runs.find((one) => one.path === asked);
  const view = viewGeneration;
  let state = null;
  try {
    // The list is the practice's, not the view's: kept whichever return
    // is shown by now (the review's note).
    adoptList(await call(["list"]));
    if (view === viewGeneration) {
      state = await call(withEng("state"));
      if (!renderFor(view, state)) state = null;
    }
  } catch (err) {
    if (view === viewGeneration) failed(err, () => showReturn(active));
  }
  if (!run) {
    // Its counts are never guessed from another return's (the review's S2).
    if (!ended.error) notice({ sentence: vocab.scan.not_in_pass, kind: "warning" });
    return;
  }
  const shown = asked === active && view === viewGeneration;
  const said = scanSummary(run, runs.filter((one) => one !== run),
                           shown && state && state.summary ? state.summary.line : "");
  if (!shown) {
    // The return it scanned is not the one shown (193 §8): its summary is
    // a notice under its own label, so nothing vanishes.
    notice({ sentence: `${run.label}: ${said.text}`, kind: "warning" });
    return;
  }
  outcome(said.text, said.cls);
}

// ── Add a return / New household (decision 196) ─────────────────────────
// One dialog, two ways in. Add a return opens from the household's card on
// the form grid, for that household and no other; New household opens from
// the toolbar on the household step. Then the form, then the request list.
// There is no household picked here: addingTo is set by openAddReturn from
// the card's own household, cleared by openNewHousehold and on close.

// The catalog, loaded once: the form grid and the roll fold's form pick.
async function loadForms() {
  if (forms.length) return;
  const result = await call(["templates"]);
  formsUnloaded = "";
  forms = result.forms;
  templatesByForm = result.templates;
  defaultYear = result.default_year || null;
}

async function openAddReturn(hh) {
  if (!hh) return;
  try {
    await loadForms();
  } catch (err) {
    failed(err, () => openAddReturn(hh));
    return;
  }
  addingTo = hh.path;
  selectedForm = null;
  hideCreateNote();
  $("form-title").textContent = fill(vocab.household.add_return_title, { household: hh.name });
  renderFormGrid();
  showStep("form");
  openDialog("modal");
}

async function openNewHousehold() {
  try {
    await loadForms();
  } catch (err) {
    failed(err, openNewHousehold);
    return;
  }
  addingTo = null;
  selectedForm = null;
  hideCreateNote();
  $("form-title").textContent = vocab.household.form_step_title;
  renderHouseholdStep();
  renderFormGrid();
  showStep("household");
  openDialog("modal");
}

// What Add a return / New household forgets once closeDialog has shut it
// (decision 201): the household a return was being added to, and a refusal.
function closeNewReturn() {
  addingTo = null;
  hideCreateNote();
}

// Add a return / New household's model, for the unsaved guard (decision
// 201): the household's four fields when one is being made, the form
// picked, and the request list as the person left it. A person is their
// kind, name, own spellings and the proposals they unticked, so a
// proposal the API sends after the dialog opened is not somebody's typing.
function wizardModel() {
  const household = addingTo ? null
    : ["hh-name", "hh-contact", "hh-members", "hh-link"].map((id) => $(id).value);
  const items = selectedForm ? {
    fields: ["ne-name", "ne-client", "ne-year", "ne-due"].map((id) => $(id).value),
    ticks: [...$("tmpl-list").querySelectorAll("input[type=checkbox]")].map((box) => box.checked),
    custom: customItems,
    people: wizardPeople.map((one) => ({
      kind: one.kind, name: one.name, own: one.own,
      off: one.proposed.filter((p) => !p.on).map((p) => p.text),
    })),
  } : null;
  return { household, form: selectedForm, items };
}

// A refused create stays in the dialog, in the API's words, until the
// person edits a field or closes it: nothing they typed is lost.
function hideCreateNote() {
  $("ne-note").classList.add("hidden");
  $("ne-note").textContent = "";
}

// The dialog is named by the heading of the step it shows (decision 201,
// 196's review N5): New household opens on its household step, whose
// heading is not the form step's, so a screen reader announces the step
// the person is on.
const STEP_HEADINGS = { household: "household-title", form: "form-title", items: "items-title" };

function showStep(step) {
  $("wiz-household").classList.toggle("hidden", step !== "household");
  $("wiz-form").classList.toggle("hidden", step !== "form");
  $("wiz-items").classList.toggle("hidden", step !== "items");
  $("modal").querySelector('[role="dialog"]').setAttribute("aria-labelledby", STEP_HEADINGS[step]);
}

// ── the household step: a new household ─────────────────────────────────
// A return is made inside a household (decision 125). New household makes
// one from these four fields, with its first return; a name that reads as
// a household already in the list is refused by the API, which points at
// the list (decision 188). The page compares nothing.

function renderHouseholdStep() {
  $("hh-name").value = "";
  $("hh-contact").value = "";
  $("hh-members").value = "";
  $("hh-link").value = "";
}

// What every create sends about the household: the folder of the one on
// screen, or the four fields of the one being made.
function householdSpec() {
  if (addingTo) return { household_path: addingTo };
  return {
    household: $("hh-name").value.trim(),
    contact: $("hh-contact").value.trim(),
    members: $("hh-members").value.split("\n").map((one) => one.trim()).filter(Boolean),
    link: $("hh-link").value.trim(),
  };
}

// The household's own contact is the greeting a new return starts with.
function householdContact() {
  if (!addingTo) return $("hh-contact").value.trim();
  const here = lastState && lastState.household;
  return here && here.path === addingTo ? here.contact : "";
}

function renderFormGrid() {
  show("form-grid", forms.map((f) =>
    el("button", { className: "form-card", dataset: { form: f.id } },
      el("span", { className: "form-num" }, f.label),
      el("span", { className: "form-who" }, f.who),
    )));
}

function chooseForm(formId) {
  const form = forms.find((f) => f.id === formId);
  if (!form) return;
  selectedForm = formId;
  templates = templatesByForm[formId] || [];
  customItems = [];
  $("items-title").textContent = fill(vocab.household.items_title, { form: form.label });
  $("tmpl-head-label").textContent = `${form.label} request list — ${vocab.ask_the_client}`;
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
  labelPeopleBlock("wp-head", "wp-add");
  renderPeople("wp-people", wizardPeople, () => {});
  if (wizardPeople[0].name) refreshProposals(wizardPeople[0], () => renderPeople("wp-people", wizardPeople, () => {}));
  renderTemplateList();
  renderCustomRows();
  // New household's way back to its four fields from the request list,
  // where 188's duplicate-name refusal is read: nothing typed is cleared.
  $("wi-household").classList.toggle("hidden", Boolean(addingTo));
  showStep("items");
  // A form picked fills its defaults in; none of that is the person's
  // typing yet, so the guard starts the list from here (decision 201).
  rebaseline("modal", ["form", "items"]);
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

function renderTemplateList() {
  show("tmpl-list", templates.map((t, i) =>
    el("label", { className: "tmpl-item" },
      el("input", { type: "checkbox", dataset: { index: String(i) }, checked: Boolean(t.core) }),
      el("span", { className: "tmpl-doc" }, t.document),
    )));
}

// ── the People block (decision 128) ──────────────────────────────────────
// Who a return is for, with the spellings its documents use. Every label,
// every kind and both refusals are the API's; the proposals are the API's
// too (`propose-spellings`, a read that records nothing) and a person
// ticks them. Nothing here infers a person from a document, and no
// spelling is ever learned except by somebody typing it.

let wizardPeople = [];     // the new return's people, before the return exists
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
    failed(err);
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
        el("span", { className: "tmpl-rules" }, words.spellings_label),
        ticks,
        own),
      el("div", { className: "editor-actions" }, remove));
  }));
}

// The block's headings and its Add button, wherever it is drawn.
function labelPeopleBlock(headId, addId) {
  $(headId).textContent = vocab.people.label;
  $(addId).textContent = vocab.people.add;
}

// ── the one row component: a new return's custom rows and the editor's ──

// A column of the request list, as the API describes it: its key in the
// record, its heading, and the sentence under the heading. The request list
// of Add a return / New household shows three of them; the editor shows
// them all.
function columnsByKey(keys) {
  return keys.map((key) => vocab.columns.find((c) => c.key === key)).filter(Boolean);
}

// One input for one cell. The two numbers take their floor and their
// ceiling (the record's own bounds, decision 187) from the vocabulary
// (never typed here); the override is a pick of the API's two
// values or nothing; everything else is text. Typing writes straight into
// the row object, so the rows are always what the inputs say.
function cellInput(row, column, onChange) {
  const key = column.key;
  const minimum = vocab.editor.minimums[key];
  const maximum = (vocab.editor.maximums || {})[key];
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
    const select = el("select", { "aria-label": column.label },
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
    const select = el("select", { "aria-label": column.label },
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
    // A blank Short name is derived (decision 144): the box shows the name
    // the API derived for the row it opened on, never one typed here.
    placeholder: key === "short_title" ? editorRowShortName(row) : undefined,
  });
  if (minimum !== undefined) input.min = minimum;
  if (maximum !== undefined) input.max = maximum;
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
      tipped(el("button", {
        className: "btn btn-small ed-unlearn",
        dataset: { identifier, keyword: word },
        "aria-label": `${vocab.editor.unlearn_label} ${word}`,
      }, vocab.editor.unlearn_label), `${vocab.editor.unlearn_label} ${word}`))),
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
// identifier as fixed text (Add a return / New household assigns them); the editor passes
// the identifier as one of its columns instead, typed like the rest.
//
// `fold` is the editor's plain view (decision 201, M13): each row is two
// table rows - the row's name as text and the boxes a preparer touches
// (`fold.plain`, and a custom row's Document), then its routing
// fold holding the rest (`fold.routing`) and the taught keywords, closed
// unless `fold.isOpen(row)` says otherwise. There is no toggle per row: the
// editor's one Advanced switch opens every fold at once (SPEC 2.7, E91). Folding hides cells and never
// drops them: every box writes into the same row object through
// cellInput, so a save carries every column whether a fold was opened or
// not. Which column goes where is the API's answer, never the page's.
function requestRows(container, rows, { columns, onChange, onRemove, onTakeBack, learned = {}, keyed = true, fold = null }) {
  const taught = Object.keys(learned).length > 0;
  const learnedBox = (tag, row) => el(tag, { className: "ed-learned", dataset: { identifier: row.identifier || "" } },
    learnedCell(row.identifier, learned));
  const removeCell = (row, index) => el("td", { className: "ed-remove" },
    el("button", { className: "btn btn-small", dataset: { index: String(index) }, "aria-label": `${vocab.editor.remove_row} ${row.identifier || ""}` },
      vocab.editor.remove_row));
  let head;
  let body;
  if (fold) {
    const byKey = new Map(columns.map((c) => [c.key, c]));
    const plain = fold.plain.map((key) => byKey.get(key)).filter(Boolean);
    const routing = fold.routing.map((key) => byKey.get(key)).filter(Boolean);
    const documentColumn = byKey.get("document");
    const nameOf = (row, custom) => (custom ? row.identifier || ""
      : `${row.identifier || ""}${vocab.triage.identifier_separator}${row.document || ""}`);
    head = el("tr", {},
      el("th", {}, documentColumn.label),
      plain.map((c) => el("th", {}, c.label)),
      el("th", {}, ""));
    body = rows.flatMap((row, index) => {
      const custom = fold.custom(row);
      const name = el("span", { className: "req-id" }, nameOf(row, custom));
      const changed = () => { name.textContent = nameOf(row, custom); onChange(rows); };
      const open = fold.isOpen(row);
      const inFold = routing.filter((c) => !(custom && c.key === "document"));
      const cell = el("td", {}, el("div", { className: "ed-fields" },
        inFold.map((c) => el("label", { className: "field" },
          el("span", {}, c.label), cellInput(row, c, changed))),
        taught ? learnedBox("div", row) : null));
      cell.colSpan = plain.length + 2;
      const routingRow = el("tr", { className: open ? "ed-routing" : "ed-routing hidden",
                                    dataset: { index: String(index) } }, cell);
      const plainRow = el("tr", { dataset: { index: String(index) } },
        el("td", { className: "ed-name" }, name,
          custom ? cellInput(row, documentColumn, changed) : null),
        plain.map((c) => el("td", { className: `ed-${c.key}` }, cellInput(row, c, changed))),
        removeCell(row, index));
      return [plainRow, routingRow];
    });
  } else {
    head = el("tr", {},
      keyed ? el("th", { className: "ed-id" }, columnsByKey(["identifier"])[0].label) : null,
      columns.map((c) => el("th", {}, c.label)),
      taught ? el("th", {}, "") : null,
      el("th", {}, ""));
    body = rows.map((row, index) => el("tr", { dataset: { index: String(index) } },
      keyed ? el("td", { className: "ed-id" }, el("span", { className: "req-id" }, row.identifier)) : null,
      columns.map((c) => el("td", { className: `ed-${c.key}` }, cellInput(row, c, () => onChange(rows)))),
      taught ? learnedBox("td", row) : null,
      removeCell(row, index),
    ));
  }
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
    // Enter on the last row adds another, as Add a return / New household always has.
    const tr = e.target.closest("tr");
    if (e.key === "Enter" && tr && tr.dataset.index === String(rows.length - 1) && e.target.matches("input")) {
      e.preventDefault();
      container.dispatchEvent(new CustomEvent("addrow", { bubbles: true }));
    }
  });
  container.replaceChildren(table);
}

// ── Add a return / New household: custom requests ───────────────────────

// Blank fields are sent blank: the catalog's item_from_spec() fills the
// file types and the keyword (the document name) by the one rule, and the
// editor shows the result afterwards.
const CUSTOM_COLUMNS = ["document"];   // the rule columns are the editor's (SPEC 2.7, E90)

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
    toastWord("name_requests");
    return;
  }
  const items = [...catalog, ...customItems.map((c) => ({ ...c, asked: true }))];
  const asked = items.filter((i) => i.asked).length;
  if (!asked) {
    toast(vocab.nothing_asked);
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
    closeDialog("modal");
    // The list this write changed arrives with it (decision 194).
    if (result.list) adoptList(result.list);
    renderFor(select(result.state.paths.engagement), result.state);
    const lines = [
      fill(vocab.household.return_created, { label: result.created, n: asked }),
    ];
    // A household's first return comes back with the sharing checklist
    // (decision 126), whose lines name folders by their paths: it is not
    // drawn (SPEC 2.4 E45; the Tester Guide carries it) - no path is ever on
    // the screen.
    // Decision 137: a household link that was not a web address was left
    // out of the new return; the sentence is the API's.
    if (result.link_dropped) lines.push(result.link_dropped);
    outcome(lines.join("\n"), result.link_dropped ? "warn" : "ok");
  } catch (err) {
    // A refusal - 188's duplicate name among them - stays in the dialog, in
    // the API's words, until a field is edited or the dialog is closed:
    // nothing the person typed is lost, and a toast would vanish (decision 196).
    // Anything else - stale, locked, failed - is a notice (decision 193).
    if (err.failure && err.failure.kind === "refused") {
      $("ne-note").textContent = failureSentence(err);
      $("ne-note").classList.remove("hidden");
    } else {
      failed(err);
    }
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
    // The short name the working folder and copies go by (decision 144);
    // blank is derived, and the box shows the derived one as its placeholder.
    short_title: rule.short_title || "",
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

// The short name the API gave the row the editor opened on
// (state.items[].short_name, decision 144): the placeholder of a blank
// Short name box. A row typed since has none until it is saved.
function editorRowShortName(row) {
  const known = ((editorState && editorState.items) || []).find((i) => i.identifier === row.identifier);
  return known ? known.short_name : undefined;
}

// The key the rows nobody asked for fold under (decision 142): not a
// label, so it can never collide with a set-aside group's.
const NOT_ASKED_GROUP = "\u0001";

// A row set to not asked folds only while no document is in it (the
// designer's ruling on the 142 build): one with any document stays with
// the active rows, as it does in the table and the Status Report.
function editorRowHasDocument(row) {
  const known = ((editorState && editorState.items) || []).find((i) => i.identifier === row.identifier);
  return Boolean(known && known.has_document);
}

function editorGroupKey(row) {
  if (isSetAside(row.manual_override)) return overrideLabel(row.manual_override, editorRowYear(row));
  return row.asked === vocab.editor.no && !editorRowHasDocument(row) ? NOT_ASKED_GROUP : "";
}

// The active rows in one table; below it one folded set-aside group
// (decision 200) holding a group per label - not asked first, then each
// not-applicable year - headed as the Status Report heads its own.
// Removal is by the row's place in editorRows whichever group it is drawn
// in, and a row whose override or Asked changes moves between the groups
// before anything is saved.
function renderEditorRows() {
  const grouping = () => editorRows.map(editorGroupKey).join("\u0000");
  const drawn = grouping();
  const options = (rows) => ({
    columns: vocab.columns,
    keyed: false,
    fold: {
      plain: vocab.editor.plain_columns,
      routing: vocab.editor.routing_columns,
      custom: editorRowIsCustom,
      isOpen: editorRowFoldOpen,
    },
    learned: (editorState && editorState.learned) || {},
    onChange: () => { if (grouping() !== drawn) renderEditorRows(); },
    onRemove: (index) => {
      editorRows.splice(editorRows.indexOf(rows[index]), 1);
      renderEditorRows();
    },
    onTakeBack: unlearnKeyword,
  });
  const active = editorRows.filter((row) => !editorGroupKey(row));
  const aside = editorRows.filter((row) => editorGroupKey(row));
  const activeBox = el("div", { className: "editor-rows" });
  requestRows(activeBox, active, options(active));
  // The rows nobody asked for first, in one group; then the set-aside
  // rows, one group per label. Setting Asked or the override moves a row
  // between the groups before the save.
  const groups = setAsideGroups(aside, (row) => editorGroupKey(row) === NOT_ASKED_GROUP, editorRowYear)
    .map((group) => {
      const box = el("div", { className: "editor-rows" });
      requestRows(box, group.rows, options(group.rows));
      return [setAsideHeading(group), box];
    });
  const folded = aside.length
    ? el("details", { className: "ed-set-aside" },
      el("summary", {}, fill(vocab.set_aside.heading, { n: aside.length })), ...groups.flat())
    : null;
  // The one Advanced switch above the rows (SPEC 2.7, E91): on, every row's
  // routing rules and taught keywords, and the paste and rename blocks, are
  // shown; off, the plain table alone. A word the vocabulary lacks is said.
  const advanced = el("button", { type: "button", className: "btn btn-small ed-advanced",
                                  "aria-pressed": String(editorAdvanced) }, shellWords("editor.advanced"));
  advanced.addEventListener("click", () => setAdvanced(!editorAdvanced));
  const above = el("div", { className: "editor-actions" }, advanced);
  $("ed-advanced-body").classList.toggle("hidden", !editorAdvanced);
  $("ed-rows").replaceChildren(...[above, activeBox, folded].filter(Boolean));
}

// The plain view's folds (decision 201) are open or shut together, by the one
// Advanced switch, and stay so when the rows are drawn again. A row the
// editor did not open on - typed or pasted since - has no items entry and
// opens unfolded, because the person is writing it now.
let editorAdvanced = false;

function editorRowItem(row) {
  return ((editorState && editorState.items) || []).find((i) => i.identifier === row.identifier);
}

function editorRowFoldOpen(row) {
  return editorAdvanced || !editorRowItem(row);
}

// A custom row is one no catalog row of the return's form has; the API
// says which (state.items[].catalog_row). Its Document is in the plain
// part, because nothing else names it.
function editorRowIsCustom(row) {
  const known = editorRowItem(row);
  return !known || !known.catalog_row;
}

function setAdvanced(on) {
  editorAdvanced = on;
  renderEditorRows();
}

// A refused save names a column that must be on screen: Advanced goes on.
function showEveryFold() {
  setAdvanced(true);
}

// Only the learned column, drawn again from the state the API just sent.
// Nothing else is touched: an unlearn lands on its own, and whatever the
// person has typed into the rows and not saved is theirs to keep.
function renderLearnedCells(learned) {
  for (const cell of $("ed-rows").querySelectorAll(".ed-learned")) {
    cell.replaceChildren(...learnedCell(cell.dataset.identifier, learned));
  }
}

// One keyword taken back: one event, recorded at once, and the request
// re-scanned by the API in the same breath because its rules just moved.
async function unlearnKeyword(identifier, keyword) {
  const view = viewGeneration;   // drawn only if this return is still the one shown (D6)
  let result;
  try {
    result = await call(withEng("unlearn"), { identifier, keyword });
  } catch (err) {
    // One sentence, said in the editor and as a notice, with Look again when
    // the list moved (the review's S3): never an error's own text (principle 7).
    editorNote(failed(err), "err");
    return;
  }
  editorState.learned = result.state.learned || {};
  renderLearnedCells(editorState.learned);
  // The page too, so the editor reopened on the state on screen (D13)
  // never shows a keyword the record no longer holds (the review's S2).
  renderFor(view, result.state);
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
    .filter((f) => f.key !== "name" && f.key !== "people" && f.editable)   // the read-only fields are cut (SPEC 2.7, E91)
    .map((f) => {
      const value = info[f.key];
      if (typeof value === "boolean") {
        // The one help kept: the warning before a risky act (P77), on Active.
        return el("label", { className: "wiz-check" },
          el("input", { type: "checkbox", checked: value, dataset: { field: f.key } }),
          el("span", {}, `${f.label} — ${f.help}`));
      }
      return el("label", { className: "field" }, el("span", {}, f.label),
        el("input", { type: vocab.editor.date_fields.includes(f.key) ? "date" : "text", value: value || "", dataset: { field: f.key } }));
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

// The editor opens on the state already on screen (decision 201, D13):
// lastState carries the rules, the items, the taught keywords, the details
// and the list's version, which is everything the editor reads. A display
// may be cached and a write never is - the save still hands back
// list_head and is judged under the lock (decision 160) - so a stale
// screen costs a refusal, never a write. Only when the state on screen is
// another return's (a switch that has not landed) is it read first; if it
// is still another's after that, the banner says so - never a button that
// does nothing (the review's S4). `focus` is the identifier of the request
// a row's Edit step came from: the editor opens with that row's first cell
// focused.
async function openEditor(focus) {
  if (!active) return;
  try {
    // Opened on the state already drawn for this return (decision 194,
    // D13): display may be cached, a write never is - the save is judged
    // under the lock by the list's head (decision 160), and a list that
    // moved since is refused as stale, with Look again (193).
    editorState = (lastState && lastState.paths && lastState.paths.engagement === active)
      ? { ...lastState }
      : await call(withEng("state"));
  } catch (err) {
    failed(err, openEditor);
    return;
  }
  // A switch landed while the state was read: the editor opens on no
  // other return than the one on screen (the review's S4, decision 201).
  if (!editorState.paths || editorState.paths.engagement !== active) {
    outcome(vocab.editor.not_this_return, "err");
    return;
  }
  editorAdvanced = false;
  editorRows = (editorState.rules || []).map(editorRow);
  renderEngagementFields(editorState.engagement || {});
  // The return's people, as the record holds them (decision 128): edited
  // here and nowhere else, and saved with the rest of the details.
  editorPeople = ((editorState.engagement || {}).people || []).map(personFromRecord);
  labelPeopleBlock("ep-head", "ep-add");
  renderPeople("ep-people", editorPeople, () => {});
  renderEditorRows();
  renameChoices();
  $("ed-paste").value = "";
  editorNote("", "ok");
  openDialog("editor");
  if (typeof focus === "string") focusEditorRow(focus);
}

// The row of the request list a page row named: its first cell takes focus
// and the row is scrolled into view. A row the editor does not list (or one
// inside a closed fold) leaves focus where the dialog put it.
function focusEditorRow(identifier) {
  for (const row of $("ed-rows").querySelectorAll("tr[data-index]")) {
    const named = row.querySelector(".req-id");
    if (!named || named.textContent.split(vocab.triage.identifier_separator)[0] !== identifier) continue;
    const cell = row.querySelector("input, select");
    if (cell && cell.offsetParent !== null) {
      row.scrollIntoView({ block: "center" });
      cell.focus();
    }
    return;
  }
}

// The requests the rename can act on: the list as the record holds it,
// which is what the rename is checked against (decision 160).
function renameChoices() {
  $("ed-rename-from").replaceChildren(...((editorState && editorState.rules) || [])
    .map((rule) => el("option", { value: rule.identifier }, rule.identifier)));
  $("ed-rename-to").value = "";
}

// A request given another identifier, its documents moved with it: one
// act, recorded at once and not part of Save (decision 160). The editor
// keeps what the person typed and not saved - the renamed row takes its
// new identifier in place - and adopts the list's version the rename left,
// which the API checked against the one this editor opened on first.
async function renameRequest() {
  const view = viewGeneration;   // drawn only if this return is still the one shown (D6)
  const from = $("ed-rename-from").value;
  const to = $("ed-rename-to").value.trim();
  if (!from || !to) return;
  const btn = $("ed-rename-btn");
  btn.disabled = true;
  try {
    const result = await call(withEng("rename"), { from, to, head: editorState.list_head });
    const renamed = result.renamed;
    editorState = { ...result.state, list_head: renamed.head };
    for (const row of editorRows) if (row.identifier === renamed.old) row.identifier = renamed.new;
    // Recorded the moment it was made, so nothing about it is unsaved: the
    // row is renamed in the guard's snapshot as it is on screen (decision 201).
    for (const row of dialogSnapshot.editor.rows) if (row.identifier === renamed.old) row.identifier = renamed.new;
    renderEditorRows();
    renameChoices();
    renderFor(view, result.state);
    const lines = [fill(vocab.editor.renamed_note, renamed)];
    if (renamed.left.length) lines.push(fill(vocab.editor.rename_left_note, { left: renamed.left.join(", ") }));
    if (renamed.scan_note) lines.push(renamed.scan_note);
    editorNote(lines.join("\n"), renamed.left.length || renamed.scan_note ? "warn" : "ok");
  } catch (err) {
    // One sentence, said in the editor and as a notice, with Look again when
    // the list moved (the review's S3): never an error's own text (principle 7).
    editorNote(failed(err), "err");
  } finally {
    btn.disabled = false;
  }
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
  const view = viewGeneration;   // drawn only if this return is still the one shown (D6)
  const btn = $("ed-save");
  btn.disabled = true;
  try {
    // The version of the list this editor opened on (decision 160): a save
    // made after another window's is refused rather than taking it back.
    const result = await call(withEng("edit"), {
      items: editorRows,
      engagement: engagementFromFields(),
      head: editorState.list_head,
    });
    // Carried only when the save changed whether the return is active,
    // the one thing the editor saves that the list shows (decision 194).
    if (result.list) adoptList(result.list);
    renderFor(view, result.state);
    closeDialog("editor");
    const saved = result.saved;
    const lines = [saved.recorded
      ? fill(vocab.editor.saved, { changed: saved.changed.length, removed: saved.removed.length })
      : vocab.editor.nothing_changed];
    // The editor's rule warnings are the state's (decision 193, ruling 2).
    const ruleWarnings = (result.state && result.state.warnings) || [];
    if (ruleWarnings.length) {
      lines.push(`${vocab.editor.warnings_heading}:`);
      for (const w of ruleWarnings) lines.push(`• ${w}`);
    }
    outcome(lines.join("\n"), ruleWarnings.length ? "warn" : "ok");
  } catch (err) {
    // A refusal names a row and a column, and the column it names must be
    // on screen: every fold opens (decision 201). The sentence is never
    // parsed; the rows stay as typed, and the dialog stays dirty.
    // It is said in the editor, where the person is reading, and as a
    // notice, with Look again when the list moved (the review's S3) - in
    // one sentence, the tracker's own or failed's (decision 193).
    showEveryFold();
    editorNote(failed(err), "err");
  } finally {
    btn.disabled = false;
  }
}

// ── the four dialogs: one way in, one way out (decision 201) ─────────────
// Every dialog is in this registry, and every one opens through
// openDialog and closes through requestClose - Cancel, Escape and a click
// on the dim behind it alike (D10). A dialog with a model keeps a snapshot
// taken when it opened; closing one whose model moved raises its bar, with
// its keep button focused and its discard button the only way out, and
// Escape while the bar shows means keep editing, so a key pressed out of
// habit never throws work away (F-T-7). The hand-over is two picks and no
// typing, so it has no model and is never dirty - but it goes the same way.
// `first` is the control focus goes to when the opener names none; `closed`
// is what a dialog forgets once it is shut.
const DIALOGS = {
  editor: {
    model: () => ({ rows: editorRows, details: engagementFromFields() }),
    first: () => $("ed-rows").querySelector("tbody input, tbody select"),
  },
  "household-modal": {
    model: () => ({
      members: $("hh-edit-members").value, contact: $("hh-edit-contact").value,
      link: $("hh-edit-link").value,
      feeds: editorFeeds.map((f) => [f.household, f.return_name]),
    }),
    first: () => $("hh-edit-members"),
  },
  "handover-modal": {
    model: null,
    first: () => $("ho-return"),
    closed: () => { handingOver = null; },
  },
  // A small confirm: the reason is optional, so there is no work to lose.
  "unfile-modal": { model: null, first: () => $("uf-note"), closed: () => { unfiling = null; } },
  modal: {
    model: () => wizardModel(),
    first: () => null,
    closed: () => closeNewReturn(),
  },
  "schedule-modal": {
    model: () => ({ enabled: $("sc-on").checked, start: $("sc-start").value, every: $("sc-every").value }),
    first: () => $("sc-cancel"),
  },
  // The roll's ticks and picks are display state, not work to lose (decision 83).
  "roll-modal": { model: null, first: () => $("roll-body").querySelector(".roll-tick") || $("roll-cancel") },
  "safeguards-modal": { model: null, first: () => $("safeguards-close") },
  "about-modal": { model: null, first: () => $("about-close") },
  "misfits-modal": { model: null, first: () => $("misfits-close") },
  // The side sheet (SPEC 7) is modal like the rest: it takes focus, Tab stays
  // inside it and Escape closes it. It hides by its attribute, not a class,
  // and sheet.js puts the scrim and the row focus back when it is shut.
  sheet: { model: null, attr: true, first: () => $("sheet-title"), closed: () => sheetClosed() },
};

const dialogStack = [];      // the open dialogs, the topmost last
const dialogOpener = {};     // id -> the element that had focus when it opened
const dialogSnapshot = {};   // id -> its model as it opened, or as a recorded act left it
const dialogKept = {};       // id -> the element that had focus when its bar went up

function snapshotOf(id) {
  const model = DIALOGS[id].model;
  return model ? JSON.parse(JSON.stringify(model())) : null;
}

// A dialog's model moved since it opened: something typed or picked and
// not saved.
function isDirty(id) {
  const model = DIALOGS[id].model;
  return Boolean(model) && JSON.stringify(model()) !== JSON.stringify(dialogSnapshot[id]);
}

// Part of a dialog's model taken again as it now stands, because what
// moved it is not unsaved work: a form picked (its defaults filled in), a
// row renamed (recorded the moment it was made).
function rebaseline(id, keys) {
  const now = snapshotOf(id);
  for (const key of keys) dialogSnapshot[id][key] = now[key];
}

// The controls Tab may reach inside a dialog: shown, and not disabled.
function focusables(root) {
  return [...root.querySelectorAll("button, input, select, textarea, summary, [tabindex]")]
    .filter((node) => !node.disabled && node.tabIndex >= 0 && node.getClientRects().length);
}

function unsavedBar(id) {
  return $(id).querySelector(".dlg-unsaved");
}

function openDialog(id, first) {
  const overlay = $(id);
  if (overlay.classList.contains("hidden") || overlay.hidden) {
    dialogOpener[id] = document.activeElement;
    dialogStack.push(id);
  }
  const bar = unsavedBar(id);
  if (bar) bar.classList.add("hidden");
  overlay.classList.remove("hidden");
  overlay.hidden = false;
  dialogSnapshot[id] = snapshotOf(id);
  const target = first || DIALOGS[id].first() || focusables(overlay)[0];
  if (target) target.focus();
}

function closeDialog(id) {
  const bar = unsavedBar(id);
  if (bar) bar.classList.add("hidden");
  if (DIALOGS[id].attr) $(id).hidden = true;
  else $(id).classList.add("hidden");
  const at = dialogStack.indexOf(id);
  if (at >= 0) dialogStack.splice(at, 1);
  if (DIALOGS[id].closed) DIALOGS[id].closed();
  const back = dialogOpener[id];
  delete dialogOpener[id];
  if (back && document.contains(back) && typeof back.focus === "function") back.focus();
}

// Cancel, Escape and a click behind the dialog all come here. While the
// bar is showing, every one of them means keep editing: only the bar's
// own discard button closes a dialog with work in it.
function requestClose(id) {
  const bar = unsavedBar(id);
  if (bar && !bar.classList.contains("hidden")) {
    keepEditing(id);
    return;
  }
  if (!isDirty(id)) {
    closeDialog(id);
    return;
  }
  dialogKept[id] = document.activeElement;
  bar.querySelector(".dlg-unsaved-text").textContent = vocab.dialogs.unsaved;
  bar.querySelector(".dlg-keep").textContent = vocab.dialogs.keep_editing;
  bar.querySelector(".dlg-discard").textContent = vocab.dialogs.discard;
  bar.classList.remove("hidden");
  bar.querySelector(".dlg-keep").focus();
}

function keepEditing(id) {
  unsavedBar(id).classList.add("hidden");
  const back = dialogKept[id];
  delete dialogKept[id];
  const target = back && $(id).contains(back) && !unsavedBar(id).contains(back)
    ? back : DIALOGS[id].first() || focusables($(id))[0];
  if (target) target.focus();
}

// Tab and Shift+Tab go round the dialog's own controls and never behind it:
// every dialog says aria-modal="true", and this is what makes it so.
function trapTab(e, id) {
  const inside = focusables($(id));
  if (!inside.length) return;
  const first = inside[0];
  const last = inside[inside.length - 1];
  const at = inside.indexOf(document.activeElement);
  if (e.shiftKey && (at <= 0)) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && (at === -1 || at === inside.length - 1)) {
    e.preventDefault();
    first.focus();
  }
}

// ── the four dialogs the menu and the notices open (SPEC 2.7, E92-E95) ────
// Safeguards and About are Help's; the folders the walk left alone is a
// notice's Show. Every word is the API's, and no path is drawn: a folder is
// its own name (the last part of where it is), never where it is.

// The four standing rules, one short line each (P64): `vocab.rules[i].short`.
// A rule without its short line is a word the vocabulary lacks: loud, never
// the long sentence in its place.
function openSafeguards() {
  const words = screenWords();
  $("safeguards-title").textContent = words.safeguards.title;
  $("safeguards-close").textContent = words.close;
  const lines = vocab.rules.map((rule) => {
    if (!rule.short) throw new Error("rules.short");
    return el("li", {}, rule.short);
  });
  show("safeguards-list", lines);
  openDialog("safeguards-modal");
}

// The product's name and its edition (the pilot's, pilot-content.js).
function openAbout() {
  const words = screenWords();
  $("about-title").textContent = vocab.product;
  $("about-edition").textContent = fill(words.about.edition, { version: PILOT.edition.version });
  $("about-close").textContent = words.close;
  openDialog("about-modal");
}

// One row per folder left alone: its own name and, beside it, the API's
// two-word reason for that kind of folder (`screen.misfits.reasons[code]`).
// The one long sentence per folder goes to the error log, and no path is
// drawn. A code the vocabulary has no word for (the year that is not a year,
// until Jason gives it one) draws the name alone: not an error.
function openMisfits() {
  const words = screenWords();
  $("misfits-title").textContent = words.misfits.title;
  $("misfits-close").textContent = words.close;
  const reasons = words.misfits.reasons || {};
  window.tracker.logError(misfits.map((one) => `${one.where || one.path}: ${one.sentence}`).join("\n"));
  show("misfits-list", misfits.map((one) => el("li", {},
    el("span", { className: "misfit-name" }, folderName(one.where || one.path)),
    reasons[one.code] && el("span", { className: "misfit-why" }, reasons[one.code]))));
  openDialog("misfits-modal");
}

// ── wiring ──────────────────────────────────────────────────────────────

$("hh-edit-cancel").addEventListener("click", () => requestClose("household-modal"));
$("hh-edit-save").addEventListener("click", saveHousehold);
$("hh-edit-feed-add").addEventListener("click", addEditorFeed);
$("hh-edit-feeds").addEventListener("click", (e) => {
  const remove = e.target.closest("button.hh-feed-remove");
  if (!remove) return;
  editorFeeds.splice(Number(remove.dataset.at), 1);
  renderEditorFeeds();
});
$("ho-cancel").addEventListener("click", () => requestClose("handover-modal"));
$("ho-return").addEventListener("change", loadHandOverRequests);
$("ho-file").addEventListener("click", fileHandOver);
$("uf-cancel").addEventListener("click", () => requestClose("unfile-modal"));
$("uf-confirm").addEventListener("click", confirmUnfile);
$("btn-copy").addEventListener("click", copyReminder);
$("btn-approve").addEventListener("click", approveReminder);
$("reminder-stages").addEventListener("click", (e) => {
  const button = e.target.closest(".rem-stage");
  if (!button || button.disabled) return;
  reminderStage = Number(button.dataset.stage);
  loadReminder();
});
$("form-grid").addEventListener("click", (e) => {
  const card = e.target.closest(".form-card");
  if (card) chooseForm(card.dataset.form);
});
$("wi-back").addEventListener("click", () => showStep("form"));
$("wh-cancel").addEventListener("click", () => requestClose("modal"));
// Back from the request list, Continue returns to it as it was left; the
// form grid is only for a household that has no form picked yet.
$("wh-next").addEventListener("click", () => showStep(selectedForm ? "items" : "form"));
$("wi-household").addEventListener("click", () => {
  showStep("household");
  $("hh-name").focus();
});
// A refusal in the dialog's note stands until the person edits a field.
$("modal").addEventListener("input", hideCreateNote);
// The roll dialog (decision 196): its ticks and form picks are held for the
// household on screen, its one button rolls it, and the people button opens
// the editor on that return - which stacks over the dialog, so the choices
// are there as they were left.
// The roll dialog's people button: one state call for the return (decision
// 194), then the editor on it - only when that read drew this return. A
// failed read has said so once (failed()) and a switch during the read owns
// the page (193's late-reply rule), so neither opens an editor or reads
// state again (the rebase review's S4).
async function reviewPeople(path) {
  if (await showReturn(path) && active === path) openEditor();
}
$("roll-body").addEventListener("change", (e) => {
  if (!e.target.closest(".roll-tick, .roll-form-pick")) return;
  if (lastState && lastState.household) gatherRollChoice(lastState.household);
});
$("roll-body").addEventListener("click", (e) => {
  const button = e.target.closest("button.roll-review-people");
  if (!button) return;
  if (lastState && lastState.household) gatherRollChoice(lastState.household);
  reviewPeople(button.dataset.path);
});
$("btn-roll").addEventListener("click", rollFromCard);
$("roll-cancel").addEventListener("click", () => requestClose("roll-modal"));
for (const id of ["safeguards", "about", "misfits"]) {
  $(`${id}-close`).addEventListener("click", () => closeDialog(`${id}-modal`));
}
$("sc-on").addEventListener("change", greyScheduleFields);
$("sc-off").addEventListener("change", greyScheduleFields);
for (const kind of ["input", "change"]) {
  $("sc-form").addEventListener(kind, () => $("sc-next").classList.add("hidden"));
}
$("sc-save").addEventListener("click", saveSchedule);
$("sc-cancel").addEventListener("click", () => requestClose("schedule-modal"));
window.tracker.onProgress(onPassMessage);
$("notices").addEventListener("click", (e) => {
  const button = e.target.closest("button[data-act]");
  if (!button) return;
  const entry = notices.find((one) => one.node.contains(button));
  if (!entry) return;
  // An action (Show, Accept) leaves the notice where it is: what it acts on
  // takes it away when it is done. Retry and the close icon end it.
  if (button.dataset.act === "action") {
    entry.action.run();
    return;
  }
  dismissNotice(entry);
  if (button.dataset.act === "retry") {
    const again = retryOf(entry);
    if (again) again();
  }
});
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
// The People block's one button, in Add a return / New household and in the editor
// (decision 128); the rows wire their own controls as they are drawn.
$("wp-add").addEventListener("click", () => {
  wizardPeople.push(blankPerson());
  renderPeople("wp-people", wizardPeople, () => {});
});
$("ep-add").addEventListener("click", () => {
  editorPeople.push(blankPerson());
  renderPeople("ep-people", editorPeople, () => {});
});
$("ed-paste-btn").addEventListener("click", () => {
  const added = pasteRows($("ed-paste").value);
  if (added) $("ed-paste").value = "";
});
$("ed-rename-btn").addEventListener("click", renameRequest);
$("ed-save").addEventListener("click", saveEditor);
$("ed-cancel").addEventListener("click", () => requestClose("editor"));
$("ne-create").addEventListener("click", createEngagement);
// Every dialog the same way (decision 201): a click on the dim behind it
// is Escape, and the bar's two answers are the only way past it.
for (const id of Object.keys(DIALOGS)) {
  if (id === "sheet") continue;   // its scrim is the click behind it (sheet.js)
  $(id).addEventListener("click", (e) => {
    if (e.target === $(id)) requestClose(id);
  });
  const bar = unsavedBar(id);
  if (!bar) continue;
  bar.querySelector(".dlg-keep").addEventListener("click", () => keepEditing(id));
  bar.querySelector(".dlg-discard").addEventListener("click", () => closeDialog(id));
}
// The side sheet's one delegate (SPEC 7): the buttons of the file on it, in
// its body and its footer, act on the row sheet.js is showing.
$("sheet").addEventListener("click", (e) => {
  const li = sheetRow();
  if (!li) return;
  const on = (className) => e.target.closest(className);
  const restore = on(".r-restore");
  if (restore) restoreMoved(li, restore);
  const keep = on(".r-keep");
  if (keep) keepMoved(li, keep);
  const withdraw = on(".r-withdraw");
  if (withdraw) withdrawAnswer({ original: li.dataset.original, identifier: withdraw.dataset.identifier, seq: li.dataset.seq }, withdraw);
  const issuer = on(".r-add-issuer");
  if (issuer) addIssuerAndFile(li, issuer);
  const file = on(".r-file");
  if (file) assignParked(li, file);
  const dismiss = on(".r-dismiss");
  if (dismiss) dismissParked(li, dismiss);
  const over = on(".r-hand-over");
  if (over) openHandOver(li.dataset.original, Number(li.dataset.seq));
  const waits = on(".r-where-it-waits");
  if (waits) fileWhereItWaits(li.dataset.original, Number(li.dataset.seq), waits);
  const copy = on("#sheet-open");
  if (copy) openReviewCopy(copy);
});
// The one keyboard rule for every dialog (decision 201): Escape asks the
// topmost to close, and Tab stays inside it.
document.addEventListener("keydown", (e) => {
  if (shellKey(e)) return;   // shell.js: F6, the search box, the sheet, the row lists
  const id = dialogStack[dialogStack.length - 1];
  if (!id) return;
  if (e.key === "Escape") {
    e.preventDefault();
    requestClose(id);
  } else if (e.key === "Tab") {
    trapTab(e, id);
  }
});

// The first `list` may answer before pages.js, sheet.js and shell.js have
// run (they load after this file), and bootstrap draws through them: it
// starts once the document and every script are in place (final review B,
// finding 1). DOMContentLoaded fires after the last synchronous script.
function startWhenLoaded(start) {
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => start(), { once: true });
  else start();
}

startWhenLoaded(bootstrap);
