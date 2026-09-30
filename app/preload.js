const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("tracker", {
  call: (args, payload) => ipcRenderer.invoke("tracker-cmd", args, payload),
  // open(path) opens in the default program; open(path, "reveal") shows the
  // file selected in File Explorer, or, for a reported folder, opens it. The path is
  // one the API reported; anything else is refused by the shell.
  open: (p, how) => ipcRenderer.invoke("open-path", p, how),
  pickFolder: (title) => ipcRenderer.invoke("pick-folder", title),
  logError: (text) => ipcRenderer.invoke("log-error", text),
  onProgress: (cb) => ipcRenderer.on("tracker-progress", (_e, m) => cb(m)),
  // The shell's launch step finished having run (decision 209): the page
  // asks again, so what it left is shown. Nothing is passed across.
  onAfterInstallDone: (listener) => ipcRenderer.on("after-install-done", () => listener()),
  // The one menu channel (SPEC-shell 5.4). Nothing here reaches the tracker.
  menu: {
    // A menu item was chosen: {id, token}. token is the page's own, echoed.
    onCommand: (listener) => ipcRenderer.on("menu", (_e, m) => listener(m)),
    // What applies now: {enable: [ids]}; or pop a right-click menu:
    // {popup, enable: [ids], token, x, y}.
    send: (message) => ipcRenderer.send("menu", message),
  },
});
