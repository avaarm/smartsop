#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# SmartSOP — Build the Python backend with PyInstaller
#
# Produces a standalone binary at dist-backend/smartsop-backend
# that includes Flask, all GMP modules, templates, and deps.
#
# Usage:  ./scripts/build-backend.sh
# ──────────────────────────────────────────────────────────

set -euo pipefail
cd "$(dirname "$0")/.."

VENV_DIR=".venv-build"
DIST_DIR="dist-backend"
ENTRY="gmp_server.py"
BINARY_NAME="smartsop-backend"

echo "==> SmartSOP Backend Builder"
echo ""

# ── Step 1: Virtual environment ──
if [ ! -d "$VENV_DIR" ]; then
  echo "[1/4] Creating build virtual environment..."
  python3 -m venv "$VENV_DIR"
else
  echo "[1/4] Using existing build virtual environment"
fi

source "$VENV_DIR/bin/activate"

# ── Step 2: Install dependencies ──
echo "[2/4] Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements-gmp.txt
pip install --quiet pyinstaller

# ── Step 3: Bundle with PyInstaller ──
echo "[3/4] Running PyInstaller..."
rm -rf build "$DIST_DIR"

pyinstaller \
  --noconfirm \
  --onedir \
  --name "$BINARY_NAME" \
  --distpath "$DIST_DIR" \
  --add-data "ml_model/gmp/templates:ml_model/gmp/templates" \
  --add-data "ml_model/gmp:ml_model/gmp" \
  --hidden-import "flask" \
  --hidden-import "flask_cors" \
  --hidden-import "pydantic" \
  --hidden-import "sqlalchemy" \
  --hidden-import "flask_sqlalchemy" \
  --hidden-import "docx" \
  --hidden-import "lxml" \
  --hidden-import "lxml.etree" \
  --hidden-import "bs4" \
  --hidden-import "openpyxl" \
  --hidden-import "reportlab" \
  --hidden-import "PyPDF2" \
  --hidden-import "pandas" \
  --collect-submodules "ml_model.gmp" \
  "$ENTRY"

# Flatten: electron-builder expects files directly under dist-backend/
if [ -d "$DIST_DIR/$BINARY_NAME" ]; then
  echo "[3/4] Flattening output directory..."
  # PyInstaller --onedir puts everything in dist-backend/smartsop-backend/
  # Move contents up one level
  mv "$DIST_DIR/$BINARY_NAME"/* "$DIST_DIR/"
  rmdir "$DIST_DIR/$BINARY_NAME" 2>/dev/null || true
fi

# ── Step 4: Verify ──
echo "[4/4] Verifying..."
if [ -f "$DIST_DIR/$BINARY_NAME" ] || [ -f "$DIST_DIR/${BINARY_NAME}.exe" ]; then
  SIZE=$(du -sh "$DIST_DIR" | cut -f1)
  echo ""
  echo "  Backend built successfully"
  echo "  Output:  $DIST_DIR/"
  echo "  Size:    $SIZE"
  echo ""
else
  echo "ERROR: Binary not found in $DIST_DIR" >&2
  exit 1
fi

deactivate
