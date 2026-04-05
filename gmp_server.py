"""GMP Document Generation Server.

Lightweight Flask server for the GMP document builder with
Ollama LLM integration and Word document generation.
"""

from flask import Flask, jsonify, send_file
from flask_cors import CORS
import os
import logging

from ml_model.gmp.routes import gmp_bp

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
CORS(app,
     origins=["http://localhost:4200", "http://127.0.0.1:4200"],
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
     expose_headers=["Content-Disposition"])

GENERATED_DOCS_DIR = os.path.join(os.path.dirname(__file__), 'generated_docs')
os.makedirs(GENERATED_DOCS_DIR, exist_ok=True)

app.register_blueprint(gmp_bp)


@app.route('/api/download/<filename>')
def download_file(filename):
    filepath = os.path.join(GENERATED_DOCS_DIR, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify({"error": "File not found"}), 404


@app.route('/health')
def health():
    return jsonify({"status": "ok"})


if __name__ == '__main__':
    print("\n  GMP Document Server")
    print("  http://localhost:5001\n")
    app.run(host='0.0.0.0', port=5001, debug=True)
