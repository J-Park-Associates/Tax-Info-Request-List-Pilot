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
// Electron keeps the page's own storage (the column widths, the cached terms
// and tour answers) in its userData folder, which it names after productName.
// The rename to Tax Document Console (P155) would silently start a new, empty
// folder, so the folder keeps the earlier name, package.json's
// config.userDataName (SPEC-rename R4): nothing to copy or move. Set before
// anything asks for a path and before the single-instance lock, which
// Electron keys on this folder, so the lock is the same across the upgrade.
app.setPath("userData", path.join(app.getPath("appData"), PKG.config.userDataName));

// Portable build: the PyInstaller-frozen API executable (package.json's
// config.apiName) ships inside resources/. From source, the app's private
// Python that Setup.bat made in the checkout's .venv, by its full path
// (decision 191): never a bare "python", which is whatever the search path
// finds first, and never the machine's own Python, which Setup never touches.
// The settings file (the clients root) lives beside the app: next to the
// packaged executable, or in the repository root from source (SETTINGS_DIR
// below says where it goes on a Mac).
// Only Windows gives an executable a suffix: the frozen API on a Mac is
// Contents/Resources/<apiName>/<apiName> (SPEC-mac R14).
const FROZEN_API = app.isPackaged
  ? path.join(process.resourcesPath, API_NAME, process.platform === "win32" ? `${API_NAME}.exe` : API_NAME)
  : null;
const SOURCE_PYTHON = process.platform === "win32"
  ? path.join(REPO_ROOT, ".venv", "Scripts", "python.exe")
  : path.join(REPO_ROOT, ".venv", "bin", "python");
// Word for word tools/lockfiles.py's NOT_SET_UP (tests/test_single_source.py).
const NOT_SET_UP =
  "The app's private Python is not set up on this computer. " +
  "Run Setup.bat once (it needs the internet), then start the app again.";
// And its Mac form, NOT_SET_UP_MAC: the file a person runs there is setup.command
// (SPEC-mac R11). Said instead of the Windows sentence, never beside it.
const NOT_SET_UP_MAC =
  "The app's private Python is not set up on this computer. " +
  "Run setup.command once (it needs the internet), then start the app again.";
// Where the settings file lives (decision 131). Beside the executable on
// Windows; on a Mac, in the product's folder in Application Support instead,
// because a Mac app is a bundle replaced whole by dragging a newer one over
// it (P155), and a file inside it would go with it, losing the clients root
// (SPEC-mac R2). Word for word tracker.settings.mac_settings_dir:
// ~/Library/Application Support/<productName>, pinned equal by a test. This
// is not Electron's own userData folder above, which keeps its earlier name.
const SETTINGS_DIR = !app.isPackaged
  ? REPO_ROOT
  : process.platform === "darwin"
    ? path.join(app.getPath("appData"), PRODUCT_NAME)
    : path.dirname(process.execPath);

// The hardware floor (SPEC-mac R6, P243): Apple silicon on macOS 14 or later.
// A Drag-to-Applications install has no installer program to refuse with, so
// the first code that runs says this and stops, before the one-instance lock
// (which writes to userData) and before any window. Word for word
// tracker.settings.MAC_FLOOR; the API makes the same check for the schedule,
// which runs it without this shell. macOS 14 is Darwin 23.
const MAC_FLOOR =
  "{product} needs a Mac with Apple silicon running macOS 14 or later; " +
  "this Mac has {what}, so the app stops here and changes nothing.";
const MAC_FLOOR_DARWIN = 23;

// MAC_FLOOR filled with what this Mac has, or "" where this is not a Mac or
// it meets the floor. The macOS release is named from the Darwin major
// version os.release() gives: 20 is macOS 11 and 25 is macOS 26.
function macFloorRefusal() {
  if (process.platform !== "darwin") return "";
  const darwin = parseInt(os.release().split(".")[0], 10);
  const silicon = process.arch === "arm64";
  if (silicon && darwin >= MAC_FLOOR_DARWIN) return "";
  const chip = silicon ? "Apple silicon" : process.arch === "x64" ? "an Intel processor" : process.arch;
  const macos = Number.isNaN(darwin) ? "a macOS it cannot name"
    : `macOS ${darwin >= 25 ? darwin + 1 : darwin >= 20 ? darwin - 9 : `10.${darwin - 4}`}`;
  return MAC_FLOOR.replace("{product}", PRODUCT_NAME).replace("{what}", `${chip} running ${macos}`);
}

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

