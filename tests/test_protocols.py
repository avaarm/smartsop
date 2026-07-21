"""Protocol authoring: CRUD, steps, reordering, and tenant isolation."""

import pytest

from util import auth, burn_superadmin, make_owner


@pytest.fixture()
def owner(client):
    burn_superadmin(client)
    token, acc_id, _ = make_owner(client, "owner@x.com", "Acme")
    return client, token, acc_id


def _create(client, token, acc_id, title="Cell Thawing"):
    return client.post(f"/api/accounts/{acc_id}/protocols", headers=auth(token),
                       json={"title": title, "description": "overview"})


def test_create_requires_auth(owner):
    client, _, acc_id = owner
    assert client.post(f"/api/accounts/{acc_id}/protocols", json={"title": "X"}).status_code == 401


def test_create_and_get_protocol(owner):
    client, token, acc_id = owner
    res = _create(client, token, acc_id)
    assert res.status_code == 201
    pid = res.get_json()["protocol"]["id"]
    assert res.get_json()["protocol"]["created_by"] == "owner@x.com"

    got = client.get(f"/api/accounts/{acc_id}/protocols/{pid}", headers=auth(token)).get_json()
    assert got["protocol"]["title"] == "Cell Thawing"
    assert got["protocol"]["steps"] == []
    assert got["protocol"]["step_count"] == 0


def test_create_title_required(owner):
    client, token, acc_id = owner
    assert client.post(f"/api/accounts/{acc_id}/protocols", headers=auth(token),
                       json={"title": "  "}).status_code == 400


def test_list_pagination(owner):
    client, token, acc_id = owner
    for i in range(3):
        _create(client, token, acc_id, title=f"P{i}")
    body = client.get(f"/api/accounts/{acc_id}/protocols?per_page=2", headers=auth(token)).get_json()
    assert body["total"] == 3 and body["pages"] == 2 and len(body["protocols"]) == 2


def test_update_protocol_meta(owner):
    client, token, acc_id = owner
    pid = _create(client, token, acc_id).get_json()["protocol"]["id"]
    res = client.put(f"/api/accounts/{acc_id}/protocols/{pid}", headers=auth(token),
                     json={"title": "Renamed", "description": "new"})
    assert res.status_code == 200
    p = res.get_json()["protocol"]
    assert p["title"] == "Renamed" and p["description"] == "new"


def test_status_not_set_via_put(owner):
    # Status is controlled by the lifecycle endpoints, not the plain update.
    client, token, acc_id = owner
    pid = _create(client, token, acc_id).get_json()["protocol"]["id"]
    res = client.put(f"/api/accounts/{acc_id}/protocols/{pid}", headers=auth(token),
                     json={"status": "effective"})
    assert res.status_code == 200
    assert res.get_json()["protocol"]["status"] == "draft"


def test_add_update_delete_step(owner):
    client, token, acc_id = owner
    pid = _create(client, token, acc_id).get_json()["protocol"]["id"]

    s1 = client.post(f"/api/accounts/{acc_id}/protocols/{pid}/steps", headers=auth(token),
                     json={"title": "Thaw", "description": "Warm to 37C",
                           "duration_seconds": 120, "warning": "Wear PPE",
                           "reagents": [{"name": "Medium", "amount": "10 mL"}]})
    assert s1.status_code == 201
    step = s1.get_json()["step"]
    assert step["order_index"] == 0
    assert step["duration_seconds"] == 120
    assert step["reagents"][0]["name"] == "Medium"

    upd = client.put(f"/api/accounts/{acc_id}/protocols/{pid}/steps/{step['id']}",
                     headers=auth(token), json={"title": "Thaw cells"})
    assert upd.get_json()["step"]["title"] == "Thaw cells"

    dele = client.delete(f"/api/accounts/{acc_id}/protocols/{pid}/steps/{step['id']}",
                         headers=auth(token))
    assert dele.status_code == 200
    assert client.get(f"/api/accounts/{acc_id}/protocols/{pid}",
                      headers=auth(token)).get_json()["protocol"]["step_count"] == 0


def test_steps_append_in_order(owner):
    client, token, acc_id = owner
    pid = _create(client, token, acc_id).get_json()["protocol"]["id"]
    ids = []
    for t in ["A", "B", "C"]:
        ids.append(client.post(f"/api/accounts/{acc_id}/protocols/{pid}/steps",
                               headers=auth(token), json={"title": t}).get_json()["step"]["id"])
    steps = client.get(f"/api/accounts/{acc_id}/protocols/{pid}",
                       headers=auth(token)).get_json()["protocol"]["steps"]
    assert [s["title"] for s in steps] == ["A", "B", "C"]

    # reorder to C, A, B
    reordered = [ids[2], ids[0], ids[1]]
    assert client.post(f"/api/accounts/{acc_id}/protocols/{pid}/steps/reorder",
                       headers=auth(token), json={"order": reordered}).status_code == 200
    steps = client.get(f"/api/accounts/{acc_id}/protocols/{pid}",
                       headers=auth(token)).get_json()["protocol"]["steps"]
    assert [s["title"] for s in steps] == ["C", "A", "B"]


def test_reorder_rejects_wrong_ids(owner):
    client, token, acc_id = owner
    pid = _create(client, token, acc_id).get_json()["protocol"]["id"]
    sid = client.post(f"/api/accounts/{acc_id}/protocols/{pid}/steps", headers=auth(token),
                      json={"title": "A"}).get_json()["step"]["id"]
    assert client.post(f"/api/accounts/{acc_id}/protocols/{pid}/steps/reorder",
                       headers=auth(token), json={"order": [sid, 9999]}).status_code == 400


def test_cross_account_isolation(client):
    burn_superadmin(client)
    a_tok, a_id, _ = make_owner(client, "a@x.com", "Acme")
    b_tok, b_id, _ = make_owner(client, "b@x.com", "Beta")
    pid = _create(client, a_tok, a_id).get_json()["protocol"]["id"]

    # B has no access to A's account at all → 403
    assert client.get(f"/api/accounts/{a_id}/protocols/{pid}", headers=auth(b_tok)).status_code == 403
    # A's protocol id under B's own account → 404
    assert client.get(f"/api/accounts/{b_id}/protocols/{pid}", headers=auth(b_tok)).status_code == 404


def test_delete_protocol(owner):
    client, token, acc_id = owner
    pid = _create(client, token, acc_id).get_json()["protocol"]["id"]
    assert client.delete(f"/api/accounts/{acc_id}/protocols/{pid}", headers=auth(token)).status_code == 200
    assert client.get(f"/api/accounts/{acc_id}/protocols/{pid}", headers=auth(token)).status_code == 404
