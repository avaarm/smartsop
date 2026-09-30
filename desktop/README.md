# SmartSOP Desktop

A native desktop client for **macOS** and **Windows** (and Linux). It's a secure
Electron shell around a **SmartSOP server**: it opens your server's web app in a
dedicated app window, so multi-user workspaces, review/approval e-signatures and
the shared audit trail all keep working exactly as they do in the browser.

On first launch it asks for your server address and remembers it. There's no
bundled backend and no local database — the desktop app always talks to one
server (your cloud host, or an on-prem box running the Docker stack).

## Run in development

You need a SmartSOP server reachable first (the dev servers, or Docker):

```bash
# from the repo root — start the app (frontend :4200 proxies /api to :5001)
npm start                # Angular SSR dev server
# and the backend on :5001 (see the root README)
```

Then, in this folder:

```bash
npm install
npm start                # opens the desktop window; enter http://localhost:4200
```

## Build installers

Each OS is built on its own machine — a Windows `.exe` cannot be cross-built
reliably from macOS. Locally you can build for the machine you're on:

```bash
npm run dist:mac         # → dist/SmartSOP-<version>.dmg  (+ .zip)
npm run dist:win         # → dist/SmartSOP Setup <version>.exe   (run on Windows)
npm run dist:dir         # unpacked app, for a quick local check
```

For real releases, push a version tag and let CI build both:

```bash
git tag v1.0.0 && git push origin v1.0.0
```

`.github/workflows/desktop-release.yml` builds the macOS and Windows installers
on their own runners and attaches them to the GitHub Release.

### Code signing (recommended for distribution)

Unsigned apps trigger Gatekeeper (macOS) / SmartScreen (Windows) warnings. To
sign & notarize, set these repository secrets — the workflow picks them up:

- macOS: `MAC_CSC_LINK` (base64 of your `.p12`), `MAC_CSC_KEY_PASSWORD`
- Windows: add your cert via electron-builder's `CSC_LINK`/`CSC_KEY_PASSWORD`

## Configuration

- The server address is stored in `config.json` in the OS user-data dir
  (`~/Library/Application Support/SmartSOP` on macOS,
  `%APPDATA%/SmartSOP` on Windows).
- Change it any time via **File → Connect to server…**.
- Override at launch with `SMARTSOP_SERVER_URL=https://… npm start`.
