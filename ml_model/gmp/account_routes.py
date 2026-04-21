"""Flask Blueprint for account management, training data, protocol upload, and data export."""

import json
import logging
import os
from pathlib import Path
from flask import Blueprint, request, jsonify, send_file, current_app

from .database import db, Account, Document, TrainingExample, ProtocolUpload, ProtocolKnowledge
from .data_collector import DataCollector
from .training_export import TrainingExporter
from .protocol_parser import ProtocolParser
from .protocol_analyzer import ProtocolAnalyzer
from .ollama_service import OllamaService
from .doc_type_inference import infer_doc_type
from .style_consolidation import consolidate_style_for_doc_type

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


@account_bp.route("/<int:account_id>", methods=["DELETE"])
def delete_account(account_id):
    """Delete an entire workspace and everything it owns.

    Cascades to: ProtocolUploads (+ knowledge), TrainingExamples,
    Documents, and any on-disk files in the account's upload directory.
    Irreversible — the frontend MUST double-prompt the user.
    """
    import shutil
    account = Account.query.get_or_404(account_id)

    # Remove per-upload files before deleting the rows so we don't leave
    # orphaned files behind if the DB delete succeeds.
    for upload in ProtocolUpload.query.filter_by(account_id=account_id).all():
        if upload.file_path and os.path.exists(upload.file_path):
            try:
                os.unlink(upload.file_path)
            except OSError as e:
                logger.warning("Could not delete %s: %s", upload.file_path, e)

    # And the upload directory itself if it's now empty.
    upload_dir = UPLOAD_DIR / str(account_id)
    if upload_dir.exists():
        try:
            shutil.rmtree(upload_dir)
        except OSError as e:
            logger.warning("Could not remove %s: %s", upload_dir, e)

    # Cascade the relational cleanup. ProtocolKnowledge has
    # cascade="all, delete-orphan" on the ProtocolUpload relationship,
    # so deleting uploads removes their knowledge rows. Training
    # examples and documents need explicit deletes since they only
    # backref the account via ForeignKey.
    ProtocolUpload.query.filter_by(account_id=account_id).delete()
    TrainingExample.query.filter_by(account_id=account_id).delete()
    Document.query.filter_by(account_id=account_id).delete()

    db.session.delete(account)
    db.session.commit()
    return jsonify({"success": True, "deleted_account_id": account_id})


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
    """Manually add a training example (e.g. paste in a gold-standard section).

    Accepts optional ``source`` (``manual`` | ``user_edited``) and
    ``quality_rating`` fields. ``user_edited`` is what the Document
    Builder's "Save as template for future docs" button uses — the user
    has approved the current section content as a gold-standard
    exemplar that the next few-shot pass should draw from.
    """
    data = request.get_json()
    if not data or not data.get("prompt") or not data.get("completion"):
        return jsonify({"success": False, "error": "prompt and completion are required"}), 400

    source = data.get("source") or "manual"
    if source not in ("manual", "user_edited"):
        return jsonify({"success": False, "error": f"unsupported source '{source}'"}), 400

    example = collector.record_section_generation(
        account_id=account_id,
        section_type=data.get("section_type", "manual"),
        prompt=data["prompt"],
        completion=data["completion"],
        context={
            "product_name": data.get("product_name", ""),
            "process_type": data.get("process_type", ""),
        },
        source=source,
    )

    if example and data.get("quality_rating") is not None:
        try:
            rating = int(data["quality_rating"])
            collector.rate_example(example.id, rating)
            # Reflect rating in the echoed example object.
            example.quality_rating = max(1, min(5, rating))
        except (TypeError, ValueError):
            pass

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


# ── Protocol Upload & Knowledge Extraction ──

