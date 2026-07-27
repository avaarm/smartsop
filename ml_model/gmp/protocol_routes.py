"""Flask Blueprint for protocols.io-style protocols (authoring + steps).

All routes are account-scoped and require membership (require_account_access).
"""

import calendar
import json
import logging
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, g
from sqlalchemy import func

from .database import (
    db, Protocol, ProtocolStep, ProtocolRun, ProtocolRunStep, ProtocolSignoff, Deviation,
    Assignment, TrainingRecord,
)
from .auth import require_account_access, has_account_role
from .protocol_import import extract_text, split_into_steps, ai_structure
from .templates import template_summaries, get_template
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

# Deviation / corrective-action (CAPA) tracking.
DEVIATION_SEVERITIES = ("minor", "major", "critical")
DEVIATION_STATUSES = ("open", "investigating", "resolved", "closed")
DEVIATION_CLOSED_STATUSES = ("resolved", "closed")

# Scheduling / assignments.
ASSIGNMENT_STATUSES = ("pending", "completed", "cancelled")
ASSIGNMENT_RECURRENCES = ("none", "daily", "weekly", "monthly")

# Training / competency.
TRAINING_VALID_DAYS = 365          # default re-certification interval
DEFAULT_ACK = "I have read and understood this procedure"
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


@protocol_bp.route("/<int:account_id>/protocols/templates", methods=["GET"])
@require_account_access
def list_templates(account_id):
    """The regulatory template gallery — prebuilt SOPs a workspace can start from."""
    return jsonify({"success": True, "templates": template_summaries()})


@protocol_bp.route("/<int:account_id>/protocols/from-template", methods=["POST"])
@require_account_access
def create_from_template(account_id):
    """Instantiate a regulatory template as a new draft protocol.

    The copy is a normal draft: it still has to go through review and approval
    before it can be made effective.
    """
    data = request.get_json(silent=True) or {}
    template = get_template((data.get("key") or "").strip())
    if template is None:
        return jsonify({"success": False, "error": "Unknown template"}), 404

    author = (g.current_user.name or "").strip() or g.current_user.email
    protocol = Protocol(
        account_id=account_id,
        title=(data.get("title") or template["name"])[:500],
        description=template["description"],
        protocol_type=template["protocol_type"],
        created_by=author,
    )
    db.session.add(protocol)
    db.session.flush()

    for i, step in enumerate(template["steps"]):
        db.session.add(ProtocolStep(
            protocol_id=protocol.id,
            order_index=i,
            title=step.get("title", "")[:500],
            description=step.get("description", ""),
            warning=step.get("warning", ""),
            duration_seconds=step.get("duration_seconds"),
            components_json=json.dumps(_clean_components(step.get("components"))),
            branch_json=_clean_branch(step.get("branch")),
        ))
    db.session.commit()
    logger.info("Protocol created from template %s (account=%s)", template["key"], account_id)
    return jsonify({
        "success": True,
        "protocol": protocol.to_dict(include_steps=True),
        "template": {"key": template["key"], "standard": template["standard"]},
    }), 201


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


