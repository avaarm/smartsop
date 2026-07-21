"""SSO scaffolding: config gating, user provisioning, and the callback flow."""

import os

import pytest

from ml_model.gmp import sso
from ml_model.gmp.database import User
from util import auth


SSO_ENV = {
    "SSO_CLIENT_ID": "cid", "SSO_CLIENT_SECRET": "secret",
    "SSO_AUTHORIZE_URL": "https://idp.example/authorize",
    "SSO_TOKEN_URL": "https://idp.example/token",
    "SSO_USERINFO_URL": "https://idp.example/userinfo",
    "SSO_PROVIDER_NAME": "Acme SSO",
    "SSO_FRONTEND_REDIRECT": "http://localhost:4200/login",
}


@pytest.fixture()
def sso_enabled(monkeypatch):
    for k, v in SSO_ENV.items():
        monkeypatch.setenv(k, v)
    yield


def test_config_disabled_without_env(client, monkeypatch):
    for k in SSO_ENV:
        monkeypatch.delenv(k, raising=False)
    body = client.get("/api/auth/sso/config").get_json()
    assert body["enabled"] is False


def test_config_enabled_with_env(client, sso_enabled):
    body = client.get("/api/auth/sso/config").get_json()
    assert body["enabled"] is True and body["provider"] == "Acme SSO"


def test_login_redirects_to_idp(client, sso_enabled):
    res = client.get("/api/auth/sso/login")
    assert res.status_code == 302
    assert res.headers["Location"].startswith("https://idp.example/authorize?")
    assert "client_id=cid" in res.headers["Location"]


def test_login_404_when_disabled(client, monkeypatch):
    for k in SSO_ENV:
        monkeypatch.delenv(k, raising=False)
    assert client.get("/api/auth/sso/login").status_code == 404


def test_provision_user_creates_and_links(app):
    with app.app_context():
        # first provisioned user becomes superadmin
        u1 = sso.provision_user({"email": "New.User@corp.com", "name": "New User"})
        assert u1.email == "new.user@corp.com" and u1.name == "New User"
        # same email again links (no duplicate)
        u2 = sso.provision_user({"email": "new.user@corp.com"})
        assert u2.id == u1.id
        assert User.query.filter_by(email="new.user@corp.com").count() == 1


def test_provision_user_requires_email(app):
    with app.app_context():
        assert sso.provision_user({"name": "no email"}) is None


def test_callback_full_flow(client, sso_enabled, monkeypatch):
    # Mock the IdP token + userinfo calls.
    monkeypatch.setattr(sso, "exchange_code", lambda code: "access-token-123")
    monkeypatch.setattr(sso, "fetch_userinfo", lambda tok: {"email": "sso.user@corp.com", "name": "SSO User"})

    # Start login so a valid state is stored in the session.
    login = client.get("/api/auth/sso/login")
    state = login.headers["Location"].split("state=")[1]

    res = client.get(f"/api/auth/sso/callback?code=abc&state={state}")
    assert res.status_code == 302
    loc = res.headers["Location"]
    assert loc.startswith("http://localhost:4200/login#sso_token=")

    # The minted JWT works against /me.
    token = loc.split("#sso_token=")[1]
    me = client.get("/api/auth/me", headers=auth(token)).get_json()
    assert me["user"]["email"] == "sso.user@corp.com"


def test_callback_rejects_bad_state(client, sso_enabled, monkeypatch):
    monkeypatch.setattr(sso, "exchange_code", lambda code: "t")
    monkeypatch.setattr(sso, "fetch_userinfo", lambda tok: {"email": "x@corp.com"})
    client.get("/api/auth/sso/login")  # sets a state
    assert client.get("/api/auth/sso/callback?code=abc&state=WRONG").status_code == 400