// The command the renderer runs first: its reply carries vocab.commands (the
// allowlist) and vocab.engagement_flag. Pinned to tracker.api.COMMANDS and
// to the renderer's first call by tests/test_single_source.py.
const BOOTSTRAP_COMMAND = "list";
// What may run before the API has said which commands exist (decision 176):
// the list, and since P221 the Overview's counts asked beside it, so the
// first Overview no longer waits for the list to finish, and since P229 the
// counts it last had today, drawn marked until those land. All are
// read-only replies (tracker.api.HELD_READING_COMMANDS, none a writing
// command).
const EARLY_COMMANDS = new Set([BOOTSTRAP_COMMAND, "firm", "firm-last"]);
// The read-only replies, word for word tracker.api.HELD_READING_COMMANDS
// (tests/test_single_source.py): the only commands run again when the engine
// they were handed to closed without a word (P220, P276). A write is never run twice.
const HELD_READING_COMMANDS = new Set(["firm", "firm-last", "list", "state"]);
// The after-install step's launch door (decision 209): the shell runs it
// itself, once, at start. It returns at once when the program has not
// changed since it last ran cleanly and the designation still names the
// computer it named; after an upgrade it registers the schedule on the
// computer that runs it and checks every record, which on a streamed
// Drive folder can take minutes. So it runs in the background and no call
// from the page waits for it (the review's S7): the first screen is drawn
// at once, and when the step did run the page is told on
// LAUNCH_DONE_CHANNEL and asks again, so its notice appears. The message
// carries the two facts of the reply the page says aloud (pilot P257): whether
// this run registered the schedule on this computer, and the engine's
// sentence for it, so the first open after an upgrade says in a toast that
// this computer now runs the schedule. Nothing else of the reply crosses.
const LAUNCH_COMMAND = "after-install";
const LAUNCH_DONE_CHANNEL = "after-install-done";
// The last-pass watch (SPEC-ui-menu-speed 1, P277): the scheduled pass writes
// last-pass.json when it starts and when it ends, and the page used to ask
// the engine for it on a timer - an engine process a minute while nothing
// happened. Now `list` names the file (vocab.shell.last_pass_file) and this
// file watches its FOLDER; a change becomes one message on LAST_PASS_CHANNEL
// that carries nothing, and the page asks the engine's `last-pass` once. The
// file itself is never read here: the engine is its one reader, and the
// message cannot carry what the shell never saw.
const LAST_PASS_CHANNEL = "last-pass-changed";
// A burst - the create, the write and the rename one atomic replace makes -
// is one message, sent this long after the last event of it.
const LAST_PASS_SETTLE_MS = 250;
// The stat fallback's interval, used only where fs.watch cannot be set: a
// stat in this process, never an engine process.
const LAST_PASS_POLL_MS = 5000;
let lastPassWatch = null;     // {file, watcher | null, polling} while a file is watched
let lastPassTimer = null;     // the settle timer
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
// The paths among them whose copy Windows would have marked as from the
// internet (state.carries_code, SPEC-mac R8): a Mac cannot mark one, so each
// time it opens one the page says shellSays.protected_view_mac. Only ever
// added to, like `openable`: saying it once too often is one more notice, and
// saying it once too few is the failure.
const carriesCode = new Set();
// The shell's own sentences (decision 193), keyed as vocab.shell keys them:
// learned from it, with these defaults - word for word tracker.api's SHELL_*
// - for a first start. learn() copies every key the API sent as a string.
const shellSays = {
  not_opened: "Not Opened; It Has Changed",
  protected_view_mac:
    "Protected View does not exist on a Mac, so this file opened normally. Keep macros off in " +
    "Excel, Word and PowerPoint: Settings > Security > Macro Security > Disable all macros " +
    "without notification.",
  killed: "Sort Stopped: Ran Too Long.",
  killed_write: "Change Stopped: Ran Too Long.",
  killed_write_note: "It May Be Partly Done.",
  killed_read: "Stopped: Ran Too Long.",
  killed_at: "It Was on {household}: {name}.",
  no_reply: "No Reply From the App",
  could_not_start: "The App Could Not Start",
  could_not_send: "Could Not Send; Nothing Changed",
  no_log: "App Failed",
};
let writingCommands = new Set();   // vocab.writing_commands, once seen
// The error log beside the tracker's database, as the API reports it
// (vocab.shell.error_log): the shell never builds that path, and never
// writes a log beside the program or in the settings folder (decision
// 186's rebase review, MF2). Until the API has named one - a failed first
// start, or no data folder - the details go to the fallback log below
// instead, and a failed command's reply says only shellSays.no_log.
let errorLog = null;
// The fallback (Jason, 2026-09-29): with no log named, a failure is still
// SAVED, in this one file in a LOCAL, NON-ROAMING per-user folder -
// %LOCALAPPDATA%\<productName>\error.log on Windows (Jason's ruling: not
// %APPDATA%, which roams with a domain profile; on a PC upgraded from the
// earlier name, %LOCALAPPDATA%\Tax Document Tracker Pilot may still hold an
// earlier log, which nothing here reads or moves - P155) - not the data
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
  const sentence = `${reply.error}\n\n${shellSays.no_log}`;
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

// A change was seen (or may have been): one message, once the burst settles.
function lastPassSoon() {
  clearTimeout(lastPassTimer);
  lastPassTimer = setTimeout(() => {
    lastPassTimer = null;
    if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send(LAST_PASS_CHANNEL);
  }, LAST_PASS_SETTLE_MS);
}

// The stat watch, only where fs.watch cannot be had: the file's size or
// modified time moved. The reason is said once, as a code with no path.
function pollLastPass(file, code) {
  keepInLog("shell's last-pass watch", `fs.watch failed (${code}); the file is looked at every ${LAST_PASS_POLL_MS / 1000} s instead`);
  fs.watchFile(file, { interval: LAST_PASS_POLL_MS, persistent: false }, (now, before) => {
    if (now.mtimeMs !== before.mtimeMs || now.size !== before.size) lastPassSoon();
  });
  lastPassWatch.polling = true;
}

