"""Typed step components (LOTO/safety block library)."""

import pytest

from util import auth, burn_superadmin, make_owner


@pytest.fixture()
def protocol(client):
    burn_superadmin(client)
    token, acc_id, _ = make_owner(client, "owner@x.com", "Acme")
    pid = client.post(f"/api/accounts/{acc_id}/protocols", headers=auth(token),
                      json={"title": "LOTO"}).get_json()["protocol"]["id"]
    sid = client.post(f"/api/accounts/{acc_id}/protocols/{pid}/steps", headers=auth(token),
                      json={"title": "Isolate"}).get_json()["step"]["id"]
    return client, token, acc_id, pid, sid


def test_add_typed_components(protocol):
    client, token, acc_id, pid, sid = protocol
    res = client.put(f"/api/accounts/{acc_id}/protocols/{pid}/steps/{sid}", headers=auth(token),
                     json={"components": [
                         {"type": "ppe", "value": "Arc-flash suit, insulated gloves"},
                         {"type": "energy_source", "value": "480V electrical"},
                         {"type": "lockout_tag", "value": "LT-4471"},
                         {"type": "second_signature", "value": True},
                     ]})
    comps = res.get_json()["step"]["components"]
    assert len(comps) == 4
    by = {c["type"]: c["value"] for c in comps}
    assert by["ppe"] == "Arc-flash suit, insulated gloves"
    assert by["energy_source"] == "480V electrical"
    assert by["second_signature"] is True  # flag coerced to bool


def test_invalid_component_types_dropped(protocol):
    client, token, acc_id, pid, sid = protocol
    res = client.put(f"/api/accounts/{acc_id}/protocols/{pid}/steps/{sid}", headers=auth(token),
                     json={"components": [
                         {"type": "ppe", "value": "Goggles"},
                         {"type": "bogus", "value": "nope"},
                         "not a dict",
                     ]})
    comps = res.get_json()["step"]["components"]
    assert [c["type"] for c in comps] == ["ppe"]


def test_flag_component_defaults_true(protocol):
    client, token, acc_id, pid, sid = protocol
    res = client.put(f"/api/accounts/{acc_id}/protocols/{pid}/steps/{sid}", headers=auth(token),
                     json={"components": [{"type": "verification_photo"}]})
    assert res.get_json()["step"]["components"][0]["value"] is True


def test_components_snapshot_into_run(protocol):
    client, token, acc_id, pid, sid = protocol
    client.put(f"/api/accounts/{acc_id}/protocols/{pid}/steps/{sid}", headers=auth(token),
               json={"components": [{"type": "hazard_class", "value": "Arc Flash"}]})
    run = client.post(f"/api/accounts/{acc_id}/protocols/{pid}/runs", headers=auth(token)).get_json()["run"]
    comps = run["steps"][0]["components"]
    assert comps == [{"type": "hazard_class", "value": "Arc Flash"}]