def _new_run(account_id, protocol, experiment_id=""):
    """Create a run and snapshot the protocol's steps (flushed, not committed).

    Returns the run, or None if the protocol has no steps to run.
    """
    steps = protocol.steps.all()
    if not steps:
        return None
    run = ProtocolRun(
        account_id=account_id,
        protocol_id=protocol.id,
        protocol_title=protocol.title,
        protocol_version=protocol.version,
        experiment_id=(experiment_id or "")[:200],
        started_by=_actor_name(),
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
    return run


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/runs", methods=["POST"])
@require_account_access
def start_run(account_id, protocol_id):
    """Start a run: snapshot the protocol's steps so later edits don't rewrite history."""
    protocol = _get_protocol(account_id, protocol_id)
    if protocol is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404

    data = request.get_json(silent=True) or {}
    run = _new_run(account_id, protocol, data.get("experiment_id"))
    if run is None:
        return jsonify({"success": False, "error": "Cannot run a protocol with no steps"}), 400
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

    # Deviation / CAPA rollup.
    dev_q = Deviation.query.filter_by(account_id=account_id)
    total_deviations = dev_q.count()
    open_deviations = dev_q.filter(
        Deviation.status.notin_(DEVIATION_CLOSED_STATUSES)
    ).count()
    sev_rows = (
        db.session.query(Deviation.severity, func.count(Deviation.id))
        .filter(Deviation.account_id == account_id)
        .group_by(Deviation.severity)
        .all()
    )
    sev = {s: n for s, n in sev_rows}

    return jsonify({
        "success": True,
        "totals": {
            "protocols": protocols,
            "effective_sops": effective,
            "runs": total_runs,
            "completed_runs": completed_runs,
            "deviations": total_deviations,
            "open_deviations": open_deviations,
        },
        "outcomes": {
            "done": outcomes.get("done", 0),
            "failed": outcomes.get("failed", 0),
            "skipped": outcomes.get("skipped", 0),
            "pending": outcomes.get("pending", 0),
        },
        "deviation_severity": {
            "minor": sev.get("minor", 0),
            "major": sev.get("major", 0),
            "critical": sev.get("critical", 0),
        },
        "avg_run_duration_seconds": avg_dur,
        "runs_by_week": weeks,
        "top_protocols": [{"title": t, "runs": n} for t, n in top],
    })


# ── Deviations / corrective actions (CAPA) ──

@protocol_bp.route("/<int:account_id>/deviations", methods=["GET"])
@require_account_access
def list_deviations(account_id):
    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(max(1, request.args.get("per_page", 20, type=int)), 100)
    query = Deviation.query.filter_by(account_id=account_id)

    status = request.args.get("status")
    if status == "open":
        query = query.filter(Deviation.status.notin_(DEVIATION_CLOSED_STATUSES))
    elif status in DEVIATION_STATUSES:
        query = query.filter_by(status=status)
    severity = request.args.get("severity")
    if severity in DEVIATION_SEVERITIES:
        query = query.filter_by(severity=severity)
    protocol_id = request.args.get("protocol_id", type=int)
    if protocol_id:
        query = query.filter_by(protocol_id=protocol_id)
    run_id = request.args.get("run_id", type=int)
    if run_id:
        query = query.filter_by(run_id=run_id)

    paginated = query.order_by(Deviation.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False)
    return jsonify({
        "success": True,
        "deviations": [d.to_dict() for d in paginated.items],
        "total": paginated.total,
        "page": paginated.page,
        "pages": paginated.pages,
    })


@protocol_bp.route("/<int:account_id>/deviations", methods=["POST"])
@require_account_access
def create_deviation(account_id):
    """Flag a deviation. Usually raised mid-run against a step, but a standalone
    deviation (no run/step) can also be logged."""
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"success": False, "error": "A title is required"}), 400

    severity = (data.get("severity") or "minor").lower()
    if severity not in DEVIATION_SEVERITIES:
        return jsonify({
            "success": False,
            "error": f"severity must be one of {', '.join(DEVIATION_SEVERITIES)}",
        }), 400

    # Resolve and validate the optional run / step context against this account.
    run_id = data.get("run_id")
    run = _get_run(account_id, run_id) if run_id else None
    if run_id and run is None:
        return jsonify({"success": False, "error": "Run not found"}), 404

    protocol_id = data.get("protocol_id") or (run.protocol_id if run else None)
    step_title = (data.get("step_title") or "")[:500]
    run_step_id = data.get("run_step_id")
    if run and run_step_id and not step_title:
        rstep = ProtocolRunStep.query.filter_by(id=run_step_id, run_id=run.id).first()
        if rstep is not None:
            step_title = rstep.title

    dev = Deviation(
        account_id=account_id,
        protocol_id=protocol_id,
        run_id=run.id if run else None,
        run_step_id=int(run_step_id) if isinstance(run_step_id, (int, float)) else None,
        step_title=step_title,
        title=title[:500],
        description=data.get("description") or "",
        severity=severity,
        corrective_action=data.get("corrective_action") or "",
        assigned_to=(data.get("assigned_to") or "")[:255],
        reported_by=_actor_name(),
        reported_by_user_id=g.current_user.id,
    )
    db.session.add(dev)
    db.session.commit()
    logger.info("Deviation flagged (account=%s, severity=%s)", account_id, severity)
    return jsonify({"success": True, "deviation": dev.to_dict()}), 201


@protocol_bp.route("/<int:account_id>/deviations/<int:deviation_id>", methods=["GET"])
@require_account_access
def get_deviation(account_id, deviation_id):
    dev = Deviation.query.filter_by(id=deviation_id, account_id=account_id).first()
    if dev is None:
        return jsonify({"success": False, "error": "Deviation not found"}), 404
    return jsonify({"success": True, "deviation": dev.to_dict()})


