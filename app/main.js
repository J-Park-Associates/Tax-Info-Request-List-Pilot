// Electron main process — window + IPC bridge to the Python tracker.
// All tracking logic lives in the Python package (tracker/api.py); this
// process only shuttles JSON and opens paths in Explorer/Excel.
//
// The renderer is treated as untrusted at this boundary: it may only run
// commands the API says exist, only open paths the API reported, and a
// tracker process that hangs is killed rather than left to disable a button
// for ever. Python still validates everything it is given; this is the
// second wall, not the first.

const { app, BrowserWindow, Menu, ipcMain, nativeTheme, shell, dialog } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "..");
// package.json is the one place the product is named and the frozen API
// executable is called; the batch file that builds it reads the same file.
const PKG = require("./package.json");
const PRODUCT_NAME = PKG.productName;
const API_NAME = PKG.config.apiName;

// Portable build: the PyInstaller-frozen API executable (package.json's
// config.apiName) ships inside resources/. From source, the app's private
// Python that Setup.bat made in the checkout's .venv, by its full path
// (decision 191): never a bare "python", which is whatever the search path
// finds first, and never the machine's own Python, which Setup never touches.
// The settings file (the clients root) lives beside the app either way: next
// to the packaged executable, or in the repository root from source.
const FROZEN_API = app.isPackaged
  ? path.join(process.resourcesPath, API_NAME, `${API_NAME}.exe`)
  : null;
const SOURCE_PYTHON = process.platform === "win32"
  ? path.join(REPO_ROOT, ".venv", "Scripts", "python.exe")
  : path.join(REPO_ROOT, ".venv", "bin", "python");
// Word for word tools/lockfiles.py's NOT_SET_UP (tests/test_single_source.py).
const NOT_SET_UP =
  "The app's private Python is not set up on this computer. " +
  "Run Setup.bat once (it needs the internet), then start the app again.";
const SETTINGS_DIR = app.isPackaged ? path.dirname(process.execPath) : REPO_ROOT;

// A command that outlives this is killed and reported, so the button it
// disabled comes back. A pass says its own limit in its first progress line
// (limit_seconds, tracker.locking.RUN_TIME_LIMIT_SECONDS - the schedule's),
// and the kill follows that instead (decision 193): the shell types no
// number of its own for a pass. Since decision 203 Sort & Scan is that
// pass - the scheduled runner for one household - so it is never cut off
// before the run limit; every other command keeps this cap (the lane's
// ruling on 203's Q1).
const TRACKER_TIMEOUT_MS = 30 * 60 * 1000;

// Word for word tracker.progress.PROGRESS_KEY (tests/test_single_source.py).
// A stdout line under the key is a progress line; the one without it,
// last, is the reply.
const PROGRESS_KEY = "progress";
// At most this much of a failed child's stderr is kept, in the error log -
// never on screen (decision 193, security principle 7).
const STDERR_CAP = 64 * 1024;

