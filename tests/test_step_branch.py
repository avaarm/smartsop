"""Conditional / branching decisions on steps."""

import pytest

from util import auth, burn_superadmin, make_owner


@pytest.fixture()
def step(client):
    burn_superadmin(client)
    token, acc_id, _ = make_owner(client, "owner@x.com", "Acme")
    pid = client.post(f"/api/accounts/{acc_id}/protocols", headers=auth(token),
                      json={"title": "Lockout"}).get_json()["protocol"]["id"]
    sid = client.post(f"/api/accounts/{acc_id}/protocols/{pid}/steps", headers=auth(token),
                      json={"title": "Check voltage"}).get_json()["step"]["id"]
    return client, token, acc_id, pid, sid


def test_set_branch(step):
    client, token, acc_id, pid, sid = step
    res = client.put(f"/api/accounts/{acc_id}/protocols/{pid}/steps/{sid}", headers=auth(token),
                     json={"branch": {"question": "Is voltage > 600V?", "options": [
                         {"label": "Yes", "action": "goto", "target": 12},
                         {"label": "No", "action": "continue"},
                         {"label": "Unsure", "action": "halt"},
                     ]}})
    b = res.get_json()["step"]["branch"]
    assert b["question"] == "Is voltage > 600V?"
    assert b["options"][0] == {"label": "Yes", "action": "goto", "target": 12}
    assert b["options"][1]["action"] == "continue" and b["options"][1]["target"] is None
    assert b["options"][2]["action"] == "halt"


def test_invalid_action_defaults_continue(step):
    client, token, acc_id, pid, sid = step
    res = client.put(f"/api/accounts/{acc_id}/protocols/{pid}/steps/{sid}", headers=auth(token),
                     json={"branch": {"question": "q", "options": [{"label": "x", "action": "bogus"}]}})
    assert res.get_json()["step"]["branch"]["options"][0]["action"] == "continue"


def test_goto_target_dropped_for_non_goto(step):
    client, token, acc_id, pid, sid = step
    res = client.put(f"/api/accounts/{acc_id}/protocols/{pid}/steps/{sid}", headers=auth(token),
                     json={"branch": {"question": "q", "options": [{"label": "x", "action": "continue", "target": 5}]}})
    assert res.get_json()["step"]["branch"]["options"][0]["target"] is None


def test_empty_branch_clears(step):
    client, token, acc_id, pid, sid = step
    client.put(f"/api/accounts/{acc_id}/protocols/{pid}/steps/{sid}", headers=auth(token),
               json={"branch": {"question": "q", "options": [{"label": "x", "action": "halt"}]}})
    res = client.put(f"/api/accounts/{acc_id}/protocols/{pid}/steps/{sid}", headers=auth(token),
                     json={"branch": {"question": "", "options": []}})
    assert res.get_json()["step"]["branch"] is None


def test_branch_snapshots_into_run(step):
    client, token, acc_id, pid, sid = step
    client.put(f"/api/accounts/{acc_id}/protocols/{pid}/steps/{sid}", headers=auth(token),
               json={"branch": {"question": "OK?", "options": [{"label": "No", "action": "halt"}]}})
    run = client.post(f"/api/accounts/{acc_id}/protocols/{pid}/runs", headers=auth(token)).get_json()["run"]
    assert run["steps"][0]["branch"]["question"] == "OK?"
    assert run["steps"][0]["branch"]["options"][0]["action"] == "halt"
