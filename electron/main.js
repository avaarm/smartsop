/**
 * SmartSOP Desktop — Electron Main Process
 *
 * Lifecycle:
 *   1. Spawn bundled Flask backend (PyInstaller binary or system python)
 *   2. Wait for /health 200
 *   3. Open BrowserWindow → http://localhost:<port>
 *   4. On quit → kill backend
 */

const { app, BrowserWindow, dialog, shell, Menu } = require('electron');
const { spawn, execSync } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');
const net = require('net');

// ── Constants ──────────────────────────────────────────────────────
const APP_NAME = 'SmartSOP';
const BACKEND_DEFAULT_PORT = 5001;
const OLLAMA_DEFAULT_PORT = 11434;
const HEALTH_POLL_MS = 500;
const HEALTH_TIMEOUT_MS = 30_000;

let mainWindow = null;
let backendProcess = null;
let backendPort = BACKEND_DEFAULT_PORT;

// ── Helpers ────────────────────────────────────────────────────────

/** Find a free TCP port starting from `preferred`. */
function findFreePort(preferred) {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.listen(preferred, '127.0.0.1', () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
    srv.on('error', () => {
      // preferred is taken — ask OS for any free port
      const srv2 = net.createServer();
      srv2.listen(0, '127.0.0.1', () => {
        const { port } = srv2.address();
        srv2.close(() => resolve(port));
      });
      srv2.on('error', reject);
    });
  });
}

/** Poll GET /health until 200 or timeout. */
function waitForBackend(port, timeoutMs = HEALTH_TIMEOUT_MS) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const poll = () => {
      if (Date.now() - start > timeoutMs) {
        return reject(new Error(`Backend did not start within ${timeoutMs / 1000}s`));
      }
      const req = http.get(`http://127.0.0.1:${port}/health`, (res) => {
        if (res.statusCode === 200) return resolve();
        setTimeout(poll, HEALTH_POLL_MS);
      });
      req.on('error', () => setTimeout(poll, HEALTH_POLL_MS));
      req.setTimeout(2000, () => { req.destroy(); setTimeout(poll, HEALTH_POLL_MS); });
    };
    poll();
  });
}

/** Resolve the path to the backend executable. */
function resolveBackendBinary() {
  const isProd = app.isPackaged;

  if (isProd) {
    // In packaged app, PyInstaller binary sits next to the app
    const exeName = process.platform === 'win32' ? 'smartsop-backend.exe' : 'smartsop-backend';
    const candidates = [
      path.join(process.resourcesPath, 'backend', exeName),
      path.join(path.dirname(app.getPath('exe')), exeName),
    ];
    for (const c of candidates) {
      if (fs.existsSync(c)) return { binary: c, args: [], cwd: path.dirname(c) };
    }
    return null;
  }

  // Development: run with system python
  const projectRoot = path.resolve(__dirname, '..');
  const pythonCandidates = ['python3', 'python'];
  for (const py of pythonCandidates) {
    try {
      execSync(`${py} --version`, { stdio: 'ignore' });
      return { binary: py, args: [path.join(projectRoot, 'gmp_server.py')], cwd: projectRoot };
    } catch { /* try next */ }
  }
  return null;
}

/** Check if Ollama is reachable. */
function checkOllama() {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${OLLAMA_DEFAULT_PORT}/api/tags`, (res) => {
      resolve(res.statusCode === 200);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(3000, () => { req.destroy(); resolve(false); });
  });
}

/** Check if a backend is already running on a given port. */
function checkExistingBackend(port) {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${port}/health`, (res) => {
      resolve(res.statusCode === 200);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(2000, () => { req.destroy(); resolve(false); });
  });
}

// ── Backend Process ────────────────────────────────────────────────

async function startBackend() {
  // In development, check if backend is already running (e.g. started manually)
  const alreadyRunning = await checkExistingBackend(BACKEND_DEFAULT_PORT);
  if (alreadyRunning) {
    backendPort = BACKEND_DEFAULT_PORT;
    console.log(`[SmartSOP] Found existing backend on port ${backendPort} — reusing it`);
    return;
  }

  const resolved = resolveBackendBinary();
  if (!resolved) {
    dialog.showErrorBox(
      `${APP_NAME} — Python Not Found`,
      'Could not locate Python 3 or the bundled backend.\n\n' +
      'Please install Python 3.10+ from https://python.org and try again.'
    );
    app.quit();
    return;
  }

  backendPort = await findFreePort(BACKEND_DEFAULT_PORT);

  const env = {
    ...process.env,
    FLASK_ENV: 'production',
    PORT: String(backendPort),
    CORS_ORIGINS: `http://127.0.0.1:${backendPort},http://localhost:${backendPort}`,
    SMARTSOP_SERVE_STATIC: '1',           // tell Flask to serve Angular files
    SMARTSOP_STATIC_DIR: getStaticDir(),
  };

  const { binary, args, cwd } = resolved;
  console.log(`[SmartSOP] Starting backend: ${binary} ${args.join(' ')} (port ${backendPort})`);

  backendProcess = spawn(binary, args, {
    cwd,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  });

  backendProcess.stdout.on('data', (d) => console.log(`[backend] ${d.toString().trim()}`));
  backendProcess.stderr.on('data', (d) => console.error(`[backend] ${d.toString().trim()}`));
  backendProcess.on('exit', (code) => {
    console.log(`[SmartSOP] Backend exited with code ${code}`);
    backendProcess = null;
  });

  await waitForBackend(backendPort);
  console.log(`[SmartSOP] Backend ready on port ${backendPort}`);
}

