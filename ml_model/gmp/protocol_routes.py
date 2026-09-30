"""Flask Blueprint for protocols.io-style protocols (authoring + steps).

All routes are account-scoped and require membership (require_account_access).
"""

import calendar
import json
import logging
import re
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, g
from sqlalchemy import func

from .database import (
    db, Protocol, ProtocolStep, ProtocolRun, ProtocolRunStep, ProtocolSignoff, Deviation,
    Assignment, TrainingRecord, Comment, AuditEvent, User,
)
from .auth import require_account_access, has_account_role, has_account_access
from .protocol_import import (
    extract_text, split_into_steps, ai_structure, extract_structured, _structured_from_text,
    extract_document, _document_from_text,
)
from .templates import template_summaries, get_template
from .doc_taxonomy import GMP_CATEGORIES, is_valid as _is_valid_category, category_name
from .doc_templates import doc_template_summaries, get_doc_template
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


VAR_RE = re.compile(r"\{\{\s*([\w .\-/#]+?)\s*\}\}")


def _protocol_variables(protocol):
    """Unique {{placeholder}} names found across a protocol's text, in order."""
    seen = []

    def scan(text):
        for m in VAR_RE.finditer(text or ""):
            name = m.group(1).strip()
            if name and name not in seen:
                seen.append(name)

    scan(protocol.title)
    scan(protocol.description)
    for s in protocol.steps:
        scan(s.section)
        scan(s.title)
        scan(s.description)
    # Document-format protocols carry their content in body_json, not steps.
    if protocol.body_json:
        try:
            for b in json.loads(protocol.body_json):
                if b.get("type") == "table":
                    for row in b.get("rows", []):
                        for cell in row:
                            scan(cell)
                else:
                    scan(b.get("text"))
        except ValueError:
            pass
    return seen


def _apply_variables(text, variables):
    """Substitute {{key}} with its value; unknown placeholders are left intact."""
    if not text or not variables:
        return text
    return VAR_RE.sub(lambda m: str(variables.get(m.group(1).strip(), m.group(0))), text)


def _next_document_number(account_id, code):
    """Next controlled-document number for a category, e.g. EQ-002 (DC-002 style).

    Scans existing working documents in that category and returns the code plus
    the next zero-padded sequence. Templates don't consume numbers.
    """
    code = (code or "").strip().upper()
    if not code:
        return ""
    rows = (db.session.query(Protocol.document_number)
            .filter(Protocol.account_id == account_id,
                    Protocol.doc_category == code,
                    Protocol.is_template.is_(False),
                    Protocol.document_number != "").all())
    mx = 0
    pat = re.compile(rf"^{re.escape(code)}-(\d+)$")
    for (dn,) in rows:
        m = pat.match(dn or "")
        if m:
            mx = max(mx, int(m.group(1)))
    return f"{code}-{mx + 1:03d}"


def _assign_document_number(protocol):
    """Give a working document its next number for its category, if it lacks one."""
    if (not protocol.is_template and protocol.doc_category
            and not (protocol.document_number or "").strip()):
        protocol.document_number = _next_document_number(protocol.account_id, protocol.doc_category)


def _apply_variables_to_blocks(blocks, variables):
    """Substitute {{key}} throughout document blocks (headings, paragraphs, cells)."""
    if not variables:
        return blocks
    out = []
    for b in blocks:
        b = dict(b)
        if b.get("type") == "table":
            b["rows"] = [[_apply_variables(c, variables) for c in row] for row in b.get("rows", [])]
        elif "text" in b:
            b["text"] = _apply_variables(b["text"], variables)
        out.append(b)
    return out


