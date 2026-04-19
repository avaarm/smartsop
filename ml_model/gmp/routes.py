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
        import os
        ollama_url = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
        _generator = GMPDocumentGenerator(ollama_url=ollama_url)
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
            "applied_style": result.get("applied_style"),
            "style_applied": bool(result.get("applied_style")),
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


# ── Paper Scraping Endpoints ──

@gmp_bp.route("/papers/search", methods=["GET"])
def search_papers():
    """Search PubMed Central for open-access papers.

    Query params:
        q: search terms (required)
        limit: max results (default 10)
    """
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"success": False, "error": "Query parameter 'q' is required"}), 400

    try:
        limit = int(request.args.get("limit", 10))
        limit = max(1, min(limit, 30))
    except ValueError:
        limit = 10

    try:
        gen = get_generator()
        papers = gen.search_papers(query, max_results=limit)
        return jsonify({"success": True, "papers": papers, "query": query})
    except Exception as e:
        logger.error(f"Paper search failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@gmp_bp.route("/papers/<pmcid>/methods", methods=["GET"])
def get_paper_methods(pmcid: str):
    """Fetch the methods section of a specific paper."""
    try:
        gen = get_generator()
        result = gen.fetch_paper_methods(pmcid)
        if result is None:
            return jsonify({
                "success": False,
                "error": "Methods section not found or paper not accessible"
            }), 404
        return jsonify({"success": True, **result})
    except Exception as e:
        logger.error(f"Failed to fetch methods for {pmcid}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@gmp_bp.route("/papers/autofill", methods=["POST"])
def autofill_from_paper():
    """Extract GMP section data from a paper and return it for autofill.

    Request body:
    {
        "pmcid": "PMC1234567",
        "context": {
            "product_name": "CD8+ T Cells",
            "process_type": "CD8 Enrichment"
        }
    }
    """
    try:
        data = request.get_json()
        pmcid = data.get("pmcid")
        context = data.get("context", {})

        if not pmcid:
            return jsonify({"success": False, "error": "pmcid is required"}), 400

        gen = get_generator()
        result = gen.autofill_from_paper(pmcid, context)
        return jsonify({"success": True, **result})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except RuntimeError as e:
        return jsonify({"success": False, "error": str(e)}), 503
    except Exception as e:
        logger.error(f"Autofill failed: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
