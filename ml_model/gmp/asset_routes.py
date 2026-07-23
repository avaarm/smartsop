"""Flask Blueprint for the asset / equipment library.

An asset is the physical thing a procedure is performed on. Each asset carries
an opaque QR slug; scanning the printed tag resolves to that asset and the SOPs
that apply to it, so a tech in the field lands on the right procedure for the
right equipment instead of a generic document.
"""

import json
import logging
import secrets

import segno
from flask import Blueprint, request, jsonify, g

from .database import db, Asset, Protocol
from .auth import require_account_access, require_auth, has_account_access

logger = logging.getLogger(__name__)

asset_bp = Blueprint("assets", __name__, url_prefix="/api")

MAX_ENERGY_SOURCES = 12
MAX_LINKED_PROTOCOLS = 30


def _new_qr_slug() -> str:
    """An unguessable slug, retried on the (astronomically unlikely) collision."""
    for _ in range(5):
        slug = secrets.token_urlsafe(12)
        if Asset.query.filter_by(qr_slug=slug).first() is None:
            return slug
    raise RuntimeError("Could not allocate a unique QR slug")


def _clean_str_list(raw, limit, item_len=200):
    if not isinstance(raw, list):
        return []
    return [str(x)[:item_len] for x in raw[:limit] if str(x).strip()]


def _clean_protocol_ids(raw, account_id):
    """Keep only ids that are real protocols in this account."""
    if not isinstance(raw, list):
        return []
    ids = [int(x) for x in raw[:MAX_LINKED_PROTOCOLS] if isinstance(x, (int, float))]
    if not ids:
        return []
    valid = {
        p.id for p in Protocol.query.filter(
            Protocol.account_id == account_id, Protocol.id.in_(ids)
        ).all()
    }
    # Preserve the caller's ordering, drop unknown/foreign ids.
    return [i for i in ids if i in valid]


def _apply_asset_fields(asset, data, account_id):
    if "name" in data:
        asset.name = (data.get("name") or "").strip()[:300]
    for field, length in (("asset_tag", 100), ("location", 300),
                          ("manufacturer", 200), ("model", 200), ("hazard_class", 200)):
        if field in data:
            setattr(asset, field, (data.get(field) or "")[:length])
    if "notes" in data:
        asset.notes = data.get("notes") or ""
    if "energy_sources" in data:
        asset.energy_sources_json = json.dumps(
            _clean_str_list(data.get("energy_sources"), MAX_ENERGY_SOURCES))
    if "protocol_ids" in data:
        asset.protocol_ids_json = json.dumps(
            _clean_protocol_ids(data.get("protocol_ids"), account_id))


def _linked_protocols(asset):
    """Resolve an asset's linked protocol ids to lightweight summaries."""
    try:
        ids = json.loads(asset.protocol_ids_json or "[]")
    except ValueError:
        ids = []
    if not ids:
        return []
    found = {
        p.id: p for p in Protocol.query.filter(
            Protocol.account_id == asset.account_id, Protocol.id.in_(ids)
        ).all()
    }
    return [
        {
            "id": p.id, "title": p.title, "status": p.status,
            "protocol_type": p.protocol_type, "version": p.version,
            "sop_number": p.sop_number,
        }
        for p in (found.get(i) for i in ids) if p is not None
    ]


# ── CRUD ──

@asset_bp.route("/accounts/<int:account_id>/assets", methods=["GET"])
@require_account_access
def list_assets(account_id):
    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(max(1, request.args.get("per_page", 50, type=int)), 200)
    query = Asset.query.filter_by(account_id=account_id)

    q = (request.args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(
            Asset.name.ilike(like), Asset.asset_tag.ilike(like), Asset.location.ilike(like)))

    paginated = query.order_by(Asset.name).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "success": True,
        "assets": [a.to_dict() for a in paginated.items],
        "total": paginated.total,
        "page": paginated.page,
        "pages": paginated.pages,
    })


@asset_bp.route("/accounts/<int:account_id>/assets", methods=["POST"])
@require_account_access
def create_asset(account_id):
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "error": "A name is required"}), 400

    asset = Asset(account_id=account_id, name=name[:300], qr_slug=_new_qr_slug())
    _apply_asset_fields(asset, data, account_id)
    db.session.add(asset)
    db.session.commit()
    logger.info("Asset created (account=%s, id=%s)", account_id, asset.id)
    return jsonify({"success": True, "asset": asset.to_dict(protocols=_linked_protocols(asset))}), 201


@asset_bp.route("/accounts/<int:account_id>/assets/<int:asset_id>", methods=["GET"])
@require_account_access
def get_asset(account_id, asset_id):
    asset = Asset.query.filter_by(id=asset_id, account_id=account_id).first()
    if asset is None:
        return jsonify({"success": False, "error": "Asset not found"}), 404
    return jsonify({"success": True, "asset": asset.to_dict(protocols=_linked_protocols(asset))})


@asset_bp.route("/accounts/<int:account_id>/assets/<int:asset_id>", methods=["PUT"])
@require_account_access
def update_asset(account_id, asset_id):
    asset = Asset.query.filter_by(id=asset_id, account_id=account_id).first()
    if asset is None:
        return jsonify({"success": False, "error": "Asset not found"}), 404
    data = request.get_json(silent=True) or {}
    if "name" in data and not (data.get("name") or "").strip():
        return jsonify({"success": False, "error": "A name is required"}), 400
    _apply_asset_fields(asset, data, account_id)
    db.session.commit()
    return jsonify({"success": True, "asset": asset.to_dict(protocols=_linked_protocols(asset))})


@asset_bp.route("/accounts/<int:account_id>/assets/<int:asset_id>", methods=["DELETE"])
@require_account_access
def delete_asset(account_id, asset_id):
    asset = Asset.query.filter_by(id=asset_id, account_id=account_id).first()
    if asset is None:
        return jsonify({"success": False, "error": "Asset not found"}), 404
    db.session.delete(asset)
    db.session.commit()
    return jsonify({"success": True})


# ── QR code ──

@asset_bp.route("/accounts/<int:account_id>/assets/<int:asset_id>/qr.svg", methods=["GET"])
@require_account_access
def asset_qr(account_id, asset_id):
    """The printable QR tag. Encodes the frontend /scan/<slug> URL."""
    asset = Asset.query.filter_by(id=asset_id, account_id=account_id).first()
    if asset is None:
        return jsonify({"success": False, "error": "Asset not found"}), 404

    base = (request.args.get("base") or request.host_url).rstrip("/")
    svg = segno.make(f"{base}/scan/{asset.qr_slug}", error="m").svg_inline(scale=6)
    return svg, 200, {"Content-Type": "image/svg+xml", "Cache-Control": "no-store"}


@asset_bp.route("/assets/scan/<slug>", methods=["GET"])
@require_auth
def scan_asset(slug):
    """Resolve a scanned QR slug to its asset + the SOPs that apply to it.

    Slug lookup is global (a QR tag carries no account context), so membership
    in the owning account is checked explicitly here.
    """
    asset = Asset.query.filter_by(qr_slug=slug).first()
    if asset is None:
        return jsonify({"success": False, "error": "Unknown asset tag"}), 404
    if not has_account_access(g.current_user, asset.account_id):
        return jsonify({"success": False, "error": "You do not have access to this asset"}), 403
    return jsonify({"success": True, "asset": asset.to_dict(protocols=_linked_protocols(asset))})