// The command the renderer runs first, and the only one allowed before the
// API has said which commands exist: its reply carries vocab.commands (the
// allowlist) and vocab.engagement_flag. Pinned to tracker.api.COMMANDS and
// to the renderer's first call by tests/test_single_source.py.
const BOOTSTRAP_COMMAND = "list";
// The after-install step's launch door (decision 209): the shell runs it
// itself, once, at start. It returns at once when the program has not
// changed since it last ran cleanly and the designation still names the
// computer it named; after an upgrade it registers the schedule on the
// computer that runs it and checks every record, which on a streamed
// Drive folder can take minutes. So it runs in the background and no call
// from the page waits for it (the review's S7): the first screen is drawn
// at once, and when the step did run the page is told on
// LAUNCH_DONE_CHANNEL and asks again, so its notice appears.
const LAUNCH_COMMAND = "after-install";
const LAUNCH_DONE_CHANNEL = "after-install-done";
let allowedCommands = null;   // vocab.commands, once seen
let engagementFlag = null;    // vocab.engagement_flag, once seen
// Sort & Scan's command (decision 203), learned, never typed: a process
// started with it is a pass - resolved at its first line, not its last.
let passCommand = null;       // vocab.pass_command, once seen
// Every pass this shell started and has not seen close, by process id:
// what will-quit tells to stop.
const passes = new Map();
// Paths the API has reported (state.paths): the only ones the shell opens,
// each with the kind the API said it is (vocab.path_kinds, decision 188).
// The renderer never names a path of its own, so anything else is refused.
const openable = new Map();
let pathKinds = {};           // vocab.path_kinds, once seen
let notOpened = "Not Opened; It Has Changed";
// The shell's own sentences (decision 193): learned from vocab.shell, with
// these defaults - word for word tracker.api's SHELL_* - for a first start.
let killed = "Sort Stopped: Ran Too Long.";
let killedWrite = "Change Stopped: Ran Too Long.";
let killedWriteNote = "It May Be Partly Done.";
let killedRead = "Stopped: Ran Too Long.";
let writingCommands = new Set();   // vocab.writing_commands, once seen
let killedAt = "It Was on {household}: {name}.";
let noReply = "No Reply From the Tracker";
let couldNotStart = "The Tracker Could Not Start";
let couldNotSend = "Could Not Send; Nothing Changed";
let noLog = "Tracker Failed";
// The error log beside the tracker's database, as the API reports it
// (vocab.shell.error_log): the shell never builds that path, and never
// writes a log beside the program or in the settings folder (decision
// 186's rebase review, MF2). Until the API has named one - a failed first
// start, or no data folder - the details go to the fallback log below
// instead, and a failed command's reply says only noLog.
let errorLog = null;
// The fallback (Jason, 2026-09-29): with no log named, a failure is still
// SAVED, in this one file in a LOCAL, NON-ROAMING per-user folder -
// %LOCALAPPDATA%\Tax Document Tracker Pilot\error.log on Windows (Jason's
// ruling: not %APPDATA%, which roams with a domain profile) - not the data
// home (nothing here creates a folder the data-home rules deny to a package;
// that one is tax-document-tracker-pilot, with hyphens), not beside the
// program, not in the settings folder. Its text may name a client: it stays
// on this PC in that file, never on screen, never sent. Capped: past
// FALLBACK_CAP it becomes error.log.1 (one copy), so it never holds more
// than twice that.
const FALLBACK_LOG_NAME = "error.log";
const FALLBACK_CAP = 256 * 1024;

function fill(pattern, values) {
  return pattern.replace(/\{(\w+)\}/g, (_, key) => values[key] ?? "");
}

// The one envelope the shell answers with (decision 193), the API's shape:
// the sentence as error, and again in failure with its kind.
function shellFailure(sentence, kind, extra = {}) {
  return { error: sentence, failure: { sentence, kind, seq: null, identifier: null }, warnings: [], ...extra };
}

// The fallback log's path, or null where there is no per-user folder. Electron
// has no getPath name for LocalAppData, so on Windows it is read from the
// environment (else the profile's AppData\Local); off Windows (the tests, a
// dev run) it is Electron's own userData folder.
function fallbackLogPath() {
  try {
    if (process.platform === "win32") {
      const local = process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local");
      return path.join(local, PRODUCT_NAME, FALLBACK_LOG_NAME);
    }
    return path.join(app.getPath("userData"), FALLBACK_LOG_NAME);
  } catch {
    return null;
  }
}

// One append, fail-safe: a write that cannot be made is dropped, never
// thrown - a broken log must not break the command whose failure it holds.
// A path that is a link or not a plain file is left alone. Only the fallback
// is capped (the API's log rotates itself).
function appendToLog(file, text, capped) {
  try {
    let info = null;
    try {
      info = fs.lstatSync(file);
    } catch {
      info = null;
    }
    if (info && (info.isSymbolicLink() || !info.isFile())) return;
    if (capped) {
      fs.mkdirSync(path.dirname(file), { recursive: true });
      if (info && info.size > FALLBACK_CAP) {
        // A folder (or anything else) that will not give way at error.log.1
        // must not stop later writes: the old log is dropped instead, so the
        // cap still holds.
        try {
          fs.rmSync(`${file}.1`, { force: true });
          fs.renameSync(file, `${file}.1`);
        } catch {
          fs.rmSync(file, { force: true });
        }
      }
    }
    fs.appendFileSync(file, text, "utf8");
  } catch {
    // dropped, by design
  }
}

