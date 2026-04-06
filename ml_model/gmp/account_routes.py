"""Flask Blueprint for account management, training data, and data export."""

import json
import logging
from flask import Blueprint, request, jsonify, send_file

from .database import db, Account, Document, TrainingExample
from .data_collector import DataCollector
from .training_export import TrainingExporter

logger = logging.getLogger(__name__)

account_bp = Blueprint("accounts", __name__, url_prefix="/api/accounts")
collector = DataCollector()
exporter = TrainingExporter()


# ── Account CRUD ──

@account_bp.route("", methods=["GET"])
def list_accounts():
    accounts = Account.query.order_by(Account.name).all()
    return jsonify({"success": True, "accounts": [a.to_dict() for a in accounts]})


@account_bp.route("", methods=["POST"])
def create_account():
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"success": False, "error": "name is required"}), 400

    slug = data.get("slug") or data["name"].lower().replace(" ", "-")
    slug = "".join(c for c in slug if c.isalnum() or c == "-")

    if Account.query.filter_by(slug=slug).first():
        return jsonify({"success": False, "error": f"Account with slug '{slug}' already exists"}), 409

    account = Account(
        name=data["name"],
        slug=slug,
        facility_name=data.get("facility_name", ""),
        department=data.get("department", ""),
        default_product=data.get("default_product", ""),
        default_process=data.get("default_process", ""),
        terminology_json=json.dumps(data.get("terminology", {})),
        style_notes=data.get("style_notes", ""),
        reference_sops_json=json.dumps(data.get("reference_sops", [])),
    )
    db.session.add(account)
    db.session.commit()
    return jsonify({"success": True, "account": account.to_dict()}), 201


@account_bp.route("/<int:account_id>", methods=["GET"])
def get_account(account_id):
    account = Account.query.get_or_404(account_id)
    return jsonify({"success": True, "account": account.to_dict()})


@account_bp.route("/<int:account_id>", methods=["PUT"])
def update_account(account_id):
    account = Account.query.get_or_404(account_id)
    data = request.get_json()

    if "name" in data:
        account.name = data["name"]
    if "facility_name" in data:
        account.facility_name = data["facility_name"]
    if "department" in data:
        account.department = data["department"]
    if "default_product" in data:
        account.default_product = data["default_product"]
    if "default_process" in data:
        account.default_process = data["default_process"]
    if "terminology" in data:
        account.terminology_json = json.dumps(data["terminology"])
    if "style_notes" in data:
        account.style_notes = data["style_notes"]
    if "reference_sops" in data:
        account.reference_sops_json = json.dumps(data["reference_sops"])

    db.session.commit()
    return jsonify({"success": True, "account": account.to_dict()})


# ── Documents (history) ──

@account_bp.route("/<int:account_id>/documents", methods=["GET"])
def list_documents(account_id):
    docs = Document.query.filter_by(account_id=account_id).order_by(
        Document.created_at.desc()
    ).all()
    return jsonify({"success": True, "documents": [d.to_dict() for d in docs]})


# ── Training Data ──

@account_bp.route("/<int:account_id>/training", methods=["GET"])
def list_training_examples(account_id):
    """List training examples with optional filters."""
    source = request.args.get("source")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))

    query = TrainingExample.query.filter_by(account_id=account_id)
    if source:
        query = query.filter_by(source=source)
    query = query.order_by(TrainingExample.created_at.desc())

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "success": True,
        "examples": [e.to_dict() for e in paginated.items],
        "total": paginated.total,
        "page": paginated.page,
        "pages": paginated.pages,
    })


@account_bp.route("/<int:account_id>/training", methods=["POST"])
def add_training_example(account_id):
    """Manually add a training example (e.g. paste in a gold-standard section)."""
    data = request.get_json()
    if not data or not data.get("prompt") or not data.get("completion"):
        return jsonify({"success": False, "error": "prompt and completion are required"}), 400

    example = collector.record_section_generation(
        account_id=account_id,
        section_type=data.get("section_type", "manual"),
        prompt=data["prompt"],
        completion=data["completion"],
        context={
            "product_name": data.get("product_name", ""),
            "process_type": data.get("process_type", ""),
        },
        source="manual",
    )
    if example:
        return jsonify({"success": True, "example": example.to_dict()}), 201
    return jsonify({"success": False, "error": "Failed to save"}), 500


@account_bp.route("/<int:account_id>/training/<int:example_id>/edit", methods=["POST"])
def record_edit(account_id, example_id):
    """Record a user's edit of an AI-generated section."""
    data = request.get_json()
    if not data or not data.get("edited_content"):
        return jsonify({"success": False, "error": "edited_content is required"}), 400

    original = TrainingExample.query.get_or_404(example_id)
    example = collector.record_user_edit(
        account_id=account_id,
        section_type=original.section_type,
        original_prompt=original.user_prompt,
        edited_content=data["edited_content"],
        context={
            "product_name": original.product_name,
            "process_type": original.process_type,
        },
        document_id=original.document_id,
    )
    if example:
        return jsonify({"success": True, "example": example.to_dict()}), 201
    return jsonify({"success": False, "error": "Failed to save"}), 500


@account_bp.route("/<int:account_id>/training/<int:example_id>/rate", methods=["POST"])
def rate_example(account_id, example_id):
    """Rate a training example 1-5."""
    data = request.get_json()
    rating = data.get("rating")
    if not rating or not isinstance(rating, int) or not 1 <= rating <= 5:
        return jsonify({"success": False, "error": "rating must be an integer 1-5"}), 400

    if collector.rate_example(example_id, rating):
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Example not found"}), 404


@account_bp.route("/<int:account_id>/training/stats", methods=["GET"])
def training_stats(account_id):
    stats = collector.get_account_stats(account_id)
    return jsonify({"success": True, **stats})


# ── Export ──

@account_bp.route("/<int:account_id>/export/jsonl", methods=["GET"])
def export_jsonl(account_id):
    """Export training data as JSONL for fine-tuning."""
    min_rating = request.args.get("min_rating", type=int)
    source = request.args.get("source")
    result = exporter.export_jsonl(account_id, min_rating=min_rating, source_filter=source)

    if not result.get("success"):
        return jsonify(result), 404

    return send_file(
        result["filepath"],
        as_attachment=True,
        download_name=result["filename"],
        mimetype="application/jsonl",
    )


@account_bp.route("/<int:account_id>/export/modelfile", methods=["GET"])
def export_modelfile(account_id):
    """Generate an Ollama Modelfile with account-specific system prompt."""
    base_model = request.args.get("base_model", "llama3")
    result = exporter.export_ollama_modelfile(account_id, base_model=base_model)

    if not result.get("success"):
        return jsonify(result), 404

    return jsonify({"success": True, **result})


@account_bp.route("/<int:account_id>/export/full", methods=["GET"])
def export_full(account_id):
    """Export all account data (documents + training examples + config)."""
    result = exporter.export_full_dataset(account_id)

    if not result.get("success"):
        return jsonify(result), 404

    return send_file(
        result["filepath"],
        as_attachment=True,
        download_name=result["filename"],
        mimetype="application/json",
    )
