"""Authentication, registration, and tenant-scoped account access."""

from util import register, login, auth, burn_superadmin, make_owner


def test_first_user_is_superadmin(client):
    res = register(client, "first@x.com", account_name="First Co")
    assert res.status_code == 201
    body = res.get_json()
    assert body["user"]["is_superadmin"] is True
    assert body["token"]


def test_second_user_is_not_superadmin(client):
    register(client, "first@x.com")
    res = register(client, "second@x.com")
    assert res.status_code == 201
    assert res.get_json()["user"]["is_superadmin"] is False


def test_duplicate_email_rejected(client):
    register(client, "dup@x.com")
    assert register(client, "dup@x.com").status_code == 409


def test_weak_password_rejected(client):
    assert register(client, "weak@x.com", password="short").status_code == 400


def test_invalid_email_rejected(client):
    assert register(client, "not-an-email").status_code == 400


def test_login_success_and_failure(client):
    register(client, "user@x.com")
    assert login(client, "user@x.com").status_code == 200
    assert login(client, "user@x.com", password="wrong").status_code == 401
    assert login(client, "missing@x.com").status_code == 401


def test_me_requires_and_returns_user(client):
    token = register(client, "me@x.com").get_json()["token"]
    assert client.get("/api/auth/me").status_code == 401
    res = client.get("/api/auth/me", headers=auth(token))
    assert res.status_code == 200
    assert res.get_json()["user"]["email"] == "me@x.com"


def test_invalid_token_rejected(client):
    assert client.get("/api/auth/me", headers=auth("garbage.token")).status_code == 401


def test_account_list_scoped_to_membership(client):
    burn_superadmin(client)
    a_tok, a_id, _ = make_owner(client, "a@x.com", "Acme")
    b_tok, b_id, _ = make_owner(client, "b@x.com", "Beta")

    a_ids = [x["id"] for x in client.get("/api/accounts", headers=auth(a_tok)).get_json()["accounts"]]
    assert a_ids == [a_id]
    b_ids = [x["id"] for x in client.get("/api/accounts", headers=auth(b_tok)).get_json()["accounts"]]
    assert b_ids == [b_id]


def test_superadmin_sees_all_accounts(client):
    su_tok = register(client, "su@x.com").get_json()["token"]  # first user → superadmin
    _, a_id, _ = make_owner(client, "a@x.com", "Acme")
    _, b_id, _ = make_owner(client, "b@x.com", "Beta")
    ids = sorted(x["id"] for x in client.get("/api/accounts", headers=auth(su_tok)).get_json()["accounts"])
    assert ids == sorted([a_id, b_id])


def test_cross_account_read_forbidden(client):
    burn_superadmin(client)
    a_tok, a_id, _ = make_owner(client, "a@x.com", "Acme")
    b_tok, _, _ = make_owner(client, "b@x.com", "Beta")
    assert client.get(f"/api/accounts/{a_id}", headers=auth(b_tok)).status_code == 403
    assert client.get(f"/api/accounts/{a_id}", headers=auth(a_tok)).status_code == 200