// What only the error log may hold (decision 193, principle 7): a failed
// command's stderr, and an error of the shell's or the page's own. It goes
// to the log the API named, else to the fallback log; never on screen.
function keepInLog(heading, text) {
  const named = Boolean(errorLog);
  const file = named ? errorLog : fallbackLogPath();
  if (!file || !text) return;
  const stamp = new Date().toISOString();
  appendToLog(file, `${stamp} ${heading}\n${String(text).slice(0, STDERR_CAP)}\n`, !named);
}

// A failed reply whose log is not the API's (no data folder yet): it says so,
// in two words, and the stderr - which may name a client's folder - is kept
// only in the fallback log, never shown (SPEC-shell 11.2).
function withNoLog(reply) {
  const sentence = `${reply.error}\n\n${noLog}`;
  return { ...reply, error: sentence, failure: { ...(reply.failure || {}), sentence } };
}

// The API's menu words, for the keys the menu has; the menu is rebuilt only
// when a word differs from what it shows.
function learnMenu(words) {
  if (!words || typeof words !== "object") return;
  let changed = false;
  for (const key of Object.keys(DEFAULT_MENU_WORDS)) {
    if (typeof words[key] === "string" && words[key] && words[key] !== menuWords[key]) {
      menuWords[key] = words[key];
      changed = true;
    }
  }
  if (changed && menuBuilt) buildMenu();
}

function learn(result) {
  const vocab = result && result.vocab;
  if (vocab && Array.isArray(vocab.commands)) allowedCommands = new Set(vocab.commands);
  if (vocab && typeof vocab.engagement_flag === "string") engagementFlag = vocab.engagement_flag;
  if (vocab && typeof vocab.pass_command === "string") passCommand = vocab.pass_command;
  if (vocab && vocab.path_kinds && typeof vocab.path_kinds === "object") pathKinds = vocab.path_kinds;
  if (vocab && vocab.shell && typeof vocab.shell.not_opened === "string") notOpened = vocab.shell.not_opened;
  const said = vocab && vocab.shell;
  if (said && typeof said.killed === "string") killed = said.killed;
  if (said && typeof said.killed_write === "string") killedWrite = said.killed_write;
  if (said && typeof said.killed_write_note === "string") killedWriteNote = said.killed_write_note;
  if (said && typeof said.killed_read === "string") killedRead = said.killed_read;
  if (vocab && Array.isArray(vocab.writing_commands)) writingCommands = new Set(vocab.writing_commands);
  if (said && typeof said.killed_at === "string") killedAt = said.killed_at;
  if (said && typeof said.no_reply === "string") noReply = said.no_reply;
  if (said && typeof said.could_not_start === "string") couldNotStart = said.could_not_start;
  if (said && typeof said.could_not_send === "string") couldNotSend = said.could_not_send;
  if (said && typeof said.no_log === "string") noLog = said.no_log;
  learnMenu(vocab && vocab.menu);
  if (said && typeof said.error_log === "string" && said.error_log) {
    errorLog = said.error_log;
    openable.set(errorLog, "file");   // Help > Open error log, through openPath (5.5)
  }
  // A row's key is "word row" (a file name on the page), and its kind is the word's.
  const paths = (result && result.paths) || (result && result.state && result.state.paths);
  if (paths && typeof paths === "object") {
    for (const [key, value] of Object.entries(paths)) {
      if (typeof value === "string" && value) {
        openable.set(value, pathKinds[key] || pathKinds[key.split(" ", 1)[0]] || null);
      }
    }
  }
}

// What a well-formed command line looks like: a known command, alone or
// followed by the engagement flag and one folder.
function commandProblem(args) {
  if (!Array.isArray(args) || !args.length || !args.every((a) => typeof a === "string")) {
    return "Malformed command.";
  }
  const [command, ...rest] = args;
  if (allowedCommands ? !allowedCommands.has(command) : command !== BOOTSTRAP_COMMAND) {
    return `Unknown command: ${command}`;
  }
  if (rest.length === 0) return null;
  if (rest.length === 2 && engagementFlag && rest[0] === engagementFlag && rest[1]) return null;
  return "Malformed command arguments.";
}