@protocol_bp.route("/<int:account_id>/deviations/<int:deviation_id>", methods=["PATCH"])
@require_account_access
def update_deviation(account_id, deviation_id):
    """Triage / resolve a deviation. Setting status to resolved/closed stamps
    resolved_at; reopening clears it."""
    dev = Deviation.query.filter_by(id=deviation_id, account_id=account_id).first()
    if dev is None:
        return jsonify({"success": False, "error": "Deviation not found"}), 404

    data = request.get_json(silent=True) or {}
    if "status" in data:
        status = (data.get("status") or "").lower()
        if status not in DEVIATION_STATUSES:
            return jsonify({
                "success": False,
                "error": f"status must be one of {', '.join(DEVIATION_STATUSES)}",
            }), 400
        dev.status = status
        dev.resolved_at = datetime.utcnow() if status in DEVIATION_CLOSED_STATUSES else None
    if "severity" in data:
        severity = (data.get("severity") or "").lower()
        if severity not in DEVIATION_SEVERITIES:
            return jsonify({
                "success": False,
                "error": f"severity must be one of {', '.join(DEVIATION_SEVERITIES)}",
            }), 400
        dev.severity = severity
    if "corrective_action" in data:
        dev.corrective_action = data.get("corrective_action") or ""
    if "assigned_to" in data:
        dev.assigned_to = (data.get("assigned_to") or "")[:255]
    if "title" in data and (data.get("title") or "").strip():
        dev.title = data["title"].strip()[:500]
    if "description" in data:
        dev.description = data.get("description") or ""

    db.session.commit()
    return jsonify({"success": True, "deviation": dev.to_dict()})


# ── Scheduling / assignments ──

def _actor_name():
    return (g.current_user.name or "").strip() or g.current_user.email


def _advance_due_date(iso_date, recurrence):
    """Next due date for a recurring assignment, or '' if not recurring/invalid."""
    if recurrence not in ("daily", "weekly", "monthly") or not iso_date:
        return ""
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d").date()
    except ValueError:
        return ""
    if recurrence == "daily":
        d = d + timedelta(days=1)
    elif recurrence == "weekly":
        d = d + timedelta(days=7)
    else:  # monthly — advance one month, clamping the day
        month = d.month % 12 + 1
        year = d.year + (1 if d.month == 12 else 0)
        day = min(d.day, calendar.monthrange(year, month)[1])
        d = datetime(year, month, day).date()
    return d.isoformat()


@protocol_bp.route("/<int:account_id>/assignments", methods=["GET"])
@require_account_access
def list_assignments(account_id):
    query = Assignment.query.filter_by(account_id=account_id)
    status = request.args.get("status")
    if status in ASSIGNMENT_STATUSES:
        query = query.filter_by(status=status)
    assignee = request.args.get("assigned_to")
    if assignee:
        query = query.filter_by(assigned_to=assignee)
    # Pending first (soonest due), then everything else newest-first.
    items = query.all()
    items.sort(key=lambda a: (
        a.status != "pending",
        a.due_date or "9999-12-31",
        -a.id,
    ))
    return jsonify({"success": True, "assignments": [a.to_dict() for a in items]})


@protocol_bp.route("/<int:account_id>/assignments", methods=["POST"])
@require_account_access
def create_assignment(account_id):
    data = request.get_json(silent=True) or {}
    protocol = _get_protocol(account_id, data.get("protocol_id"))
    if protocol is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404

    recurrence = (data.get("recurrence") or "none").lower()
    if recurrence not in ASSIGNMENT_RECURRENCES:
        return jsonify({
            "success": False,
            "error": f"recurrence must be one of {', '.join(ASSIGNMENT_RECURRENCES)}",
        }), 400

    a = Assignment(
        account_id=account_id,
        protocol_id=protocol.id,
        protocol_title=protocol.title,
        assigned_to=(data.get("assigned_to") or "")[:255],
        assigned_by=_actor_name(),
        due_date=(data.get("due_date") or "")[:30],
        recurrence=recurrence,
        notes=data.get("notes") or "",
    )
    db.session.add(a)
    db.session.commit()
    return jsonify({"success": True, "assignment": a.to_dict()}), 201


