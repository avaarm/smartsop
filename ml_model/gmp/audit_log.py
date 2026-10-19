"""Shared helper for appending to the immutable audit trail.

Kept in its own module so every blueprint (documents, accounts, …) records to
the same append-only trail without importing one another.
"""

import json

from flask import g

from .database import db, AuditEvent


def actor_name():
    """Human-readable name of the acting user (falls back to their email)."""
    user = getattr(g, "current_user", None)
    if user is None:
        return ""
    return (user.name or "").strip() or user.email


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
        actor=actor_name(),
        actor_user_id=g.current_user.id,
    )
    db.session.add(ev)
    return ev
