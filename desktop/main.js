// SmartSOP desktop client (Electron).
//
// This is a thin, secure desktop shell around a SmartSOP *server*: it loads the
// server's web app in a dedicated window (the server's SSR frontend proxies /api
// to the backend, so everything is one origin — no CORS, no bundled backend).
// First run asks which server to connect to; the choice is remembered.

const { app, BrowserWindow, Menu, shell, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');

const SMOKE = process.env.SMOKE === '1';           // CI/dev: load, confirm, quit
const isMac = process.platform === 'darwin';

// ── tiny JSON config in the OS user-data dir (no extra deps) ────────────────
const configPath = () => path.join(app.getPath('userData'), 'config.json');

function readConfig() {
  try { return JSON.parse(fs.readFileSync(configPath(), 'utf8')); }
  catch { return {}; }
}
function writeConfig(cfg) {
  try {
    fs.mkdirSync(app.getPath('userData'), { recursive: true });
    fs.writeFileSync(configPath(), JSON.stringify(cfg, null, 2));
  } catch (e) { console.error('config write failed', e); }
}

function normalizeUrl(raw) {
  let u = String(raw || '').trim();
  if (!u) return '';
  if (!/^https?:\/\//i.test(u)) u = 'http://' + u;
  return u.replace(/\/+$/, '');
}

let win = null;

function currentServerUrl() {
  return normalizeUrl(process.env.SMARTSOP_SERVER_URL || readConfig().serverUrl || '');
}

function loadTarget() {
  const url = currentServerUrl();
  if (url) win.loadURL(url).catch(err => console.error('loadURL failed', err));
  else win.loadFile(path.join(__dirname, 'connect.html'));
}

function createWindow() {
  const cfg = readConfig();
  const b = cfg.bounds || {};
  win = new BrowserWindow({
    width: b.width || 1280,
    height: b.height || 820,
    x: b.x,
    y: b.y,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: '#0f0f14',
    title: 'SmartSOP',
    autoHideMenuBar: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  loadTarget();

  const saveBounds = () => {
    if (!win || win.isDestroyed()) return;
    const c = readConfig();
    c.bounds = win.getBounds();
    writeConfig(c);
  };
  win.on('close', saveBounds);

  // Links to other origins (docs, external sites, target=_blank) open in the
  // system browser rather than replacing the app window.
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
  win.webContents.on('will-navigate', (event, navUrl) => {
    const base = currentServerUrl();
    if (!base) return;
    try {
      if (new URL(navUrl).origin !== new URL(base).origin) {
        event.preventDefault();
        shell.openExternal(navUrl);
      }
    } catch { /* ignore malformed */ }
  });

  // Surface a clear message if the server can't be reached.
  win.webContents.on('did-fail-load', (_e, code, desc, failedUrl, isMainFrame) => {
    if (SMOKE) { console.error('SMOKE_FAIL', code, desc, failedUrl); app.exit(2); return; }
    if (isMainFrame && code !== -3 /* not a user abort */) {
      dialog.showMessageBox(win, {
        type: 'error',
        title: 'Cannot reach SmartSOP server',
        message: `Could not load ${failedUrl}`,
        detail: `${desc} (code ${code}).\n\nCheck the server address and that the server is running, then reconnect.`,
        buttons: ['Change server…', 'Retry'],
        defaultId: 0,
      }).then(({ response }) => {
        if (response === 0) connectToServer();
        else loadTarget();
      });
    }
  });

  if (SMOKE) {
    win.webContents.on('did-finish-load', () => {
      console.log('SMOKE_OK', win.webContents.getURL());
      setTimeout(() => app.quit(), 400);
    });
  }
}

// Forget the saved server and show the connect screen again.
function connectToServer() {
  const c = readConfig();
  delete c.serverUrl;
  writeConfig(c);
  if (win) win.loadFile(path.join(__dirname, 'connect.html'));
}

function buildMenu() {
  const template = [
    ...(isMac ? [{ role: 'appMenu' }] : []),
    {
      label: 'File',
      submenu: [
        { label: 'Connect to server…', click: connectToServer },
        { type: 'separator' },
        isMac ? { role: 'close' } : { role: 'quit' },
      ],
    },
    { role: 'editMenu' },
    {
      label: 'View',
      submenu: [
        { label: 'Reload', accelerator: 'CmdOrCtrl+R', click: () => win && loadTarget() },
        { role: 'forceReload' },
        { type: 'separator' },
        { role: 'resetZoom' }, { role: 'zoomIn' }, { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
        { role: 'toggleDevTools' },
      ],
    },
    {
      label: 'History',
      submenu: [
        { label: 'Back', accelerator: 'CmdOrCtrl+[', click: () => win && win.webContents.navigationHistory.canGoBack && win.webContents.navigationHistory.goBack() },
        { label: 'Forward', accelerator: 'CmdOrCtrl+]', click: () => win && win.webContents.navigationHistory.canGoForward && win.webContents.navigationHistory.goForward() },
      ],
    },
    { role: 'windowMenu' },
    {
      role: 'help',
      submenu: [
        { label: 'SmartSOP on GitHub', click: () => shell.openExternal('https://github.com/avaarm/smartsop') },
        {
          label: 'About SmartSOP', click: () => dialog.showMessageBox(win, {
            type: 'info', title: 'SmartSOP',
            message: `SmartSOP Desktop ${app.getVersion()}`,
            detail: `Server: ${currentServerUrl() || '(not connected)'}`,
          }),
        },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// ── IPC from the connect screen ─────────────────────────────────────────────
ipcMain.handle('smartsop:getConfig', () => ({ serverUrl: currentServerUrl() }));
ipcMain.handle('smartsop:setServerUrl', (_e, rawUrl) => {
  const url = normalizeUrl(rawUrl);
  if (!url) return '';
  const c = readConfig();
  c.serverUrl = url;
  writeConfig(c);
  if (win) win.loadURL(url).catch(err => console.error('loadURL failed', err));
  return url;
});

app.whenReady().then(() => {
  buildMenu();
  createWindow();

  // Auto-update (packaged builds only; guarded so dev/unsigned never crashes).
  if (app.isPackaged && !SMOKE) {
    try {
      const { autoUpdater } = require('electron-updater');
      autoUpdater.checkForUpdatesAndNotify().catch(() => {});
    } catch (e) { /* updater optional */ }
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (!isMac) app.quit();
});