@protocol_bp.route("/<int:account_id>/assignments/<int:assignment_id>", methods=["GET"])
@require_account_access
def get_assignment(account_id, assignment_id):
    a = Assignment.query.filter_by(id=assignment_id, account_id=account_id).first()
    if a is None:
        return jsonify({"success": False, "error": "Assignment not found"}), 404
    return jsonify({"success": True, "assignment": a.to_dict()})


@protocol_bp.route("/<int:account_id>/assignments/<int:assignment_id>", methods=["PATCH"])
@require_account_access
def update_assignment(account_id, assignment_id):
    """Update an assignment. Completing a recurring one spawns the next occurrence."""
    a = Assignment.query.filter_by(id=assignment_id, account_id=account_id).first()
    if a is None:
        return jsonify({"success": False, "error": "Assignment not found"}), 404

    data = request.get_json(silent=True) or {}
    spawned = None
    if "status" in data:
        status = (data.get("status") or "").lower()
        if status not in ASSIGNMENT_STATUSES:
            return jsonify({
                "success": False,
                "error": f"status must be one of {', '.join(ASSIGNMENT_STATUSES)}",
            }), 400
        was_open = a.status == "pending"
        a.status = status
        a.completed_at = datetime.utcnow() if status == "completed" else None
        # Completing a recurring assignment schedules the next round.
        if status == "completed" and was_open and a.recurrence != "none":
            next_due = _advance_due_date(a.due_date, a.recurrence)
            if next_due:
                spawned = Assignment(
                    account_id=account_id,
                    protocol_id=a.protocol_id,
                    protocol_title=a.protocol_title,
                    assigned_to=a.assigned_to,
                    assigned_by=a.assigned_by,
                    due_date=next_due,
                    recurrence=a.recurrence,
                    notes=a.notes,
                )
                db.session.add(spawned)
    if "assigned_to" in data:
        a.assigned_to = (data.get("assigned_to") or "")[:255]
    if "due_date" in data:
        a.due_date = (data.get("due_date") or "")[:30]
    if "recurrence" in data:
        recurrence = (data.get("recurrence") or "none").lower()
        if recurrence not in ASSIGNMENT_RECURRENCES:
            return jsonify({"success": False, "error": "Invalid recurrence"}), 400
        a.recurrence = recurrence
    if "notes" in data:
        a.notes = data.get("notes") or ""

    db.session.commit()
    body = {"success": True, "assignment": a.to_dict()}
    if spawned is not None:
        body["next_occurrence"] = spawned.to_dict()
    return jsonify(body)


@protocol_bp.route("/<int:account_id>/assignments/<int:assignment_id>", methods=["DELETE"])
@require_account_access
def delete_assignment(account_id, assignment_id):
    a = Assignment.query.filter_by(id=assignment_id, account_id=account_id).first()
    if a is None:
        return jsonify({"success": False, "error": "Assignment not found"}), 404
    db.session.delete(a)
    db.session.commit()
    return jsonify({"success": True})


@protocol_bp.route("/<int:account_id>/assignments/<int:assignment_id>/start", methods=["POST"])
@require_account_access
def start_assignment(account_id, assignment_id):
    """Start a run of the assignment's SOP and link it to the assignment."""
    a = Assignment.query.filter_by(id=assignment_id, account_id=account_id).first()
    if a is None:
        return jsonify({"success": False, "error": "Assignment not found"}), 404
    protocol = _get_protocol(account_id, a.protocol_id)
    if protocol is None:
        return jsonify({"success": False, "error": "The assigned protocol no longer exists"}), 404

    run = _new_run(account_id, protocol)
    if run is None:
        return jsonify({"success": False, "error": "Cannot run a protocol with no steps"}), 400
    a.run_id = run.id
    db.session.commit()
    return jsonify({"success": True, "run": run.to_dict(include_steps=True),
                    "assignment": a.to_dict()}), 201


# ── Training / competency ──