UPLOAD_DIR = Path(__file__).parent.parent.parent / "generated_docs" / "uploads"
ALLOWED_EXTENSIONS = {"docx", "pdf"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

parser = ProtocolParser()


def _get_upload_dir(account_id: int) -> Path:
    d = UPLOAD_DIR / str(account_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


@account_bp.route("/<int:account_id>/protocols/upload", methods=["POST"])
def upload_protocol(account_id):
    """Upload a .docx or .pdf protocol and parse its structure."""
    Account.query.get_or_404(account_id)

    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"success": False, "error": "Empty filename"}), 400

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"success": False, "error": f"File type .{ext} not supported. Use .docx or .pdf"}), 400

    # Save file
    upload_dir = _get_upload_dir(account_id)
    safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in file.filename)
    file_path = upload_dir / safe_name
    file.save(str(file_path))

    # Check size
    file_size = file_path.stat().st_size
    if file_size > MAX_FILE_SIZE:
        file_path.unlink()
        return jsonify({"success": False, "error": "File too large (max 20 MB)"}), 400

    # Create DB record
    upload = ProtocolUpload(
        account_id=account_id,
        filename=file.filename,
        file_type=ext,
        file_path=str(file_path),
        status="uploaded",
    )
    db.session.add(upload)
    db.session.commit()

    # Parse immediately (fast, no LLM)
    try:
        parsed = parser.parse(str(file_path), ext)
        upload.raw_text = parsed.get("text", "")[:100000]  # Cap at 100k chars
        upload.structure_json = json.dumps(parsed.get("sections", []))
        upload.formatting_json = json.dumps(parsed.get("formatting", {}))
        # Cheap heuristic classification — user can override in the UI.
        inferred_type, confidence = infer_doc_type(file.filename, upload.raw_text)
        if inferred_type:
            upload.doc_type = inferred_type
            upload.doc_type_source = "inferred"
        upload.status = "parsed"
        db.session.commit()
    except Exception as e:
        upload.status = "error"
        upload.error_message = str(e)
        db.session.commit()
        logger.error(f"Parse failed for {file.filename}: {e}")
        return jsonify({"success": False, "error": f"Parse failed: {str(e)}"}), 500

    return jsonify({
        "success": True,
        "upload": upload.to_dict(),
        "metadata": parsed.get("metadata", {}),
    }), 201


@account_bp.route("/<int:account_id>/protocols/<int:upload_id>/analyze", methods=["POST"])
def analyze_protocol(account_id, upload_id):
    """Trigger LLM analysis on a parsed protocol to extract knowledge."""
    upload = ProtocolUpload.query.get_or_404(upload_id)
    if upload.account_id != account_id:
        return jsonify({"success": False, "error": "Upload not found"}), 404
    if upload.status not in ("parsed", "complete"):
        return jsonify({"success": False, "error": f"Upload status is '{upload.status}', must be 'parsed'"}), 400

    ollama_url = current_app.config.get("OLLAMA_HOST", "http://localhost:11434")
    ollama = OllamaService(base_url=ollama_url)
    analyzer = ProtocolAnalyzer(ollama)

    upload.status = "analyzing"
    db.session.commit()

    try:
        parsed_data = {
            "text": upload.raw_text,
            "sections": json.loads(upload.structure_json or "[]"),
            "formatting": json.loads(upload.formatting_json or "{}"),
        }

        # Clear previous knowledge from this upload
        ProtocolKnowledge.query.filter_by(upload_id=upload_id).delete()
        db.session.commit()

        results = analyzer.analyze(parsed_data)

        for item in results:
            knowledge = ProtocolKnowledge(
                account_id=account_id,
                upload_id=upload_id,
                category=item["category"],
                knowledge_json=item["knowledge_json"],
                summary=item["summary"],
                confidence=item.get("confidence"),
                is_active=True,
            )
            db.session.add(knowledge)

        upload.status = "complete"
        db.session.commit()

        return jsonify({
            "success": True,
            "upload": upload.to_dict(),
        })

    except Exception as e:
        upload.status = "error"
        upload.error_message = str(e)
        db.session.commit()
        logger.error(f"Analysis failed for upload {upload_id}: {e}")
        return jsonify({"success": False, "error": f"Analysis failed: {str(e)}"}), 500


@account_bp.route("/<int:account_id>/protocols", methods=["GET"])
def list_protocols(account_id):
    """List all protocol uploads for an account."""
    uploads = ProtocolUpload.query.filter_by(account_id=account_id).order_by(
        ProtocolUpload.created_at.desc()
    ).all()
    return jsonify({"success": True, "uploads": [u.to_dict() for u in uploads]})


@account_bp.route("/<int:account_id>/protocols/<int:upload_id>", methods=["GET"])
def get_protocol(account_id, upload_id):
    """Get a single protocol upload with its knowledge."""
    upload = ProtocolUpload.query.get_or_404(upload_id)
    if upload.account_id != account_id:
        return jsonify({"success": False, "error": "Not found"}), 404
    return jsonify({"success": True, "upload": upload.to_dict()})