// Watch the folder of `file`, not the file: the pass replaces the file whole
// (a temporary file, then a rename), so the file is a new file after every
// write and a watch on the old one is lost (kqueue, inotify). An event for
// another file in the folder is ignored; one with no name is taken as
// ours, since Node does not promise a name.
function watchLastPass(file) {
  if (lastPassWatch && lastPassWatch.file === file) return;
  unwatchLastPass();
  lastPassWatch = { file, watcher: null, polling: false };
  const mine = path.basename(file);
  try {
    const watcher = fs.watch(path.dirname(file), { persistent: false }, (_event, name) => {
      if (name && String(name) !== mine) return;
      lastPassSoon();
    });
    lastPassWatch.watcher = watcher;
    watcher.on("error", (err) => {
      try {
        watcher.close();
      } catch {
        // already closed
      }
      if (lastPassWatch && lastPassWatch.watcher === watcher) {
        lastPassWatch.watcher = null;
        pollLastPass(file, (err && err.code) || "error");
      }
    });
  } catch (err) {
    pollLastPass(file, (err && err.code) || "error");
  }
}

function unwatchLastPass() {
  clearTimeout(lastPassTimer);
  lastPassTimer = null;
  const held = lastPassWatch;
  lastPassWatch = null;
  if (!held) return;
  if (held.watcher) {
    try {
      held.watcher.close();
    } catch {
      // already closed
    }
  }
  if (held.polling) fs.unwatchFile(held.file);
}

