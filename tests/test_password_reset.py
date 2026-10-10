"""Self-service password reset: forgot-password → reset-password."""

from util import register, login, auth


def _request_reset(client, email):
    return client.post("/api/auth/forgot-password", json={"email": email})


def test_forgot_password_is_generic_and_returns_dev_link(client):
    register(client, "reset-me@corp.com", password="origpass123")
    res = _request_reset(client, "reset-me@corp.com")
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert "a password reset link has been sent" in body["message"]
    # No SMTP in tests (non-production) → the link is returned for the dev flow.
    assert "reset_link" in body and "/reset-password?token=" in body["reset_link"]


def test_unknown_email_gives_same_response_no_enumeration(client):
    register(client, "known@corp.com", password="origpass123")
    known = _request_reset(client, "known@corp.com").get_json()
    unknown = _request_reset(client, "nobody@corp.com").get_json()
    assert known["message"] == unknown["message"]
    # Unknown email must NOT get a usable token.
    assert "reset_link" not in unknown


def test_reset_changes_password_and_logs_in(client):
    register(client, "changer@corp.com", password="origpass123")
    link = _request_reset(client, "changer@corp.com").get_json()["reset_link"]
    token = link.split("token=", 1)[1]

    # Old password still works until reset.
    assert login(client, "changer@corp.com", "origpass123").status_code == 200

    res = client.post("/api/auth/reset-password", json={"token": token, "password": "brandnew456"})
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert body["token"]                      # signed straight in
    assert body["user"]["email"] == "changer@corp.com"

    # New password works; old one no longer does.
    assert login(client, "changer@corp.com", "brandnew456").status_code == 200
    assert login(client, "changer@corp.com", "origpass123").status_code == 401


def test_reset_token_is_single_use(client):
    register(client, "once@corp.com", password="origpass123")
    token = _request_reset(client, "once@corp.com").get_json()["reset_link"].split("token=", 1)[1]
    assert client.post("/api/auth/reset-password",
                       json={"token": token, "password": "firstreset1"}).status_code == 200
    # The same token can't be replayed — the password fingerprint changed.
    again = client.post("/api/auth/reset-password", json={"token": token, "password": "secondreset2"})
    assert again.status_code == 400


def test_reset_rejects_bad_token_and_short_password(client):
    register(client, "guard@corp.com", password="origpass123")
    token = _request_reset(client, "guard@corp.com").get_json()["reset_link"].split("token=", 1)[1]
    assert client.post("/api/auth/reset-password",
                       json={"token": "garbage", "password": "longenough1"}).status_code == 400
    assert client.post("/api/auth/reset-password",
                       json={"token": token, "password": "short"}).status_code == 400


def test_reset_token_cannot_authenticate_as_bearer(client):
    """A reset token must not be usable as an access token."""
    register(client, "sep@corp.com", password="origpass123")
    token = _request_reset(client, "sep@corp.com").get_json()["reset_link"].split("token=", 1)[1]
    assert client.get("/api/auth/me", headers=auth(token)).status_code == 401
