#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# SmartSOP — Full Desktop App Build Pipeline
#
# Builds the Angular frontend, Python backend, and packages
# everything into platform-specific installers via Electron.
#
# Usage:
#   ./scripts/build-app.sh              # build for current platform
#   ./scripts/build-app.sh --mac        # macOS .dmg + .zip
#   ./scripts/build-app.sh --win        # Windows .exe installer
#   ./scripts/build-app.sh --linux      # Linux .AppImage + .deb
#   ./scripts/build-app.sh --all        # all platforms
# ──────────────────────────────────────────────────────────

set -euo pipefail
cd "$(dirname "$0")/.."

PLATFORM="${1:---current}"

echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║     SmartSOP Desktop App Builder      ║"
echo "  ╚═══════════════════════════════════════╝"
echo ""

# ── Step 1: Angular frontend ──
echo "━━━ Step 1/4: Building Angular frontend ━━━"
if command -v npx &>/dev/null; then
  npx ng build --configuration production
else
  ./node_modules/.bin/ng build --configuration production
fi
echo "  Frontend built → dist/smartsop/browser/"
echo ""

# ── Step 2: Python backend ──
echo "━━━ Step 2/4: Building Python backend ━━━"
bash scripts/build-backend.sh
echo ""

# ── Step 3: Prepare Electron resources ──
echo "━━━ Step 3/4: Preparing Electron resources ━━━"

# Create build-resources dir for icons if missing
mkdir -p electron/build-resources

# Generate placeholder icons if none exist
if [ ! -f electron/build-resources/icon.png ]; then
  echo "  (Using placeholder icon — replace with your brand icon)"
  # Create a minimal 256x256 PNG placeholder via Python
  python3 -c "
import struct, zlib
def create_png(w, h, r, g, b):
    def chunk(ctype, data):
        c = ctype + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    raw = b''
    for y in range(h):
        raw += b'\x00'
        for x in range(w):
            raw += bytes([r, g, b, 255])
    return (b'\x89PNG\r\n\x1a\n' +
            chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(raw)) +
            chunk(b'IEND', b''))
with open('electron/build-resources/icon.png', 'wb') as f:
    f.write(create_png(256, 256, 34, 197, 94))
" 2>/dev/null || echo "  Could not generate placeholder icon (non-critical)"
fi

# Create macOS entitlements if missing
if [ ! -f electron/build-resources/entitlements.mac.plist ]; then
  cat > electron/build-resources/entitlements.mac.plist << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.cs.allow-jit</key>
    <true/>
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <true/>
    <key>com.apple.security.cs.allow-dyld-environment-variables</key>
    <true/>
    <key>com.apple.security.network.client</key>
    <true/>
    <key>com.apple.security.network.server</key>
    <true/>
    <key>com.apple.security.files.user-selected.read-write</key>
    <true/>
</dict>
</plist>
PLIST
fi
echo "  Electron resources ready"
echo ""

# ── Step 4: Package with electron-builder ──
echo "━━━ Step 4/4: Packaging Electron app ━━━"

BUILD_CMD="npx electron-builder"

case "$PLATFORM" in
  --mac)     $BUILD_CMD --mac ;;
  --win)     $BUILD_CMD --win ;;
  --linux)   $BUILD_CMD --linux ;;
  --all)     $BUILD_CMD --mac --win --linux ;;
  --current) $BUILD_CMD ;;
  *)
    echo "Unknown platform flag: $PLATFORM"
    echo "Usage: build-app.sh [--mac|--win|--linux|--all]"
    exit 1
    ;;
esac

echo ""
echo "  ✓ Build complete!"
echo "  Installers written to: release/"
echo ""
ls -lh release/ 2>/dev/null || true
