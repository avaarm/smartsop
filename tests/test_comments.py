"""Comments & collaboration: step + protocol level, threads, pin, resolve."""

from util import burn_superadmin, register, make_owner, auth


def _protocol_with_step(client, token, account_id):
    h = auth(token)
    p = client.post(f"/api/accounts/{account_id}/protocols",
                    json={"title": "SOP"}, headers=h).get_json()["protocol"]
    s = client.post(f"/api/accounts/{account_id}/protocols/{p['id']}/steps",
                    json={"title": "Isolate"}, headers=h).get_json()["step"]
    return p["id"], s["id"]


def _c(client, acc, pid, token):
    return f"/api/accounts/{acc}/protocols/{pid}/comments"


def test_protocol_level_comment(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "c1@corp.com", "Cco")
    pid, _ = _protocol_with_step(client, token, acc)
    res = client.post(_c(client, acc, pid, token),
                      json={"body": "Should we add a second-signature step?"}, headers=auth(token))
    assert res.status_code == 201
    c = res.get_json()["comment"]
    assert c["level"] == "protocol"
    assert c["step_id"] is None
    assert c["author"]


def test_step_level_comment(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "c2@corp.com", "Dco")
    pid, sid = _protocol_with_step(client, token, acc)
    c = client.post(_c(client, acc, pid, token),
                    json={"body": "Torque spec looks low.", "step_id": sid},
                    headers=auth(token)).get_json()["comment"]
    assert c["level"] == "step"
    assert c["step_id"] == sid


def test_body_required(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "c3@corp.com", "Eco")
    pid, _ = _protocol_with_step(client, token, acc)
    assert client.post(_c(client, acc, pid, token), json={"body": "  "},
                       headers=auth(token)).status_code == 400


def test_step_must_belong_to_protocol(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "c4@corp.com", "Fco")
    pid, _ = _protocol_with_step(client, token, acc)
    assert client.post(_c(client, acc, pid, token),
                       json={"body": "x", "step_id": 99999}, headers=auth(token)).status_code == 404


def test_threaded_reply_inherits_anchor(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "c5@corp.com", "Gco")
    pid, sid = _protocol_with_step(client, token, acc)
    h = auth(token)
    parent = client.post(_c(client, acc, pid, token),
                         json={"body": "Torque spec?", "step_id": sid}, headers=h).get_json()["comment"]
    reply = client.post(_c(client, acc, pid, token),
                        json={"body": "Confirmed 45 Nm.", "parent_id": parent["id"]},
                        headers=h).get_json()["comment"]
    assert reply["parent_id"] == parent["id"]
    assert reply["step_id"] == sid          # inherited from parent

    # A reply to a reply flattens onto the top-level parent (one level deep).
    reply2 = client.post(_c(client, acc, pid, token),
                         json={"body": "Thanks.", "parent_id": reply["id"]},
                         headers=h).get_json()["comment"]
    assert reply2["parent_id"] == parent["id"]


def test_pin_and_resolve(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "c6@corp.com", "Hco")
    pid, _ = _protocol_with_step(client, token, acc)
    h = auth(token)
    c = client.post(_c(client, acc, pid, token), json={"body": "Canonical answer."},
                    headers=h).get_json()["comment"]

    pinned = client.patch(f"{_c(client, acc, pid, token)}/{c['id']}",
                          json={"is_pinned": True}, headers=h).get_json()["comment"]
    assert pinned["is_pinned"] is True

    resolved = client.patch(f"{_c(client, acc, pid, token)}/{c['id']}",
                            json={"resolved": True}, headers=h).get_json()["comment"]
    assert resolved["resolved"] is True and resolved["resolved_by"] and resolved["resolved_at"]

    reopened = client.patch(f"{_c(client, acc, pid, token)}/{c['id']}",
                            json={"resolved": False}, headers=h).get_json()["comment"]
    assert reopened["resolved"] is False and reopened["resolved_at"] is None


def test_only_author_can_edit_body(client):
    burn_superadmin(client)
    owner_t, acc, _ = make_owner(client, "owner@corp.com", "Ico")
    # A second member of the same account.
    register(client, "member@corp.com")
    from util import login
    member_t = login(client, "member@corp.com").get_json()["token"]
    client.post(f"/api/accounts/{acc}/members",
                json={"email": "member@corp.com", "role": "member"}, headers=auth(owner_t))

    pid, _ = _protocol_with_step(client, owner_t, acc)
    c = client.post(_c(client, acc, pid, owner_t), json={"body": "owner's note"},
                    headers=auth(owner_t)).get_json()["comment"]
    # Member cannot edit the owner's body...
    assert client.patch(f"{_c(client, acc, pid, owner_t)}/{c['id']}",
                        json={"body": "hijacked"}, headers=auth(member_t)).status_code == 403
    # ...but can resolve the thread.
    assert client.patch(f"{_c(client, acc, pid, owner_t)}/{c['id']}",
                        json={"resolved": True}, headers=auth(member_t)).status_code == 200


def test_delete_removes_replies(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "c8@corp.com", "Jco")
    pid, _ = _protocol_with_step(client, token, acc)
    h = auth(token)
    parent = client.post(_c(client, acc, pid, token), json={"body": "q"}, headers=h).get_json()["comment"]
    client.post(_c(client, acc, pid, token), json={"body": "a", "parent_id": parent["id"]}, headers=h)
    assert len(client.get(_c(client, acc, pid, token), headers=h).get_json()["comments"]) == 2

    client.delete(f"{_c(client, acc, pid, token)}/{parent['id']}", headers=h)
    assert len(client.get(_c(client, acc, pid, token), headers=h).get_json()["comments"]) == 0


def test_cross_account_isolation(client):
    burn_superadmin(client)
    t1, a1, _ = make_owner(client, "c9@corp.com", "Kco")
    t2, a2, _ = make_owner(client, "c10@corp.com", "Lco")
    pid, _ = _protocol_with_step(client, t1, a1)
    client.post(_c(client, a1, pid, t1), json={"body": "secret"}, headers=auth(t1))
    # User 2 is not a member of account 1.
    assert client.get(_c(client, a1, pid, t2), headers=auth(t2)).status_code == 403