@protocol_bp.route("/<int:account_id>/competency", methods=["GET"])
@require_account_access
def list_competency(account_id):
    query = TrainingRecord.query.filter_by(account_id=account_id)
    protocol_id = request.args.get("protocol_id", type=int)
    if protocol_id:
        query = query.filter_by(protocol_id=protocol_id)
    trainee = request.args.get("trainee")
    if trainee:
        query = query.filter_by(trainee=trainee)

    records = query.order_by(TrainingRecord.created_at.desc()).all()
    if request.args.get("status") == "assigned":
        records = [r for r in records if r.status == "assigned"]
    elif request.args.get("status") == "current":
        records = [r for r in records if r.is_current()]
    elif request.args.get("status") == "expired":
        records = [r for r in records if r.is_expired()]

    return jsonify({"success": True, "training": [r.to_dict() for r in records]})


@protocol_bp.route("/<int:account_id>/competency", methods=["POST"])
@require_account_access
def assign_competency(account_id):
    data = request.get_json(silent=True) or {}
    protocol = _get_protocol(account_id, data.get("protocol_id"))
    if protocol is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404
    trainee = (data.get("trainee") or "").strip()
    if not trainee:
        return jsonify({"success": False, "error": "A trainee is required"}), 400

    rec = TrainingRecord(
        account_id=account_id,
        protocol_id=protocol.id,
        protocol_title=protocol.title,
        protocol_version=protocol.version,
        trainee=trainee[:255],
        assigned_by=_actor_name(),
        expires_at=(data.get("expires_at") or "")[:30],
    )
    db.session.add(rec)
    db.session.commit()
    return jsonify({"success": True, "training": rec.to_dict()}), 201


@protocol_bp.route("/<int:account_id>/competency/<int:record_id>/acknowledge", methods=["POST"])
@require_account_access
def acknowledge_competency(account_id, record_id):
    """Record read-and-understood. Sets the expiry to +1 year if not given."""
    rec = TrainingRecord.query.filter_by(id=record_id, account_id=account_id).first()
    if rec is None:
        return jsonify({"success": False, "error": "Training record not found"}), 404

    data = request.get_json(silent=True) or {}
    now = datetime.utcnow()
    rec.status = "acknowledged"
    rec.acknowledged_at = now
    rec.acknowledgement = (data.get("acknowledgement") or DEFAULT_ACK)[:300]
    # Re-certification date: explicit, else one year out.
    rec.expires_at = (data.get("expires_at")
                      or (now.date() + timedelta(days=TRAINING_VALID_DAYS)).isoformat())[:30]
    db.session.commit()
    return jsonify({"success": True, "training": rec.to_dict()})


@protocol_bp.route("/<int:account_id>/competency/<int:record_id>", methods=["DELETE"])
@require_account_access
def delete_competency(account_id, record_id):
    rec = TrainingRecord.query.filter_by(id=record_id, account_id=account_id).first()
    if rec is None:
        return jsonify({"success": False, "error": "Training record not found"}), 404
    db.session.delete(rec)
    db.session.commit()
    return jsonify({"success": True})


# ── Controlled-document lifecycle (SOP review / approval) ──


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
    _copy_steps(source, clone)
    db.session.commit()
    return jsonify({"success": True, "protocol": clone.to_dict(include_steps=True)}), 201


# ── Version history, diff, and rollback ──