@account_bp.route("/<int:account_id>/protocols/<int:upload_id>", methods=["PATCH"])
def update_protocol(account_id, upload_id):
    """Update mutable fields on an upload — currently just ``doc_type``.

    Body: ``{"doc_type": "batch_record"}`` (empty string clears it).
    Any user-supplied change is stamped as ``doc_type_source="user"`` so the
    UI can distinguish between auto-detected and manually-set values.
    """
    upload = ProtocolUpload.query.get_or_404(upload_id)
    if upload.account_id != account_id:
        return jsonify({"success": False, "error": "Not found"}), 404

    data = request.get_json(silent=True) or {}
    if "doc_type" in data:
        upload.doc_type = (data.get("doc_type") or "").strip()
        upload.doc_type_source = "user"
        db.session.commit()

    return jsonify({"success": True, "upload": upload.to_dict()})


@account_bp.route("/<int:account_id>/protocols/knowledge", methods=["GET"])
def list_protocol_knowledge(account_id):
    """Get all active knowledge for an account, merged across uploads."""
    items = ProtocolKnowledge.query.filter_by(
        account_id=account_id, is_active=True
    ).all()
    return jsonify({"success": True, "knowledge": [k.to_dict() for k in items]})


@account_bp.route("/<int:account_id>/protocols/knowledge/<int:knowledge_id>", methods=["PUT"])
def update_knowledge(account_id, knowledge_id):
    """Toggle active state or edit knowledge content."""
    knowledge = ProtocolKnowledge.query.get_or_404(knowledge_id)
    if knowledge.account_id != account_id:
        return jsonify({"success": False, "error": "Not found"}), 404

    data = request.get_json()
    if "is_active" in data:
        knowledge.is_active = data["is_active"]
    if "knowledge_json" in data:
        knowledge.knowledge_json = data["knowledge_json"]
    if "summary" in data:
        knowledge.summary = data["summary"]

    db.session.commit()
    return jsonify({"success": True, "knowledge": knowledge.to_dict()})


@account_bp.route("/<int:account_id>/protocols/<int:upload_id>", methods=["DELETE"])
def delete_protocol(account_id, upload_id):
    """Delete a protocol upload and its knowledge."""
    upload = ProtocolUpload.query.get_or_404(upload_id)
    if upload.account_id != account_id:
        return jsonify({"success": False, "error": "Not found"}), 404

    # Remove file
    if upload.file_path and os.path.exists(upload.file_path):
        os.unlink(upload.file_path)

    db.session.delete(upload)
    db.session.commit()
    return jsonify({"success": True})


@account_bp.route("/demo", methods=["POST"])
def seed_demo_workspace():
    """Create a demo workspace pre-populated with sample Fred-Hutch
    cell-processing batch records.

    Gives first-time users something concrete to click through so they
    can see the full extract → learn → generate → compare loop without
    needing their own documents on hand.

    If a demo account already exists (slug ``demo-workspace``), returns
    it as-is rather than duplicating. Idempotent.
    """
    import shutil
    from .database import Account

    SAMPLE_DIR = Path(__file__).parent / "sample_docs"
    DEMO_SLUG = "demo-workspace"

    # Return the existing demo account if we've already seeded it
    existing = Account.query.filter_by(slug=DEMO_SLUG).first()
    if existing:
        return jsonify({
            "success": True,
            "account": existing.to_dict(),
            "already_seeded": True,
            "upload_count": ProtocolUpload.query.filter_by(
                account_id=existing.id
            ).count(),
        })

    if not SAMPLE_DIR.exists():
        return jsonify({
            "success": False,
            "error": "Sample documents bundle not installed",
        }), 500

    account = Account(
        name="Demo Workspace (Fred Hutch samples)",
        slug=DEMO_SLUG,
        facility_name="Fred Hutch Cell Processing Facility (demo)",
        department="Manufacturing",
        default_product="CD4+ / CD8+ T Cells",
        default_process="CliniMACS Prodigy Enrichment",
        terminology_json=json.dumps({
            "BSC": "Biosafety Cabinet",
            "TSCD": "Total Sterile Connecting Device",
            "CPF": "Cell Processing Facility",
            "IPA": "Isopropyl Alcohol",
        }),
        style_notes=(
            "Use passive voice. Refer to operators as Manufacturing Technician. "
            "Always cite procedure numbers when referencing SOPs."
        ),
        reference_sops_json=json.dumps([
            "EQ-002 Operation and Maintenance of Biological Safety Cabinets",
            "GN-005 Aseptic Technique",
            "PR-010 Cell Processing and Cryopreservation",
        ]),
    )
    db.session.add(account)
    db.session.commit()

    # Copy each bundled sample into the account's upload dir, parse it,
    # and if a ``.knowledge.json`` sidecar exists next to the DOCX, load
    # the pre-extracted knowledge rows directly so the demo account
    # lands in "Knowledge extracted" status — no Ollama required.
    dest_dir = _get_upload_dir(account.id)
    uploads: list[dict] = []
    for sample_path in sorted(SAMPLE_DIR.glob("*.docx")):
        try:
            dest = dest_dir / sample_path.name
            shutil.copyfile(sample_path, dest)
            upload = ProtocolUpload(
                account_id=account.id,
                filename=sample_path.name,
                file_type="docx",
                file_path=str(dest),
                status="uploaded",
            )
            db.session.add(upload)
            db.session.commit()

            parsed = parser.parse(str(dest), "docx")
            upload.raw_text = parsed.get("text", "")[:100000]
            upload.structure_json = json.dumps(parsed.get("sections", []))
            upload.formatting_json = json.dumps(parsed.get("formatting", {}))
            inferred, _ = infer_doc_type(sample_path.name, upload.raw_text)
            if inferred:
                upload.doc_type = inferred
                upload.doc_type_source = "inferred"

            # Look for a sidecar knowledge file bundled with the sample.
            # If present, create ProtocolKnowledge rows so the demo
            # workspace ships as "Knowledge extracted" not "Parsed".
            sidecar = sample_path.with_suffix(".knowledge.json")
            if sidecar.exists():
                try:
                    sidecar_data = json.loads(sidecar.read_text())
                    for category, payload in sidecar_data.items():
                        if not isinstance(payload, dict):
                            continue
                        k = ProtocolKnowledge(
                            account_id=account.id,
                            upload_id=upload.id,
                            category=category,
                            knowledge_json=json.dumps(
                                payload.get("knowledge") or {}
                            ),
                            summary=payload.get("summary") or "",
                            confidence=payload.get("confidence"),
                            is_active=True,
                        )
                        db.session.add(k)
                    upload.status = "complete"
                    db.session.commit()
                except Exception as e:
                    logger.warning(
                        "Sidecar %s could not be loaded: %s — leaving upload as parsed",
                        sidecar.name, e,
                    )
                    upload.status = "parsed"
                    db.session.commit()
            else:
                upload.status = "parsed"
                db.session.commit()

            uploads.append(upload.to_dict())
        except Exception as e:
            logger.warning("Failed to seed sample %s: %s", sample_path.name, e)

    return jsonify({
        "success": True,
        "account": account.to_dict(),
        "uploads": uploads,
        "already_seeded": False,
    }), 201


