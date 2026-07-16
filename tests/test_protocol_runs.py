"""Running a protocol: run records, per-step outcomes, and isolation."""

import pytest

from util import auth, burn_superadmin, make_owner


@pytest.fixture()
def protocol(client):
    """An owner with a 3-step protocol ready to run."""
    burn_superadmin(client)
    token, acc_id, _ = make_owner(client, "owner@x.com", "Acme")
    pid = client.post(f"/api/accounts/{acc_id}/protocols", headers=auth(token),
                      json={"title": "Thawing"}).get_json()["protocol"]["id"]
    for t, dur in [("Retrieve vial", 60), ("Warm to 37C", 120), ("Transfer", None)]:
        client.post(f"/api/accounts/{acc_id}/protocols/{pid}/steps", headers=auth(token),
                    json={"title": t, "duration_seconds": dur})
    return client, token, acc_id, pid


def _start(client, token, acc_id, pid, **kw):
    return client.post(f"/api/accounts/{acc_id}/protocols/{pid}/runs", headers=auth(token), json=kw)


def test_start_run_snapshots_steps(protocol):
    client, token, acc_id, pid = protocol
    res = _start(client, token, acc_id, pid, experiment_id="EXP-001")
    assert res.status_code == 201
    run = res.get_json()["run"]
    assert run["status"] == "running"
    assert run["protocol_title"] == "Thawing"
    assert run["experiment_id"] == "EXP-001"
    assert run["total_steps"] == 3 and run["completed_steps"] == 0
    assert [s["title"] for s in run["steps"]] == ["Retrieve vial", "Warm to 37C", "Transfer"]
    assert run["steps"][0]["duration_seconds"] == 60
    assert all(s["status"] == "pending" for s in run["steps"])


def test_run_snapshot_survives_protocol_edit(protocol):
    client, token, acc_id, pid = protocol
    run = _start(client, token, acc_id, pid).get_json()["run"]
    # Rename a protocol step after the run started
    step_id = run["steps"][0]["step_id"]
    client.put(f"/api/accounts/{acc_id}/protocols/{pid}/steps/{step_id}", headers=auth(token),
               json={"title": "CHANGED"})
    fetched = client.get(f"/api/accounts/{acc_id}/runs/{run['id']}", headers=auth(token)).get_json()["run"]
    assert fetched["steps"][0]["title"] == "Retrieve vial"  # snapshot unchanged


def test_cannot_run_empty_protocol(client):
    burn_superadmin(client)
    token, acc_id, _ = make_owner(client, "o@x.com", "Acme")
    pid = client.post(f"/api/accounts/{acc_id}/protocols", headers=auth(token),
                      json={"title": "Empty"}).get_json()["protocol"]["id"]
    assert _start(client, token, acc_id, pid).status_code == 400


def test_step_outcomes_done_fail_skip(protocol):
    client, token, acc_id, pid = protocol
    run = _start(client, token, acc_id, pid).get_json()["run"]
    rid = run["id"]
    s1, s2, s3 = [s["id"] for s in run["steps"]]

    done = client.patch(f"/api/accounts/{acc_id}/runs/{rid}/steps/{s1}", headers=auth(token),
                        json={"status": "done", "note": "vial intact"}).get_json()["step"]
    assert done["status"] == "done"
    assert done["completed_by"] == "owner@x.com" and done["completed_at"]
    assert done["note"] == "vial intact"

    assert client.patch(f"/api/accounts/{acc_id}/runs/{rid}/steps/{s2}", headers=auth(token),
                        json={"status": "failed"}).get_json()["step"]["status"] == "failed"
    assert client.patch(f"/api/accounts/{acc_id}/runs/{rid}/steps/{s3}", headers=auth(token),
                        json={"status": "skipped"}).get_json()["step"]["status"] == "skipped"

    fetched = client.get(f"/api/accounts/{acc_id}/runs/{rid}", headers=auth(token)).get_json()["run"]
    assert fetched["completed_steps"] == 3 and fetched["total_steps"] == 3


def test_reset_step_to_pending_clears_stamp(protocol):
    client, token, acc_id, pid = protocol
    run = _start(client, token, acc_id, pid).get_json()["run"]
    rid, s1 = run["id"], run["steps"][0]["id"]
    client.patch(f"/api/accounts/{acc_id}/runs/{rid}/steps/{s1}", headers=auth(token), json={"status": "done"})
    reset = client.patch(f"/api/accounts/{acc_id}/runs/{rid}/steps/{s1}", headers=auth(token),
                         json={"status": "pending"}).get_json()["step"]
    assert reset["status"] == "pending" and reset["completed_at"] is None and reset["completed_by"] == ""


def test_invalid_status_rejected(protocol):
    client, token, acc_id, pid = protocol
    run = _start(client, token, acc_id, pid).get_json()["run"]
    assert client.patch(f"/api/accounts/{acc_id}/runs/{run['id']}/steps/{run['steps'][0]['id']}",
                        headers=auth(token), json={"status": "bogus"}).status_code == 400


def test_finish_run(protocol):
    client, token, acc_id, pid = protocol
    run = _start(client, token, acc_id, pid).get_json()["run"]
    res = client.post(f"/api/accounts/{acc_id}/runs/{run['id']}/finish", headers=auth(token))
    assert res.status_code == 200
    body = res.get_json()["run"]
    assert body["status"] == "completed" and body["completed_at"]


def test_list_runs_and_filter_by_protocol(protocol):
    client, token, acc_id, pid = protocol
    _start(client, token, acc_id, pid)
    _start(client, token, acc_id, pid)
    body = client.get(f"/api/accounts/{acc_id}/runs", headers=auth(token)).get_json()
    assert body["total"] == 2
    filtered = client.get(f"/api/accounts/{acc_id}/runs?protocol_id={pid}", headers=auth(token)).get_json()
    assert filtered["total"] == 2


def test_run_requires_auth_and_is_account_scoped(protocol):
    client, token, acc_id, pid = protocol
    run = _start(client, token, acc_id, pid).get_json()["run"]
    assert client.get(f"/api/accounts/{acc_id}/runs/{run['id']}").status_code == 401

    b_tok, b_id, _ = make_owner(client, "b@x.com", "Beta")
    assert client.get(f"/api/accounts/{acc_id}/runs/{run['id']}", headers=auth(b_tok)).status_code == 403
    assert client.get(f"/api/accounts/{b_id}/runs/{run['id']}", headers=auth(b_tok)).status_code == 404
