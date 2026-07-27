"""Training / competency: assign an SOP, acknowledge, track expiry."""

from datetime import datetime, timedelta

from util import burn_superadmin, make_owner, auth


def _protocol(client, token, account_id, title="Gowning SOP"):
    return client.post(f"/api/accounts/{account_id}/protocols",
                       json={"title": title}, headers=auth(token)).get_json()["protocol"]


def test_assign_training(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "tr1@corp.com", "Trco")
    p = _protocol(client, token, acc)
    res = client.post(f"/api/accounts/{acc}/competency",
                      json={"protocol_id": p["id"], "trainee": "J. Doe"}, headers=auth(token))
    assert res.status_code == 201
    rec = res.get_json()["training"]
    assert rec["status"] == "assigned"
    assert rec["protocol_title"] == "Gowning SOP"
    assert rec["protocol_version"] == 1            # version trained on, snapshotted
    assert rec["assigned_by"]
    assert rec["is_current"] is False              # not acknowledged yet


def test_trainee_required(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "tr2@corp.com", "Urco")
    p = _protocol(client, token, acc)
    assert client.post(f"/api/accounts/{acc}/competency",
                       json={"protocol_id": p["id"]}, headers=auth(token)).status_code == 400


def test_bad_protocol_404(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "tr3@corp.com", "Vrco")
    assert client.post(f"/api/accounts/{acc}/competency",
                       json={"protocol_id": 99999, "trainee": "x"},
                       headers=auth(token)).status_code == 404


def test_acknowledge_sets_expiry_one_year_out(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "tr4@corp.com", "Wrco")
    p = _protocol(client, token, acc)
    rec = client.post(f"/api/accounts/{acc}/competency",
                      json={"protocol_id": p["id"], "trainee": "J. Doe"},
                      headers=auth(token)).get_json()["training"]

    res = client.post(f"/api/accounts/{acc}/competency/{rec['id']}/acknowledge",
                      json={}, headers=auth(token))
    ack = res.get_json()["training"]
    assert ack["status"] == "acknowledged"
    assert ack["acknowledged_at"]
    assert ack["acknowledgement"]                  # default read-and-understood statement
    assert ack["is_current"] is True
    assert ack["is_expired"] is False

    expected = (datetime.utcnow().date() + timedelta(days=365)).isoformat()
    assert ack["expires_at"] == expected


def test_expired_training_is_not_current(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "tr5@corp.com", "Xrco")
    p = _protocol(client, token, acc)
    rec = client.post(f"/api/accounts/{acc}/competency",
                      json={"protocol_id": p["id"], "trainee": "J. Doe"},
                      headers=auth(token)).get_json()["training"]

    yesterday = (datetime.utcnow().date() - timedelta(days=1)).isoformat()
    ack = client.post(f"/api/accounts/{acc}/competency/{rec['id']}/acknowledge",
                      json={"expires_at": yesterday}, headers=auth(token)).get_json()["training"]
    assert ack["is_expired"] is True
    assert ack["is_current"] is False


def test_status_filters(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "tr6@corp.com", "Yrco")
    h = auth(token)
    p = _protocol(client, token, acc)
    # One assigned, one acknowledged-current, one expired.
    a = client.post(f"/api/accounts/{acc}/competency", json={"protocol_id": p["id"], "trainee": "A"}, headers=h).get_json()["training"]
    b = client.post(f"/api/accounts/{acc}/competency", json={"protocol_id": p["id"], "trainee": "B"}, headers=h).get_json()["training"]
    c = client.post(f"/api/accounts/{acc}/competency", json={"protocol_id": p["id"], "trainee": "C"}, headers=h).get_json()["training"]
    client.post(f"/api/accounts/{acc}/competency/{b['id']}/acknowledge", json={}, headers=h)
    past = (datetime.utcnow().date() - timedelta(days=1)).isoformat()
    client.post(f"/api/accounts/{acc}/competency/{c['id']}/acknowledge", json={"expires_at": past}, headers=h)

    assert len(client.get(f"/api/accounts/{acc}/competency?status=assigned", headers=h).get_json()["training"]) == 1
    assert len(client.get(f"/api/accounts/{acc}/competency?status=current", headers=h).get_json()["training"]) == 1
    assert len(client.get(f"/api/accounts/{acc}/competency?status=expired", headers=h).get_json()["training"]) == 1
    assert len(client.get(f"/api/accounts/{acc}/competency", headers=h).get_json()["training"]) == 3


def test_delete_training(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "tr7@corp.com", "Zrco")
    h = auth(token)
    p = _protocol(client, token, acc)
    rec = client.post(f"/api/accounts/{acc}/competency",
                      json={"protocol_id": p["id"], "trainee": "J"}, headers=h).get_json()["training"]
    assert client.delete(f"/api/accounts/{acc}/competency/{rec['id']}", headers=h).status_code == 200
    assert len(client.get(f"/api/accounts/{acc}/competency", headers=h).get_json()["training"]) == 0


def test_cross_account_isolation(client):
    burn_superadmin(client)
    t1, a1, _ = make_owner(client, "tr8@corp.com", "Aqco")
    t2, a2, _ = make_owner(client, "tr9@corp.com", "Bqco")
    p = _protocol(client, t1, a1)
    rec = client.post(f"/api/accounts/{a1}/competency",
                      json={"protocol_id": p["id"], "trainee": "J"}, headers=auth(t1)).get_json()["training"]
    # User 2 can't acknowledge or delete account 1's record.
    assert client.post(f"/api/accounts/{a1}/competency/{rec['id']}/acknowledge",
                       json={}, headers=auth(t2)).status_code == 403
    assert client.delete(f"/api/accounts/{a2}/competency/{rec['id']}",
                         headers=auth(t2)).status_code == 404
