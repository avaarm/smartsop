/**
 * SmartSOP — Electron Preload Script
 *
 * Exposes a minimal API to the renderer so the Angular app can
 * detect it's running inside the desktop shell.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('smartsop', {
  isDesktop: true,
  platform: process.platform,
  version: process.env.npm_package_version || '1.0.0',
});
