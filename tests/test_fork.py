"""Fork / copy a protocol into a new independent draft."""

from util import burn_superadmin, make_owner, auth


def _protocol(client, token, account_id):
    h = auth(token)
    p = client.post(f"/api/accounts/{account_id}/protocols",
                    json={"title": "Original SOP", "description": "abc"}, headers=h).get_json()["protocol"]
    client.put(f"/api/accounts/{account_id}/protocols/{p['id']}",
               json={"protocol_type": "sop", "department": "QA"}, headers=h)
    for t in ("Step A", "Step B"):
        client.post(f"/api/accounts/{account_id}/protocols/{p['id']}/steps",
                    json={"title": t, "components": [{"type": "ppe", "value": "Gloves"}]}, headers=h)
    return p["id"]


def test_copy_creates_independent_draft(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "f1@corp.com", "Fco")
    pid = _protocol(client, token, acc)
    res = client.post(f"/api/accounts/{acc}/protocols/{pid}/copy", headers=auth(token))
    assert res.status_code == 201
    copy = res.get_json()["protocol"]

    assert copy["id"] != pid
    assert copy["title"] == "Original SOP (copy)"
    assert copy["status"] == "draft"
    assert copy["version"] == 1
    assert copy["supersedes_id"] is None          # independent lineage, not a version
    assert copy["protocol_type"] == "sop"
    assert copy["department"] == "QA"
    assert [s["title"] for s in copy["steps"]] == ["Step A", "Step B"]
    # Typed components are carried over.
    assert copy["steps"][0]["components"][0]["type"] == "ppe"


def test_copy_does_not_touch_original(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "f2@corp.com", "Gco")
    pid = _protocol(client, token, acc)
    client.post(f"/api/accounts/{acc}/protocols/{pid}/copy", headers=auth(token))

    # Editing the copy must not change the original — verify the original is intact.
    original = client.get(f"/api/accounts/{acc}/protocols/{pid}", headers=auth(token)).get_json()["protocol"]
    assert original["title"] == "Original SOP"
    assert original["version"] == 1


def test_copy_bad_protocol_404(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "f3@corp.com", "Hco")
    assert client.post(f"/api/accounts/{acc}/protocols/99999/copy",
                       headers=auth(token)).status_code == 404


def test_copy_cross_account_forbidden(client):
    burn_superadmin(client)
    t1, a1, _ = make_owner(client, "f4@corp.com", "Ico")
    t2, _, _ = make_owner(client, "f5@corp.com", "Jco")
    pid = _protocol(client, t1, a1)
    assert client.post(f"/api/accounts/{a1}/protocols/{pid}/copy",
                       headers=auth(t2)).status_code == 403
