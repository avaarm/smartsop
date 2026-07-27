"""Scheduling / assignments: assign an SOP, due dates, recurrence, start→run."""

from datetime import datetime, timedelta

from util import burn_superadmin, make_owner, auth


def _runnable_protocol(client, token, account_id, title="PM Round"):
    h = auth(token)
    p = client.post(f"/api/accounts/{account_id}/protocols",
                    json={"title": title}, headers=h).get_json()["protocol"]
    client.post(f"/api/accounts/{account_id}/protocols/{p['id']}/steps",
                json={"title": "Inspect", "description": "Walk the line."}, headers=h)
    return p["id"]


def _yesterday():
    return (datetime.utcnow().date() - timedelta(days=1)).isoformat()


def test_create_assignment(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "s1@corp.com", "Sco")
    pid = _runnable_protocol(client, token, acc)
    res = client.post(f"/api/accounts/{acc}/assignments", json={
        "protocol_id": pid, "assigned_to": "Night shift",
        "due_date": "2026-08-01", "recurrence": "monthly",
        "notes": "Monthly PM round.",
    }, headers=auth(token))
    assert res.status_code == 201
    a = res.get_json()["assignment"]
    assert a["protocol_title"] == "PM Round"       # snapshotted
    assert a["assigned_by"]                          # actor recorded
    assert a["status"] == "pending"
    assert a["recurrence"] == "monthly"


def test_create_requires_valid_protocol(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "s2@corp.com", "Tco")
    assert client.post(f"/api/accounts/{acc}/assignments",
                       json={"protocol_id": 99999}, headers=auth(token)).status_code == 404


def test_invalid_recurrence_rejected(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "s3@corp.com", "Uco")
    pid = _runnable_protocol(client, token, acc)
    assert client.post(f"/api/accounts/{acc}/assignments",
                       json={"protocol_id": pid, "recurrence": "hourly"},
                       headers=auth(token)).status_code == 400


def test_overdue_flag(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "s4@corp.com", "Vco")
    pid = _runnable_protocol(client, token, acc)
    a = client.post(f"/api/accounts/{acc}/assignments",
                    json={"protocol_id": pid, "due_date": _yesterday()},
                    headers=auth(token)).get_json()["assignment"]
    assert a["is_overdue"] is True

    # A due date in the future is not overdue.
    future = client.post(f"/api/accounts/{acc}/assignments",
                         json={"protocol_id": pid, "due_date": "2999-01-01"},
                         headers=auth(token)).get_json()["assignment"]
    assert future["is_overdue"] is False


def test_list_sorted_pending_first_by_due(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "s5@corp.com", "Wco")
    h = auth(token)
    pid = _runnable_protocol(client, token, acc)
    client.post(f"/api/accounts/{acc}/assignments",
                json={"protocol_id": pid, "due_date": "2026-09-01"}, headers=h)
    client.post(f"/api/accounts/{acc}/assignments",
                json={"protocol_id": pid, "due_date": "2026-08-01"}, headers=h)

    items = client.get(f"/api/accounts/{acc}/assignments", headers=h).get_json()["assignments"]
    assert [a["due_date"] for a in items] == ["2026-08-01", "2026-09-01"]


def test_complete_spawns_next_monthly_occurrence(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "s6@corp.com", "Xco")
    h = auth(token)
    pid = _runnable_protocol(client, token, acc)
    a = client.post(f"/api/accounts/{acc}/assignments",
                    json={"protocol_id": pid, "due_date": "2026-01-31", "recurrence": "monthly"},
                    headers=h).get_json()["assignment"]

    res = client.patch(f"/api/accounts/{acc}/assignments/{a['id']}",
                       json={"status": "completed"}, headers=h).get_json()
    assert res["assignment"]["status"] == "completed"
    assert res["assignment"]["completed_at"]
    # Jan 31 + 1 month clamps to Feb 28 (2026 is not a leap year).
    assert res["next_occurrence"]["due_date"] == "2026-02-28"
    assert res["next_occurrence"]["status"] == "pending"

    # There are now exactly two: one completed, one fresh pending.
    items = client.get(f"/api/accounts/{acc}/assignments", headers=h).get_json()["assignments"]
    assert len(items) == 2


def test_complete_non_recurring_spawns_nothing(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "s7@corp.com", "Yco")
    h = auth(token)
    pid = _runnable_protocol(client, token, acc)
    a = client.post(f"/api/accounts/{acc}/assignments",
                    json={"protocol_id": pid, "due_date": "2026-05-01"}, headers=h
                    ).get_json()["assignment"]
    res = client.patch(f"/api/accounts/{acc}/assignments/{a['id']}",
                       json={"status": "completed"}, headers=h).get_json()
    assert "next_occurrence" not in res
    items = client.get(f"/api/accounts/{acc}/assignments", headers=h).get_json()["assignments"]
    assert len(items) == 1


def test_completing_twice_does_not_double_spawn(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "s8@corp.com", "Zco")
    h = auth(token)
    pid = _runnable_protocol(client, token, acc)
    a = client.post(f"/api/accounts/{acc}/assignments",
                    json={"protocol_id": pid, "due_date": "2026-03-15", "recurrence": "weekly"},
                    headers=h).get_json()["assignment"]
    client.patch(f"/api/accounts/{acc}/assignments/{a['id']}", json={"status": "completed"}, headers=h)
    # Re-PATCH an already-completed task: no second spawn (was_open guard).
    res = client.patch(f"/api/accounts/{acc}/assignments/{a['id']}",
                       json={"status": "completed"}, headers=h).get_json()
    assert "next_occurrence" not in res
    items = client.get(f"/api/accounts/{acc}/assignments", headers=h).get_json()["assignments"]
    assert len(items) == 2   # original + one spawned, not two


def test_start_assignment_creates_linked_run(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "s9@corp.com", "Aaco")
    h = auth(token)
    pid = _runnable_protocol(client, token, acc)
    a = client.post(f"/api/accounts/{acc}/assignments",
                    json={"protocol_id": pid}, headers=h).get_json()["assignment"]

    res = client.post(f"/api/accounts/{acc}/assignments/{a['id']}/start", headers=h)
    assert res.status_code == 201
    body = res.get_json()
    assert body["run"]["protocol_id"] == pid
    assert body["assignment"]["run_id"] == body["run"]["id"]


def test_delete_assignment(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "s10@corp.com", "Abco")
    h = auth(token)
    pid = _runnable_protocol(client, token, acc)
    a = client.post(f"/api/accounts/{acc}/assignments",
                    json={"protocol_id": pid}, headers=h).get_json()["assignment"]
    assert client.delete(f"/api/accounts/{acc}/assignments/{a['id']}", headers=h).status_code == 200
    assert client.get(f"/api/accounts/{acc}/assignments/{a['id']}", headers=h).status_code == 404


def test_cross_account_isolation(client):
    burn_superadmin(client)
    t1, a1, _ = make_owner(client, "s11@corp.com", "Acco")
    t2, a2, _ = make_owner(client, "s12@corp.com", "Adco")
    pid = _runnable_protocol(client, t1, a1)
    a = client.post(f"/api/accounts/{a1}/assignments",
                    json={"protocol_id": pid}, headers=auth(t1)).get_json()["assignment"]
    assert client.get(f"/api/accounts/{a2}/assignments/{a['id']}",
                      headers=auth(t2)).status_code == 404
    assert client.get(f"/api/accounts/{a1}/assignments/{a['id']}",
                      headers=auth(t2)).status_code == 403
