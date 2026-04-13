# SmartSOP — Installation Guide

## Desktop App (Recommended)

### Prerequisites

1. **Ollama** — local LLM runtime  
   Download from [ollama.com](https://ollama.com), then pull a model:
   ```bash
   ollama pull llama3
   ```

### Install

| Platform | File | Notes |
|----------|------|-------|
| macOS    | `SmartSOP-1.0.0-arm64.dmg` (Apple Silicon) or `SmartSOP-1.0.0-x64.dmg` (Intel) | Drag to Applications. On first launch, right-click → Open if Gatekeeper blocks it. |
| Windows  | `SmartSOP-Setup-1.0.0.exe` | Run installer. Optionally choose install location. |
| Linux    | `SmartSOP-1.0.0.AppImage` | `chmod +x SmartSOP-*.AppImage && ./SmartSOP-*.AppImage` |

### First Launch

1. Make sure **Ollama is running** (it starts automatically on macOS after install)
2. Open SmartSOP
3. If Ollama is not detected, you'll see a prompt — AI features require Ollama but you can still browse templates without it

---

## Docker (Team / Server Deployment)

Run the full stack with a single command:

```bash
git clone https://github.com/smartsop/smartsop.git
cd smartsop
docker compose up -d
```

Services:
- **Frontend:** http://localhost:4000
- **Backend API:** http://localhost:5001
- **Ollama:** http://localhost:11434

Pull a model inside the Ollama container:
```bash
docker compose exec ollama ollama pull llama3
```

---

## From Source (Development)

### Requirements

- **Node.js** 18+ and npm
- **Python** 3.10+
- **Ollama** with `llama3` model

### Steps

```bash
# 1. Clone
git clone https://github.com/smartsop/smartsop.git
cd smartsop

# 2. Install frontend dependencies
npm install

# 3. Install backend dependencies
pip install -r requirements-gmp.txt

# 4. Start Ollama (if not already running)
ollama serve &
ollama pull llama3

# 5. Start backend
python3 gmp_server.py &
# → http://localhost:5001

# 6. Start frontend (dev server with hot reload)
npm start
# → http://localhost:4200
```

### Run as Desktop App (Development)

```bash
# Build Angular frontend first
npm run build:frontend

# Launch Electron in dev mode
npm run start:desktop
```

---

## Building Distributables

### Prerequisites

- Node.js 18+, npm
- Python 3.10+ with `pip` and `venv`
- Platform-specific:
  - **macOS:** Xcode Command Line Tools
  - **Windows:** Visual Studio Build Tools
  - **Linux:** `dpkg`, `fakeroot` (for .deb)

### Build Commands

```bash
# Install dependencies
npm install

# Build for current platform
npm run build:app

# Build for a specific platform
npm run build:app:mac     # .dmg + .zip
npm run build:app:win     # .exe (NSIS installer)
npm run build:app:linux   # .AppImage + .deb

# Build for all platforms (requires cross-compilation setup)
npm run build:app:all
```

Output goes to `release/`.

### What the Build Does

1. **Angular frontend** → `dist/smartsop/browser/` (production build, tree-shaken, minified)
2. **Python backend** → `dist-backend/` (PyInstaller standalone binary, no Python install needed)
3. **Electron package** → `release/` (platform installer with both frontend + backend bundled)

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API endpoint |
| `PORT` | `5001` | Backend server port |
| `CORS_ORIGINS` | `http://localhost:4200` | Allowed CORS origins (comma-separated) |
| `FLASK_ENV` | `development` | `development` or `production` |
| `DATABASE_URL` | `smartsop.db` | SQLite database path |

### Data Locations

| What | Desktop App | Docker | From Source |
|------|------------|--------|-------------|
| Database | `~/Library/Application Support/SmartSOP/smartsop.db` (macOS) | Docker volume | `./smartsop.db` |
| Generated docs | `./generated_docs/` | Docker volume | `./generated_docs/` |
| Ollama models | `~/.ollama/models/` | Docker volume | `~/.ollama/models/` |

---

## Troubleshooting

### "Ollama is not running"
Make sure Ollama is installed and running:
```bash
ollama serve    # start the server
ollama list     # verify models are available
```

### "Backend did not start within 30s"
Check if port 5001 is already in use:
```bash
lsof -i :5001   # macOS/Linux
netstat -ano | findstr 5001  # Windows
```

### macOS Gatekeeper blocks the app
Right-click the app → Open → Open. This is a one-time step for unsigned apps.

### AI features slow
- Ensure at least 16 GB RAM for best LLM performance
- Close other memory-heavy applications
- Consider using a quantized model: `ollama pull llama3:8b-instruct-q4_0`

---

## Uninstall

### Desktop App
- **macOS:** Drag SmartSOP from Applications to Trash
- **Windows:** Settings → Apps → SmartSOP → Uninstall
- **Linux:** Delete the AppImage file

### Docker
```bash
docker compose down -v   # removes containers and volumes
```

### Data cleanup (optional)
```bash
rm -f smartsop.db
rm -rf generated_docs/
```
