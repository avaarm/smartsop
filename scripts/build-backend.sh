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
  --add-data "ml_model/gmp/sample_docs:ml_model/gmp/sample_docs" \
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
  --hidden-import "pdfplumber" \
  --hidden-import "pdfminer" \
  --hidden-import "pdfminer.high_level" \
  --hidden-import "pdfminer.layout" \
  --hidden-import "pandas" \
  --collect-submodules "ml_model.gmp" \
  --collect-submodules "pdfminer" \
  "$ENTRY"

# Flatten: electron-builder expects files directly under dist-backend/.
# PyInstaller --onedir produces dist-backend/smartsop-backend/{smartsop-backend[.exe], _internal/...}
# The inner binary has the same name as its parent directory, so we must
# rename it first before moving to avoid the collision.
# On Windows PyInstaller produces smartsop-backend.exe.
if [ -d "$DIST_DIR/$BINARY_NAME" ]; then
  echo "[3/4] Flattening output directory..."
  INNER="$DIST_DIR/$BINARY_NAME"
  if [ -f "$INNER/${BINARY_NAME}.exe" ]; then
    BIN_FILE="${BINARY_NAME}.exe"
  else
    BIN_FILE="$BINARY_NAME"
  fi
  # Rename inner binary to a temp name so it can share a parent with _internal/
  mv "$INNER/$BIN_FILE" "$DIST_DIR/.${BINARY_NAME}.bin"
  # Move remaining contents (e.g. _internal/) up
  mv "$INNER"/* "$DIST_DIR/" 2>/dev/null || true
  rmdir "$INNER"
  # Put the binary back with its original name
  mv "$DIST_DIR/.${BINARY_NAME}.bin" "$DIST_DIR/$BIN_FILE"
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