def record_audit(account_id, action, entity_type="", entity_id=None, summary="", detail=None):
    """Append an immutable audit-trail entry to the current session.

    Adds (does not commit) so the entry is persisted atomically with the action
    that produced it by the caller's existing commit.
    """
    ev = AuditEvent(
        account_id=account_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=(summary or "")[:500],
        detail_json=json.dumps(detail) if detail else "",
        actor=_actor_name(),
        actor_user_id=g.current_user.id,
    )
    db.session.add(ev)
    return ev


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

    query = Protocol.query.filter_by(account_id=account_id)

    # Templates live in their own library; keep them out of the working list
    # unless explicitly requested with ?templates=true.
    want_templates = request.args.get("templates") == "true"
    query = query.filter_by(is_template=want_templates)

    # SOP Finder: match the query across the protocol's own fields AND its step
    # text, so searching a term that appears inside a step still surfaces it.
    q = (request.args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        step_match = (
            db.session.query(ProtocolStep.protocol_id)
            .filter(db.or_(ProtocolStep.title.ilike(like),
                           ProtocolStep.description.ilike(like),
                           ProtocolStep.section.ilike(like)))
            .subquery()
        )
        query = query.filter(db.or_(
            Protocol.title.ilike(like),
            Protocol.description.ilike(like),
            Protocol.sop_number.ilike(like),
            Protocol.department.ilike(like),
            Protocol.id.in_(db.session.query(step_match.c.protocol_id)),
        ))

    paginated = (
        query.order_by(Protocol.updated_at.desc())
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
    db.session.flush()
    record_audit(account_id, "protocol.created", "protocol", protocol.id,
                 f"Created “{protocol.title}”")
    db.session.commit()
    return jsonify({"success": True, "protocol": protocol.to_dict(include_steps=True)}), 201


@protocol_bp.route("/<int:account_id>/protocols/templates", methods=["GET"])
@require_account_access
def list_templates(account_id):
    """The regulatory template gallery — prebuilt SOPs a workspace can start from."""
    return jsonify({"success": True, "templates": template_summaries()})


@protocol_bp.route("/<int:account_id>/protocols/doc-templates", methods=["GET"])
@require_account_access
def list_doc_templates(account_id):
    """Built-in facility document templates (batch records, test methods, etc.),
    structured per the facility's own SOPs — the 'what do you want to write?'
    starting points. Optionally filter to one category with ?category=BR."""
    cat = (request.args.get("category") or "").strip().upper()
    templates = doc_template_summaries()
    if cat:
        templates = [t for t in templates if t["doc_category"] == cat]
    return jsonify({"success": True, "templates": templates})


@protocol_bp.route("/<int:account_id>/protocols/from-doc-template", methods=["POST"])
@require_account_access
def create_from_doc_template(account_id):
    """Start a new document from a built-in facility template, with any
    {{fill-in}} fields substituted. Lands as a draft for the normal lifecycle."""
    data = request.get_json(silent=True) or {}
    template = get_doc_template((data.get("key") or "").strip())
    if template is None:
        return jsonify({"success": False, "error": "Unknown template"}), 404
    variables = data.get("variables") if isinstance(data.get("variables"), dict) else None
    # Default the title to the template's first heading (it often carries the
    # {{product}} / {{method_name}} placeholder) so filling variables names the doc.
    default_title = template["name"]
    for b in template.get("body", []):
        if b.get("type") == "heading":
            default_title = b.get("text", default_title)
            break
    title = (data.get("title") or default_title)[:500]
    if variables:
        title = _apply_variables(title, variables)[:500]

    author = (g.current_user.name or "").strip() or g.current_user.email
    protocol = Protocol(
        account_id=account_id,
        title=title,
        description=template.get("description", ""),
        protocol_type=template["protocol_type"],
        created_by=author,
        doc_category=template.get("doc_category", ""),
        doc_format=template.get("doc_format", "steps"),
    )
    if template.get("doc_format") == "document":
        blocks = template.get("body", [])
        if variables:
            blocks = _apply_variables_to_blocks(blocks, variables)
        protocol.body_json = json.dumps(blocks)
    db.session.add(protocol)
    db.session.flush()
    _assign_document_number(protocol)
    if template.get("doc_format") != "document":
        for i, step in enumerate(template.get("steps", [])):
            db.session.add(ProtocolStep(
                protocol_id=protocol.id, order_index=i,
                section=_apply_variables(step.get("section", ""), variables),
                title=_apply_variables(step.get("title", ""), variables)[:500],
                description=_apply_variables(step.get("description", ""), variables),
                warning=step.get("warning", ""),
                duration_seconds=step.get("duration_seconds"),
            ))
    record_audit(account_id, "protocol.created", "protocol", protocol.id,
                 f"Started “{protocol.title}” from the {template['name']} template")
    db.session.commit()
    logger.info("Protocol created from doc-template %s (account=%s)", template["key"], account_id)
    return jsonify({"success": True, "protocol": protocol.to_dict(include_steps=True)}), 201


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
    file_bytes = None
    file_name = ""
    if upload is not None:
        file_name = upload.filename or ""
        file_bytes = upload.read()
        text = extract_text(file_name, file_bytes)
        title = (request.form.get("title") or "").strip()
        # Uploaded files are almost always real documents (batch records, CMC
        # sections, forms), so default to document-fidelity — keep tables,
        # headings and checkboxes 1-to-1 instead of flattening them into steps.
        mode = (request.form.get("mode") or "document").lower()
        as_template = request.form.get("as_template") in ("true", "1", "yes")
        category = (request.form.get("category") or "").strip()[:120]
        doc_category = (request.form.get("doc_category") or "").strip().upper()[:10]
        product_code = (request.form.get("product_code") or "").strip()[:60]
        if not title:
            base = file_name.rsplit(".", 1)[0].replace("_", " ").strip()
            title = base[:500] or "Imported document"
    else:
        data = request.get_json(silent=True) or {}
        text = data.get("text") or ""
        title = (data.get("title") or "").strip() or "Imported document"
        mode = (data.get("mode") or "numbered").lower()
        as_template = bool(data.get("as_template"))
        category = (data.get("category") or "").strip()[:120]
        doc_category = (data.get("doc_category") or "").strip().upper()[:10]
        product_code = (data.get("product_code") or "").strip()[:60]
    if doc_category and not _is_valid_category(doc_category):
        doc_category = ""

    # ── Document-fidelity mode ──────────────────────────────────────────────
    # Keep the upload as a real document — headings, paragraphs, tables and
    # checkboxes preserved 1-to-1 — instead of mangling it into a step list.
    # The original file is stored so a filled copy exports byte-faithfully.
    if mode == "document":
        if file_bytes is not None:
            doc_data = extract_document(file_name, file_bytes)
        else:
            doc_data = _document_from_text(text)
        blocks = doc_data.get("blocks") or []
        if not blocks:
            return jsonify({"success": False, "error": "Could not read any content from the file"}), 400
        author = (g.current_user.name or "").strip() or g.current_user.email
        protocol = Protocol(
            account_id=account_id, title=title[:500], created_by=author,
            description="",
            doc_format="document", body_json=json.dumps(blocks),
            original_filename=(file_name or "")[:300],
            is_template=as_template,
            template_category=(category or "General") if as_template else "",
            doc_category=doc_category, product_code=product_code,
        )
        if file_bytes is not None and (file_name or "").lower().endswith(".docx"):
            protocol.original_file = file_bytes
        db.session.add(protocol)
        db.session.flush()
        _assign_document_number(protocol)
        if as_template:
            record_audit(account_id, "template.created", "protocol", protocol.id,
                         f"Imported “{protocol.title}” into the {protocol.template_category} template library")
        db.session.commit()
        return jsonify({
            "success": True,
            "protocol": protocol.to_dict(include_steps=True),
            "mode": "document",
            "block_count": len(blocks),
        }), 201

    if not text.strip():
        return jsonify({"success": False, "error": "No text to import"}), 400

    used = mode
    if mode == "structured":
        # 1-to-1 structural extraction — preserve headings/sections, full body,
        # and tables. Best for real documents (CMC, batch records, SOPs).
        if file_bytes is not None:
            steps = extract_structured(file_name, file_bytes)
        else:
            steps = _structured_from_text(text)
            steps = [s for s in steps if s.get("section") or s.get("title") or s.get("description")]
    elif mode == "ai":
        steps = ai_structure(text, getattr(get_generator(), "ollama", None))
        if steps is None:
            steps = extract_structured(file_name, file_bytes) if file_bytes is not None \
                else split_into_steps(text, "numbered")
            used = "structured (AI unavailable)"
    else:
        if mode not in ("numbered", "lines", "markdown"):
            mode = used = "numbered"
        steps = split_into_steps(text, mode)

    if not steps:
        return jsonify({"success": False, "error": "Could not extract any content from the input"}), 400

    author = (g.current_user.name or "").strip() or g.current_user.email
    protocol = Protocol(
        account_id=account_id, title=title[:500], created_by=author,
        is_template=as_template, template_category=(category or "General") if as_template else "",
        doc_category=doc_category, product_code=product_code,
    )
    db.session.add(protocol)
    db.session.flush()
    _assign_document_number(protocol)
    for i, s in enumerate(steps):
        db.session.add(ProtocolStep(
            protocol_id=protocol.id, order_index=i,
            section=s.get("section", ""),
            title=s.get("title", ""), description=s.get("description", ""),
            duration_seconds=s.get("duration_seconds"), warning=s.get("warning", ""),
        ))
    if as_template:
        record_audit(account_id, "template.created", "protocol", protocol.id,
                     f"Imported “{protocol.title}” into the {protocol.template_category} template library")
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


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/template-variables", methods=["GET"])
@require_account_access
def template_variables(account_id, protocol_id):
    """The {{placeholders}} in a template, so 'use' can prompt to fill them in."""
    protocol = _get_protocol(account_id, protocol_id)
    if protocol is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404
    return jsonify({"success": True, "variables": _protocol_variables(protocol)})


@protocol_bp.route("/<int:account_id>/protocols/doc-categories", methods=["GET"])
@require_account_access
def doc_categories(account_id):
    """The facility's document taxonomy with, per category, how many of the org's
    own templates and how many effective documents exist — so 'what do you want
    to write?' shows exactly what's available to start from."""
    tpl_counts = dict(
        db.session.query(Protocol.doc_category, func.count(Protocol.id))
        .filter(Protocol.account_id == account_id, Protocol.is_template.is_(True))
        .group_by(Protocol.doc_category).all()
    )
    eff_counts = dict(
        db.session.query(Protocol.doc_category, func.count(Protocol.id))
        .filter(Protocol.account_id == account_id, Protocol.is_template.is_(False),
                Protocol.status == "effective")
        .group_by(Protocol.doc_category).all()
    )
    cats = []
    for c in GMP_CATEGORIES:
        cats.append({**c,
                     "template_count": int(tpl_counts.get(c["code"], 0)),
                     "effective_count": int(eff_counts.get(c["code"], 0))})
    return jsonify({"success": True, "categories": cats})


@protocol_bp.route("/<int:account_id>/protocols/register", methods=["GET"])
@require_account_access
def document_register(account_id):
    """The controlled-document register — effective batch records grouped by
    protocol / part number, and effective procedures grouped by category —
    mirroring a facility's 'Controlled Documents' home page.

    ?status=effective (default) | approved | all — which documents to include.
    """
    status = (request.args.get("status") or "effective").lower()
    q = Protocol.query.filter_by(account_id=account_id, is_template=False)
    if status != "all":
        q = q.filter(Protocol.status == status)
    docs = q.order_by(Protocol.document_number, Protocol.title).all()

    def row(p):
        return {
            "id": p.id,
            "document_number": p.document_number or "",
            "title": p.title,
            "version": p.version,
            "status": p.status,
            "effective_date": p.effective_date or "",
            "doc_category": p.doc_category or "",
            "product_code": p.product_code or "",
        }

    br_groups, proc_groups = {}, {}
    for p in docs:
        r = row(p)
        if (p.doc_category or "") == "BR":
            br_groups.setdefault(p.product_code or "General (Formulation)", []).append(r)
        else:
            proc_groups.setdefault(p.doc_category or "—", []).append(r)

    batch_records = [{"group": k, "items": v} for k, v in sorted(br_groups.items())]
    procedures = [{"code": k, "name": (category_name(k) if k != "—" else "Uncategorized"), "items": v}
                  for k, v in sorted(proc_groups.items())]
    return jsonify({"success": True, "status": status,
                    "batch_records": batch_records, "procedures": procedures})


def _export_filename(protocol, ext):
    slug = "".join(c if c.isalnum() else "-" for c in (protocol.title or "protocol")).strip("-").lower()
    return f"{slug or 'protocol'}-v{protocol.version}.{ext}"


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/export.json", methods=["GET"])
@require_account_access
def export_protocol_json(account_id, protocol_id):
    """Download the protocol as JSON — machine-readable archive / backup."""
    protocol = _get_protocol(account_id, protocol_id)
    if protocol is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404
    payload = json.dumps(protocol.to_dict(include_steps=True), indent=2)
    return payload, 200, {
        "Content-Type": "application/json",
        "Content-Disposition": f'attachment; filename="{_export_filename(protocol, "json")}"',
    }


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/export.pdf", methods=["GET"])
@require_account_access
def export_protocol_pdf(account_id, protocol_id):
    """Download the protocol as a printable PDF — the OSHA / ISO audit artifact."""
    protocol = _get_protocol(account_id, protocol_id)
    if protocol is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404
    from .protocol_export import protocol_to_pdf, document_to_pdf
    if (protocol.doc_format or "steps") == "document":
        buf = document_to_pdf(protocol.to_dict(include_steps=True))
    else:
        buf = protocol_to_pdf(protocol.to_dict(include_steps=True))
    return buf.read(), 200, {
        "Content-Type": "application/pdf",
        "Content-Disposition": f'attachment; filename="{_export_filename(protocol, "pdf")}"',
    }


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/original", methods=["GET"])
@require_account_access
def download_original(account_id, protocol_id):
    """Download the exact file that was uploaded — so you can always get your
    approved document back, byte-for-byte."""
    protocol = _get_protocol(account_id, protocol_id)
    if protocol is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404
    if not protocol.original_file:
        return jsonify({"success": False, "error": "No original file stored for this document"}), 404
    name = (protocol.original_filename or _export_filename(protocol, "docx")).replace('"', "")
    return protocol.original_file, 200, {
        "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "Content-Disposition": f'attachment; filename="{name}"',
    }


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/render.docx", methods=["POST"])
@require_account_access
def render_document_docx(account_id, protocol_id):
    """Fill {{variables}} into the document and download a Word file that matches
    the original's formatting — the real time-saver: reuse an approved doc,
    change only the project-specific fields."""
    protocol = _get_protocol(account_id, protocol_id)
    if protocol is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404
    data = request.get_json(silent=True) or {}
    variables = data.get("variables") if isinstance(data.get("variables"), dict) else {}
    from .protocol_docx import render_filled_docx
    buf = render_filled_docx(protocol, variables)
    if buf is None:
        return jsonify({"success": False, "error": "This document has no content to render"}), 400
    return buf.read(), 200, {
        "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "Content-Disposition": f'attachment; filename="{_export_filename(protocol, "docx")}"',
    }


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
    # Inline document editing: persist the edited blocks (adapt a template's
    # wording/tables for a new project) back to body_json.
    if "body" in data and isinstance(data.get("body"), list):
        protocol.body_json = json.dumps(data["body"])
    if "protocol_type" in data:
        ptype = (data.get("protocol_type") or "").lower()
        if ptype not in PROTOCOL_TYPES:
            return jsonify({"success": False, "error": f"protocol_type must be one of {', '.join(PROTOCOL_TYPES)}"}), 400
        protocol.protocol_type = ptype
    for field in ("sop_number", "department", "review_date"):
        if field in data:
            setattr(protocol, field, (data.get(field) or "")[:200])
    if "doc_category" in data:
        code = (data.get("doc_category") or "").strip().upper()[:10]
        protocol.doc_category = code if (not code or _is_valid_category(code)) else protocol.doc_category
        _assign_document_number(protocol)   # auto-number once categorized
    if "product_code" in data:
        protocol.product_code = (data.get("product_code") or "").strip()[:60]
    if "document_number" in data:           # explicit override wins
        protocol.document_number = (data.get("document_number") or "").strip()[:40]
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


def _unmet_run_step_gate(step):
    """Return an error message if a run step's completion gates aren't satisfied.

    A step flagged `verification_photo` needs a verification recorded; a step
    flagged `second_signature` needs a peer witness sign-off before it can be
    marked Done. Returns None when all required gates are met.
    """
    try:
        components = json.loads(step.components_json or "[]")
    except ValueError:
        components = []
    needs_photo = any(c.get("type") == "verification_photo" and c.get("value")
                      for c in components if isinstance(c, dict))
    needs_signature = any(c.get("type") == "second_signature" and c.get("value")
                          for c in components if isinstance(c, dict))
    if needs_photo and not (step.verification or "").strip():
        return "This step requires a verification photo before it can be completed."
    if needs_signature and not step.witnessed_by_user_id:
        return "This step requires a second-person signature before it can be completed."
    return None


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

    # ── Satisfy run-time gates (verification photo / second signature) ──
    if "verification" in data:
        step.verification = (data.get("verification") or "")[:2000]

    if data.get("witness_email") and data.get("witness_password"):
        witness = User.query.filter_by(email=data["witness_email"].strip().lower()).first()
        if witness is None or not witness.check_password(data["witness_password"]):
            return jsonify({"success": False, "error": "Witness credentials are invalid"}), 401
        if witness.id == g.current_user.id:
            return jsonify({"success": False, "error": "The witness must be a different person"}), 400
        if not has_account_access(witness, account_id):
            return jsonify({"success": False, "error": "The witness is not a member of this account"}), 403
        step.witnessed_by = (witness.name or "").strip() or witness.email
        step.witnessed_by_user_id = witness.id
        step.witnessed_at = datetime.utcnow()

    if "status" in data:
        status = (data.get("status") or "").lower()
        if status not in RUN_STEP_STATUSES:
            return jsonify({
                "success": False,
                "error": f"status must be one of {', '.join(RUN_STEP_STATUSES)}",
            }), 400

        # Gates only block *completion* (Done); Fail/Skip/pending are always allowed.
        if status == "done":
            gate_error = _unmet_run_step_gate(step)
            if gate_error:
                return jsonify({"success": False, "error": gate_error}), 400

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
    record_audit(account_id, "run.finished", "run", run.id,
                 f"Finished run of “{run.protocol_title}” (v{run.protocol_version})")
    db.session.commit()
    return jsonify({"success": True, "run": run.to_dict(include_steps=True)})


# ── Audit trail ──

@protocol_bp.route("/<int:account_id>/audit", methods=["GET"])
@require_account_access
def list_audit(account_id):
    """The account's audit trail — append-only, newest first, filterable."""
    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(max(1, request.args.get("per_page", 50, type=int)), 200)
    query = AuditEvent.query.filter_by(account_id=account_id)

    action = request.args.get("action")
    if action:
        query = query.filter_by(action=action)
    entity_type = request.args.get("entity_type")
    if entity_type:
        query = query.filter_by(entity_type=entity_type)

    paginated = query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False)
    return jsonify({
        "success": True,
        "events": [e.to_dict() for e in paginated.items],
        "total": paginated.total,
        "page": paginated.page,
        "pages": paginated.pages,
    })


@protocol_bp.route("/<int:account_id>/audit/export.csv", methods=["GET"])
@require_account_access
def export_audit_csv(account_id):
    """Download the full audit trail as CSV — the artifact handed to an auditor."""
    import csv
    import io
    events = (AuditEvent.query.filter_by(account_id=account_id)
              .order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc()).all())
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Timestamp (UTC)", "Actor", "Action", "Entity", "Entity ID", "Summary"])
    for e in events:
        writer.writerow([
            e.created_at.isoformat() if e.created_at else "",
            e.actor, e.action, e.entity_type, e.entity_id or "", e.summary,
        ])
    return buf.getvalue(), 200, {
        "Content-Type": "text/csv",
        "Content-Disposition": 'attachment; filename="audit-trail.csv"',
    }


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
    db.session.flush()
    record_audit(account_id, "deviation.created", "deviation", dev.id,
                 f"Flagged {severity} deviation: “{dev.title}”")
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
    newly_closed = False
    if "status" in data:
        status = (data.get("status") or "").lower()
        if status not in DEVIATION_STATUSES:
            return jsonify({
                "success": False,
                "error": f"status must be one of {', '.join(DEVIATION_STATUSES)}",
            }), 400
        newly_closed = (status in DEVIATION_CLOSED_STATUSES
                        and dev.status not in DEVIATION_CLOSED_STATUSES)
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

    if newly_closed:
        record_audit(account_id, "deviation.resolved", "deviation", dev.id,
                     f"Resolved deviation “{dev.title}” ({dev.status})")
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
    record_audit(account_id, "competency.acknowledged", "training", rec.id,
                 f"{rec.trainee} acknowledged training on “{rec.protocol_title}” "
                 f"(v{rec.protocol_version}); re-cert due {rec.expires_at}")
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


