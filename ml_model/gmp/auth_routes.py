"""Flask Blueprint for user authentication (register, login, current user)."""

import logging
import os

from flask import Blueprint, request, jsonify, g, session, redirect

from .database import db, User, Account, Membership
from .auth import require_auth, generate_token
from .extensions import limiter, AUTH_RATELIMIT
from . import sso

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

MIN_PASSWORD_LENGTH = 8


def _slugify(name: str) -> str:
    slug = name.lower().replace(" ", "-")
    return "".join(c for c in slug if c.isalnum() or c == "-") or "account"


@auth_bp.route("/register", methods=["POST"])
@limiter.limit(AUTH_RATELIMIT)
def register():
    """Create a user. The first user ever created becomes the platform superadmin.

    If `account_name` is supplied, a new account is created and the user becomes
    its owner so they have somewhere to work immediately.
    """
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    name = (data.get("name") or "").strip()
    account_name = (data.get("account_name") or "").strip()

    if not email or "@" not in email:
        return jsonify({"success": False, "error": "A valid email is required"}), 400
    if len(password) < MIN_PASSWORD_LENGTH:
        return jsonify({
            "success": False,
            "error": f"Password must be at least {MIN_PASSWORD_LENGTH} characters",
        }), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"success": False, "error": "An account with this email already exists"}), 409

    is_first_user = User.query.count() == 0
    user = User(email=email, name=name, is_superadmin=is_first_user)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()  # assign user.id

    if account_name:
        slug = _slugify(account_name)
        if Account.query.filter_by(slug=slug).first():
            slug = f"{slug}-{user.id}"
        account = Account(name=account_name, slug=slug)
        db.session.add(account)
        db.session.flush()
        db.session.add(Membership(user_id=user.id, account_id=account.id, role="owner"))

    db.session.commit()
    logger.info("Registered user %s (superadmin=%s)", email, is_first_user)
    token = generate_token(user)
    return jsonify({
        "success": True,
        "token": token,
        "user": user.to_dict(include_memberships=True),
    }), 201


@auth_bp.route("/login", methods=["POST"])
@limiter.limit(AUTH_RATELIMIT)
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password):
        return jsonify({"success": False, "error": "Invalid email or password"}), 401
    if not user.is_active:
        return jsonify({"success": False, "error": "This account has been disabled"}), 403

    token = generate_token(user)
    return jsonify({
        "success": True,
        "token": token,
        "user": user.to_dict(include_memberships=True),
    })


@auth_bp.route("/me", methods=["GET"])
@require_auth
def me():
    return jsonify({"success": True, "user": g.current_user.to_dict(include_memberships=True)})


# ── Single sign-on (OIDC / OAuth2) ──

@auth_bp.route("/sso/config", methods=["GET"])
def sso_config():
    """Tells the login page whether to offer an SSO button."""
    return jsonify({"success": True, **sso.sso_config()})


@auth_bp.route("/sso/login", methods=["GET"])
def sso_login():
    if not sso.sso_enabled():
        return jsonify({"success": False, "error": "SSO is not configured"}), 404
    state = sso.make_state()
    session["sso_state"] = state
    return redirect(sso.authorize_url(state))


@auth_bp.route("/sso/callback", methods=["GET"])
def sso_callback():
    if not sso.sso_enabled():
        return jsonify({"success": False, "error": "SSO is not configured"}), 404
    if not request.args.get("state") or request.args.get("state") != session.pop("sso_state", None):
        return jsonify({"success": False, "error": "Invalid SSO state"}), 400
    code = request.args.get("code")
    if not code:
        return jsonify({"success": False, "error": "Missing authorization code"}), 400

    try:
        access_token = sso.exchange_code(code)
        userinfo = sso.fetch_userinfo(access_token)
    except Exception:
        logger.exception("SSO token/userinfo exchange failed")
        return jsonify({"success": False, "error": "SSO exchange failed"}), 502

    user = sso.provision_user(userinfo)
    if user is None:
        return jsonify({"success": False, "error": "SSO did not return a usable email"}), 400
    if not user.is_active:
        return jsonify({"success": False, "error": "This account has been disabled"}), 403

    token = generate_token(user)
    # Hand the JWT back to the SPA in the URL fragment (never a query string).
    frontend = os.environ.get("SSO_FRONTEND_REDIRECT", "/login")
    return redirect(f"{frontend}#sso_token={token}")