// One command, one process. A pass (decision 203: the command named by
// vocab.pass_command) resolves with its first "started" line and runs on:
// its later lines go to onProgress, and when it closes onEnded gets its
// final line (or the shell's own failure) and its exit code. A pass that
// closes before it started - a refusal, the lock notice - resolves with
// that reply, as any command does.
function runTracker(args, payload, onProgress, onEnded) {
  const problem = commandProblem(args);
  if (problem) return Promise.resolve(shellFailure(problem, "refused"));
  return spawnTracker(args, payload, onProgress, onEnded);
}

// Start the tracker with one command already allowed: the renderer's
// through runTracker's check, and the shell's own launch door (decision 209).
function spawnTracker(args, payload, onProgress, onEnded) {
  // Serialised before anything starts (decision 176): a payload that will
  // not serialise used to throw once the tracker was already running and
  // waiting on stdin, which it then did until the timeout below.
  let body;
  try {
    body = payload === undefined ? undefined : JSON.stringify(payload);
  } catch (err) {
    // Said by its class; its message goes to the error log only (the review's S5).
    keepInLog("shell could not serialise a payload", `${err.name}: ${err.message}`);
    return Promise.resolve(shellFailure(fill(couldNotSend, { kind: err.name || "Error" }), "refused"));
  }
  if (!FROZEN_API && !fs.existsSync(SOURCE_PYTHON)) return Promise.resolve(shellFailure(NOT_SET_UP, "refused"));
  return new Promise((resolve) => {
    const env = { ...process.env, TRACKER_SETTINGS_DIR: SETTINGS_DIR, TRACKER_PRODUCT_NAME: PRODUCT_NAME };
    const proc = FROZEN_API
      ? spawn(FROZEN_API, args, { windowsHide: true, env })
      : spawn(SOURCE_PYTHON, ["-m", "tracker.api", ...args], {
          cwd: REPO_ROOT,
          windowsHide: true,
          env,
        });
    const startedAt = Date.now();
    const isPass = passCommand !== null && args[0] === passCommand;
    if (isPass && proc.pid) passes.set(proc.pid, proc);
    let running = false;      // a pass that said it started: the click has its answer
    let killedReply = null;   // what a pass killed after it started ends with
    let limitMs = TRACKER_TIMEOUT_MS;
    let pending = "";         // stdout not yet ended by a newline
    let reply;                // the last line that was not a progress line
    let last = null;          // the last progress line's fields
    let stderr = "";
    let settled = false;
    let timer = null;
    const settle = (value) => {
      if (settled) return;
      settled = true;
      if (!running) clearTimeout(timer);
      if (value && !value.error) learn(value);
      resolve(value);
    };
    const kill = () => {
      proc.kill();
      const minutes = Math.max(1, Math.round(limitMs / 60000));
      const where = last && last.name ? ` ${fill(killedAt, last)}` : "";
      // A sort says a sort stopped; a change says it may be partly done; any
      // other command only that it stopped (final review A, finding 5).
      const said = isPass ? fill(killed, { minutes })
        : writingCommands.has(args[0]) ? `${fill(killedWrite, { minutes })} ${killedWriteNote}`
        : fill(killedRead, { minutes });
      const failure = shellFailure(said + where, "failed", { progress: last, killed: true });
      if (running) killedReply = failure;   // said when it closes, as its ending
      else settle(failure);
    };
    const arm = (ms) => {
      clearTimeout(timer);
      timer = setTimeout(kill, Math.max(0, ms));
    };
    arm(TRACKER_TIMEOUT_MS);
    // One line at a time: a progress line is passed on (and its limit, when
    // it says one, re-arms the kill from the spawn); any other line is the
    // reply candidate, and the last one wins (decision 193).
    const take = (line) => {
      if (!line.trim()) return;
      let parsed;
      try {
        parsed = JSON.parse(line);
      } catch {
        reply = undefined;
        return;
      }
      const said = parsed && typeof parsed === "object" ? parsed[PROGRESS_KEY] : null;
      if (said && typeof said === "object") {
        last = said;
        if (onProgress) onProgress(said);
        if (Number.isFinite(said.limit_seconds) && said.limit_seconds > 0) {
          limitMs = said.limit_seconds * 1000;
          arm(limitMs - (Date.now() - startedAt));
        }
        // A pass has begun (decision 203): the click is answered now, and
        // the pass runs on, watched, until it closes.
        if (isPass && !settled && said.event === "started") {
          running = true;
          settle({ started: said, pass: said.pass, warnings: [] });
        }
        return;
      }
      reply = parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : undefined;
    };
    proc.stdout.setEncoding("utf8");
    proc.stdout.on("data", (d) => {
      pending += d;
      let at;
      while ((at = pending.indexOf("\n")) >= 0) {
        take(pending.slice(0, at));
        pending = pending.slice(at + 1);
      }
    });
    proc.stderr.on("data", (d) => {
      if (stderr.length < STDERR_CAP) stderr += d;
    });
    proc.stdin.on("error", () => {});   // a process that died before reading stdin is reported by "close"
    // Said by its code, never its message, which names the executable's path.
    proc.on("error", (err) =>
      settle(shellFailure(fill(couldNotStart, { code: (err && err.code) || "?" }), "failed"))
    );
    proc.on("close", (code) => {
      take(pending);
      pending = "";
      clearTimeout(timer);
      passes.delete(proc.pid);
      // Nothing of stderr goes on screen: a
      // failed command's goes to the log beside the tracker's database, for
      // a developer at this machine (decision 193, security principle 7).
      // With none named - no data folder yet - the stderr goes to the
      // fallback log and the reply says just noLog (Jason, 2026-09-29),
      // never a log beside the program (decision 186's rebase review, MF2).
      const out = killedReply || reply || shellFailure(fill(noReply, { code }), "failed", { progress: last });
      const failed = !reply || reply.error;
      if (failed) keepInLog("shell stderr of a failed command", stderr);
      const ending = failed && stderr && !errorLog ? withNoLog(out) : out;
      if (!running) settle(ending);
      else if (onEnded) onEnded({ reply: ending, code });
    });
    if (body !== undefined) proc.stdin.write(body, "utf8");
    proc.stdin.end();
  });
}

