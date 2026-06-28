"""Flask Blueprint for account management, training data, and data export."""

import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file, g
from sqlalchemy import func

from .database import db, Account, Document, TrainingExample, Membership, User
from .data_collector import DataCollector
from .training_export import TrainingExporter
from .auth import require_auth, require_account_access, has_account_role

ROLES = ("owner", "admin", "member")
MANAGER_ROLES = ("owner", "admin")
DOC_STATUSES = ("generated", "reviewed", "approved")

logger = logging.getLogger(__name__)

account_bp = Blueprint("accounts", __name__, url_prefix="/api/accounts")
collector = DataCollector()
exporter = TrainingExporter()


# ── Account CRUD ──

@account_bp.route("", methods=["GET"])
@require_auth
def list_accounts():
    """List accounts the current user can access (all accounts for a superadmin)."""
    user = g.current_user
    if user.is_superadmin:
        accounts = Account.query.order_by(Account.name).all()
    else:
        account_ids = [m.account_id for m in user.memberships]
        accounts = (
            Account.query.filter(Account.id.in_(account_ids))
            .order_by(Account.name)
            .all()
        )

    # Count documents and training examples for the whole set in two grouped
    # queries instead of two per account (avoids N+1 as the org count grows).
    ids = [a.id for a in accounts]
    doc_counts = dict(
        db.session.query(Document.account_id, func.count(Document.id))
        .filter(Document.account_id.in_(ids))
        .group_by(Document.account_id)
        .all()
    ) if ids else {}
    train_counts = dict(
        db.session.query(TrainingExample.account_id, func.count(TrainingExample.id))
        .filter(TrainingExample.account_id.in_(ids))
        .group_by(TrainingExample.account_id)
        .all()
    ) if ids else {}

    payload = [
        a.to_dict(counts={
            "documents": doc_counts.get(a.id, 0),
            "training": train_counts.get(a.id, 0),
        })
        for a in accounts
    ]
    return jsonify({"success": True, "accounts": payload})


@account_bp.route("", methods=["POST"])
@require_auth
def create_account():
    data = request.get_json(silent=True)
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
    db.session.flush()
    # The creator owns the account they just made.
    db.session.add(Membership(user_id=g.current_user.id, account_id=account.id, role="owner"))
    db.session.commit()
    return jsonify({"success": True, "account": account.to_dict()}), 201


@account_bp.route("/<int:account_id>", methods=["GET"])
@require_account_access
def get_account(account_id):
    account = Account.query.get_or_404(account_id)
    return jsonify({"success": True, "account": account.to_dict()})


@account_bp.route("/<int:account_id>", methods=["PUT"])
@require_account_access
def update_account(account_id):
    if not has_account_role(g.current_user, account_id, ("owner", "admin")):
        return jsonify({"success": False, "error": "Only account owners or admins can update settings"}), 403
    account = Account.query.get_or_404(account_id)
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "No JSON body"}), 400

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


# ── Members (team) ──

def _member_dict(membership, user):
    return {
        "user_id": user.id,
        "email": user.email,
        "name": user.name,
        "role": membership.role,
        "is_superadmin": user.is_superadmin,
        "joined_at": membership.created_at.isoformat() if membership.created_at else None,
    }


def _owner_count(account_id):
    return Membership.query.filter_by(account_id=account_id, role="owner").count()


@account_bp.route("/<int:account_id>/members", methods=["GET"])
@require_account_access
def list_members(account_id):
    rows = (
        db.session.query(Membership, User)
        .join(User, Membership.user_id == User.id)
        .filter(Membership.account_id == account_id)
        .order_by(User.name, User.email)
        .all()
    )
    return jsonify({"success": True, "members": [_member_dict(m, u) for m, u in rows]})


@account_bp.route("/<int:account_id>/members", methods=["POST"])
@require_account_access
def add_member(account_id):
    if not has_account_role(g.current_user, account_id, MANAGER_ROLES):
        return jsonify({"success": False, "error": "Only owners or admins can add members"}), 403

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    role = (data.get("role") or "member").lower()
    if not email:
        return jsonify({"success": False, "error": "email is required"}), 400
    if role not in ROLES:
        return jsonify({"success": False, "error": f"role must be one of {', '.join(ROLES)}"}), 400
    # Only an owner (or superadmin) may grant the owner role.
    if role == "owner" and not has_account_role(g.current_user, account_id, ("owner",)):
        return jsonify({"success": False, "error": "Only an owner can grant the owner role"}), 403

    user = User.query.filter_by(email=email).first()
    if user is None:
        return jsonify({
            "success": False,
            "error": "No registered user with that email. Ask them to sign up first.",
        }), 404
    if Membership.query.filter_by(user_id=user.id, account_id=account_id).first():
        return jsonify({"success": False, "error": "That user is already a member"}), 409

    membership = Membership(user_id=user.id, account_id=account_id, role=role)
    db.session.add(membership)
    db.session.commit()
    return jsonify({"success": True, "member": _member_dict(membership, user)}), 201


