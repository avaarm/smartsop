"""Flask Blueprint for protocols.io-style protocols (authoring + steps).

All routes are account-scoped and require membership (require_account_access).
"""

import json
import logging
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, g
from sqlalchemy import func

from .database import db, Protocol, ProtocolStep, ProtocolRun, ProtocolRunStep, ProtocolSignoff
from .auth import require_account_access, has_account_role
from .protocol_import import extract_text, split_into_steps, ai_structure
from .generator_provider import get_generator

RUN_STEP_STATUSES = ("pending", "done", "failed", "skipped")
PROTOCOL_TYPES = ("protocol", "sop", "gmp_sop")

# Typed step components (LOTO / safety block library). Flag types render as a
# required action at run time; the rest carry a text value.
COMPONENT_TYPES = (
    "ppe", "energy_source", "isolation_device", "lockout_tag", "authorized_person",
    "hazard_class", "torque", "pressure", "temperature", "expected_result",
    "return_to_service", "verification_photo", "second_signature",
)
COMPONENT_FLAG_TYPES = ("verification_photo", "second_signature")
MAX_COMPONENTS = 30
BRANCH_ACTIONS = ("continue", "goto", "halt")
MAX_BRANCH_OPTIONS = 8
MANAGER_ROLES = ("owner", "admin")
DEFAULT_MEANING = {
    "reviewer": "Reviewed for accuracy and completeness",
    "approver": "Approved for use",
}

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
    if "components" in data:
        step.components_json = json.dumps(_clean_components(data.get("components")))
    if "branch" in data:
        step.branch_json = _clean_branch(data.get("branch"))


def _clean_branch(raw):
    """Validate a decision/branch → JSON string, or '' to clear."""
    if not isinstance(raw, dict):
        return ""
    question = str(raw.get("question", "")).strip()[:300]
    options = []
    for o in (raw.get("options") or [])[:MAX_BRANCH_OPTIONS]:
        if not isinstance(o, dict):
            continue
        action = str(o.get("action", "continue")).lower()
        if action not in BRANCH_ACTIONS:
            action = "continue"
        target = o.get("target")
        options.append({
            "label": str(o.get("label", "")).strip()[:120],
            "action": action,
            "target": int(target) if isinstance(target, (int, float)) and action == "goto" else None,
        })
    if not question and not options:
        return ""
    return json.dumps({"question": question, "options": options})


def _clean_components(raw):
    """Validate/normalize typed components to [{type, value}]."""
    if not isinstance(raw, list):
        return []
    out = []
    for c in raw[:MAX_COMPONENTS]:
        if not isinstance(c, dict):
            continue
        ctype = str(c.get("type", "")).lower()
        if ctype not in COMPONENT_TYPES:
            continue
        if ctype in COMPONENT_FLAG_TYPES:
            out.append({"type": ctype, "value": bool(c.get("value", True))})
        else:
            out.append({"type": ctype, "value": str(c.get("value", ""))[:500]})
    return out


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


@protocol_bp.route("/<int:account_id>/protocols/import", methods=["POST"])
@require_account_access
def import_protocol(account_id):
    """Create a protocol from pasted text or an uploaded Word/PDF/text file.

    mode: numbered | lines | markdown | ai  (ai falls back to numbered when the
    LLM is unavailable). Returns the created protocol and the mode actually used.
    """
    upload = request.files.get("file")
    if upload is not None:
        text = extract_text(upload.filename, upload.read())
        title = (request.form.get("title") or "").strip()
        mode = (request.form.get("mode") or "numbered").lower()
        if not title:
            base = (upload.filename or "").rsplit(".", 1)[0].replace("_", " ").strip()
            title = base[:500] or "Imported protocol"
    else:
        data = request.get_json(silent=True) or {}
        text = data.get("text") or ""
        title = (data.get("title") or "").strip() or "Imported protocol"
        mode = (data.get("mode") or "numbered").lower()

    if not text.strip():
        return jsonify({"success": False, "error": "No text to import"}), 400

    used = mode
    if mode == "ai":
        steps = ai_structure(text, getattr(get_generator(), "ollama", None))
        if steps is None:
            steps = split_into_steps(text, "numbered")
            used = "numbered (AI unavailable)"
    else:
        if mode not in ("numbered", "lines", "markdown"):
            mode = used = "numbered"
        steps = split_into_steps(text, mode)

    if not steps:
        return jsonify({"success": False, "error": "Could not extract any steps from the input"}), 400

    author = (g.current_user.name or "").strip() or g.current_user.email
    protocol = Protocol(account_id=account_id, title=title[:500], created_by=author)
    db.session.add(protocol)
    db.session.flush()
    for i, s in enumerate(steps):
        db.session.add(ProtocolStep(
            protocol_id=protocol.id, order_index=i,
            title=s.get("title", ""), description=s.get("description", ""),
            duration_seconds=s.get("duration_seconds"), warning=s.get("warning", ""),
        ))
    db.session.commit()
    return jsonify({
        "success": True,
        "protocol": protocol.to_dict(include_steps=True),
        "mode": used,
        "step_count": len(steps),
    }), 201


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
    if "protocol_type" in data:
        ptype = (data.get("protocol_type") or "").lower()
        if ptype not in PROTOCOL_TYPES:
            return jsonify({"success": False, "error": f"protocol_type must be one of {', '.join(PROTOCOL_TYPES)}"}), 400
        protocol.protocol_type = ptype
    for field in ("sop_number", "department", "review_date"):
        if field in data:
            setattr(protocol, field, (data.get(field) or "")[:200])
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


