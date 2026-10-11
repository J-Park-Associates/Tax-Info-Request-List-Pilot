// The harness's double of app.js (SPEC-shell 14.4): exactly the globals and
// functions shell.js and tooltip.js use, and nothing else. Loaded in place
// of app.js by the harness server. It is the contract, written as code: what
// the shell needs of app.js is what is defined here, and app.js keeps
// defining it. Never loaded by the app.
"use strict";

const $ = (id) => document.getElementById(id);
let vocab = null;
let households = [];
let engagements = [];
let active = null;
let locked = false;
let scanning = null;
let paths = null;
let lastState = null;
const dialogStack = [];

function fill(pattern, values) {
  return pattern.replace(/\{(\w+)\}/g, (_, key) => values[key] ?? "");
}

function toast(msg) {
  const box = $("toast");
  box.textContent = msg;
  box.classList.remove("hidden");
  clearTimeout(box._t);
  box._t = setTimeout(() => box.classList.add("hidden"), 6000);
}

// The builder and the per-PC store, as app.js defines them (shell.js and
// pages.js build with `el` under the name `h`).
const EL_ATTRIBUTES = new Set([
  "className", "dataset", "id", "type", "value", "placeholder",
  "label", "rows", "checked", "selected", "disabled", "hidden", "tabindex", "role",
  "aria-label", "aria-current", "aria-selected", "aria-expanded", "aria-busy", "aria-hidden",
  "aria-labelledby", "aria-valuemin", "aria-valuemax", "aria-valuenow", "aria-live",
  "aria-controls", "aria-description", "aria-keyshortcuts", "aria-disabled", "aria-pressed",
  "aria-sort", "aria-haspopup",
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

function storeRead(key, json = false) {
  try {
    const held = window.localStorage.getItem(key);
    return json && held !== null ? JSON.parse(held) : held;
  } catch (err) {
    return null;
  }
}

// A null value forgets the key.
function storeWrite(key, value) {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch (err) {
    // Not kept past a restart.
  }
}

// What a place shows while its read is on its way.
function shellWaiting() {
  return [el("span", { className: "visually-hidden" }, screenWords().loading), ...shellSkeleton(3)];
}

class TrackerError extends Error {
  constructor(result) {
    super(result.error);
    this.failure = result.failure;
  }
}

async function call(args, payload) {
  return takeReply(await window.tracker.call(args, payload));
}

// A reply with an error throws its envelope (the double says no warnings).
function takeReply(result) {
  if (result.error) throw new TrackerError(result);
  return result;
}

// The notice machinery, in app.js's shape: the same nodes, the same classes.
const notices = [];
function drawNotice(entry) {
  const buttons = $("notice-buttons").content;
  const clone = (act) => buttons.querySelector(`[data-act="${act}"]`).cloneNode(true);
  const acts = [];
  if (entry.action) {
    const one = clone("retry");
    one.dataset.act = "action";
    one.textContent = entry.action.label;
    acts.push(one);
  } else if (entry.kind === "failed" && entry.retry) acts.push(clone("retry"));
  const dismiss = clone("dismiss");
  dismiss.setAttribute("aria-label", vocab.screen.icons.dismiss);
  setTip(dismiss, vocab.screen.icons.dismiss);
  entry.node.replaceChildren(
    Object.assign(document.createElement("span"), { className: "notice-text", textContent: entry.sentence }),
    ...acts, dismiss);
}
function notice(failure, { retry, action } = {}) {
  const kind = failure.kind || "failed";
  let entry = notices.find((one) => one.sentence === failure.sentence && one.kind === kind && one.key === (failure.key || null));
  if (!entry) {
    entry = { sentence: failure.sentence, kind, key: failure.key || null, retry, action };
    entry.node = Object.assign(document.createElement("div"), { className: `notice notice-${entry.kind}` });
    notices.push(entry);
    $("notices").append(entry.node);
  }
  drawNotice(entry);
  return entry;
}
function dismissNotice(entry) {
  const at = notices.indexOf(entry);
  if (at >= 0) notices.splice(at, 1);
  entry.node.remove();
}
const keyedNotices = new Map();
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
function syncNotices(prefix, wanted) {
  const keep = new Set(wanted.map((one) => `${prefix}:${one.key}`));
  for (const key of [...keyedNotices.keys()]) if (key.indexOf(`${prefix}:`) === 0 && !keep.has(key)) clearNotice(key);
  for (const one of wanted) {
    if (keyedNotice(`${prefix}:${one.key}`, one.failure, one.opts) && one.detail) window.tracker.logError(one.detail);
  }
}
function failureSentence(err) {
  window.tracker.logError(String(err.message));
  return err.failure ? err.failure.sentence : String(err.message);
}
function failed(err, retry) {
  notice({ sentence: failureSentence(err), kind: "failed" }, { retry });
}
$("notices").addEventListener("click", (e) => {
  const button = e.target.closest("button[data-act]");
  const entry = button && notices.find((one) => one.node.contains(button));
  if (!entry) return;
  if (button.dataset.act === "action") {
    entry.action.run();
    return;
  }
  dismissNotice(entry);
  if (button.dataset.act === "retry" && entry.retry) entry.retry();
});

// The lock, as app.js keeps it: the shell reads `locked` and `lockStale`.
let lockStale = false;
function appRouteChanged() {}
// F5 forgets a Sort's answer (P131); the double keeps none.
function forgetSortAnswers() {}

async function showReturn(path) {
  active = path;
  paths = null;
  try {
    lastState = await call(["state", "--engagement", path]);
    paths = lastState.paths;
    if (lastState.lock) {
      lockStale = Boolean(lastState.lock.stale);
      locked = !lastState.lock.stale;
      keyedNotice("lock", { sentence: fill(lastState.lock.stale ? vocab.lock.left_behind : vocab.lock.running, { host: lastState.lock.host }).trim(), kind: lastState.lock.stale ? "warning" : "locked" });
    } else {
      clearNotice("lock");
      lockStale = false;
      locked = false;
    }
    shellStateArrived(lastState);
    return true;
  } catch (err) {
    failed(err, () => showReturn(path));
    return false;
  }
}

function adoptList(listed) {
  engagements = listed.engagements || [];
  households = listed.households || [];
  shellAdopt(listed);
}

async function bootstrap() {
  try {
    const listed = await call(["list"]);
    vocab = listed.vocab;
    shellVocabulary();
    adoptList(listed);
    shellNeedsRoot(listed.needs_root, listed);
  } catch (err) {
    failed(err, bootstrap);
  }
}

async function saveRoot() {
  try {
    await call(["set-root"], { root: setupDraft.root });
    await bootstrap();
  } catch (err) {
    failed(err, saveRoot);
  }
}

// A pass: the double advances it once a second so the sort states can be seen.
let passTimer = null;
function runScan() {
  scanning = { args: ["sort"], pass: "p1", stopping: false };
  let n = 1;
  shellProgress({ n, of: 12, household: "Smith Family" });
  shellChanged();
  passTimer = setInterval(() => {
    n += 1;
    if (n > 12) return scanDone();
    shellProgress({ n, of: 12, household: "Smith Family" });
    shellChanged();
  }, 1000);
}
function scanDone() {
  clearInterval(passTimer);
  scanning = null;
  shellProgress({});
  shellChanged();
}
function stopPass() {
  if (!scanning) return;
  scanning.stopping = true;
  shellChanged();
  setTimeout(scanDone, 1500);
}

// The writes and dialogs: each says it was asked, which is all the shell needs.
const asked = (name) => (...args) => toast(`${name}${args.length ? "*" : ""}`);
const openNewHousehold = asked("openNewHousehold");
const openHouseholdEditor = asked("openHouseholdEditor");
const openAddReturn = asked("openAddReturn");
const markShared = asked("markShared");
const openEditor = asked("openEditor");
const openSchedule = asked("openSchedule");
const repairSchedule = asked("repairSchedule");
const clearLock = asked("clearLock");
const acceptFolderName = asked("acceptFolderName");

// pages.js reads a request's set-aside label the way app.js words it.
function isSetAside(override) {
  return override === vocab.overrides.not_applicable;
}
function overrideLabel(override, year) {
  return isSetAside(override) && year ? fill(vocab.labels[vocab.overrides.not_applicable].label, { year }) : override || "";
}

// shell.js fills the setup page's draft, which saveRoot() sends.
let setupDraft = { root: "", firm: "", phone: "" };

// The side sheet is sheet.js's and the rest of these are app.js's; the double
// has neither, so a Check or Draft reminder step, a dialog or a navigation that
// would close the sheet says so in a notice or does nothing.
function closeSheet() {}
function sheetStateArrived() {}
const openCheck = () => unanswered("check");
const openReminder = () => unanswered("draft_reminder");
const openRoll = () => unanswered("roll_forward");
const openSafeguards = () => unanswered("safeguards");
const openAbout = () => unanswered("about");
const openMisfits = () => unanswered("misfits");