function stopBackend() {
  if (backendProcess) {
    console.log('[SmartSOP] Stopping backend...');
    backendProcess.kill('SIGTERM');
    // Force kill after 5 seconds
    setTimeout(() => {
      if (backendProcess && !backendProcess.killed) {
        backendProcess.kill('SIGKILL');
      }
    }, 5000);
    backendProcess = null;
  } else {
    console.log('[SmartSOP] Backend was external — leaving it running');
  }
}

/** Where Angular's production build lives. */
function getStaticDir() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'frontend');
  }
  return path.join(__dirname, '..', 'dist', 'smartsop', 'browser');
}

// ── Window ─────────────────────────────────────────────────────────

/** In dev mode when reusing an external backend, spin up a tiny
 *  Express server to serve Angular static files + proxy /api. */
let devServer = null;
async function startDevFrontendServer() {
  const express = require('express');
  const { createProxyMiddleware } = require('http-proxy-middleware');
  const devApp = express();

  const staticDir = getStaticDir();
  // Proxy /api and /health to Flask backend (must be before static middleware).
  // Use pathFilter instead of app.use('/api') to preserve the full path.
  devApp.use(createProxyMiddleware({ target: `http://127.0.0.1:${backendPort}`, changeOrigin: true, pathFilter: ['/api', '/health'] }));
  // Serve Angular static files
  devApp.use(express.static(staticDir));
  // SPA fallback
  devApp.get('*', (req, res) => res.sendFile(path.join(staticDir, 'index.html')));

  const devPort = await findFreePort(4201);
  return new Promise((resolve) => {
    devServer = devApp.listen(devPort, '127.0.0.1', () => {
      console.log(`[SmartSOP] Dev frontend server on port ${devPort}`);
      resolve(devPort);
    });
  });
}

function createWindow(loadPort) {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: APP_NAME,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    backgroundColor: '#0f0f0f',
    show: false,
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
  });

  mainWindow.loadURL(`http://127.0.0.1:${loadPort}`);

  mainWindow.once('ready-to-show', () => mainWindow.show());
  mainWindow.on('closed', () => { mainWindow = null; });

  // Open external links in system browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

function buildMenu() {
  const isMac = process.platform === 'darwin';
  const template = [
    ...(isMac ? [{ role: 'appMenu' }] : []),
    { role: 'fileMenu' },
    { role: 'editMenu' },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
      ],
    },
    { role: 'windowMenu' },
    {
      label: 'Help',
      submenu: [
        {
          label: 'Documentation',
          click: () => shell.openExternal('https://smartsop.io/docs'),
        },
        {
          label: 'Report Issue',
          click: () => shell.openExternal('https://github.com/smartsop/smartsop/issues'),
        },
        { type: 'separator' },
        {
          label: 'About SmartSOP',
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: 'About SmartSOP',
              message: `SmartSOP v${app.getVersion()}`,
              detail: 'AI-powered GMP documentation platform for pharma & biotech.\n\n' +
                      'Powered by Ollama + Llama 3\n' +
                      'All data stays on your machine.',
            });
          },
        },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// ── App Lifecycle ──────────────────────────────────────────────────

app.whenReady().then(async () => {
  buildMenu();

  // Check Ollama first
  const ollamaOk = await checkOllama();
  if (!ollamaOk) {
    const { response } = await dialog.showMessageBox({
      type: 'warning',
      title: `${APP_NAME} — Ollama Required`,
      message: 'Ollama is not running.',
      detail:
        'SmartSOP uses Ollama to run AI models locally for document generation.\n\n' +
        '1. Install Ollama from https://ollama.com\n' +
        '2. Run: ollama pull llama3\n' +
        '3. Make sure Ollama is running, then restart SmartSOP.\n\n' +
        'You can still browse templates without Ollama, but AI features will be unavailable.',
      buttons: ['Continue Anyway', 'Quit & Install Ollama'],
      defaultId: 0,
    });
    if (response === 1) {
      shell.openExternal('https://ollama.com');
      app.quit();
      return;
    }
  }

  try {
    await startBackend();
  } catch (err) {
    dialog.showErrorBox(`${APP_NAME} — Backend Error`, err.message);
    app.quit();
    return;
  }

  // Decide which port to load the window from:
  // - If we spawned backend ourselves (with SERVE_STATIC), load from backendPort
  // - If reusing external backend, spin up a dev frontend server
  let loadPort = backendPort;
  const staticDir = getStaticDir();
  if (!backendProcess && fs.existsSync(path.join(staticDir, 'index.html'))) {
    try {
      loadPort = await startDevFrontendServer();
    } catch (err) {
      console.log(`[SmartSOP] Dev frontend server failed, falling back to backend port: ${err.message}`);
      loadPort = backendPort;
    }
  }

  createWindow(loadPort);

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow(loadPort);
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    stopBackend();
    if (devServer) devServer.close();
    app.quit();
  }
});

app.on('before-quit', stopBackend);