# ── Comments & collaboration ──

@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/comments", methods=["GET"])
@require_account_access
def list_comments(account_id, protocol_id):
    protocol = _get_protocol(account_id, protocol_id)
    if protocol is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404
    comments = (
        Comment.query.filter_by(account_id=account_id, protocol_id=protocol_id)
        .order_by(Comment.created_at.asc()).all()
    )
    return jsonify({"success": True, "comments": [c.to_dict() for c in comments]})


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/comments", methods=["POST"])
@require_account_access
def create_comment(account_id, protocol_id):
    protocol = _get_protocol(account_id, protocol_id)
    if protocol is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404

    data = request.get_json(silent=True) or {}
    body = (data.get("body") or "").strip()
    if not body:
        return jsonify({"success": False, "error": "A comment body is required"}), 400

    # An inline comment must point at a real step of this protocol.
    step_id = data.get("step_id")
    if step_id is not None:
        if ProtocolStep.query.filter_by(id=step_id, protocol_id=protocol_id).first() is None:
            return jsonify({"success": False, "error": "Step not found on this protocol"}), 404

    # A reply must answer a comment on the same protocol.
    parent_id = data.get("parent_id")
    if parent_id is not None:
        parent = Comment.query.filter_by(
            id=parent_id, protocol_id=protocol_id, account_id=account_id).first()
        if parent is None:
            return jsonify({"success": False, "error": "Parent comment not found"}), 404
        # Replies inherit the parent's anchor; keep threads one level deep.
        step_id = parent.step_id
        parent_id = parent.parent_id or parent.id

    comment = Comment(
        account_id=account_id,
        protocol_id=protocol_id,
        step_id=int(step_id) if isinstance(step_id, (int, float)) else None,
        parent_id=int(parent_id) if isinstance(parent_id, (int, float)) else None,
        body=body,
        author=_actor_name(),
        author_user_id=g.current_user.id,
    )
    db.session.add(comment)
    db.session.commit()
    return jsonify({"success": True, "comment": comment.to_dict()}), 201


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/comments/<int:comment_id>",
                   methods=["PATCH"])
