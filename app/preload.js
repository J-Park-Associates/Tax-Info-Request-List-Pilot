const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("tracker", {
  call: (args, payload) => ipcRenderer.invoke("tracker-cmd", args, payload),
  open: (p) => ipcRenderer.invoke("open-path", p),
  pickFolder: () => ipcRenderer.invoke("pick-folder"),
});
