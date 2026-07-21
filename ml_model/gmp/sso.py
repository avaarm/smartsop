"""OpenID Connect / OAuth2 SSO scaffolding.

Enabled when the SSO_* environment variables are configured. The flow:
  /api/auth/sso/login    -> redirect to the IdP authorize URL (with state)
  /api/auth/sso/callback -> exchange code, fetch userinfo, provision/link a
                            local user, mint our JWT, redirect to the frontend.

Works with any standards-compliant IdP (Okta, Azure AD, Google, Auth0, Keycloak).
A real IdP is required for a live round-trip; the provisioning + config logic is
unit-tested with the IdP mocked.
"""

import os
import secrets
from urllib.parse import urlencode

import requests

from .database import db, User

REQUIRED_ENV = ("SSO_CLIENT_ID", "SSO_CLIENT_SECRET",
                "SSO_AUTHORIZE_URL", "SSO_TOKEN_URL", "SSO_USERINFO_URL")


def sso_enabled() -> bool:
    return all(os.environ.get(k) for k in REQUIRED_ENV)


def sso_config() -> dict:
    return {"enabled": sso_enabled(), "provider": os.environ.get("SSO_PROVIDER_NAME", "SSO")}


def _redirect_uri() -> str:
    return os.environ.get("SSO_REDIRECT_URI", "http://localhost:5001/api/auth/sso/callback")


def make_state() -> str:
    return secrets.token_urlsafe(24)


def authorize_url(state: str) -> str:
    params = {
        "client_id": os.environ["SSO_CLIENT_ID"],
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": os.environ.get("SSO_SCOPE", "openid email profile"),
        "state": state,
    }
    return os.environ["SSO_AUTHORIZE_URL"] + "?" + urlencode(params)


def exchange_code(code: str):
    """Exchange an authorization code for an access token."""
    resp = requests.post(os.environ["SSO_TOKEN_URL"], data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": _redirect_uri(),
        "client_id": os.environ["SSO_CLIENT_ID"],
        "client_secret": os.environ["SSO_CLIENT_SECRET"],
    }, headers={"Accept": "application/json"}, timeout=15)
    resp.raise_for_status()
    return resp.json().get("access_token")


def fetch_userinfo(access_token: str) -> dict:
    resp = requests.get(os.environ["SSO_USERINFO_URL"],
                        headers={"Authorization": f"Bearer {access_token}"}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def provision_user(userinfo: dict):
    """Find-or-create a local user from IdP claims. Returns the User or None."""
    email = (userinfo.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return None
    user = User.query.filter_by(email=email).first()
    if user is None:
        is_first = User.query.count() == 0
        name = userinfo.get("name") or userinfo.get("given_name") or ""
        user = User(email=email, name=name, is_superadmin=is_first)
        # SSO users authenticate via the IdP; give them an unusable random password.
        user.set_password(secrets.token_urlsafe(32))
        db.session.add(user)
        db.session.commit()
    return user