@account_bp.route("/<int:account_id>/members/<int:user_id>", methods=["PATCH"])
@require_account_access
def update_member(account_id, user_id):
    if not has_account_role(g.current_user, account_id, MANAGER_ROLES):
        return jsonify({"success": False, "error": "Only owners or admins can change roles"}), 403

    data = request.get_json(silent=True) or {}
    role = (data.get("role") or "").lower()
    if role not in ROLES:
        return jsonify({"success": False, "error": f"role must be one of {', '.join(ROLES)}"}), 400

    membership = Membership.query.filter_by(account_id=account_id, user_id=user_id).first()
    if membership is None:
        return jsonify({"success": False, "error": "Member not found"}), 404
    if role == "owner" and not has_account_role(g.current_user, account_id, ("owner",)):
        return jsonify({"success": False, "error": "Only an owner can grant the owner role"}), 403
    # Don't let the last owner be demoted — the account would become unmanageable.
    if membership.role == "owner" and role != "owner" and _owner_count(account_id) <= 1:
        return jsonify({"success": False, "error": "Cannot demote the last owner"}), 400

    membership.role = role
    db.session.commit()
    user = db.session.get(User, user_id)
    return jsonify({"success": True, "member": _member_dict(membership, user)})


@account_bp.route("/<int:account_id>/members/<int:user_id>", methods=["DELETE"])
@require_account_access
def remove_member(account_id, user_id):
    if not has_account_role(g.current_user, account_id, MANAGER_ROLES):
        return jsonify({"success": False, "error": "Only owners or admins can remove members"}), 403

    membership = Membership.query.filter_by(account_id=account_id, user_id=user_id).first()
    if membership is None:
        return jsonify({"success": False, "error": "Member not found"}), 404
    if membership.role == "owner" and _owner_count(account_id) <= 1:
        return jsonify({"success": False, "error": "Cannot remove the last owner"}), 400

    db.session.delete(membership)
    db.session.commit()
    return jsonify({"success": True})


# ── Documents (history) ──

@account_bp.route("/<int:account_id>/documents", methods=["GET"])
@require_account_access
def list_documents(account_id):
    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(max(1, request.args.get("per_page", 50, type=int)), 200)
    paginated = (
        Document.query.filter_by(account_id=account_id)
        .order_by(Document.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    return jsonify({
        "success": True,
        "documents": [d.to_dict() for d in paginated.items],
        "total": paginated.total,
        "page": paginated.page,
        "pages": paginated.pages,
    })


@account_bp.route("/<int:account_id>/documents/<int:doc_id>/status", methods=["PATCH"])
@require_account_access
def update_document_status(account_id, doc_id):
    """Move a document through the generated -> reviewed -> approved workflow.

    Anyone in the account can mark a document reviewed or reopen it, but only
    owners/admins can approve a document (QA sign-off) or change one that is
    already approved.
    """
    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "").lower()
    if status not in DOC_STATUSES:
        return jsonify({"success": False, "error": f"status must be one of {', '.join(DOC_STATUSES)}"}), 400

    doc = Document.query.filter_by(id=doc_id, account_id=account_id).first()
    if doc is None:
        return jsonify({"success": False, "error": "Document not found"}), 404

    # Approving, or touching an already-approved record, is a manager action.
    needs_manager = status == "approved" or doc.status == "approved"
    if needs_manager and not has_account_role(g.current_user, account_id, MANAGER_ROLES):
        return jsonify({
            "success": False,
            "error": "Only owners or admins can approve or change an approved document",
        }), 403

    # Record who acted and when. Reopening to "generated" voids prior sign-offs.
    actor = (g.current_user.name or "").strip() or g.current_user.email
    now = datetime.utcnow()
    if status == "generated":
        doc.reviewed_by = doc.reviewed_at = None
        doc.approved_by = doc.approved_at = None
    elif status == "reviewed":
        doc.reviewed_by, doc.reviewed_at = actor, now
        doc.approved_by = doc.approved_at = None
    elif status == "approved":
        doc.approved_by, doc.approved_at = actor, now

    doc.status = status
    db.session.commit()
    return jsonify({"success": True, "document": doc.to_dict()})


# ── Training Data ──

@account_bp.route("/<int:account_id>/training", methods=["GET"])
@require_account_access
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
@require_account_access
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
@require_account_access
def record_edit(account_id, example_id):
    """Record a user's edit of an AI-generated section."""
    data = request.get_json(silent=True)
    if not data or not data.get("edited_content"):
        return jsonify({"success": False, "error": "edited_content is required"}), 400

    original = TrainingExample.query.filter_by(id=example_id, account_id=account_id).first()
    if original is None:
        return jsonify({"success": False, "error": "Training example not found for this account"}), 404
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
@require_account_access
def rate_example(account_id, example_id):
    """Rate a training example 1-5."""
    data = request.get_json(silent=True) or {}
    rating = data.get("rating")
    if not rating or not isinstance(rating, int) or not 1 <= rating <= 5:
        return jsonify({"success": False, "error": "rating must be an integer 1-5"}), 400

    example = TrainingExample.query.filter_by(id=example_id, account_id=account_id).first()
    if example is None:
        return jsonify({"success": False, "error": "Example not found"}), 404

    if collector.rate_example(example_id, rating):
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Example not found"}), 404


@account_bp.route("/<int:account_id>/training/stats", methods=["GET"])
@require_account_access
def training_stats(account_id):
    stats = collector.get_account_stats(account_id)
    return jsonify({"success": True, **stats})


# ── Export ──

@account_bp.route("/<int:account_id>/export/jsonl", methods=["GET"])
@require_account_access
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
@require_account_access
def export_modelfile(account_id):
    """Generate an Ollama Modelfile with account-specific system prompt."""
    base_model = request.args.get("base_model", "llama3")
    result = exporter.export_ollama_modelfile(account_id, base_model=base_model)

    if not result.get("success"):
        return jsonify(result), 404

    return jsonify({"success": True, **result})


@account_bp.route("/<int:account_id>/export/full", methods=["GET"])
@require_account_access
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