# ── Runs (executing a protocol) ──

def _get_run(account_id, run_id):
    return ProtocolRun.query.filter_by(id=run_id, account_id=account_id).first()


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/runs", methods=["POST"])
@require_account_access
def start_run(account_id, protocol_id):
    """Start a run: snapshot the protocol's steps so later edits don't rewrite history."""
    protocol = _get_protocol(account_id, protocol_id)
    if protocol is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404

    steps = protocol.steps.all()
    if not steps:
        return jsonify({"success": False, "error": "Cannot run a protocol with no steps"}), 400

    data = request.get_json(silent=True) or {}
    actor = (g.current_user.name or "").strip() or g.current_user.email
    run = ProtocolRun(
        account_id=account_id,
        protocol_id=protocol_id,
        protocol_title=protocol.title,
        protocol_version=protocol.version,
        experiment_id=(data.get("experiment_id") or "")[:200],
        started_by=actor,
    )
    db.session.add(run)
    db.session.flush()

    for step in steps:
        db.session.add(ProtocolRunStep(
            run_id=run.id,
            step_id=step.id,
            order_index=step.order_index,
            title=step.title,
            description=step.description,
            duration_seconds=step.duration_seconds,
            warning=step.warning,
            reagents_json=step.reagents_json,
            components_json=step.components_json,
            branch_json=step.branch_json,
        ))
    db.session.commit()
    return jsonify({"success": True, "run": run.to_dict(include_steps=True)}), 201


@protocol_bp.route("/<int:account_id>/runs", methods=["GET"])
@require_account_access
def list_runs(account_id):
    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(max(1, request.args.get("per_page", 20, type=int)), 100)
    query = ProtocolRun.query.filter_by(account_id=account_id)
    protocol_id = request.args.get("protocol_id", type=int)
    if protocol_id:
        query = query.filter_by(protocol_id=protocol_id)
    paginated = query.order_by(ProtocolRun.started_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False)
    return jsonify({
        "success": True,
        "runs": [r.to_dict() for r in paginated.items],
        "total": paginated.total,
        "page": paginated.page,
        "pages": paginated.pages,
    })


@protocol_bp.route("/<int:account_id>/runs/<int:run_id>", methods=["GET"])
@require_account_access
def get_run(account_id, run_id):
    run = _get_run(account_id, run_id)
    if run is None:
        return jsonify({"success": False, "error": "Run not found"}), 404
    return jsonify({"success": True, "run": run.to_dict(include_steps=True)})


@protocol_bp.route("/<int:account_id>/runs/<int:run_id>", methods=["PUT"])
@require_account_access
def update_run(account_id, run_id):
    run = _get_run(account_id, run_id)
    if run is None:
        return jsonify({"success": False, "error": "Run not found"}), 404
    data = request.get_json(silent=True) or {}
    if "experiment_id" in data:
        run.experiment_id = (data.get("experiment_id") or "")[:200]
    db.session.commit()
    return jsonify({"success": True, "run": run.to_dict()})


@protocol_bp.route("/<int:account_id>/runs/<int:run_id>/steps/<int:run_step_id>", methods=["PATCH"])
@require_account_access
def set_run_step_outcome(account_id, run_id, run_step_id):
    """Mark a run step Done / Fail / Skip (or back to pending) and record a note."""
    run = _get_run(account_id, run_id)
    if run is None:
        return jsonify({"success": False, "error": "Run not found"}), 404
    step = ProtocolRunStep.query.filter_by(id=run_step_id, run_id=run_id).first()
    if step is None:
        return jsonify({"success": False, "error": "Run step not found"}), 404

    data = request.get_json(silent=True) or {}
    if "status" in data:
        status = (data.get("status") or "").lower()
        if status not in RUN_STEP_STATUSES:
            return jsonify({
                "success": False,
                "error": f"status must be one of {', '.join(RUN_STEP_STATUSES)}",
            }), 400
        step.status = status
        if status == "pending":
            step.completed_by, step.completed_at = "", None
        else:
            step.completed_by = (g.current_user.name or "").strip() or g.current_user.email
            step.completed_at = datetime.utcnow()
    if "note" in data:
        step.note = data.get("note") or ""

    db.session.commit()
    return jsonify({"success": True, "step": step.to_dict()})


