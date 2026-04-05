"""Flask Blueprint for GMP document generation API endpoints."""

import logging
from flask import Blueprint, request, jsonify

from .document_generator import GMPDocumentGenerator

logger = logging.getLogger(__name__)

gmp_bp = Blueprint("gmp", __name__, url_prefix="/api/gmp")

# Lazy initialization
_generator = None


def get_generator() -> GMPDocumentGenerator:
    global _generator
    if _generator is None:
        _generator = GMPDocumentGenerator()
    return _generator


@gmp_bp.route("/templates", methods=["GET"])
def list_templates():
    """List all available GMP document templates."""
    try:
        gen = get_generator()
        return jsonify({"success": True, "templates": gen.list_templates()})
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@gmp_bp.route("/templates/<template_id>", methods=["GET"])
def get_template(template_id: str):
    """Get the full schema for a template."""
    try:
        gen = get_generator()
        schema = gen.get_template_schema(template_id)
        return jsonify({"success": True, "template": schema})
    except FileNotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except Exception as e:
        logger.error(f"Failed to get template {template_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@gmp_bp.route("/generate", methods=["POST"])
def generate_document():
    """Generate a GMP document."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No JSON body"}), 400

        doc_type = data.get("doc_type")
        if not doc_type:
            return jsonify({"success": False, "error": "doc_type is required"}), 400

        gen = get_generator()
        result = gen.generate_document(doc_type, data)

        return jsonify({
            "success": True,
            "doc_id": result["doc_id"],
            "filename": result["filename"],
            "download_url": result["download_url"],
            "preview_sections": result["preview_sections"],
        })
    except FileNotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except RuntimeError as e:
        return jsonify({"success": False, "error": str(e)}), 503
    except Exception as e:
        logger.error(f"Document generation failed: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@gmp_bp.route("/preview", methods=["POST"])
def preview_section():
    """Generate a preview for a single document section."""
    try:
        data = request.get_json()
        doc_type = data.get("doc_type")
        section_id = data.get("section_id")
        context = data.get("context", {})

        if not doc_type or not section_id:
            return jsonify({
                "success": False,
                "error": "doc_type and section_id are required"
            }), 400

        gen = get_generator()
        result = gen.preview_section(doc_type, section_id, context)
        return jsonify({"success": True, "data": result})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except Exception as e:
        logger.error(f"Section preview failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@gmp_bp.route("/ollama/status", methods=["GET"])
def ollama_status():
    """Check Ollama service status."""
    try:
        gen = get_generator()
        return jsonify({"success": True, **gen.get_ollama_status()})
    except Exception as e:
        return jsonify({"success": False, "available": False, "error": str(e)})
