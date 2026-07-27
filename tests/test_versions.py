"""Version history, diff, and rollback for controlled documents."""

from util import burn_superadmin, make_owner, auth


def _protocol_with_steps(client, token, account_id, titles):
    h = auth(token)
    p = client.post(f"/api/accounts/{account_id}/protocols",
                    json={"title": "SOP"}, headers=h).get_json()["protocol"]
    for t in titles:
        client.post(f"/api/accounts/{account_id}/protocols/{p['id']}/steps",
                    json={"title": t}, headers=h)
    return p["id"]


def test_version_chain_from_any_member(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "v1@corp.com", "Vaco")
    h = auth(token)
    pid = _protocol_with_steps(client, token, acc, ["A", "B"])
    v2 = client.post(f"/api/accounts/{acc}/protocols/{pid}/new-version", headers=h
                     ).get_json()["protocol"]
    v3 = client.post(f"/api/accounts/{acc}/protocols/{v2['id']}/new-version", headers=h
                     ).get_json()["protocol"]

    # Ask from the middle of the chain — still get the whole lineage.
    body = client.get(f"/api/accounts/{acc}/protocols/{v2['id']}/versions", headers=h).get_json()
    versions = body["versions"]
    assert [v["version"] for v in versions] == [1, 2, 3]
    current = [v for v in versions if v["is_current"]]
    assert len(current) == 1 and current[0]["id"] == v2["id"]
    assert versions[-1]["id"] == v3["id"]


def test_diff_reports_added_modified_unchanged(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "v2@corp.com", "Vbco")
    h = auth(token)
    pid = _protocol_with_steps(client, token, acc, ["Step A", "Step B"])
    v2 = client.post(f"/api/accounts/{acc}/protocols/{pid}/new-version", headers=h
                     ).get_json()["protocol"]

    # Modify step B, add step C in v2.
    b_step = v2["steps"][1]
    client.put(f"/api/accounts/{acc}/protocols/{v2['id']}/steps/{b_step['id']}",
               json={"title": "Step B — revised"}, headers=h)
    client.post(f"/api/accounts/{acc}/protocols/{v2['id']}/steps",
                json={"title": "Step C"}, headers=h)

    body = client.get(f"/api/accounts/{acc}/protocols/{v2['id']}/diff", headers=h).get_json()
    assert body["from"]["version"] == 1 and body["to"]["version"] == 2
    steps = body["diff"]["steps"]
    changes = {s["index"]: s["change"] for s in steps}
    assert changes == {0: "unchanged", 1: "modified", 2: "added"}
    modified = next(s for s in steps if s["change"] == "modified")
    assert "title" in modified["fields"]


def test_diff_reports_removed_step_and_meta(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "v3@corp.com", "Vcco")
    h = auth(token)
    pid = _protocol_with_steps(client, token, acc, ["A", "B", "C"])
    v2 = client.post(f"/api/accounts/{acc}/protocols/{pid}/new-version", headers=h
                     ).get_json()["protocol"]

    client.delete(f"/api/accounts/{acc}/protocols/{v2['id']}/steps/{v2['steps'][2]['id']}",
                  headers=h)
    client.put(f"/api/accounts/{acc}/protocols/{v2['id']}",
               json={"title": "Renamed SOP"}, headers=h)

    body = client.get(f"/api/accounts/{acc}/protocols/{v2['id']}/diff", headers=h).get_json()
    assert any(c["field"] == "title" for c in body["diff"]["meta_changes"])
    assert any(s["change"] == "removed" for s in body["diff"]["steps"])


def test_diff_explicit_from_to(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "v4@corp.com", "Vdco")
    h = auth(token)
    pid = _protocol_with_steps(client, token, acc, ["A"])
    v2 = client.post(f"/api/accounts/{acc}/protocols/{pid}/new-version", headers=h
                     ).get_json()["protocol"]
    v3 = client.post(f"/api/accounts/{acc}/protocols/{v2['id']}/new-version", headers=h
                     ).get_json()["protocol"]

    body = client.get(
        f"/api/accounts/{acc}/protocols/{v3['id']}/diff?from={pid}&to={v3['id']}",
        headers=h).get_json()
    assert body["from"]["version"] == 1 and body["to"]["version"] == 3


def test_diff_v1_has_no_base(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "v5@corp.com", "Veco")
    pid = _protocol_with_steps(client, token, acc, ["A"])
    # v1 supersedes nothing → 400.
    assert client.get(f"/api/accounts/{acc}/protocols/{pid}/diff",
                      headers=auth(token)).status_code == 400


def test_restore_drafts_new_version_from_old_content(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "v6@corp.com", "Vfco")
    h = auth(token)
    pid = _protocol_with_steps(client, token, acc, ["Original A", "Original B"])
    v2 = client.post(f"/api/accounts/{acc}/protocols/{pid}/new-version", headers=h
                     ).get_json()["protocol"]
    # v2 diverges: drop a step.
    client.delete(f"/api/accounts/{acc}/protocols/{v2['id']}/steps/{v2['steps'][1]['id']}",
                  headers=h)

    res = client.post(f"/api/accounts/{acc}/protocols/{v2['id']}/restore",
                      json={"source_id": pid}, headers=h)
    assert res.status_code == 201
    body = res.get_json()
    restored = body["protocol"]
    assert body["restored_from"] == 1
    assert restored["status"] == "draft"
    assert restored["version"] == 3               # supersedes the head (v2)
    assert restored["supersedes_id"] == v2["id"]
    assert [s["title"] for s in restored["steps"]] == ["Original A", "Original B"]


def test_restore_rejects_foreign_source(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "v7@corp.com", "Vgco")
    h = auth(token)
    pid = _protocol_with_steps(client, token, acc, ["A"])
    other = _protocol_with_steps(client, token, acc, ["X"])   # unrelated lineage
    assert client.post(f"/api/accounts/{acc}/protocols/{pid}/restore",
                       json={"source_id": other}, headers=h).status_code == 400
    assert client.post(f"/api/accounts/{acc}/protocols/{pid}/restore",
                       json={"source_id": 99999}, headers=h).status_code == 404


def test_versions_cross_account_isolation(client):
    burn_superadmin(client)
    t1, a1, _ = make_owner(client, "v8@corp.com", "Vhco")
    t2, a2, _ = make_owner(client, "v9@corp.com", "Vico")
    pid = _protocol_with_steps(client, t1, a1, ["A"])
    assert client.get(f"/api/accounts/{a2}/protocols/{pid}/versions",
                      headers=auth(t2)).status_code == 404
    assert client.get(f"/api/accounts/{a1}/protocols/{pid}/versions",
                      headers=auth(t2)).status_code == 403