@protocol_bp.route("/<int:account_id>/runs/<int:run_id>/finish", methods=["POST"])
@require_account_access
def finish_run(account_id, run_id):
    run = _get_run(account_id, run_id)
    if run is None:
        return jsonify({"success": False, "error": "Run not found"}), 404
    run.status = "completed"
    run.completed_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"success": True, "run": run.to_dict(include_steps=True)})


# ── Analytics ──

@protocol_bp.route("/<int:account_id>/analytics", methods=["GET"])
@require_account_access
def analytics(account_id):
    """Aggregate protocol + run metrics for a dashboard."""
    protocols = Protocol.query.filter_by(account_id=account_id).count()
    effective = Protocol.query.filter_by(account_id=account_id, status="effective").count()

    runs_q = ProtocolRun.query.filter_by(account_id=account_id)
    total_runs = runs_q.count()
    completed_runs = runs_q.filter_by(status="completed").count()

    # Run-step outcomes across the account (deviations = failed).
    outcome_rows = (
        db.session.query(ProtocolRunStep.status, func.count(ProtocolRunStep.id))
        .join(ProtocolRun, ProtocolRunStep.run_id == ProtocolRun.id)
        .filter(ProtocolRun.account_id == account_id)
        .group_by(ProtocolRunStep.status)
        .all()
    )
    outcomes = {s: n for s, n in outcome_rows}

    # Average duration of completed runs.
    completed = runs_q.filter(
        ProtocolRun.status == "completed", ProtocolRun.completed_at.isnot(None)
    ).all()
    durations = [
        (r.completed_at - r.started_at).total_seconds()
        for r in completed if r.started_at and r.completed_at
    ]
    avg_dur = int(sum(durations) / len(durations)) if durations else 0

    # Runs per week for the last 8 weeks.
    now = datetime.utcnow()
    weeks = []
    for w in range(7, -1, -1):
        start = now - timedelta(days=(w + 1) * 7)
        end = now - timedelta(days=w * 7)
        weeks.append({
            "week_ending": end.date().isoformat(),
            "runs": runs_q.filter(ProtocolRun.started_at >= start,
                                  ProtocolRun.started_at < end).count(),
        })

    top = (
        db.session.query(ProtocolRun.protocol_title, func.count(ProtocolRun.id))
        .filter(ProtocolRun.account_id == account_id)
        .group_by(ProtocolRun.protocol_title)
        .order_by(func.count(ProtocolRun.id).desc())
        .limit(5)
        .all()
    )

    return jsonify({
        "success": True,
        "totals": {
            "protocols": protocols,
            "effective_sops": effective,
            "runs": total_runs,
            "completed_runs": completed_runs,
        },
        "outcomes": {
            "done": outcomes.get("done", 0),
            "failed": outcomes.get("failed", 0),
            "skipped": outcomes.get("skipped", 0),
            "pending": outcomes.get("pending", 0),
        },
        "avg_run_duration_seconds": avg_dur,
        "runs_by_week": weeks,
        "top_protocols": [{"title": t, "runs": n} for t, n in top],
    })


# ── Controlled-document lifecycle (SOP review / approval) ──