// Opened only while it is still what the API reported it as (decision 188,
// E-14): lstat, never stat, so a link swapped in for a folder or a file -
// Node reports a junction as a symbolic link too - is seen for what it is,
// and a folder is opened only as a folder and a file only as a file.
// With `reveal` the item is shown in File Explorer instead (a file selected in
// its folder, a folder opened): the same allow-list, the same lstat, the same
// refusal - a file name on the page, never a new path.
async function openPath(p, reveal) {
  if (typeof p !== "string" || !openable.has(p)) {
    return "That path is not one the tracker reported; nothing was opened.";
  }
  return openChecked(p, openable.get(p), reveal === "reveal");
}

// The check itself, shared with Open error log's fallback, which is the
// shell's own file and so not among the paths the API reported.
async function openChecked(p, kind, reveal) {
  let info;
  try {
    info = await fs.promises.lstat(p);
  } catch {
    return notOpened;
  }
  const same = kind === "folder" ? info.isDirectory()
    : kind === "file" || kind === "reveal" ? info.isFile() : false;
  if (info.isSymbolicLink() || !same) return notOpened;
  // A reveal-only kind (a filed, moved or set-aside working copy) is shown,
  // never opened: only a marked review copy opens in the default program
  // (decision 190). A plain open of one is refused, as any other unreported path.
  if (kind === "reveal" && !reveal) return notOpened;
  if (reveal && (kind === "file" || kind === "reveal")) {
    shell.showItemInFolder(p);
    return "";
  }
  return shell.openPath(p);
}

// A pass's progress lines go to the window that asked, on their own channel
// (decision 193), and so does its ending once the click has been answered
// (decision 203): {args, reply, code}. A window gone by then hears nothing.
ipcMain.handle("tracker-cmd", (event, args, payload) => {
  const send = (message) => {
    if (!event.sender.isDestroyed()) event.sender.send("tracker-progress", { args, ...message });
  };
  return runTracker(args, payload, (progress) => send({ progress }), (ended) => send(ended));
});
ipcMain.handle("open-path", (_event, p, how) => openPath(p, how));
// An error of the page's own: its text goes to the error log, never on screen.
ipcMain.handle("log-error", (_event, text) => {
  keepInLog("renderer error", typeof text === "string" ? text : "");
});
ipcMain.handle("pick-folder", async (_event, title) => {
  const result = await dialog.showOpenDialog({
    title: typeof title === "string" ? title : undefined,
    properties: ["openDirectory"],
  });
  return result.canceled ? null : result.filePaths[0];
});

