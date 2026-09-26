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

// A pass over one engagement can OCR every PDF in it; the scheduled task is
// allowed two hours. A command that outlives this is killed and reported,
// so the button it disabled comes back.
const TRACKER_TIMEOUT_MS = 30 * 60 * 1000;

// The command the renderer runs first, and the only one allowed before the
// API has said which commands exist: its reply carries vocab.commands (the
// allowlist) and vocab.engagement_flag. Pinned to tracker.api.COMMANDS and
// to the renderer's first call by tests/test_single_source.py.
const BOOTSTRAP_COMMAND = "list";
// The after-install step's launch door (decision 209): the shell runs it
// itself, once, before the page's first call is answered. It returns at
// once when the program has not changed since it last ran cleanly; after
// an upgrade it registers the schedule on the computer that runs it and
// checks the record. Its findings reach the page through the first call's
// reply (after_install), so nothing here reads its answer.
const LAUNCH_COMMAND = "after-install";
let launchStep = Promise.resolve();
let allowedCommands = null;   // vocab.commands, once seen
let engagementFlag = null;    // vocab.engagement_flag, once seen
// Paths the API has reported (state.paths): the only ones the shell opens,
// each with the kind the API said it is (vocab.path_kinds, decision 188).
// The renderer never names a path of its own, so anything else is refused.
const openable = new Map();
let pathKinds = {};           // vocab.path_kinds, once seen
let notOpened = "That is no longer the folder or file the tracker reported; nothing was opened.";

function learn(result) {
  const vocab = result && result.vocab;
  if (vocab && Array.isArray(vocab.commands)) allowedCommands = new Set(vocab.commands);
  if (vocab && typeof vocab.engagement_flag === "string") engagementFlag = vocab.engagement_flag;
  if (vocab && vocab.path_kinds && typeof vocab.path_kinds === "object") pathKinds = vocab.path_kinds;
  if (vocab && vocab.shell && typeof vocab.shell.not_opened === "string") notOpened = vocab.shell.not_opened;
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

function runTracker(args, payload) {
  const problem = commandProblem(args);
  if (problem) return Promise.resolve({ error: problem });
  return spawnTracker(args, payload);
}

// Start the tracker with one command already allowed: the renderer's
// through runTracker's check, and the shell's own launch door.
function spawnTracker(args, payload) {
  // Serialised before anything starts (decision 176): a payload that will
  // not serialise used to throw once the tracker was already running and
  // waiting on stdin, which it then did until the timeout below.
  let body;
  try {
    body = payload === undefined ? undefined : JSON.stringify(payload);
  } catch (err) {
    return Promise.resolve({ error: `The app could not send that to the tracker: ${err.message}` });
  }
  if (!FROZEN_API && !fs.existsSync(SOURCE_PYTHON)) return Promise.resolve({ error: NOT_SET_UP });
  return new Promise((resolve) => {
    const env = { ...process.env, TRACKER_SETTINGS_DIR: SETTINGS_DIR, TRACKER_PRODUCT_NAME: PRODUCT_NAME };
    const proc = FROZEN_API
      ? spawn(FROZEN_API, args, { windowsHide: true, env })
      : spawn(SOURCE_PYTHON, ["-m", "tracker.api", ...args], {
          cwd: REPO_ROOT,
          windowsHide: true,
          env,
        });
    let stdout = "";
    let stderr = "";
    let settled = false;
    const settle = (value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (value && !value.error) learn(value);
      resolve(value);
    };
    const timer = setTimeout(() => {
      proc.kill();
      settle({ error: `The tracker took longer than ${TRACKER_TIMEOUT_MS / 60000} minutes and was stopped.` });
    }, TRACKER_TIMEOUT_MS);
    proc.stdout.on("data", (d) => (stdout += d));
    proc.stderr.on("data", (d) => (stderr += d));
    proc.stdin.on("error", () => {});   // a process that died before reading stdin is reported by "close"
    proc.on("error", (err) =>
      settle({ error: `Could not start the tracker: ${err.message}` })
    );
    proc.on("close", (code) => {
      try {
        settle(JSON.parse(stdout));
      } catch {
        settle({
          error: `Unexpected tracker output (exit code ${code}).\n${(stderr || stdout).slice(0, 400)}`,
        });
      }
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

// Every call from the page waits for the launch door first, so the first
// screen is drawn from what the after-install step left.
ipcMain.handle("tracker-cmd", async (_event, args, payload) => {
  await launchStep;
  return runTracker(args, payload);
});
ipcMain.handle("open-path", (_event, p) => openPath(p));
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
  app.whenReady().then(() => {
    launchStep = spawnTracker([LAUNCH_COMMAND], { reason: "launch" }).catch(() => null);
    createWindow();
  });
}
app.on("window-all-closed", () => app.quit());