def _actor_name():
    return (g.current_user.name or "").strip() or g.current_user.email


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/submit", methods=["POST"])
@require_account_access
def submit_protocol(account_id, protocol_id):
    """Move a draft into review."""
    protocol = _get_protocol(account_id, protocol_id)
    if protocol is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404
    if protocol.status not in ("draft", "rejected"):
        return jsonify({"success": False, "error": "Only a draft can be submitted for review"}), 400
    if protocol.steps.count() == 0:
        return jsonify({"success": False, "error": "Add at least one step before submitting"}), 400
    protocol.status = "in_review"
    db.session.commit()
    return jsonify({"success": True, "protocol": protocol.to_dict(include_steps=True)})


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/sign", methods=["POST"])
@require_account_access
def sign_protocol(account_id, protocol_id):
    """Apply an electronic signature (review or approval).

    Identity is re-verified with the signer's password, and the signature
    records who / when / role / meaning / decision — an immutable audit trail.
    """
    protocol = _get_protocol(account_id, protocol_id)
    if protocol is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404

    data = request.get_json(silent=True) or {}
    role = (data.get("role") or "").lower()
    decision = (data.get("decision") or "approved").lower()
    if role not in ("reviewer", "approver"):
        return jsonify({"success": False, "error": "role must be reviewer or approver"}), 400
    if decision not in ("approved", "rejected"):
        return jsonify({"success": False, "error": "decision must be approved or rejected"}), 400
    if protocol.status != "in_review":
        return jsonify({"success": False, "error": "This protocol is not open for signing"}), 400
    # Approval is a manager action.
    if role == "approver" and not has_account_role(g.current_user, account_id, MANAGER_ROLES):
        return jsonify({"success": False, "error": "Only owners or admins can approve"}), 403

    # 21 CFR Part 11: confirm the signer's identity at the moment of signing.
    password = data.get("password") or ""
    if not g.current_user.check_password(password):
        return jsonify({"success": False, "error": "Invalid password — e-signature not applied"}), 401

    signoff = ProtocolSignoff(
        protocol_id=protocol_id,
        role=role,
        decision=decision,
        meaning=(data.get("meaning") or DEFAULT_MEANING.get(role, ""))[:300],
        comment=data.get("comment") or "",
        signed_by=_actor_name(),
        signed_by_user_id=g.current_user.id,
    )
    db.session.add(signoff)

    # An approver's decision moves the document.
    if role == "approver":
        protocol.status = "approved" if decision == "approved" else "rejected"

    db.session.commit()
    return jsonify({"success": True, "protocol": protocol.to_dict(include_steps=True)})


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/make-effective", methods=["POST"])
@require_account_access
def make_effective(account_id, protocol_id):
    """Release an approved SOP as the effective (current) version."""
    protocol = _get_protocol(account_id, protocol_id)
    if protocol is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404
    if not has_account_role(g.current_user, account_id, MANAGER_ROLES):
        return jsonify({"success": False, "error": "Only owners or admins can release an SOP"}), 403
    if protocol.status != "approved":
        return jsonify({"success": False, "error": "Only an approved protocol can be made effective"}), 400

    data = request.get_json(silent=True) or {}
    protocol.status = "effective"
    protocol.effective_date = (data.get("effective_date") or datetime.utcnow().date().isoformat())[:30]
    if data.get("review_date"):
        protocol.review_date = data["review_date"][:30]

    # A new effective version retires the one it supersedes.
    if protocol.supersedes_id:
        prior = Protocol.query.filter_by(id=protocol.supersedes_id, account_id=account_id).first()
        if prior and prior.status == "effective":
            prior.status = "retired"

    db.session.commit()
    return jsonify({"success": True, "protocol": protocol.to_dict(include_steps=True)})


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/retire", methods=["POST"])
@require_account_access
def retire_protocol(account_id, protocol_id):
    protocol = _get_protocol(account_id, protocol_id)
    if protocol is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404
    if not has_account_role(g.current_user, account_id, MANAGER_ROLES):
        return jsonify({"success": False, "error": "Only owners or admins can retire an SOP"}), 403
    if protocol.status not in ("effective", "approved"):
        return jsonify({"success": False, "error": "Only an effective or approved protocol can be retired"}), 400
    protocol.status = "retired"
    db.session.commit()
    return jsonify({"success": True, "protocol": protocol.to_dict(include_steps=True)})


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/new-version", methods=["POST"])
@require_account_access
def new_version(account_id, protocol_id):
    """Draft a new version: clone the protocol + steps, bump version, supersede."""
    source = _get_protocol(account_id, protocol_id)
    if source is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404

    clone = Protocol(
        account_id=account_id,
        title=source.title,
        description=source.description,
        protocol_type=source.protocol_type,
        status="draft",
        version=source.version + 1,
        created_by=_actor_name(),
        sop_number=source.sop_number,
        department=source.department,
        review_date=source.review_date,
        supersedes_id=source.id,
    )
    db.session.add(clone)
    db.session.flush()
    for step in source.steps:
        db.session.add(ProtocolStep(
            protocol_id=clone.id,
            order_index=step.order_index,
            section=step.section,
            title=step.title,
            description=step.description,
            duration_seconds=step.duration_seconds,
            warning=step.warning,
            reagents_json=step.reagents_json,
            components_json=step.components_json,
            branch_json=step.branch_json,
        ))
    db.session.commit()
    return jsonify({"success": True, "protocol": clone.to_dict(include_steps=True)}), 201
