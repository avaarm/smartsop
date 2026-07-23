"""Deviation / corrective-action (CAPA) capture: flag, list/filter, resolve."""

from util import burn_superadmin, make_owner, auth


def _seed_run(client, token, account_id):
    """Create a protocol with one step and start a run. Returns (protocol_id, run)."""
    h = auth(token)
    p = client.post(f"/api/accounts/{account_id}/protocols",
                    json={"title": "Lockout"}, headers=h).get_json()["protocol"]
    client.post(f"/api/accounts/{account_id}/protocols/{p['id']}/steps",
                json={"title": "Isolate", "description": "Open the breaker"}, headers=h)
    run = client.post(f"/api/accounts/{account_id}/protocols/{p['id']}/runs",
                      json={}, headers=h).get_json()["run"]
    return p["id"], run


def test_flag_deviation_during_run(client):
    burn_superadmin(client)
    token, account_id, _ = make_owner(client, "op@corp.com", "Corp")
    protocol_id, run = _seed_run(client, token, account_id)
    step = run["steps"][0]

    res = client.post(f"/api/accounts/{account_id}/deviations", json={
        "title": "Breaker would not open",
        "description": "Handle jammed",
        "severity": "major",
        "run_id": run["id"],
        "run_step_id": step["id"],
    }, headers=auth(token))
    assert res.status_code == 201
    dev = res.get_json()["deviation"]
    assert dev["severity"] == "major"
    assert dev["status"] == "open"
    assert dev["run_id"] == run["id"]
    assert dev["protocol_id"] == protocol_id      # inherited from the run
    assert dev["step_title"] == "Isolate"         # snapshotted from the run step
    assert dev["reported_by"]                       # actor recorded


def test_title_required(client):
    burn_superadmin(client)
    token, account_id, _ = make_owner(client, "op2@corp.com", "Corp2")
    res = client.post(f"/api/accounts/{account_id}/deviations",
                      json={"description": "no title"}, headers=auth(token))
    assert res.status_code == 400


def test_invalid_severity_rejected(client):
    burn_superadmin(client)
    token, account_id, _ = make_owner(client, "op3@corp.com", "Corp3")
    res = client.post(f"/api/accounts/{account_id}/deviations",
                      json={"title": "x", "severity": "catastrophic"}, headers=auth(token))
    assert res.status_code == 400


def test_standalone_deviation_without_run(client):
    burn_superadmin(client)
    token, account_id, _ = make_owner(client, "op4@corp.com", "Corp4")
    res = client.post(f"/api/accounts/{account_id}/deviations",
                      json={"title": "Near miss in aisle 3", "severity": "minor"},
                      headers=auth(token))
    assert res.status_code == 201
    dev = res.get_json()["deviation"]
    assert dev["run_id"] is None and dev["protocol_id"] is None


def test_bad_run_id_404(client):
    burn_superadmin(client)
    token, account_id, _ = make_owner(client, "op5@corp.com", "Corp5")
    res = client.post(f"/api/accounts/{account_id}/deviations",
                      json={"title": "x", "run_id": 99999}, headers=auth(token))
    assert res.status_code == 404


def test_list_and_filter(client):
    burn_superadmin(client)
    token, account_id, _ = make_owner(client, "op6@corp.com", "Corp6")
    h = auth(token)
    for sev in ("minor", "major", "critical"):
        client.post(f"/api/accounts/{account_id}/deviations",
                    json={"title": f"d-{sev}", "severity": sev}, headers=h)

    alld = client.get(f"/api/accounts/{account_id}/deviations", headers=h).get_json()
    assert alld["total"] == 3

    crit = client.get(f"/api/accounts/{account_id}/deviations?severity=critical",
                      headers=h).get_json()
    assert crit["total"] == 1 and crit["deviations"][0]["severity"] == "critical"

    opend = client.get(f"/api/accounts/{account_id}/deviations?status=open",
                       headers=h).get_json()
    assert opend["total"] == 3    # nothing resolved yet


def test_resolve_stamps_resolved_at(client):
    burn_superadmin(client)
    token, account_id, _ = make_owner(client, "op7@corp.com", "Corp7")
    h = auth(token)
    dev = client.post(f"/api/accounts/{account_id}/deviations",
                      json={"title": "leak", "severity": "major"}, headers=h
                      ).get_json()["deviation"]
    assert dev["resolved_at"] is None

    res = client.patch(f"/api/accounts/{account_id}/deviations/{dev['id']}", json={
        "status": "resolved",
        "corrective_action": "Replaced the gasket",
    }, headers=h)
    updated = res.get_json()["deviation"]
    assert updated["status"] == "resolved"
    assert updated["resolved_at"] is not None
    assert updated["corrective_action"] == "Replaced the gasket"

    # An open filter now excludes it.
    opend = client.get(f"/api/accounts/{account_id}/deviations?status=open",
                       headers=h).get_json()
    assert opend["total"] == 0

    # Reopening clears the resolved stamp.
    reopened = client.patch(f"/api/accounts/{account_id}/deviations/{dev['id']}",
                            json={"status": "investigating"}, headers=h
                            ).get_json()["deviation"]
    assert reopened["resolved_at"] is None


def test_analytics_counts_open_deviations(client):
    burn_superadmin(client)
    token, account_id, _ = make_owner(client, "op8@corp.com", "Corp8")
    h = auth(token)
    d1 = client.post(f"/api/accounts/{account_id}/deviations",
                     json={"title": "a", "severity": "critical"}, headers=h
                     ).get_json()["deviation"]
    client.post(f"/api/accounts/{account_id}/deviations",
                json={"title": "b", "severity": "minor"}, headers=h)
    client.patch(f"/api/accounts/{account_id}/deviations/{d1['id']}",
                 json={"status": "closed"}, headers=h)

    stats = client.get(f"/api/accounts/{account_id}/analytics", headers=h).get_json()
    assert stats["totals"]["deviations"] == 2
    assert stats["totals"]["open_deviations"] == 1        # one closed
    assert stats["deviation_severity"]["critical"] == 1


def test_cross_account_isolation(client):
    burn_superadmin(client)
    t1, a1, _ = make_owner(client, "a@corp.com", "Aco")
    t2, a2, _ = make_owner(client, "b@corp.com", "Bco")
    dev = client.post(f"/api/accounts/{a1}/deviations",
                      json={"title": "secret"}, headers=auth(t1)).get_json()["deviation"]

    # User 2 cannot read account 1's deviation via their own account scope.
    assert client.get(f"/api/accounts/{a2}/deviations/{dev['id']}",
                      headers=auth(t2)).status_code == 404
    # …nor by pointing at account 1 (not a member).
    assert client.get(f"/api/accounts/{a1}/deviations/{dev['id']}",
                      headers=auth(t2)).status_code == 403
