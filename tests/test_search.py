"""SOP Finder — keyword search across protocol fields and step content."""

from util import burn_superadmin, make_owner, auth


def _mk(client, token, acc, title, *, description="", sop_number="", department="", steps=()):
    h = auth(token)
    p = client.post(f"/api/accounts/{acc}/protocols",
                    json={"title": title, "description": description}, headers=h).get_json()["protocol"]
    if sop_number or department:
        client.put(f"/api/accounts/{acc}/protocols/{p['id']}",
                   json={"sop_number": sop_number, "department": department}, headers=h)
    for s in steps:
        client.post(f"/api/accounts/{acc}/protocols/{p['id']}/steps", json=s, headers=h)
    return p["id"]


def _search(client, token, acc, q):
    return client.get(f"/api/accounts/{acc}/protocols?q={q}", headers=auth(token)).get_json()


def test_search_by_title(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "s1@corp.com", "Sco")
    _mk(client, token, acc, "LOTO — West Plant Compressor")
    _mk(client, token, acc, "Gowning procedure")
    res = _search(client, token, acc, "compressor")
    assert res["total"] == 1
    assert res["protocols"][0]["title"] == "LOTO — West Plant Compressor"


def test_search_is_case_insensitive(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "s2@corp.com", "Tco")
    _mk(client, token, acc, "Arc Flash Work Permit")
    assert _search(client, token, acc, "ARC")["total"] == 1
    assert _search(client, token, acc, "flash")["total"] == 1


def test_search_matches_step_content(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "s3@corp.com", "Uco")
    # The word "reciprocating" appears only inside a step, not the title.
    _mk(client, token, acc, "Air Unit Lockout",
        steps=[{"title": "Isolate", "description": "Shut down the reciprocating air unit."}])
    _mk(client, token, acc, "Unrelated SOP")
    res = _search(client, token, acc, "reciprocating")
    assert res["total"] == 1 and res["protocols"][0]["title"] == "Air Unit Lockout"


def test_search_matches_sop_number_and_department(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "s4@corp.com", "Vco")
    _mk(client, token, acc, "Cleaning SOP", sop_number="SOP-4471", department="Electrical")
    assert _search(client, token, acc, "4471")["total"] == 1
    assert _search(client, token, acc, "electrical")["total"] == 1


def test_search_no_match_is_empty(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "s5@corp.com", "Wco")
    _mk(client, token, acc, "Gowning")
    assert _search(client, token, acc, "zzzznope")["total"] == 0


def test_empty_query_returns_all(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "s6@corp.com", "Xco")
    _mk(client, token, acc, "One")
    _mk(client, token, acc, "Two")
    assert client.get(f"/api/accounts/{acc}/protocols", headers=auth(token)).get_json()["total"] == 2


def test_search_is_account_scoped(client):
    burn_superadmin(client)
    t1, a1, _ = make_owner(client, "s7@corp.com", "Yco")
    t2, a2, _ = make_owner(client, "s8@corp.com", "Zco")
    _mk(client, t1, a1, "Compressor lockout")   # account 1 only
    assert _search(client, t2, a2, "compressor")["total"] == 0