// ---- The menu bar and the right-click menus (SPEC-shell 5) ----------------
// Built here from the API's words (vocab.menu): these defaults are word for
// word tracker.api's MENU, so the menu is there from the first frame, and a
// test keeps the two equal. `&` marks an access key.
const DEFAULT_MENU_WORDS = {
  file: "&File",
  new_household: "New Household…",
  change_root: "Change Clients Folder…",
  open_root: "Open Clients Folder",
  exit: "Exit",
  edit: "&Edit",
  client: "&Client",
  edit_household: "Edit Household…",
  add_return: "Add a Return…",
  roll_forward: "Roll Forward…",
  mark_shared: "Mark as Shared",
  edit_list: "Edit Request List…",
  draft_reminder: "Draft Reminder…",
  open_client_folder: "Open Client Folder",
  open_inbox: "Open Inbox",
  open_working: "Open Working Folder",
  view: "&View",
  overview: "Overview",
  needs_review: "Needs Review",
  reminders: "Reminders",
  clients: "Clients",
  find: "Find",
  refresh: "Refresh",
  reset_columns: "Reset Column Widths",
  tools: "&Tools",
  sort_now: "Sort Now",
  stop_sorting: "Stop Sorting",
  schedule: "Schedule…",
  repair_schedule: "Repair Schedule",
  firm_report: "Firm Report",
  clear_lock: "Clear Stuck Lock",
  help: "&Help",
  tour: "Take the Tour",
  safeguards: "Safeguards",
  terms: "Terms",
  error_log: "Open Error Log",
  about: "About",
  check: "Check…",
  not_requested: "Not Requested",
  another_return: "Another Return…",
  put_back: "Put Back",
  keep_here: "Keep Here",
  edit_request: "Edit Request…",
  unfile: "Unfile",
  mark_missing: "Mark Missing",
  show_in_explorer: "Show in File Explorer",
};
let menuWords = { ...DEFAULT_MENU_WORDS };
// The one channel the shell sends the page a chosen item on: {id, token}.
// The page answers it as it answers a click - through window.tracker.call,
// with every check in place. Nothing here reaches the tracker.
const MENU_CHANNEL = "menu";
// The page's own token is a row key it made, never a path; at most this long.
const MENU_TOKEN_MAX = 64;
const SEPARATOR = "-";
// [id, accelerator]: the menu bar, in order, under its top-level word. There
// is no Reload, Zoom, Toggle full screen or Developer tools item and no
// accelerator for one (P58): F5 is Refresh, and the page re-reads. Exit is
// the quit role; Alt+F4 is Windows' own.
const BAR = [
  ["file", [["new_household", "CmdOrCtrl+N"], ["change_root"], ["open_root"], SEPARATOR, ["exit"]]],
  ["edit", null],
  ["client", [["edit_household"], ["add_return"], ["roll_forward"], ["mark_shared"], SEPARATOR,
    ["edit_list", "CmdOrCtrl+E"], ["draft_reminder"], SEPARATOR,
    ["open_client_folder"], ["open_inbox"], ["open_working"]]],
  ["view", [["overview", "CmdOrCtrl+1"], ["needs_review", "CmdOrCtrl+2"], ["reminders", "CmdOrCtrl+3"],
    ["clients", "CmdOrCtrl+4"], SEPARATOR, ["find", "CmdOrCtrl+F"], ["refresh", "F5"], SEPARATOR, ["reset_columns"]]],
  ["tools", [["sort_now", "F9"], ["stop_sorting"], SEPARATOR, ["schedule"], ["repair_schedule"],
    ["firm_report"], SEPARATOR, ["clear_lock"]]],
  ["help", [["tour"], ["safeguards"], ["terms"], ["error_log"], SEPARATOR, ["about"]]],
];
// The right-click menus, by the name the page asks for (5.2).
const POPUPS = new Map([
  ["household", ["edit_household", "add_return", "roll_forward", "mark_shared", SEPARATOR,
    "open_client_folder", "open_inbox"]],
  ["return", ["edit_list", "draft_reminder", SEPARATOR, "open_working", "open_client_folder", "open_inbox"]],
  ["file", ["check", "not_requested", "another_return", "show_in_explorer"]],
  ["moved", ["check", "put_back", "keep_here", "show_in_explorer"]],
  ["request", ["edit_request"]],
  ["received", ["unfile", "mark_missing", "show_in_explorer"]],
]);
// What needs nothing of the page: enabled from the first frame.
const ALWAYS = new Set(["change_root", "exit", "refresh", "tour", "safeguards", "terms", "error_log", "about"]);
const BAR_IDS = new Set(BAR.flatMap(([, items]) => (items || []).filter((i) => i !== SEPARATOR).map((i) => i[0])));
// What the page last said applies (5.3); until it speaks only ALWAYS does.
let menuEnabled = new Set();
let menuBuilt = false;
let mainWindow = null;

