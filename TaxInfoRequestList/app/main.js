// Electron main process — window + IPC bridge to the Python tracker.
// All tracking logic lives in the Python package (tracker/api.py); this
// process only shuttles JSON and opens paths in Explorer/Excel.

const { app, BrowserWindow, ipcMain, shell, dialog } = require("electron");
const { spawn } = require("child_process");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "..");

// Portable build: a PyInstaller-frozen tracker-api.exe ships inside
// resources/, and demo data lives next to the packaged exe. Dev mode
// falls back to the system Python + repo layout.
const FROZEN_API = app.isPackaged
  ? path.join(process.resourcesPath, "tracker-api", "tracker-api.exe")
  : null;
const DEMO_ROOT = app.isPackaged
  ? path.join(path.dirname(process.execPath), "demo-marketing")
  : null;

function runTracker(args, payload) {
  return new Promise((resolve) => {
    const proc = FROZEN_API
      ? spawn(FROZEN_API, args, {
          windowsHide: true,
          env: { ...process.env, TRACKER_DEMO_ROOT: DEMO_ROOT },
        })
      : spawn("python", ["-m", "tracker.api", ...args], {
          cwd: REPO_ROOT,
          windowsHide: true,
        });
    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (d) => (stdout += d));
    proc.stderr.on("data", (d) => (stderr += d));
    proc.on("error", (err) =>
      resolve({ error: `Could not start Python: ${err.message}` })
    );
    proc.on("close", () => {
      try {
        resolve(JSON.parse(stdout));
      } catch {
        resolve({
          error: `Unexpected tracker output.\n${(stderr || stdout).slice(0, 400)}`,
        });
      }
    });
    if (payload !== undefined) proc.stdin.write(JSON.stringify(payload));
    proc.stdin.end();
  });
}

ipcMain.handle("tracker-cmd", (_event, args, payload) => runTracker(args, payload));
ipcMain.handle("open-path", (_event, p) => shell.openPath(p));

function createWindow() {
  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    title: "Tax Document Tracker — J Park & Associates",
    backgroundColor: "#F5F7FA",
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  win.loadFile(path.join(__dirname, "renderer", "index.html"));
}

app.whenReady().then(createWindow);
app.on("window-all-closed", () => app.quit());
