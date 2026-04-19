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


@app.route('/api/system/status')
def system_status():
    """Report LLM provider availability so the frontend onboarding wizard
    can tell the user whether Ollama is reachable, which cloud fallback
    (if any) is configured, and the active model."""
    from ml_model.gmp.ollama_service import OllamaService
    from ml_model.gmp.llm_provider import load_config, CONFIG_PATH

    svc = OllamaService(base_url=app.config.get("OLLAMA_HOST", OLLAMA_HOST))
    ollama_ok = svc.check_health()
    fallback = svc.fallback
    fallback_info = None
    if fallback is not None:
        fallback_info = {
            "name": fallback.name,
            "model": fallback.model,
            "healthy": fallback.check_health(),
            "has_api_key": bool(getattr(fallback, "api_key", "")),
        }

    # Expose non-secret config so the wizard can pre-fill which provider
    # is currently selected and whether each API key is already set.
    cfg = load_config()
    return jsonify({
        "success": True,
        "ollama": {
            "reachable": ollama_ok,
            "base_url": svc.base_url,
            "model": svc.model,
        },
        "fallback": fallback_info,
        "active_provider": svc.active_provider_name,
        "config": {
            "provider": cfg.get("provider") or "",
            "has_openai_key": bool(cfg.get("openai_api_key")),
            "openai_model": cfg.get("openai_model") or "",
            "has_anthropic_key": bool(cfg.get("anthropic_api_key")),
            "anthropic_model": cfg.get("anthropic_model") or "",
            "config_path": str(CONFIG_PATH),
        },
    })


@app.route('/api/system/llm-config', methods=['POST'])
def update_llm_config():
    """Persist the user's LLM preference (provider + API keys) to
    ``~/.smartsop/llm.json``. The frontend wizard POSTs here."""
    from flask import request
    from ml_model.gmp.llm_provider import save_config, load_config

    payload = request.get_json(silent=True) or {}
    save_config(payload)
    # Echo the effective config (env + file layered), never the keys.
    cfg = load_config()
    safe = {
        "provider": cfg.get("provider", ""),
        "has_openai_key": bool(cfg.get("openai_api_key")),
        "openai_model": cfg.get("openai_model", ""),
        "has_anthropic_key": bool(cfg.get("anthropic_api_key")),
        "anthropic_model": cfg.get("anthropic_model", ""),
    }
    return jsonify({"success": True, "config": safe})


# ── SPA fallback: serve index.html for any non-API route ───────────
if SERVE_STATIC:
    @app.errorhandler(404)
    def spa_fallback(e):
        """Catch 404s and serve the Angular SPA for non-API routes."""
        from flask import request as req
        path = req.path.lstrip('/')

        # Never intercept API or health routes — let them 404 normally
        if path.startswith('api/') or path == 'health':
            return jsonify({"error": "Not found"}), 404

        # If the path matches a real static file (JS, CSS, assets), serve it
        full = os.path.join(STATIC_DIR, path)
        if path and os.path.isfile(full):
            return send_from_directory(STATIC_DIR, path)

        # Otherwise serve index.html (Angular SPA routing)
        return send_from_directory(STATIC_DIR, 'index.html')

    @app.route('/')
    def serve_root():
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
