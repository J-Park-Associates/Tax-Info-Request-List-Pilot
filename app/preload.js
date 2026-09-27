const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("tracker", {
  call: (args, payload) => ipcRenderer.invoke("tracker-cmd", args, payload),
  open: (p) => ipcRenderer.invoke("open-path", p),
  pickFolder: (title) => ipcRenderer.invoke("pick-folder", title),
  logError: (text) => ipcRenderer.invoke("log-error", text),
  onProgress: (cb) => ipcRenderer.on("tracker-progress", (_e, m) => cb(m)),
  // The shell's launch step finished having run (decision 209): the page
  // asks again, so what it left is shown. Nothing is passed across.
  onAfterInstallDone: (listener) => ipcRenderer.on("after-install-done", () => listener()),
});