def _copy_steps(source, dest):
    """Clone every step of `source` onto `dest` (dest must be flushed)."""
    for step in source.steps:
        db.session.add(ProtocolStep(
            protocol_id=dest.id,
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


def _version_chain(protocol):
    """Every protocol in this one's version lineage, ordered oldest → newest.

    Walks the supersedes chain backwards, then forwards, so any member of the
    chain returns the whole history.
    """
    account_id = protocol.account_id
    seen = {protocol.id: protocol}

    cur = protocol
    while cur.supersedes_id and cur.supersedes_id not in seen:
        prior = Protocol.query.filter_by(id=cur.supersedes_id, account_id=account_id).first()
        if prior is None:
            break
        seen[prior.id] = prior
        cur = prior

    frontier = list(seen.values())
    while frontier:
        node = frontier.pop()
        for child in Protocol.query.filter_by(supersedes_id=node.id, account_id=account_id).all():
            if child.id not in seen:
                seen[child.id] = child
                frontier.append(child)

    return sorted(seen.values(), key=lambda p: (p.version, p.id))


def _version_summary(p, current_id):
    return {
        "id": p.id,
        "version": p.version,
        "status": p.status,
        "created_by": p.created_by,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "effective_date": p.effective_date,
        "step_count": p.steps.count(),
        "is_current": p.id == current_id,
    }


STEP_DIFF_FIELDS = ("title", "description", "warning", "duration_seconds",
                    "reagents_json", "components_json", "branch_json")
STEP_FIELD_LABELS = {
    "reagents_json": "reagents", "components_json": "components", "branch_json": "branch",
    "duration_seconds": "duration",
}


def _diff_protocols(a, b):
    """Field- and step-level diff of version `a` → version `b`.

    Steps are matched by position: they carry no stable cross-version id, so an
    insertion mid-list shifts everything after it (reported honestly as changes).
    """
    meta = []
    for f in ("title", "description", "protocol_type", "sop_number", "department", "review_date"):
        av, bv = getattr(a, f) or "", getattr(b, f) or ""
        if av != bv:
            meta.append({"field": f, "from": av, "to": bv})

    a_steps, b_steps = a.steps.all(), b.steps.all()
    steps = []
    for i in range(max(len(a_steps), len(b_steps))):
        sa = a_steps[i] if i < len(a_steps) else None
        sb = b_steps[i] if i < len(b_steps) else None
        if sa is None:
            steps.append({"index": i, "change": "added", "title": sb.title})
        elif sb is None:
            steps.append({"index": i, "change": "removed", "title": sa.title})
        else:
            changed = [STEP_FIELD_LABELS.get(f, f) for f in STEP_DIFF_FIELDS
                       if (getattr(sa, f) or "") != (getattr(sb, f) or "")]
            if changed:
                steps.append({"index": i, "change": "modified",
                              "title": sb.title, "fields": changed})
            else:
                steps.append({"index": i, "change": "unchanged", "title": sb.title})
    return {"meta_changes": meta, "steps": steps}


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/versions", methods=["GET"])
@require_account_access
def list_versions(account_id, protocol_id):
    """The full version history for a protocol's lineage."""
    protocol = _get_protocol(account_id, protocol_id)
    if protocol is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404
    chain = _version_chain(protocol)
    return jsonify({
        "success": True,
        "versions": [_version_summary(p, protocol_id) for p in chain],
    })


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/diff", methods=["GET"])
@require_account_access
def diff_versions(account_id, protocol_id):
    """Diff two versions. `from`/`to` are protocol ids; defaults compare the
    given protocol against the version it supersedes."""
    to_id = request.args.get("to", type=int) or protocol_id
    to_p = _get_protocol(account_id, to_id)
    if to_p is None:
        return jsonify({"success": False, "error": "Target version not found"}), 404

    from_id = request.args.get("from", type=int) or to_p.supersedes_id
    if not from_id:
        return jsonify({"success": False, "error": "No earlier version to compare against"}), 400
    from_p = _get_protocol(account_id, from_id)
    if from_p is None:
        return jsonify({"success": False, "error": "Base version not found"}), 404

    return jsonify({
        "success": True,
        "from": _version_summary(from_p, protocol_id),
        "to": _version_summary(to_p, protocol_id),
        "diff": _diff_protocols(from_p, to_p),
    })


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/restore", methods=["POST"])
@require_account_access
def restore_version(account_id, protocol_id):
    """Roll back to a prior version's content.

    Controlled documents are never mutated in place, so a rollback drafts a new
    version (superseding the current head) whose steps are copied from the
    chosen source version.
    """
    data = request.get_json(silent=True) or {}
    source_id = data.get("source_id")
    source = _get_protocol(account_id, source_id) if source_id else None
    if source is None:
        return jsonify({"success": False, "error": "Source version not found"}), 404

    chain = _version_chain(_get_protocol(account_id, protocol_id))
    if source.id not in {p.id for p in chain}:
        return jsonify({"success": False, "error": "That version is not in this lineage"}), 400

    head = chain[-1]  # highest version
    clone = Protocol(
        account_id=account_id,
        title=source.title,
        description=source.description,
        protocol_type=source.protocol_type,
        status="draft",
        version=head.version + 1,
        created_by=_actor_name(),
        sop_number=source.sop_number,
        department=source.department,
        review_date=source.review_date,
        supersedes_id=head.id,
    )
    db.session.add(clone)
    db.session.flush()
    _copy_steps(source, clone)
    db.session.commit()
    logger.info("Restored v%s content as draft v%s (account=%s)",
                source.version, clone.version, account_id)
    return jsonify({
        "success": True,
        "protocol": clone.to_dict(include_steps=True),
        "restored_from": source.version,
    }), 201