function learn(result) {
  const vocab = result && result.vocab;
  if (vocab && Array.isArray(vocab.commands)) allowedCommands = new Set(vocab.commands);
  // The commands that run a pass or the after-install step, which never go to
  // the engine (P276); before this is seen only EARLY_COMMANDS may run.
  if (vocab && Array.isArray(vocab.own_process_commands)) ownProcessCommands = new Set(vocab.own_process_commands);
  if (vocab && typeof vocab.engagement_flag === "string") engagementFlag = vocab.engagement_flag;
  if (vocab && typeof vocab.pass_command === "string") passCommand = vocab.pass_command;
  if (vocab && vocab.path_kinds && typeof vocab.path_kinds === "object") pathKinds = vocab.path_kinds;
  const said = vocab && vocab.shell;
  for (const key of Object.keys(shellSays)) {
    if (said && typeof said[key] === "string") shellSays[key] = said[key];
  }
  if (vocab && Array.isArray(vocab.writing_commands)) writingCommands = new Set(vocab.writing_commands);
  learnMenu(vocab && vocab.menu);
  if (said && typeof said.error_log === "string" && said.error_log) {
    errorLog = said.error_log;
    openable.set(errorLog, "file");   // Help > Open error log, through openPath (5.5)
  }
  // The last-pass file the API named: its folder is watched (P277). A list
  // that names none (no data home) ends the watch; a reply with no shell
  // words at all (a firm, a state) leaves it alone.
  if (said && typeof said === "object") {
    if (typeof said.last_pass_file === "string" && said.last_pass_file) watchLastPass(said.last_pass_file);
    else unwatchLastPass();
  }
  // A row's key is "word row" (a file name on the page), and its kind is the word's.
  const code = (result && result.carries_code) || (result && result.state && result.state.carries_code);
  if (Array.isArray(code)) {
    for (const p of code) if (typeof p === "string" && p) carriesCode.add(p);
  }
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
  if (allowedCommands ? !allowedCommands.has(command) : !EARLY_COMMANDS.has(command)) {
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
// The command is handed to the engine (P276) while it is free; a pass, a
// command the API says runs alone (vocab.own_process_commands), the launch
// door, a `fresh` re-run and any command while there is no usable engine start
// a process of their own, as every command did before the engine.
function spawnTracker(args, payload, onProgress, onEnded, { fresh = false } = {}) {
  // Serialised before anything starts (decision 176): a payload that will
  // not serialise used to throw once the tracker was already running and
  // waiting on stdin, which it then did until the timeout below.
  let body;
  try {
    body = payload === undefined ? undefined : JSON.stringify(payload);
  } catch (err) {
    // Said by its class; its message goes to the error log only (the review's S5).
    keepInLog("shell could not serialise a payload", `${err.name}: ${err.message}`);
    return Promise.resolve(shellFailure(fill(shellSays.could_not_send, { kind: err.name || "Error" }), "refused"));
  }
  if (!FROZEN_API && !fs.existsSync(SOURCE_PYTHON)) {
    return Promise.resolve(shellFailure(process.platform === "darwin" ? NOT_SET_UP_MAC : NOT_SET_UP, "refused"));
  }
  return new Promise((resolve) => {
    const isPass = passCommand !== null && args[0] === passCommand;
    const alone = isPass || fresh || args[0] === LAUNCH_COMMAND || ownProcessCommands.has(args[0]);
    const handed = alone ? null : takeEngine(args, body);
    const carrier = handed ? handed.mine : null;
    const proc = carrier ? carrier.proc : startTracker(args);
    const startedAt = Date.now();
    if (isPass && proc.pid) passes.set(proc.pid, proc);
    let running = false;      // a pass that said it started: the click has its answer
    let killedReply = null;   // what a pass killed after it started ends with
    let limitMs = TRACKER_TIMEOUT_MS;
    let reply;                // the last line that was not a progress line
    let last = null;          // the last progress line's fields
    let ownStderr = "";       // a process of its own's; the engine's is kept on the engine
    let settled = false;
    let timer = null;
    const stderrOf = () => (carrier ? carrier.stderr : ownStderr);
    const settle = (value) => {
      if (settled) return;
      settled = true;
      if (!running) clearTimeout(timer);
      if (value && !value.error) learn(value);
      resolve(value);
    };
    const kill = () => {
      // The only way to stop a stuck command in the engine is to end the
      // engine: it is killed and a new one started (SPEC-ui-menu-speed 3.4).
      if (carrier) {
        carrier.current = null;   // answered below, not by lost()
        endEngine(carrier, { label: "killed at the time limit", planned: false });
      } else proc.kill();
      const minutes = Math.max(1, Math.round(limitMs / 60000));
      const where = last && last.name ? ` ${fill(shellSays.killed_at, last)}` : "";
      // A sort says a sort stopped; a change says it may be partly done; any
      // other command only that it stopped (final review A, finding 5).
      const said = isPass ? fill(shellSays.killed, { minutes })
        : writingCommands.has(args[0]) ? `${fill(shellSays.killed_write, { minutes })} ${shellSays.killed_write_note}`
        : fill(shellSays.killed_read, { minutes });
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
    // The command's ending, for a process that closed and for an engine that
    // said its end line alike. Nothing of stderr goes on screen: a failed
    // command's goes to the log beside the tracker's database, for a
    // developer at this machine (decision 193, security principle 7). With
    // none named - no data folder yet - the stderr goes to the fallback log
    // and the reply says just no_log (Jason, 2026-09-29), never a log beside
    // the program (decision 186's rebase review, MF2).
    const finish = (code) => {
      clearTimeout(timer);
      const out = killedReply || reply || shellFailure(fill(shellSays.no_reply, { code }), "failed", { progress: last });
      const failed = !reply || reply.error;
      if (failed) keepInLog("shell stderr of a failed command", stderrOf());
      const ending = failed && stderrOf() && !errorLog ? withNoLog(out) : out;
      if (!running) settle(ending);
      else if (onEnded) onEnded({ reply: ending, code });
    };
    if (carrier) {
      // Handed to the engine: the request line, then the payload's bytes, and
      // no end of input (tracker.resident). The engine's reader calls take()
      // for each line and finish() at this command's end line; if the engine
      // ends while it holds the command, lost() answers it.
      carrier.stderr = "";
      carrier.current = {
        id: handed.id,
        take,
        end: finish,
        lost: (code, startError) => {
          if (settled) return;
          clearTimeout(timer);
          const heard = stderrOf();
          if (heard) keepInLog("shell stderr of an engine that closed without a reply", heard);
          // A read is asked once more, of a process of its own; a write never
          // is, since it cannot be known that it did nothing (P220, P276).
          if (HELD_READING_COMMANDS.has(args[0]) && !writingCommands.has(args[0])) {
            settled = true;
            resolve(spawnTracker(args, payload, onProgress, onEnded, { fresh: true }));
            return;
          }
          const said = startError ? fill(shellSays.could_not_start, { code: startError })
            : fill(shellSays.no_reply, { code });
          const out = shellFailure(said, "failed", { progress: last });
          settle(!errorLog && heard ? withNoLog(out) : out);
        },
      };
      carrier.proc.stdin.write(handed.head, "utf8");
      if (handed.bytes > 0) carrier.proc.stdin.write(body, "utf8");
      return;
    }
    // Read once (P220, findings-3 #3), by the one line reader the engine uses.
    const reader = lineReader(take);
    proc.stdout.setEncoding("utf8");
    proc.stdout.on("data", reader);
    proc.stderr.on("data", (d) => {
      if (ownStderr.length < STDERR_CAP) ownStderr += d;
    });
    proc.stdin.on("error", () => {});   // a process that died before reading stdin is reported by "close"
    // Said by its code, never its message, which names the executable's path.
    proc.on("error", (err) =>
      settle(shellFailure(fill(shellSays.could_not_start, { code: (err && err.code) || "?" }), "failed"))
    );
    proc.on("close", (code) => {
      reader.flush();
      passes.delete(proc.pid);
      finish(code);
    });
    if (body !== undefined) proc.stdin.write(body, "utf8");
    proc.stdin.end();
  });
}

// Joins the pieces of a line once, when it ends - never the whole of what came
// so far, again for every piece (which cost 176 ms of the window's process for
// a 3.9 MB Overview, P220 findings-3 #3). Each piece is searched for a newline
// on its own. `flush` hands over what is left when the stream closes.
function lineReader(onLine) {
  let pieces = [];
  const feed = (d) => {
    let from = 0;
    let at;
    while ((at = d.indexOf("\n", from)) >= 0) {
      pieces.push(d.slice(from, at));
      onLine(pieces.join(""));
      pieces = [];
      from = at + 1;
    }
    if (from < d.length) pieces.push(from ? d.slice(from) : d);
  };
  feed.flush = () => {
    const rest = pieces.join("");
    pieces = [];
    onLine(rest);
  };
  return feed;
}

// One tracker process, started as every command's is: the packaged API, or
// the checkout's private Python from the checkout, with the settings folder
// and the product's name in its environment, its window hidden. `module` is
// what the checkout runs with -m: the API, or the engine's.
function startTracker(args, module = "tracker.api") {
  const env = { ...process.env, TRACKER_SETTINGS_DIR: SETTINGS_DIR, TRACKER_PRODUCT_NAME: PRODUCT_NAME };
  return FROZEN_API
    ? spawn(FROZEN_API, args, { windowsHide: true, env })
    : spawn(SOURCE_PYTHON, ["-m", module, ...args], {
        cwd: REPO_ROOT,
        windowsHide: true,
        env,
      });
}

// ── the engine (P276, Jason 2026-10-11, Q12 b; replaces P220's spare) ──
// Starting Python and importing the tracker is most of what a small command
// costs (state about 296 ms fresh and about 7 ms from the engine on the
// development Mac; about 0.85 s a command on the office PC). So one tracker
// process is started when the app opens, with tracker.resident's --resident,
// and answers each command handed to it while it is free: a request line
// {id, argv, bytes}, then the payload's bytes, and no end of input; its reply
// is whatever the API prints, then a line of its own {engine_end, code,
// retiring}. A command that comes while it is busy, every pass, the launch
// door and the commands the API names (vocab.own_process_commands) start a
// process of their own, as before: no queue, so a slow command never holds
// another behind it.
//
// Decision 171's lock rule, one store per command, P118's holds and the kill
// per command are kept by the engine itself (tracker.resident), which ends
// itself after any command that left the process unlike it found it; this
// file keeps the kill (the engine is killed and a new one started), the
// restart budget and the program stamp. What the tracker fixes at import is
// the program's own place and the product's name (the environment it is
// started with, the same a fresh process gets), so an engine from before the
// program changed - an upgrade, a pull from source - is told to finish and a
// new one started, and that one command runs in a process of its own.
const RESIDENT_FLAG = "--resident";   // tracker.resident.RESIDENT_FLAG
const ENGINE_END_KEY = "engine_end";  // tracker.resident.END_KEY
// An end line starts with its key, so a reply (which never does) costs no parse.
const ENGINE_END_PREFIX = `{"${ENGINE_END_KEY}"`;
const ENGINE_LINE_MAX = 64 * 1024;    // tracker.resident.LINE_MAX
const ENGINE_PAYLOAD_MAX = 32 * 1024 * 1024;   // tracker.resident.PAYLOAD_MAX
// A spawn error with one of these codes means the program is missing or not
// runnable: the engine is off for the session at once.
const ENGINE_PROGRAM_ERRORS = new Set(["ENOENT", "EACCES"]);
// A third unplanned end within five minutes leaves the engine off for the
// session: every command then runs in a process of its own, and the error
// log says so (Jason's question D: no notice).
const ENGINE_RESTARTS = 3;
const ENGINE_RESTART_WINDOW_MS = 5 * 60 * 1000;
let engine = null;      // {proc, stamp, current, nextId, stderr, retiring, replaced, done}
let engineOff = false;  // for the rest of the session
let engineStops = [];   // [{at, code}] of the unplanned ends inside the window
let quitting = false;   // will-quit has begun: no new engine
let ownProcessCommands = new Set();   // vocab.own_process_commands, once seen

// The program as it is now: the packaged API's size and time, or from source
// the newest time of the tracker's modules. null when it cannot be read, and
// then no engine is used.
function programStamp() {
  try {
    if (FROZEN_API) {
      const info = fs.statSync(FROZEN_API);
      return `${info.size}:${info.mtimeMs}`;
    }
    const folder = path.join(REPO_ROOT, "tracker");
    let newest = 0;
    for (const name of fs.readdirSync(folder)) {
      if (name.endsWith(".py")) newest = Math.max(newest, fs.statSync(path.join(folder, name)).mtimeMs);
    }
    return `source:${newest}`;
  } catch {
    return null;
  }
}

// Start the engine, when none is running and none is ruled out.
function startEngine() {
  if (engine || engineOff || quitting) return;
  if (!FROZEN_API && !fs.existsSync(SOURCE_PYTHON)) return;
  const stamp = programStamp();
  if (stamp === null) return;
  let proc;
  try {
    proc = startTracker([RESIDENT_FLAG], "tracker.resident");
  } catch (err) {
    // Node throws at the call only for what time does not mend (EINVAL, EPERM,
    // ENOMEM, a bad argument); ENOENT, EACCES, EAGAIN and EMFILE arrive later,
    // as the 'error' event below. So a throw here is no engine for the
    // session, and the error log says its code once.
    engineCannotStart(err);
    return;
  }
  const mine = { proc, stamp, current: null, nextId: 1, stderr: "", retiring: false, replaced: false, done: false };
  const reader = lineReader((line) => engineLine(mine, line));
  proc.stdout.setEncoding("utf8");
  proc.stdout.on("data", reader);
  proc.stderr.on("data", (d) => {
    if (mine.stderr.length < STDERR_CAP) mine.stderr += d;
  });
  if (proc.stdin) proc.stdin.on("error", () => {});
  // A process that cannot be spawned is no engine, and commands start their own
  // processes meanwhile. If the program is missing or not runnable (ENOENT,
  // EACCES) no later start would do better: the engine is off for the session
  // and the error log says the code once. Any other error (EAGAIN, EMFILE) may
  // be passing: it is one unplanned end in the restart budget, and a new engine
  // is tried.
  proc.on("error", (err) => {
    const code = (err && err.code) || "?";
    if (ENGINE_PROGRAM_ERRORS.has(code)) {
      engineCannotStart(err);
      endEngine(mine, { label: "could not start", planned: true, startError: code });
    } else {
      endEngine(mine, { label: `could not start (${code})`, planned: false, startError: code });
    }
  });
  proc.on("close", (code, signal) => {
    reader.flush();
    endEngine(mine, { label: "closed on its own", planned: false, code, signal });
  });
  engine = mine;
}

function engineCannotStart(err) {
  if (engineOff) return;
  engineOff = true;
  keepInLog("shell: the engine could not start", `${(err && err.code) || "?"}; every command now starts its own process`);
}

// One line of the engine's output: its end line settles the command it holds,
// any other line is that command's (a progress line or the reply candidate).
function engineLine(mine, line) {
  if (!line) return;
  // Only the head of the line is looked at: a reply can be megabytes long.
  if (line.slice(0, ENGINE_END_PREFIX.length) !== ENGINE_END_PREFIX) {
    if (mine.current) mine.current.take(line);
    return;
  }
  let said = null;
  try {
    said = JSON.parse(line);
  } catch {
    said = null;
  }
  const current = mine.current;
  // An end line for another command, or for none, is a broken stream: the
  // engine can no longer be trusted, so it is ended and the command is
  // answered as if it had died.
  if (!said || !current || said[ENGINE_END_KEY] !== current.id) {
    mine.proc.kill();
    endEngine(mine, { label: "broken stream", planned: false, code: null });
    return;
  }
  mine.current = null;
  if (said.retiring === true) {
    // It ends itself after this line; the next command goes to a new engine.
    mine.retiring = true;
    if (engine === mine) engine = null;
    startEngine();
  }
  current.end(Number.isInteger(said.code) ? said.code : null);
}

// The engine is over - killed, retired, closed, replaced or never started -
// once. A command it still held is answered by that command's own `lost`; an
// unplanned end counts against the budget; a new engine starts unless the
// engine is off for the session or the app is quitting.
function endEngine(mine, how) {
  if (mine.done) return;
  mine.done = true;
  if (engine === mine) engine = null;
  const lost = mine.current;
  mine.current = null;
  if (how.label === "killed at the time limit") mine.proc.kill();
  const planned = mine.retiring || mine.replaced || quitting || how.planned === true;
  if (!quitting) {
    const why = mine.retiring ? "retired" : mine.replaced ? "replaced: the program changed" : how.label;
    keepInLog("shell: the engine ended", `${why}; exit code ${how.code === undefined || how.code === null ? "none" : how.code}${how.signal ? `; signal ${how.signal}` : ""}`);
  }
  if (lost) lost.lost(how.code === undefined ? null : how.code, how.startError);
  if (!planned) {
    countUnplannedStop(how.startError || (how.code === undefined || how.code === null ? how.signal || "none" : how.code));
  }
  startEngine();
}

function countUnplannedStop(code) {
  const now = Date.now();
  engineStops = engineStops.filter((one) => now - one.at < ENGINE_RESTART_WINDOW_MS);
  engineStops.push({ at: now, code });
  if (engineStops.length < ENGINE_RESTARTS || engineOff) return;
  engineOff = true;
  keepInLog("shell: the engine is off for this session",
    `engine stopped ${ENGINE_RESTARTS} times in ${ENGINE_RESTART_WINDOW_MS / 60000} minutes; ` +
    `every command now starts its own process (exit codes: ${engineStops.map((one) => one.code).join(", ")})`);
}

// The engine, taken for a command that may go to it: one that is free, from
// this program, and whose request fits the framing; otherwise null and the
// command starts a process of its own. An engine still starting counts as
// free: its frame waits in the pipe, which costs that click no more than a
// fresh process would. An engine from before the program changed is told to
// finish (its input ended: it is idle and exits at the end of input) and
// replaced, and this one command runs alone.
function takeEngine(args, body) {
  const mine = engine;
  if (!mine || engineOff || quitting || mine.current || mine.retiring || mine.done) return null;
  if (mine.proc.exitCode !== null && mine.proc.exitCode !== undefined) return null;
  if (mine.stamp !== programStamp()) {
    mine.replaced = true;
    engine = null;
    try {
      mine.proc.stdin.end();
    } catch {
      // already closed
    }
    startEngine();
    return null;
  }
  const bytes = body === undefined ? 0 : Buffer.byteLength(body, "utf8");
  const head = `${JSON.stringify({ id: mine.nextId, argv: args, bytes })}\n`;
  if (Buffer.byteLength(head, "utf8") > ENGINE_LINE_MAX || bytes > ENGINE_PAYLOAD_MAX) return null;
  const id = mine.nextId;
  mine.nextId += 1;
  return { mine, id, head, bytes };
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
    return "That path is not one the app reported; nothing was opened.";
  }
  const failed = await openChecked(p, openable.get(p), reveal === "reveal");
  // R8 (P240): the file has opened, normally, and a Mac has no Protected View
  // to open it in. The reply is then not "" but the sentence, for the page to
  // say in the notice where Open's own result appears (renderer/shell.js):
  // each time, nothing waits on it, nothing is refused. Only the path the API
  // listed in state.carries_code, only opened and never revealed.
  if (!failed && reveal !== "reveal" && process.platform === "darwin" && carriesCode.has(p)) {
    return { says: shellSays.protected_view_mac };
  }
  return failed;
}

// The check itself, shared with Open error log's fallback, which is the
// shell's own file and so not among the paths the API reported.
async function openChecked(p, kind, reveal) {
  let info;
  try {
    info = await fs.promises.lstat(p);
  } catch {
    return shellSays.not_opened;
  }
  const same = kind === "folder" ? info.isDirectory()
    : kind === "file" || kind === "reveal" ? info.isFile() : false;
  if (info.isSymbolicLink() || !same) return shellSays.not_opened;
  // A reveal-only kind (a filed, moved or set-aside working copy) is shown,
  // never opened: only a marked review copy opens in the default program
  // (decision 190). A plain open of one is refused, as any other unreported path.
  if (kind === "reveal" && !reveal) return shellSays.not_opened;
  if (reveal && (kind === "file" || kind === "reveal")) {
    shell.showItemInFolder(p);
    return "";
  }
  return shell.openPath(p);
}

// Only the app's own window may ask the shell anything (SPEC-architecture
// R5.4), as the menu channel has always required: a message from anything
// else - another frame, a page the window was led to - is refused the way
// each channel refuses, and the error log keeps its channel alone, never
// what it carried.
function fromMainWindow(event) {
  return Boolean(mainWindow) && Boolean(event) && event.sender === mainWindow.webContents;
}
const NOT_FROM_THE_WINDOW = "That message is not from the app's window; nothing was done.";
function refusedStranger(channel) {
  keepInLog("shell refused a message not from the app's window", channel);
}

// A pass's progress lines go to the window that asked, on their own channel
// (decision 193), and so does its ending once the click has been answered
// (decision 203): {args, reply, code}. A window gone by then hears nothing.
ipcMain.handle("tracker-cmd", (event, args, payload) => {
  if (!fromMainWindow(event)) {
    refusedStranger("tracker-cmd");
    return shellFailure(NOT_FROM_THE_WINDOW, "refused");
  }
  const send = (message) => {
    if (!event.sender.isDestroyed()) event.sender.send("tracker-progress", { args, ...message });
  };
  return runTracker(args, payload, (progress) => send({ progress }), (ended) => send(ended));
});
ipcMain.handle("open-path", (event, p, how) => {
  if (!fromMainWindow(event)) {
    refusedStranger("open-path");
    return NOT_FROM_THE_WINDOW;
  }
  return openPath(p, how);
});
// An error of the page's own: its text goes to the error log, never on screen.
ipcMain.handle("log-error", (event, text) => {
  if (!fromMainWindow(event)) {
    refusedStranger("log-error");
    return;
  }
  keepInLog("renderer error", typeof text === "string" ? text : "");
});
// A stranger's ask is answered as a cancelled pick: no dialog opens.
ipcMain.handle("pick-folder", async (event, title) => {
  if (!fromMainWindow(event)) {
    refusedStranger("pick-folder");
    return null;
  }
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
  client: "H&ousehold",
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
  clients: "Households",
  find: "Find",
  refresh: "Refresh",
  reset_columns: "Reset Column Widths",
  compact_rows: "&Compact Rows",
  show_under_construction: "Show &Under Construction",
  tools: "&Tools",
  sort_now: "Sort Now",
  stop_sorting: "Stop Sorting",
  schedule: "Schedule…",
  repair_schedule: "Repair Schedule",
  remove_schedule_here: "Remove the Schedule From This Mac…",
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
    ["clients", "CmdOrCtrl+4"], SEPARATOR, ["find", "CmdOrCtrl+F"], ["refresh", "F5"], SEPARATOR, ["reset_columns"], ["compact_rows"],
    ["show_under_construction"]]],
  ["tools", [["sort_now", "F9"], ["stop_sorting"], SEPARATOR, ["schedule"], ["repair_schedule"], ["remove_schedule_here"],
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
// What needs nothing of the page: enabled from the first frame. Removing a
// Mac's schedule needs no clients folder: it is for the app's last act.
const ALWAYS = new Set(["change_root", "exit", "refresh", "tour", "safeguards", "terms", "error_log", "about",
  "compact_rows", "show_under_construction", "remove_schedule_here"]);
// The items a Mac alone has (SPEC-mac R29): dragging an app to the Bin leaves
// its launchd agent behind, so a Mac can take the schedule away first.
const MAC_ONLY = new Set(["remove_schedule_here"]);
const BAR_IDS = new Set(BAR.flatMap(([, items]) => (items || []).filter((i) => i !== SEPARATOR).map((i) => i[0])));
// The bar's checked items: Windows draws the tick. The page owns what each
// one says and sends the ticked ids as `checked` (P197).
const CHECKABLE = new Set(["compact_rows", "show_under_construction"]);
// Ticked before the page speaks: the Under Construction items show on a new install, rows start Comfortable (P197, P271).
const DEFAULT_TICKED = new Set(["show_under_construction"]);
// What the page last said applies (5.3); until it speaks only ALWAYS does.
let menuEnabled = new Set();
// Ticked until the page speaks: DEFAULT_TICKED.
let menuChecked = new Set(DEFAULT_TICKED);
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
    label: shown(menuWords[id]),
    enabled,
    click: () => {
      if (id === "error_log") openErrorLog().catch(() => null);
      else sendMenu({ id, token });
      // Windows flips a check item's tick itself; put it back to what the page
      // last said, so a page whose answer fails never leaves it flipped. The
      // page's own message then ticks it (P197, review NIT 1).
      if (CHECKABLE.has(id) && menuBuilt) buildMenu();
    },
  };
}

// A menu word as the platform shows it. The & of "&Tools" is a Windows
// mnemonic (Alt+T); a Mac has none, and a label that carried one would show
// the ampersand if Electron does not strip it (SPEC-mac R11, kit step H11), so
// it is taken out here, once, for every label and item.
function shown(word) {
  return process.platform === "darwin" ? word.replace(/&(?!&)/g, "") : word;
}

function buildTemplate() {
  const mac = process.platform === "darwin";
  const bar = BAR.map(([key, items]) => {
    // Edit is the platform's own: Undo, Redo, Cut, Copy, Paste and Select all.
    if (!items) return { label: shown(menuWords[key]), role: "editMenu" };
    // Quit lives in the app menu on a Mac (below), so File has no Exit there,
    // and nor the separator that stood before it.
    const entries = (mac ? items.filter((item) => item[0] !== "exit") : items.filter((item) => !MAC_ONLY.has(item[0])));
    if (mac && entries[entries.length - 1] === SEPARATOR) entries.pop();
    return {
      label: shown(menuWords[key]),
      submenu: entries.map((item) => {
        if (item === SEPARATOR) return { type: "separator" };
        const [id, accelerator] = item;
        if (id === "exit") return { label: shown(menuWords.exit), role: "quit" };
        const built = menuItem(id, ALWAYS.has(id) || menuEnabled.has(id), "");
        if (accelerator) built.accelerator = accelerator;
        if (CHECKABLE.has(id)) Object.assign(built, { type: "checkbox", checked: menuChecked.has(id) });
        return built;
      }),
    };
  });
  // On a Mac the first menu is the application's own: About, Hide, Hide
  // Others, Show All and Quit with Cmd+Q, all Electron's roles, named for the
  // product by the system. It adds no reload, zoom or developer-tools item.
  return mac ? [{ role: "appMenu" }, ...bar] : bar;
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
  if (!fromMainWindow(event)) return;
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
  const equal = (a, b) => a.size === b.size && [...a].every((id) => b.has(id));
  const next = new Set(enable);
  // `checked` is optional: a message without it leaves the ticks as they are.
  const ticked = known(message.checked, CHECKABLE);
  const nextChecked = ticked ? new Set(ticked) : menuChecked;
  const same = equal(next, menuEnabled) && equal(nextChecked, menuChecked);
  menuEnabled = next;
  menuChecked = nextChecked;
  if (!same && menuBuilt) buildMenu();
}
ipcMain.on(MENU_CHANNEL, onMenuMessage);

// The window's colour before the page paints (5.6): the page's own
// background for the theme the system is in, read from the one place it is
// defined - pilot-ui.css's --window-light and --window-dark - and left to the
// page when a Windows contrast theme is on (it paints its own). Read
// defensively: a stylesheet without the names (or without the file) gives
// nothing, never a thrown error at start.
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
  return tokenColour(read("pilot-ui.css"), name);
}

function createWindow() {
  // The app's own menu, in both builds (5.1): Electron's default one carries
  // reload, zoom and developer-tools accelerators (the council's E-7), and
  // the last would open the console devTools below keeps closed. This one
  // has none of them.
  buildMenu();
  const win = new BrowserWindow({
    // The sizes below are the page's, not the window's (P203): every list's
    // 1100 px budget (SPEC-firm-columns 14, SPEC-shell's minimum window)
    // assumes the page is 1100 wide, and without this Windows counts its
    // frame in the 1100, leaving the page 1084 and the Overview list a
    // sideways scrollbar. The window is drawn larger than the page by its frame (on the office PC about 16 px wider and 39 px taller).
    useContentSize: true,
    width: 1400,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    title: PRODUCT_NAME,
    // The title bar and taskbar icon of the unpackaged launch (Start App.bat);
    // the packaged .exe carries the same file, written in by electron-packager.
    // macOS ignores a window icon: the bundle's icon is the .icns the packager
    // is given (SPEC-mac R14, R15).
    icon: path.join(__dirname, "assets", "icon.ico"),
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
const floorRefusal = macFloorRefusal();
if (floorRefusal) {
  stopAtTheFloor(floorRefusal);
} else if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  // Before the window opens: Windows groups a running window with its
  // shortcut, and shows the shortcut's icon on the taskbar button, by this
  // id. It is a fixed string, never derived from the name, so a rename does
  // not split a pinned button from its window. A Mac has no such id; its
  // bundle identifier is the same string, given to the packager by
  // build-mac.sh (SPEC-mac R14).
  if (process.platform === "win32") app.setAppUserModelId("com.jparkassociates.taxdocumentconsole");
  app.on("second-instance", () => {
    const [win] = BrowserWindow.getAllWindows();
    if (!win) return;
    if (win.isMinimized()) win.restore();
    win.focus();
  });
  app.whenReady().then(() => {
    // The engine (P276) starts before the window is made, so its start overlaps
    // the window's load; the first list is handed to it while it is still
    // starting, which costs that click no more than a process of its own.
    startEngine();
    const win = createWindow();
    // Not awaited by anything: a step that fails records its own sentence
    // for the notice (tracker.api's launch door), and one that cannot
    // start is tried again at the next launch.
    spawnTracker([LAUNCH_COMMAND], { reason: "launch" })
      .then((result) => {
        if (result && result.ran && !win.isDestroyed()) {
          win.webContents.send(LAUNCH_DONE_CHANNEL, {
            installed: result.installed === true,
            schedule_sentence: typeof result.schedule_sentence === "string" ? result.schedule_sentence : "",
          });
        }
      })
      .catch(() => null);
  });
}
// R6: said once the app is ready (a message box needs it), and nothing else
// runs: no lock, no window, no tracker, nothing written.
function stopAtTheFloor(sentence) {
  app.whenReady().then(() => {
    dialog.showMessageBoxSync({ type: "error", message: sentence, buttons: ["OK"] });
    app.quit();
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
  unwatchLastPass();
  for (const proc of passes.values()) proc.stdout.destroy();
  // The engine's input is ended, never killed: one holding a write finishes it
  // and exits at the end of input, as a fresh write process finishes after the
  // app has gone (P276). If this shell dies, its pipe closes and it exits so.
  quitting = true;
  if (engine) {
    try {
      engine.proc.stdin.end();
    } catch {
      // already closed
    }
  }
});
