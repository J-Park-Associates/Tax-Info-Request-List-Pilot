// Electron main process — window + IPC bridge to the Python tracker.
// All tracking logic lives in the Python package (tracker/api.py); this
// process only shuttles JSON and opens paths in Explorer/Excel.
//
// The renderer is treated as untrusted at this boundary: it may only run
// commands the API says exist, only open paths the API reported, and a
// tracker process that hangs is killed rather than left to disable a button
// for ever. Python still validates everything it is given; this is the
// second wall, not the first.

const { app, BrowserWindow, Menu, ipcMain, shell, dialog } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
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

// Word for word tracker.progress.PROGRESS_KEY and
// tracker.settings.ERROR_LOG_FILENAME (tests/test_single_source.py). A
// stdout line under the key is a progress line; the one without it, last,
// is the reply.
const PROGRESS_KEY = "progress";
const ERROR_LOG_FILENAME = "tracker-errors.log";
// At most this much of a failed child's stderr is kept, and only in the
// error log - never on screen (decision 193, security principle 7).
const STDERR_CAP = 64 * 1024;

// The command the renderer runs first, and the only one allowed before the
// API has said which commands exist: its reply carries vocab.commands (the
// allowlist) and vocab.engagement_flag. Pinned to tracker.api.COMMANDS and
// to the renderer's first call by tests/test_single_source.py.
const BOOTSTRAP_COMMAND = "list";
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
let notOpened = "That is no longer the folder or file the tracker reported; nothing was opened.";
// The shell's own sentences (decision 193): learned from vocab.shell, with
// these defaults - word for word tracker.api's SHELL_* - for a first start.
let killed = "The pass ran past its limit of {minutes} minutes and was stopped. What it finished " +
  "is on the record, and the next pass does the rest.";
let killedAt = "It was on {household}: {name}.";
let noReply = "The tracker ended without a reply (exit code {code}); the details are in the error log.";
let couldNotStart = "The tracker could not start ({code}).";
let couldNotSend = "The app could not send that to the tracker ({kind}); nothing was changed.";
// The error log beside the tracker's database, as the API reports it
// (vocab.shell.error_log): the shell never builds that path. Before the API
// has said (a failed first start), the settings folder it passes to Python.
let errorLog = null;

function fill(pattern, values) {
  return pattern.replace(/\{(\w+)\}/g, (_, key) => values[key] ?? "");
}

// The one envelope the shell answers with (decision 193), the API's shape:
// the sentence as error, and again in failure with its kind.
function shellFailure(sentence, kind, extra = {}) {
  return { error: sentence, failure: { sentence, kind, seq: null, identifier: null }, warnings: [], ...extra };
}

// What only the error log may hold (decision 193, principle 7): a failed
// command's stderr, and an error of the shell's or the page's own.
function keepInLog(heading, text) {
  if (!text) return;
  const target = errorLog || path.join(SETTINGS_DIR, ERROR_LOG_FILENAME);
  const stamp = new Date().toISOString();
  fs.promises.appendFile(target, `${stamp} ${heading}\n${String(text).slice(0, STDERR_CAP)}\n`, "utf8")
    .catch(() => {});
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
  if (said && typeof said.killed_at === "string") killedAt = said.killed_at;
  if (said && typeof said.no_reply === "string") noReply = said.no_reply;
  if (said && typeof said.could_not_start === "string") couldNotStart = said.could_not_start;
  if (said && typeof said.could_not_send === "string") couldNotSend = said.could_not_send;
  if (said && typeof said.error_log === "string" && said.error_log) errorLog = said.error_log;
  const paths = (result && result.paths) || (result && result.state && result.state.paths);
  if (paths && typeof paths === "object") {
    for (const [key, value] of Object.entries(paths)) {
      if (typeof value === "string" && value) openable.set(value, pathKinds[key] || null);
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
      const failure = shellFailure(fill(killed, { minutes }) + where, "failed", { progress: last, killed: true });
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
      // Nothing of stderr goes on screen: a failed command's goes to the
      // error log beside the tracker's database, for a developer at this
      // machine (decision 193, security principle 7).
      if (!reply || reply.error) keepInLog("shell stderr of a failed command", stderr);
      const ending = killedReply || reply || shellFailure(fill(noReply, { code }), "failed", { progress: last });
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
async function openPath(p) {
  if (typeof p !== "string" || !openable.has(p)) {
    return "That path is not one the tracker reported; nothing was opened.";
  }
  const kind = openable.get(p);
  let info;
  try {
    info = await fs.promises.lstat(p);
  } catch {
    return notOpened;
  }
  const same = kind === "folder" ? info.isDirectory() : kind === "file" ? info.isFile() : false;
  if (info.isSymbolicLink() || !same) return notOpened;
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
ipcMain.handle("open-path", (_event, p) => openPath(p));
// An error of the page's own: its text goes to the error log, never on screen.
ipcMain.handle("log-error", (_event, text) => keepInLog("renderer error", typeof text === "string" ? text : ""));
ipcMain.handle("pick-folder", async (_event, title) => {
  const result = await dialog.showOpenDialog({
    title: typeof title === "string" ? title : undefined,
    properties: ["openDirectory"],
  });
  return result.canceled ? null : result.filePaths[0];
});

// The window's colour before the page paints is the stylesheet's page
// background, read from the one place it is defined.
function pageBackground() {
  const css = fs.readFileSync(path.join(__dirname, "renderer", "style.css"), "utf8");
  const match = /--bg:\s*(#[0-9a-fA-F]{3,8})/.exec(css);
  return match ? match[1] : undefined;
}

function createWindow() {
  // No menu in the packaged app (the council's E-7): Electron's default one
  // carries reload, zoom and developer-tools accelerators, and the last
  // would open the console devTools below keeps closed. From source the
  // menu stays, for the person working on the shell.
  if (app.isPackaged) Menu.setApplicationMenu(null);
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
  win.loadFile(path.join(__dirname, "renderer", "index.html"));
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
  app.whenReady().then(createWindow);
}
app.on("window-all-closed", () => app.quit());
// Closing the app stops its pass after the file it is on (decision 203,
// R6): its progress pipe breaks, which the runner takes as Stop - what it
// did is recorded, its locks are let go, and the next pass does the rest.
// Not a kill, which would leave the lock for two hours and more, and not a
// pass left running where no one can stop it.
app.on("will-quit", () => {
  for (const proc of passes.values()) proc.stdout.destroy();
});
