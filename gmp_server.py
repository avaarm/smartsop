"""GMP Document Generation Server.

Lightweight Flask server for the GMP document builder with
Ollama LLM integration and Word document generation.

When SMARTSOP_SERVE_STATIC=1 (set by Electron), Flask also
serves the Angular production build so the desktop app only
needs a single origin.
"""

from flask import Flask, jsonify, send_file, send_from_directory
from flask_cors import CORS
import os
import logging

from ml_model.gmp.routes import gmp_bp
from ml_model.gmp.account_routes import account_bp
from ml_model.gmp.database import init_db

logging.basicConfig(level=logging.INFO)

# ── Resolve static-file directory (Electron desktop mode) ──────────
SERVE_STATIC = os.environ.get('SMARTSOP_SERVE_STATIC', '').strip() == '1'
STATIC_DIR = os.environ.get(
    'SMARTSOP_STATIC_DIR',
    os.path.join(os.path.dirname(__file__), 'dist', 'smartsop', 'browser')
)

if SERVE_STATIC and os.path.isdir(STATIC_DIR):
    # Don't use Flask's built-in static handler — it intercepts SPA routes.
    # We'll handle static + SPA fallback manually in the catch-all below.
    app = Flask(__name__, static_folder=None)
else:
    app = Flask(__name__)
    SERVE_STATIC = False  # directory not available

allowed_origins = os.environ.get(
    'CORS_ORIGINS',
    'http://localhost:4200,http://127.0.0.1:4200'
).split(',')
CORS(app,
     origins=allowed_origins,
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
     expose_headers=["Content-Disposition"])

GENERATED_DOCS_DIR = os.path.join(os.path.dirname(__file__), 'generated_docs')
os.makedirs(GENERATED_DOCS_DIR, exist_ok=True)

# Allow Ollama host override via environment variable (for Docker networking)
OLLAMA_HOST = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
app.config['OLLAMA_HOST'] = OLLAMA_HOST

# Initialize SQLite database
init_db(app)

app.register_blueprint(gmp_bp)
app.register_blueprint(account_bp)


@app.route('/api/download/<filename>')
def download_file(filename):
    filepath = os.path.join(GENERATED_DOCS_DIR, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify({"error": "File not found"}), 404


@app.route('/health')
def health():
    return jsonify({"status": "ok"})


# ── SPA fallback: serve index.html for any non-API route ───────────
if SERVE_STATIC:
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_spa(path):
        # If the path matches a real file (JS, CSS, assets), serve it
        full = os.path.join(STATIC_DIR, path)
        if path and os.path.isfile(full):
            return send_from_directory(STATIC_DIR, path)
        # Otherwise serve index.html (Angular SPA routing)
        return send_from_directory(STATIC_DIR, 'index.html')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    is_dev = os.environ.get('FLASK_ENV', 'development') == 'development'
    print(f"\n  GMP Document Server")
    print(f"  http://localhost:{port}")
    if SERVE_STATIC:
        print(f"  Serving frontend from {STATIC_DIR}")
    print()
    app.run(host='0.0.0.0', port=port, debug=is_dev)
