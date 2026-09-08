"""GMP Document Generation Server.

Lightweight Flask server for the GMP document builder with
Ollama LLM integration and Word document generation.
"""

from flask import Flask, jsonify
from flask_cors import CORS
from flask_migrate import Migrate
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename
import os
import logging

from sqlalchemy import text

from ml_model.gmp.routes import gmp_bp
from ml_model.gmp.account_routes import account_bp
from ml_model.gmp.auth_routes import auth_bp
from ml_model.gmp.protocol_routes import protocol_bp
from ml_model.gmp.asset_routes import asset_bp
from ml_model.gmp.database import init_db, db
from ml_model.gmp.storage import get_document_storage
from ml_model.gmp.extensions import limiter
from ml_model.gmp.celery_app import make_celery

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# Deployment environment: "development" (default) or "production". Honors the
# conventional FLASK_ENV too, so existing deploy configs activate prod mode.
APP_ENV = (os.environ.get("APP_ENV") or os.environ.get("FLASK_ENV") or "development").lower()

# Fail fast in production if signing secrets are missing or left at a known
# placeholder — a default secret means forgeable session cookies and JWTs.
_INSECURE_SECRETS = {"", "dev-insecure-secret-change-me", "please-change-me-in-production",
                     "your_jwt_secret_here", "changeme"}
_configured_secret = os.environ.get("SECRET_KEY") or os.environ.get("JWT_SECRET")
if APP_ENV == "production" and (not _configured_secret
                                or _configured_secret.strip() in _INSECURE_SECRETS):
    raise RuntimeError(
        "SECRET_KEY (or JWT_SECRET) must be set to a real secret when running in "
        "production — refusing to start with a missing or placeholder signing key."
    )

# Signs the Flask session cookie (used for the SSO state / CSRF check).
app.secret_key = _configured_secret or "dev-insecure-secret-change-me"

# Cap request bodies to protect against oversized/abusive payloads (default 16 MB).
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))

allowed_origins = os.environ.get('CORS_ORIGINS', 'http://localhost:4200,http://127.0.0.1:4200').split(',')
CORS(app,
     origins=allowed_origins,
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
     expose_headers=["Content-Disposition"])

# Allow Ollama host override via environment variable (for Docker networking)
OLLAMA_HOST = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
app.config['OLLAMA_HOST'] = OLLAMA_HOST

# Initialize SQLite database
init_db(app)

# Alembic migrations via `flask db ...` (init/migrate/upgrade).
migrate = Migrate(app, db)

# Celery: long LLM calls run as tasks. `celery_app` is the worker entrypoint
# (celery -A gmp_server:celery_app worker). Importing tasks registers them.
celery_app = make_celery(app)
from ml_model.gmp import tasks  # noqa: E402,F401  (registers tasks on celery_app)

# Rate limiting (protects auth + LLM endpoints; see extensions.py)
limiter.init_app(app)

app.register_blueprint(gmp_bp)
app.register_blueprint(account_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(protocol_bp)
app.register_blueprint(asset_bp)


@app.route('/api/download/<filename>')
def download_file(filename):
    # secure_filename strips any path separators / traversal sequences so a
    # crafted name like "../../etc/passwd" can't escape the storage backend.
    safe_name = secure_filename(filename)
    if not safe_name:
        return jsonify({"error": "Invalid filename"}), 400
    # download_response streams from local disk or redirects to a presigned S3
    # URL, depending on the configured backend; returns None if not found.
    response = get_document_storage().download_response(safe_name)
    if response is None:
        return jsonify({"error": "File not found"}), 404
    return response


@app.route('/health')
def health():
    """Liveness probe: the process is up. Cheap, no dependencies."""
    return jsonify({"status": "ok"})


@app.route('/ready')
def ready():
    """Readiness probe: the instance can serve traffic (database reachable)."""
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ready"})
    except Exception:
        logging.exception("Readiness check failed")
        return jsonify({"status": "unavailable"}), 503


@app.errorhandler(HTTPException)
def handle_http_exception(e):
    """Return JSON (not HTML) for HTTP errors so API clients get a consistent shape."""
    return jsonify({"success": False, "error": e.description}), e.code


@app.errorhandler(Exception)
def handle_unexpected_exception(e):
    """Catch-all so unexpected errors return JSON without leaking a stack trace."""
    logging.exception("Unhandled exception")
    return jsonify({"success": False, "error": "Internal server error"}), 500


if __name__ == '__main__':
    print("\n  GMP Document Server")
    print("  http://localhost:5001\n")
    # Debug (with the auto-reloader and interactive traceback) stays off in
    # production. This entrypoint is for local dev; deploy behind gunicorn/uwsgi.
    app.run(host='0.0.0.0', port=5001, debug=APP_ENV != "production")