// The window a chosen item is sent to; a window gone hears nothing.
function sendMenu(message) {
  if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send(MENU_CHANNEL, message);
}

// Open error log (5.5) is the shell's alone: the log the API named, else the
// fallback log, opened through the same lstat check as openPath (a regular
// file and no link); if neither is there the page is told and says so.
async function openErrorLog() {
  const target = errorLog || fallbackLogPath();
  const problem = target ? await openChecked(target, "file") : "none";
  if (problem) sendMenu({ id: "error_log", missing: true });
}

// One item, by id: the API's word for its label; a click is the page's to
// answer, with the row's own token when there is one.
function menuItem(id, enabled, token) {
  return {
    label: menuWords[id],
    enabled,
    click: () => {
      if (id === "error_log") openErrorLog().catch(() => null);
      else sendMenu({ id, token });
    },
  };
}

function buildTemplate() {
  return BAR.map(([key, items]) => {
    // Edit is Windows' own: Undo, Redo, Cut, Copy, Paste and Select all.
    if (!items) return { label: menuWords[key], role: "editMenu" };
    return {
      label: menuWords[key],
      submenu: items.map((item) => {
        if (item === SEPARATOR) return { type: "separator" };
        const [id, accelerator] = item;
        if (id === "exit") return { label: menuWords.exit, role: "quit" };
        const built = menuItem(id, ALWAYS.has(id) || menuEnabled.has(id), "");
        if (accelerator) built.accelerator = accelerator;
        return built;
      }),
    };
  });
}

function buildMenu() {
  Menu.setApplicationMenu(Menu.buildFromTemplate(buildTemplate()));
  menuBuilt = true;
}

// A right-click menu at the pointer, or where the page says when that is
// inside the window. `enable` is this popup's own list; the page leaves the
// writing items out of it for a locked return (5.2).
function popupMenu(win, name, enable, token, x, y) {
  const enabled = new Set(enable);
  const items = POPUPS.get(name).map((id) => (id === SEPARATOR
    ? { type: "separator" } : menuItem(id, enabled.has(id), token)));
  const at = { window: win };
  const inside = (n, limit) => Number.isFinite(n) && n >= 0 && n <= limit;
  const box = win.getContentBounds();
  if (inside(x, box.width) && inside(y, box.height)) {
    at.x = Math.round(x);
    at.y = Math.round(y);
  }
  Menu.buildFromTemplate(items).popup(at);
}

// Every message on the menu channel is untrusted (5.4): ids not in the
// template are dropped, a popup must be one of the six, a token must be a
// short string. Nothing the page says adds, removes or renames an item.
function onMenuMessage(event, message) {
  if (!mainWindow || event.sender !== mainWindow.webContents) return;
  if (!message || typeof message !== "object" || Array.isArray(message)) return;
  const known = (list, allowed) => (Array.isArray(list)
    ? list.filter((id) => typeof id === "string" && allowed.has(id)) : null);
  if (message.popup !== undefined) {
    if (typeof message.popup !== "string" || !POPUPS.has(message.popup)) return;
    const token = message.token === undefined ? "" : message.token;
    if (typeof token !== "string" || token.length > MENU_TOKEN_MAX) return;
    const allowed = new Set(POPUPS.get(message.popup).filter((id) => id !== SEPARATOR));
    popupMenu(mainWindow, message.popup, known(message.enable, allowed) || [], token, message.x, message.y);
    return;
  }
  const enable = known(message.enable, BAR_IDS);
  if (!enable) return;
  const next = new Set(enable);
  const same = next.size === menuEnabled.size && [...next].every((id) => menuEnabled.has(id));
  menuEnabled = next;
  if (!same && menuBuilt) buildMenu();
}
ipcMain.on(MENU_CHANNEL, onMenuMessage);