@account_bp.route("/<int:account_id>/effective-style", methods=["GET"])
def get_effective_style(account_id):
    """Return the consolidated style SmartSOP will use when generating
    documents of the given type for this account.

    Query string:
        doc_type: Optional template ID (e.g. ``batch_record``). When
            omitted, merges across ALL uploads for the account.

    The response includes a ``summary`` that's small enough to render as
    a status banner ("Using style learned from 5 documents"), and the
    full ``style`` spec for callers that want the details.
    """
    from .database import Account

    account = Account.query.get_or_404(account_id)
    doc_type = (request.args.get("doc_type") or "").strip()

    uploads = ProtocolUpload.query.filter_by(account_id=account_id).all()
    upload_dicts = [u.to_dict() for u in uploads]

    terminology = {}
    try:
        terminology = json.loads(account.terminology_json or "{}")
    except json.JSONDecodeError:
        pass

    style = consolidate_style_for_doc_type(
        upload_dicts,
        doc_type=doc_type,
        account_terms=terminology or None,
        account_style_notes=account.style_notes or None,
    )

    # Count contributing uploads for the banner
    if doc_type:
        matching = [u for u in upload_dicts if u.get("doc_type") == doc_type]
        contributing = matching or upload_dicts
    else:
        contributing = upload_dicts

    analyzed = [
        u for u in contributing
        if any((k or {}).get("is_active", True) for k in (u.get("knowledge") or []))
    ]

    body = style.get("body_font") or {}
    page = style.get("page") or {}
    shading = style.get("shading_roles") or {}

    return jsonify({
        "success": True,
        "doc_type": doc_type or None,
        "summary": {
            "upload_count": len(contributing),
            "analyzed_upload_count": len(analyzed),
            "has_learned_style": bool(body or page or shading),
            "orientation": page.get("orientation"),
            "body_font_name": body.get("name"),
            "body_font_size_pt": body.get("size_pt"),
            "section_header_shading": shading.get("section_header"),
            "label_cell_shading": shading.get("label_cell"),
            "terminology_count": len(style.get("terminology") or {}),
            "rules_count": len(style.get("procedural_rules") or []),
            "table_templates_count": len(style.get("table_templates") or []),
        },
        "style": style,
    })
