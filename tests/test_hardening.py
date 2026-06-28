"""Security hardening: traversal, JSON errors, and cross-account training access."""

from util import auth, burn_superadmin, make_owner


def test_download_path_traversal_blocked(client):
    res = client.get("/api/download/..%2f..%2f..%2fetc%2fpasswd")
    assert res.status_code in (400, 404)
    assert res.is_json  # never serves a file


def test_download_missing_returns_json_404(client):
    res = client.get("/api/download/nope.docx")
    assert res.status_code == 404 and res.is_json


def test_unknown_route_returns_json(client):
    res = client.get("/api/does-not-exist")
    assert res.status_code == 404 and res.is_json
    assert res.get_json()["success"] is False


def test_health_and_ready(client):
    assert client.get("/health").status_code == 200
    assert client.get("/ready").get_json()["status"] == "ready"


def test_cross_account_training_access_blocked(client):
    burn_superadmin(client)
    a_tok, a_id, _ = make_owner(client, "a@x.com", "Acme")
    b_tok, b_id, _ = make_owner(client, "b@x.com", "Beta")

    # Seed a training example in account A.
    add = client.post(f"/api/accounts/{a_id}/training", headers=auth(a_tok),
                      json={"prompt": "p", "completion": "c"})
    ex_id = add.get_json()["example"]["id"]

    # Account B has no access to A's account → 403.
    assert client.post(f"/api/accounts/{a_id}/training/{ex_id}/rate",
                       headers=auth(b_tok), json={"rating": 5}).status_code == 403
    # Even scoping the call under B's own account, A's example id isn't there → 404.
    assert client.post(f"/api/accounts/{b_id}/training/{ex_id}/rate",
                       headers=auth(b_tok), json={"rating": 5}).status_code == 404


def test_update_account_missing_body(client):
    token, acc_id, _ = make_owner(client, "owner@x.com", "Acme")  # first user → superadmin, still owner
    res = client.put(f"/api/accounts/{acc_id}", headers=auth(token), data="", content_type="application/json")
    assert res.status_code == 400 and res.is_json
