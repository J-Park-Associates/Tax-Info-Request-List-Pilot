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

class TrackerError extends Error {
  constructor(result) {
    super(result.error);
    this.failure = result.failure;
  }
}

async function call(args, payload) {
  const result = await window.tracker.call(args, payload);
  if (result.error) throw new TrackerError(result);
  return result;
}

// The notice machinery, in app.js's shape: the same nodes, the same classes.
const notices = [];
function drawNotice(entry) {
  const buttons = $("notice-buttons").content;
  const acts = [];
  if (entry.kind === "failed" && entry.retry) acts.push("retry");
  acts.push("dismiss");
  entry.node.replaceChildren(
    Object.assign(document.createElement("span"), { className: "notice-text", textContent: entry.sentence }),
    ...acts.map((act) => buttons.querySelector(`[data-act="${act}"]`).cloneNode(true)));
}
function notice(failure, { retry } = {}) {
  let entry = notices.find((one) => one.sentence === failure.sentence && one.kind === failure.kind);
  if (!entry) {
    entry = { sentence: failure.sentence, kind: failure.kind || "failed", retry };
    entry.node = Object.assign(document.createElement("div"), { className: `notice notice-${entry.kind}` });
    notices.push(entry);
    $("notices").append(entry.node);
  }
  drawNotice(entry);
  return entry;
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
  notices.splice(notices.indexOf(entry), 1);
  entry.node.remove();
  if (button.dataset.act === "retry" && entry.retry) entry.retry();
});

async function showReturn(path) {
  active = path;
  paths = null;
  try {
    lastState = await call(["state", "--engagement", path]);
    paths = lastState.paths;
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
    await call(["set-root"], { root: $("root-input").value });
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

// shell.js reads the old screen's stale-lock button and the setup inputs.
