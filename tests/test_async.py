"""Async LLM task endpoints (enqueue + poll), exercised in eager mode."""

from util import register, auth, burn_superadmin, make_owner


def test_config_reports_async_disabled_in_eager(client):
    # No broker configured in tests → eager → async API reported off.
    assert client.get("/api/gmp/config").get_json()["async_tasks"] is False


def test_enqueue_and_poll_returns_result(client):
    token = register(client, "u@x.com", account_name="Acme").get_json()["token"]
    res = client.post("/api/gmp/preview/async", headers=auth(token),
                      json={"doc_type": "sop", "section_id": "purpose", "context": {}})
    assert res.status_code == 202
    task_id = res.get_json()["task_id"]
    assert task_id

    poll = client.get(f"/api/gmp/tasks/{task_id}", headers=auth(token)).get_json()
    assert poll["state"] == "SUCCESS"
    assert poll["result"]["content"] == "AI content for purpose"


def test_enqueue_requires_auth(client):
    assert client.post("/api/gmp/preview/async",
                       json={"doc_type": "sop", "section_id": "x"}).status_code == 401


def test_enqueue_validates_fields(client):
    token = register(client, "u@x.com").get_json()["token"]
    assert client.post("/api/gmp/preview/async", headers=auth(token),
                       json={"doc_type": "sop"}).status_code == 400


def test_enqueue_blocks_cross_account(client):
    burn_superadmin(client)
    _, a_id, _ = make_owner(client, "a@x.com", "Acme")
    b_tok, _, _ = make_owner(client, "b@x.com", "Beta")
    res = client.post("/api/gmp/preview/async", headers=auth(b_tok),
                      json={"doc_type": "sop", "section_id": "x", "context": {"account_id": a_id}})
    assert res.status_code == 403
