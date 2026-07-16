"""Flask Blueprint for protocols.io-style protocols (authoring + steps).

All routes are account-scoped and require membership (require_account_access).
"""

import json
import logging

from flask import Blueprint, request, jsonify, g
from sqlalchemy import func

from .database import db, Protocol, ProtocolStep
from .auth import require_account_access

logger = logging.getLogger(__name__)

protocol_bp = Blueprint("protocols", __name__, url_prefix="/api/accounts")


def _get_protocol(account_id, protocol_id):
    return Protocol.query.filter_by(id=protocol_id, account_id=account_id).first()


def _apply_step_fields(step, data):
    """Copy editable fields from a request body onto a step."""
    if "section" in data:
        step.section = (data.get("section") or "")[:200]
    if "title" in data:
        step.title = (data.get("title") or "")[:500]
    if "description" in data:
        step.description = data.get("description") or ""
    if "warning" in data:
        step.warning = data.get("warning") or ""
    if "duration_seconds" in data:
        raw = data.get("duration_seconds")
        step.duration_seconds = int(raw) if raw not in (None, "") else None
    if "reagents" in data:
        reagents = data.get("reagents") or []
        step.reagents_json = json.dumps(reagents if isinstance(reagents, list) else [])


# ── Protocols ──

@protocol_bp.route("/<int:account_id>/protocols", methods=["GET"])
@require_account_access
def list_protocols(account_id):
    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(max(1, request.args.get("per_page", 20, type=int)), 100)
    paginated = (
        Protocol.query.filter_by(account_id=account_id)
        .order_by(Protocol.updated_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    return jsonify({
        "success": True,
        "protocols": [p.to_dict() for p in paginated.items],
        "total": paginated.total,
        "page": paginated.page,
        "pages": paginated.pages,
    })


@protocol_bp.route("/<int:account_id>/protocols", methods=["POST"])
@require_account_access
def create_protocol(account_id):
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"success": False, "error": "title is required"}), 400

    author = (g.current_user.name or "").strip() or g.current_user.email
    protocol = Protocol(
        account_id=account_id,
        title=title[:500],
        description=data.get("description", ""),
        created_by=author,
    )
    db.session.add(protocol)
    db.session.commit()
    return jsonify({"success": True, "protocol": protocol.to_dict(include_steps=True)}), 201


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>", methods=["GET"])
@require_account_access
def get_protocol(account_id, protocol_id):
    protocol = _get_protocol(account_id, protocol_id)
    if protocol is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404
    return jsonify({"success": True, "protocol": protocol.to_dict(include_steps=True)})


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>", methods=["PUT"])
@require_account_access
def update_protocol(account_id, protocol_id):
    protocol = _get_protocol(account_id, protocol_id)
    if protocol is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404
    data = request.get_json(silent=True) or {}
    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify({"success": False, "error": "title cannot be empty"}), 400
        protocol.title = title[:500]
    if "description" in data:
        protocol.description = data.get("description") or ""
    if "status" in data:
        status = (data.get("status") or "").lower()
        if status not in ("draft", "published"):
            return jsonify({"success": False, "error": "status must be draft or published"}), 400
        protocol.status = status
    db.session.commit()
    return jsonify({"success": True, "protocol": protocol.to_dict(include_steps=True)})


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>", methods=["DELETE"])
@require_account_access
def delete_protocol(account_id, protocol_id):
    protocol = _get_protocol(account_id, protocol_id)
    if protocol is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404
    db.session.delete(protocol)
    db.session.commit()
    return jsonify({"success": True})


# ── Steps ──

@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/steps", methods=["POST"])
@require_account_access
def add_step(account_id, protocol_id):
    protocol = _get_protocol(account_id, protocol_id)
    if protocol is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404

    data = request.get_json(silent=True) or {}
    next_index = (db.session.query(func.max(ProtocolStep.order_index))
                  .filter_by(protocol_id=protocol_id).scalar())
    step = ProtocolStep(
        protocol_id=protocol_id,
        order_index=(next_index + 1) if next_index is not None else 0,
    )
    _apply_step_fields(step, data)
    db.session.add(step)
    db.session.commit()
    return jsonify({"success": True, "step": step.to_dict()}), 201


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/steps/<int:step_id>", methods=["PUT"])
@require_account_access
def update_step(account_id, protocol_id, step_id):
    if _get_protocol(account_id, protocol_id) is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404
    step = ProtocolStep.query.filter_by(id=step_id, protocol_id=protocol_id).first()
    if step is None:
        return jsonify({"success": False, "error": "Step not found"}), 404
    _apply_step_fields(step, request.get_json(silent=True) or {})
    db.session.commit()
    return jsonify({"success": True, "step": step.to_dict()})


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/steps/<int:step_id>", methods=["DELETE"])
@require_account_access
def delete_step(account_id, protocol_id, step_id):
    if _get_protocol(account_id, protocol_id) is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404
    step = ProtocolStep.query.filter_by(id=step_id, protocol_id=protocol_id).first()
    if step is None:
        return jsonify({"success": False, "error": "Step not found"}), 404
    db.session.delete(step)
    db.session.commit()
    return jsonify({"success": True})


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/steps/reorder", methods=["POST"])
@require_account_access
def reorder_steps(account_id, protocol_id):
    if _get_protocol(account_id, protocol_id) is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404

    data = request.get_json(silent=True) or {}
    order = data.get("order")
    if not isinstance(order, list):
        return jsonify({"success": False, "error": "order must be a list of step ids"}), 400

    steps = {s.id: s for s in ProtocolStep.query.filter_by(protocol_id=protocol_id).all()}
    if set(order) != set(steps.keys()):
        return jsonify({"success": False, "error": "order must contain exactly this protocol's step ids"}), 400

    for index, step_id in enumerate(order):
        steps[step_id].order_index = index
    db.session.commit()
    return jsonify({"success": True})