// The window's colour before the page paints (5.6): the page's own
// background for the theme the system is in, read from the one place it is
// defined - pilot-ui.css's --window-light and --window-dark - and left to the
// page when a Windows contrast theme is on (it paints its own). Read
// defensively: a stylesheet without the names (or without the file) gives
// the older page background, then nothing, never a thrown error at start.
function tokenColour(css, name) {
  const match = new RegExp(`${name}:\\s*(#[0-9a-fA-F]{3,8})`).exec(css);
  return match ? match[1] : undefined;
}

function pageBackground() {
  if (nativeTheme.shouldUseHighContrastColors) return undefined;
  const read = (file) => {
    try {
      return fs.readFileSync(path.join(__dirname, "renderer", file), "utf8");
    } catch {
      return "";
    }
  };
  const name = nativeTheme.shouldUseDarkColors ? "--window-dark" : "--window-light";
  return tokenColour(read("pilot-ui.css"), name) || tokenColour(read("style.css"), "--bg");
}

function createWindow() {
  // The app's own menu, in both builds (5.1): Electron's default one carries
  // reload, zoom and developer-tools accelerators (the council's E-7), and
  // the last would open the console devTools below keeps closed. This one
  // has none of them.
  buildMenu();
  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    title: PRODUCT_NAME,
    backgroundColor: pageBackground(),
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      // No developer tools in the packaged app (decision 176): they are a
      // console on the page, and from it window.tracker.call() reaches the
      // API with any payload a person at the machine types.
      devTools: !app.isPackaged,
    },
  });
  // One page, no navigation, no pop-ups: the renderer has nowhere else to go.
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  win.webContents.on("will-navigate", (event) => event.preventDefault());
  // What the page keeps in its storage goes to disk as the window closes
  // (pilot P46), not at the end of a shutdown that a quick restart can
  // overtake - Electron lets go of the one-instance lock before it closes
  // that storage, so the new window found it held and read nothing.
  win.on("close", () => win.webContents.session.flushStorageData());
  mainWindow = win;
  win.on("closed", () => {
    if (mainWindow === win) mainWindow = null;
  });
  win.loadFile(path.join(__dirname, "renderer", "index.html"));
  return win;
}

// One window (decision 160). A second double-click used to open a second
// window, and two windows are two request-list editors: the one opened
// first saved over the other's save. So the shell takes the single-instance
// lock; a launch that cannot have it quits before any window is made, and
// the running one answers it by bringing its window forward.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    const [win] = BrowserWindow.getAllWindows();
    if (!win) return;
    if (win.isMinimized()) win.restore();
    win.focus();
  });
  app.whenReady().then(() => {
    const win = createWindow();
    // Not awaited by anything: a step that fails records its own sentence
    // for the notice (tracker.api's launch door), and one that cannot
    // start is tried again at the next launch.
    spawnTracker([LAUNCH_COMMAND], { reason: "launch" })
      .then((result) => {
        if (result && result.ran && !win.isDestroyed()) win.webContents.send(LAUNCH_DONE_CHANNEL);
      })
      .catch(() => null);
  });
}
// A switch between light and dark while the app is open sets the window's
// colour again, so a resize does not flash the old one behind the page. The
// theme source stays the system's: the page follows it through
// prefers-color-scheme and nothing in the renderer asks.
nativeTheme.themeSource = "system";
nativeTheme.on("updated", () => {
  const colour = pageBackground();
  if (mainWindow && !mainWindow.isDestroyed() && colour) mainWindow.setBackgroundColor(colour);
});
app.on("window-all-closed", () => app.quit());
// Closing the app stops its pass after the file it is on (decision 203,
// R6): its progress pipe breaks, which the runner takes as Stop - what it
// did is recorded, its locks are let go, and the next pass does the rest.
// Not a kill, which would leave the lock for two hours and more, and not a
// pass left running where no one can stop it.
app.on("will-quit", () => {
  for (const proc of passes.values()) proc.stdout.destroy();
});
