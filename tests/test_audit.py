"""Audit trail — immutable, account-scoped record of regulated actions."""

from util import burn_superadmin, make_owner, make_owner as _mo, auth, register, login


def _events(client, acc, token, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"/api/accounts/{acc}/audit" + (f"?{q}" if q else "")
    return client.get(url, headers=auth(token)).get_json()["events"]


def _protocol_with_step(client, token, acc):
    h = auth(token)
    p = client.post(f"/api/accounts/{acc}/protocols", json={"title": "SOP"}, headers=h).get_json()["protocol"]
    client.post(f"/api/accounts/{acc}/protocols/{p['id']}/steps", json={"title": "A"}, headers=h)
    return p["id"]


def test_protocol_creation_is_audited(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "au1@corp.com", "Auco")
    client.post(f"/api/accounts/{acc}/protocols", json={"title": "Gowning"}, headers=auth(token))
    events = _events(client, acc, token)
    assert any(e["action"] == "protocol.created" and "Gowning" in e["summary"] for e in events)
    ev = events[0]
    assert ev["actor"] and ev["entity_type"] == "protocol" and ev["created_at"]


def test_lifecycle_transitions_are_audited(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "au2@corp.com", "Buco")
    h = auth(token)
    pid = _protocol_with_step(client, token, acc)
    client.post(f"/api/accounts/{acc}/protocols/{pid}/submit", headers=h)
    client.post(f"/api/accounts/{acc}/protocols/{pid}/sign",
                json={"role": "approver", "decision": "approved", "password": "password123"}, headers=h)
    client.post(f"/api/accounts/{acc}/protocols/{pid}/make-effective", json={}, headers=h)

    actions = [e["action"] for e in _events(client, acc, token)]
    assert "protocol.submitted" in actions
    assert "protocol.signed" in actions
    assert "protocol.made_effective" in actions


def test_sign_event_captures_meaning(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "au3@corp.com", "Cuco")
    h = auth(token)
    pid = _protocol_with_step(client, token, acc)
    client.post(f"/api/accounts/{acc}/protocols/{pid}/submit", headers=h)
    client.post(f"/api/accounts/{acc}/protocols/{pid}/sign",
                json={"role": "approver", "decision": "approved", "password": "password123",
                      "meaning": "Approved for use"}, headers=h)
    sign = next(e for e in _events(client, acc, token) if e["action"] == "protocol.signed")
    assert sign["detail"]["decision"] == "approved"
    assert sign["detail"]["meaning"] == "Approved for use"


def test_deviation_and_competency_audited(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "au4@corp.com", "Duco")
    h = auth(token)
    pid = _protocol_with_step(client, token, acc)
    dev = client.post(f"/api/accounts/{acc}/deviations",
                      json={"title": "leak", "severity": "major"}, headers=h).get_json()["deviation"]
    client.patch(f"/api/accounts/{acc}/deviations/{dev['id']}", json={"status": "resolved"}, headers=h)
    rec = client.post(f"/api/accounts/{acc}/competency",
                      json={"protocol_id": pid, "trainee": "J. Doe"}, headers=h).get_json()["training"]
    client.post(f"/api/accounts/{acc}/competency/{rec['id']}/acknowledge", json={}, headers=h)

    actions = [e["action"] for e in _events(client, acc, token)]
    assert "deviation.created" in actions
    assert "deviation.resolved" in actions
    assert "competency.acknowledged" in actions


def test_filter_by_action(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "au5@corp.com", "Euco")
    _protocol_with_step(client, token, acc)
    _protocol_with_step(client, token, acc)
    created = _events(client, acc, token, action="protocol.created")
    assert len(created) == 2 and all(e["action"] == "protocol.created" for e in created)


def test_export_csv(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "au6@corp.com", "Fuco")
    _protocol_with_step(client, token, acc)
    res = client.get(f"/api/accounts/{acc}/audit/export.csv", headers=auth(token))
    assert res.status_code == 200
    assert res.headers["Content-Type"].startswith("text/csv")
    assert "attachment" in res.headers["Content-Disposition"]
    body = res.data.decode()
    assert "Timestamp (UTC),Actor,Action,Entity,Entity ID,Summary" in body
    assert "protocol.created" in body


def test_audit_is_account_scoped(client):
    burn_superadmin(client)
    t1, a1, _ = make_owner(client, "au7@corp.com", "Guco")
    t2, a2, _ = make_owner(client, "au8@corp.com", "Huco")
    _protocol_with_step(client, t1, a1)
    # Account 2's trail does not see account 1's events…
    assert _events(client, a2, t2) == []
    # …and a non-member is refused.
    assert client.get(f"/api/accounts/{a1}/audit", headers=auth(t2)).status_code == 403


def test_run_finish_audited(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "au9@corp.com", "Iuco")
    h = auth(token)
    pid = _protocol_with_step(client, token, acc)
    run = client.post(f"/api/accounts/{acc}/protocols/{pid}/runs", json={}, headers=h).get_json()["run"]
    client.post(f"/api/accounts/{acc}/runs/{run['id']}/finish", headers=h)
    assert any(e["action"] == "run.finished" for e in _events(client, acc, token))