@require_account_access
def update_comment(account_id, protocol_id, comment_id):
    """Edit the body (author only), or pin / resolve a thread (any member)."""
    comment = Comment.query.filter_by(
        id=comment_id, protocol_id=protocol_id, account_id=account_id).first()
    if comment is None:
        return jsonify({"success": False, "error": "Comment not found"}), 404

    data = request.get_json(silent=True) or {}
    is_author = comment.author_user_id == g.current_user.id

    if "body" in data:
        if not is_author:
            return jsonify({"success": False, "error": "Only the author can edit a comment"}), 403
        body = (data.get("body") or "").strip()
        if not body:
            return jsonify({"success": False, "error": "A comment body is required"}), 400
        comment.body = body
    if "is_pinned" in data:
        comment.is_pinned = bool(data.get("is_pinned"))
    if "resolved" in data:
        comment.resolved = bool(data.get("resolved"))
        if comment.resolved:
            comment.resolved_by = _actor_name()
            comment.resolved_at = datetime.utcnow()
        else:
            comment.resolved_by, comment.resolved_at = "", None

    db.session.commit()
    return jsonify({"success": True, "comment": comment.to_dict()})


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/comments/<int:comment_id>",
                   methods=["DELETE"])
@require_account_access
def delete_comment(account_id, protocol_id, comment_id):
    """Delete a comment. Author or an account manager, and its replies with it."""
    comment = Comment.query.filter_by(
        id=comment_id, protocol_id=protocol_id, account_id=account_id).first()
    if comment is None:
        return jsonify({"success": False, "error": "Comment not found"}), 404
    if comment.author_user_id != g.current_user.id and \
            not has_account_role(g.current_user, account_id, MANAGER_ROLES):
        return jsonify({"success": False, "error": "Only the author or a manager can delete"}), 403

    # Remove any replies to this comment too.
    Comment.query.filter_by(parent_id=comment.id, protocol_id=protocol_id).delete()
    db.session.delete(comment)
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
    record_audit(account_id, "protocol.submitted", "protocol", protocol.id,
                 f"Submitted “{protocol.title}” (v{protocol.version}) for review")
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

    record_audit(account_id, "protocol.signed", "protocol", protocol.id,
                 f"{role.capitalize()} e-signature ({decision}) on “{protocol.title}” "
                 f"(v{protocol.version})",
                 detail={"role": role, "decision": decision, "meaning": signoff.meaning})
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
            record_audit(account_id, "protocol.retired", "protocol", prior.id,
                         f"Superseded by v{protocol.version} of “{protocol.title}”")

    record_audit(account_id, "protocol.made_effective", "protocol", protocol.id,
                 f"Released “{protocol.title}” v{protocol.version} as effective "
                 f"(effective {protocol.effective_date})")
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
    record_audit(account_id, "protocol.retired", "protocol", protocol.id,
                 f"Retired “{protocol.title}” (v{protocol.version})")
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
    _copy_document_fields(source, clone)
    clone.document_number = source.document_number   # same doc, new revision
    record_audit(account_id, "protocol.new_version", "protocol", clone.id,
                 f"Drafted v{clone.version} of “{clone.title}” (from v{source.version})")
    db.session.commit()
    return jsonify({"success": True, "protocol": clone.to_dict(include_steps=True)}), 201


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/copy", methods=["POST"])
@require_account_access
def copy_protocol(account_id, protocol_id):
    """Fork a protocol into a new, independent draft (not a version in the chain).

    Unlike new-version, the copy has its own version-1 lineage — a fresh
    document you can adapt without touching the original's history.
    """
    source = _get_protocol(account_id, protocol_id)
    if source is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404

    data = request.get_json(silent=True) or {}
    # Fill-in variables: {{product}}, {{batch_number}}, … supplied when starting
    # a project from a template are substituted throughout the copy.
    variables = data.get("variables") if isinstance(data.get("variables"), dict) else None
    title = (data.get("title") or f"{source.title} (copy)")[:500]
    if variables:
        title = _apply_variables(title, variables)[:500]

    clone = Protocol(
        account_id=account_id,
        title=title,
        description=_apply_variables(source.description, variables),
        protocol_type=source.protocol_type,
        status="draft",
        version=1,
        created_by=_actor_name(),
        department=source.department,
    )
    db.session.add(clone)
    db.session.flush()
    _copy_steps(source, clone)
    _copy_document_fields(source, clone, variables)
    if variables:
        for st in clone.steps:
            st.section = _apply_variables(st.section, variables)
            st.title = _apply_variables(st.title, variables)
            st.description = _apply_variables(st.description, variables)
    db.session.commit()
    logger.info("Protocol %s forked to %s (account=%s)", protocol_id, clone.id, account_id)
    return jsonify({"success": True, "protocol": clone.to_dict(include_steps=True)}), 201


