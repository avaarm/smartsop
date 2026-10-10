"""Authentication and authorization helpers (JWT + account membership).

Tokens are short-lived JWTs sent as `Authorization: Bearer <token>`. Access to
an account's data is gated by a Membership row (or superadmin), which is what
keeps one organization's documents and training data isolated from another's.
"""

import os
import functools
import logging
from datetime import datetime, timedelta

import jwt
from flask import request, jsonify, g

from .database import db, User, Membership

logger = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"
TOKEN_TTL_HOURS = int(os.environ.get("JWT_TTL_HOURS", 24 * 7))

_warned_insecure_secret = False


def get_jwt_secret() -> str:
    """Return the signing secret, warning once if a dev fallback is used."""
    global _warned_insecure_secret
    secret = os.environ.get("JWT_SECRET") or os.environ.get("SECRET_KEY")
    if not secret:
        if not _warned_insecure_secret:
            logger.warning(
                "JWT_SECRET is not set — using an insecure development key. "
                "Set JWT_SECRET (or SECRET_KEY) before deploying."
            )
            _warned_insecure_secret = True
        secret = "dev-insecure-secret-change-me"
    return secret


def generate_token(user: User) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "iat": now,
        "exp": now + timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])


# ── Password-reset tokens ──────────────────────────────────────────────────
# A reset token is a short-lived JWT with purpose="pwreset". It carries a
# fingerprint of the current password hash so it's single-use: once the password
# changes (or the user signs in and the hash is rehashed), outstanding reset
# tokens stop validating. It can never be used as an auth token (purpose check).

RESET_TTL_MINUTES = int(os.environ.get("PASSWORD_RESET_TTL_MINUTES", 60))


def _password_fingerprint(user: User) -> str:
    import hashlib
    basis = f"{user.id}:{user.password_hash}".encode()
    return hashlib.sha256(basis).hexdigest()[:16]


def generate_reset_token(user: User) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": str(user.id),
        "purpose": "pwreset",
        "fp": _password_fingerprint(user),
        "iat": now,
        "exp": now + timedelta(minutes=RESET_TTL_MINUTES),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def user_from_reset_token(token: str):
    """Return the user a valid, unexpired, unused reset token belongs to, else None."""
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("purpose") != "pwreset":
        return None
    try:
        user = db.session.get(User, int(payload.get("sub", 0)))
    except (TypeError, ValueError):
        return None
    if user is None or not user.is_active:
        return None
    if payload.get("fp") != _password_fingerprint(user):   # already used / changed
        return None
    return user


def _user_from_request():
    """Resolve the authenticated, active user from the Bearer token, or None."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[len("Bearer "):].strip()
    if not token:
        return None
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        return None
    # Purpose-scoped tokens (e.g. password reset) are valid JWTs signed with the
    # same secret, but must never authenticate a request.
    if payload.get("purpose"):
        return None
    try:
        user_id = int(payload.get("sub", 0))
    except (TypeError, ValueError):
        return None
    user = db.session.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


def require_auth(fn):
    """Require a valid token. Sets g.current_user."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        user = _user_from_request()
        if user is None:
            return jsonify({"success": False, "error": "Authentication required"}), 401
        g.current_user = user
        return fn(*args, **kwargs)

    return wrapper


def get_membership(user: User, account_id: int):
    if user is None or account_id is None:
        return None
    return Membership.query.filter_by(user_id=user.id, account_id=account_id).first()


def has_account_access(user: User, account_id) -> bool:
    if user is None:
        return False
    if user.is_superadmin:
        return True
    return get_membership(user, account_id) is not None


def has_account_role(user: User, account_id, roles) -> bool:
    if user is None:
        return False
    if user.is_superadmin:
        return True
    membership = get_membership(user, account_id)
    return membership is not None and membership.role in roles


def require_account_access(fn):
    """Require a valid token AND membership in the route's <int:account_id>.

    Sets g.current_user. Returns 401 if unauthenticated, 403 if the user is
    not a member of the account (and not a superadmin).
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        user = _user_from_request()
        if user is None:
            return jsonify({"success": False, "error": "Authentication required"}), 401
        g.current_user = user
        account_id = kwargs.get("account_id")
        if not has_account_access(user, account_id):
            return jsonify({"success": False, "error": "You do not have access to this account"}), 403
        return fn(*args, **kwargs)

    return wrapper
