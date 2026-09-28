"""Run-time gates: verification-photo and second-signature block completion."""

from util import burn_superadmin, make_owner, auth, register, login


def _run_with_gated_step(client, token, acc, components):
    h = auth(token)
    p = client.post(f"/api/accounts/{acc}/protocols", json={"title": "LOTO"}, headers=h).get_json()["protocol"]
    client.post(f"/api/accounts/{acc}/protocols/{p['id']}/steps",
                json={"title": "Isolate", "components": components}, headers=h)
    run = client.post(f"/api/accounts/{acc}/protocols/{p['id']}/runs", json={}, headers=h).get_json()["run"]
    return run


def test_verification_photo_gate_blocks_then_allows(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "g1@corp.com", "Gco")
    h = auth(token)
    run = _run_with_gated_step(client, token, acc,
                              [{"type": "verification_photo", "value": True}])
    sid = run["steps"][0]["id"]

    # Done is blocked until a verification is recorded.
    blocked = client.patch(f"/api/accounts/{acc}/runs/{run['id']}/steps/{sid}",
                           json={"status": "done"}, headers=h)
    assert blocked.status_code == 400
    assert "verification photo" in blocked.get_json()["error"].lower()

    # Record verification, then Done succeeds.
    ok = client.patch(f"/api/accounts/{acc}/runs/{run['id']}/steps/{sid}",
                      json={"status": "done", "verification": "photo IMG_4471.jpg attached"}, headers=h)
    assert ok.status_code == 200
    body = ok.get_json()["step"]
    assert body["status"] == "done" and body["verification"]


def test_gates_do_not_block_fail_or_skip(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "g2@corp.com", "Hco")
    h = auth(token)
    run = _run_with_gated_step(client, token, acc,
                              [{"type": "second_signature", "value": True}])
    sid = run["steps"][0]["id"]
    # Fail and Skip are always allowed even with an unmet gate.
    assert client.patch(f"/api/accounts/{acc}/runs/{run['id']}/steps/{sid}",
                        json={"status": "failed"}, headers=h).status_code == 200
    assert client.patch(f"/api/accounts/{acc}/runs/{run['id']}/steps/{sid}",
                        json={"status": "skipped"}, headers=h).status_code == 200


def test_second_signature_gate_requires_a_different_member(client):
    burn_superadmin(client)
    owner_t, acc, _ = make_owner(client, "owner@corp.com", "Ico")
    # Add a second member (the witness).
    register(client, "peer@corp.com")
    client.post(f"/api/accounts/{acc}/members",
                json={"email": "peer@corp.com", "role": "member"}, headers=auth(owner_t))

    run = _run_with_gated_step(client, owner_t, acc,
                              [{"type": "second_signature", "value": True}])
    sid = run["steps"][0]["id"]
    url = f"/api/accounts/{acc}/runs/{run['id']}/steps/{sid}"

    # Blocked with no witness.
    assert client.patch(url, json={"status": "done"}, headers=auth(owner_t)).status_code == 400

    # The executor cannot witness their own step.
    self_sig = client.patch(url, json={"status": "done", "witness_email": "owner@corp.com",
                                       "witness_password": "password123"}, headers=auth(owner_t))
    assert self_sig.status_code == 400 and "different person" in self_sig.get_json()["error"]

    # Wrong password is rejected.
    bad = client.patch(url, json={"status": "done", "witness_email": "peer@corp.com",
                                  "witness_password": "wrong"}, headers=auth(owner_t))
    assert bad.status_code == 401

    # A valid peer sign-off completes the step.
    ok = client.patch(url, json={"status": "done", "witness_email": "peer@corp.com",
                                 "witness_password": "password123"}, headers=auth(owner_t))
    assert ok.status_code == 200
    step = ok.get_json()["step"]
    assert step["status"] == "done" and step["witnessed_by"] and step["witnessed_at"]


def test_non_member_cannot_witness(client):
    burn_superadmin(client)
    owner_t, acc, _ = make_owner(client, "o2@corp.com", "Jco")
    register(client, "outsider@corp.com")     # exists, but not a member of this account
    run = _run_with_gated_step(client, owner_t, acc,
                              [{"type": "second_signature", "value": True}])
    sid = run["steps"][0]["id"]
    res = client.patch(f"/api/accounts/{acc}/runs/{run['id']}/steps/{sid}",
                       json={"status": "done", "witness_email": "outsider@corp.com",
                             "witness_password": "password123"}, headers=auth(owner_t))
    assert res.status_code == 403


def test_ungated_step_completes_freely(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "g3@corp.com", "Kco")
    h = auth(token)
    run = _run_with_gated_step(client, token, acc, [{"type": "ppe", "value": "Gloves"}])
    sid = run["steps"][0]["id"]
    assert client.patch(f"/api/accounts/{acc}/runs/{run['id']}/steps/{sid}",
                        json={"status": "done"}, headers=h).status_code == 200
