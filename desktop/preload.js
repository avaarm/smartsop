// Minimal, namespaced bridge for the first-run connect screen only.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('smartsop', {
  getConfig: () => ipcRenderer.invoke('smartsop:getConfig'),
  setServerUrl: (url) => ipcRenderer.invoke('smartsop:setServerUrl', url),
});