@protocol_bp.route("/<int:account_id>/protocols/<int:protocol_id>/save-as-template", methods=["POST"])
@require_account_access
def save_as_template(account_id, protocol_id):
    """Save a copy of this document into the org's reusable template library.

    The original stays a working document; the template is a pristine, document-
    type-categorized copy you start future projects from.
    """
    source = _get_protocol(account_id, protocol_id)
    if source is None:
        return jsonify({"success": False, "error": "Protocol not found"}), 404

    data = request.get_json(silent=True) or {}
    category = (data.get("category") or source.template_category or "General")[:120]
    title = (data.get("title") or source.title)[:500]
    doc_cat = (data.get("doc_category") or "").strip().upper()[:10]
    if doc_cat and not _is_valid_category(doc_cat):
        doc_cat = ""

    template = Protocol(
        account_id=account_id,
        title=title,
        description=source.description,
        protocol_type=source.protocol_type,
        status="draft",
        version=1,
        created_by=_actor_name(),
        department=source.department,
        is_template=True,
        template_category=category,
    )
    db.session.add(template)
    db.session.flush()
    _copy_steps(source, template)
    _copy_document_fields(source, template)
    if doc_cat:                       # explicit override wins over the source's
        template.doc_category = doc_cat
    record_audit(account_id, "template.created", "protocol", template.id,
                 f"Saved “{title}” to the {category} template library")
    db.session.commit()
    return jsonify({"success": True, "template": template.to_dict(include_steps=True)}), 201


# ── Version history, diff, and rollback ──

def _copy_document_fields(source, dest, variables=None):
    """Carry document-fidelity content (format, blocks, original file) onto a
    clone. When `variables` are given, {{placeholders}} in the blocks are filled
    so 'start from our template' produces a ready-to-edit document."""
    dest.doc_format = source.doc_format or "steps"
    dest.original_filename = source.original_filename
    dest.original_file = source.original_file
    dest.doc_category = source.doc_category
    dest.product_code = source.product_code
    if source.body_json:
        try:
            blocks = json.loads(source.body_json)
        except ValueError:
            blocks = []
        if variables:
            blocks = _apply_variables_to_blocks(blocks, variables)
        dest.body_json = json.dumps(blocks)


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
