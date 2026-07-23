"""Protocol/run analytics aggregation."""

import pytest

from util import auth, burn_superadmin, make_owner


@pytest.fixture()
def seeded(client):
    burn_superadmin(client)
    token, acc_id, _ = make_owner(client, "owner@x.com", "Acme")
    pid = client.post(f"/api/accounts/{acc_id}/protocols", headers=auth(token),
                      json={"title": "Thaw"}).get_json()["protocol"]["id"]
    for t in ["a", "b"]:
        client.post(f"/api/accounts/{acc_id}/protocols/{pid}/steps", headers=auth(token), json={"title": t})
    return client, token, acc_id, pid


def test_empty_analytics(client):
    burn_superadmin(client)
    token, acc_id, _ = make_owner(client, "o@x.com", "Acme")
    body = client.get(f"/api/accounts/{acc_id}/analytics", headers=auth(token)).get_json()
    assert body["totals"] == {
        "protocols": 0, "effective_sops": 0, "runs": 0, "completed_runs": 0,
        "deviations": 0, "open_deviations": 0,
    }
    assert body["avg_run_duration_seconds"] == 0
    assert len(body["runs_by_week"]) == 8


def test_analytics_counts_runs_and_outcomes(seeded):
    client, token, acc_id, pid = seeded

    # Run 1: one done, one failed, then finish.
    run = client.post(f"/api/accounts/{acc_id}/protocols/{pid}/runs", headers=auth(token)).get_json()["run"]
    s1, s2 = [s["id"] for s in run["steps"]]
    client.patch(f"/api/accounts/{acc_id}/runs/{run['id']}/steps/{s1}", headers=auth(token), json={"status": "done"})
    client.patch(f"/api/accounts/{acc_id}/runs/{run['id']}/steps/{s2}", headers=auth(token), json={"status": "failed"})
    client.post(f"/api/accounts/{acc_id}/runs/{run['id']}/finish", headers=auth(token))

    # Run 2: left in progress.
    client.post(f"/api/accounts/{acc_id}/protocols/{pid}/runs", headers=auth(token))

    body = client.get(f"/api/accounts/{acc_id}/analytics", headers=auth(token)).get_json()
    assert body["totals"]["protocols"] == 1
    assert body["totals"]["runs"] == 2
    assert body["totals"]["completed_runs"] == 1
    assert body["outcomes"]["done"] == 1
    assert body["outcomes"]["failed"] == 1   # deviation
    # 4 run-steps total (2 per run); 2 still pending
    assert body["outcomes"]["pending"] == 2
    assert body["top_protocols"][0] == {"title": "Thaw", "runs": 2}


def test_analytics_is_scoped(seeded):
    client, token, acc_id, pid = seeded
    b_tok, _, _ = make_owner(client, "b@x.com", "Beta")
    assert client.get(f"/api/accounts/{acc_id}/analytics", headers=auth(b_tok)).status_code == 403
    assert client.get(f"/api/accounts/{acc_id}/analytics").status_code == 401
