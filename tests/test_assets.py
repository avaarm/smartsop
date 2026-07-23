"""Asset / equipment library: CRUD, protocol linking, QR generation and scanning."""

from util import burn_superadmin, make_owner, auth


def _make_protocol(client, token, account_id, title="LOTO"):
    return client.post(f"/api/accounts/{account_id}/protocols",
                       json={"title": title}, headers=auth(token)).get_json()["protocol"]


def test_create_asset_gets_qr_slug(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "a1@corp.com", "Aco")
    res = client.post(f"/api/accounts/{acc}/assets", json={
        "name": "West Plant Switchgear",
        "asset_tag": "SWG-4471",
        "location": "Bldg 2 / Electrical Room",
        "hazard_class": "Arc flash Cat 4",
        "energy_sources": ["480V AC", "Control 120V"],
    }, headers=auth(token))
    assert res.status_code == 201
    asset = res.get_json()["asset"]
    assert asset["qr_slug"]                       # opaque slug allocated
    assert asset["qr_slug"] != str(asset["id"])   # not the sequential id
    assert asset["energy_sources"] == ["480V AC", "Control 120V"]


def test_name_required(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "a2@corp.com", "Bco")
    assert client.post(f"/api/accounts/{acc}/assets", json={"location": "x"},
                       headers=auth(token)).status_code == 400


def test_qr_slugs_are_unique(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "a3@corp.com", "Cco")
    slugs = set()
    for i in range(5):
        a = client.post(f"/api/accounts/{acc}/assets", json={"name": f"Pump {i}"},
                        headers=auth(token)).get_json()["asset"]
        slugs.add(a["qr_slug"])
    assert len(slugs) == 5


def test_link_protocols_and_resolve(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "a4@corp.com", "Dco")
    p1 = _make_protocol(client, token, acc, "LOTO — Switchgear")
    p2 = _make_protocol(client, token, acc, "Return to service")

    asset = client.post(f"/api/accounts/{acc}/assets", json={
        "name": "Switchgear", "protocol_ids": [p1["id"], p2["id"]],
    }, headers=auth(token)).get_json()["asset"]
    assert asset["protocol_ids"] == [p1["id"], p2["id"]]

    full = client.get(f"/api/accounts/{acc}/assets/{asset['id']}",
                      headers=auth(token)).get_json()["asset"]
    assert [p["title"] for p in full["protocols"]] == ["LOTO — Switchgear", "Return to service"]


def test_foreign_protocol_ids_are_dropped(client):
    burn_superadmin(client)
    t1, a1, _ = make_owner(client, "a5@corp.com", "Eco")
    t2, a2, _ = make_owner(client, "a6@corp.com", "Fco")
    foreign = _make_protocol(client, t2, a2, "Someone else's SOP")
    mine = _make_protocol(client, t1, a1, "My SOP")

    asset = client.post(f"/api/accounts/{a1}/assets", json={
        "name": "Compressor", "protocol_ids": [mine["id"], foreign["id"], 99999],
    }, headers=auth(t1)).get_json()["asset"]
    assert asset["protocol_ids"] == [mine["id"]]   # foreign + unknown ids stripped


def test_update_and_delete(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "a7@corp.com", "Gco")
    asset = client.post(f"/api/accounts/{acc}/assets", json={"name": "Pump A"},
                        headers=auth(token)).get_json()["asset"]

    updated = client.put(f"/api/accounts/{acc}/assets/{asset['id']}",
                         json={"name": "Pump A-1", "location": "Yard"},
                         headers=auth(token)).get_json()["asset"]
    assert updated["name"] == "Pump A-1" and updated["location"] == "Yard"
    # The QR slug is stable across edits — printed tags stay valid.
    assert updated["qr_slug"] == asset["qr_slug"]

    assert client.delete(f"/api/accounts/{acc}/assets/{asset['id']}",
                         headers=auth(token)).status_code == 200
    assert client.get(f"/api/accounts/{acc}/assets/{asset['id']}",
                      headers=auth(token)).status_code == 404


def test_search_assets(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "a8@corp.com", "Hco")
    h = auth(token)
    client.post(f"/api/accounts/{acc}/assets", json={"name": "West Switchgear"}, headers=h)
    client.post(f"/api/accounts/{acc}/assets", json={"name": "East Pump", "asset_tag": "PMP-9"}, headers=h)

    hits = client.get(f"/api/accounts/{acc}/assets?q=switch", headers=h).get_json()
    assert hits["total"] == 1 and hits["assets"][0]["name"] == "West Switchgear"
    by_tag = client.get(f"/api/accounts/{acc}/assets?q=PMP", headers=h).get_json()
    assert by_tag["total"] == 1


def test_qr_svg_endpoint(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "a9@corp.com", "Ico")
    asset = client.post(f"/api/accounts/{acc}/assets", json={"name": "Switchgear"},
                        headers=auth(token)).get_json()["asset"]

    res = client.get(f"/api/accounts/{acc}/assets/{asset['id']}/qr.svg?base=https://app.test",
                     headers=auth(token))
    assert res.status_code == 200
    assert res.headers["Content-Type"].startswith("image/svg+xml")
    assert b"<svg" in res.data


def test_scan_resolves_asset_with_protocols(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "a10@corp.com", "Jco")
    p = _make_protocol(client, token, acc, "LOTO — Switchgear")
    asset = client.post(f"/api/accounts/{acc}/assets", json={
        "name": "Switchgear", "hazard_class": "Arc flash Cat 4",
        "energy_sources": ["480V AC"], "protocol_ids": [p["id"]],
    }, headers=auth(token)).get_json()["asset"]

    scanned = client.get(f"/api/assets/scan/{asset['qr_slug']}", headers=auth(token))
    assert scanned.status_code == 200
    body = scanned.get_json()["asset"]
    assert body["name"] == "Switchgear"
    assert body["energy_sources"] == ["480V AC"]
    assert body["protocols"][0]["title"] == "LOTO — Switchgear"


def test_scan_unknown_slug_404(client):
    burn_superadmin(client)
    token, _, _ = make_owner(client, "a11@corp.com", "Kco")
    assert client.get("/api/assets/scan/not-a-real-slug",
                      headers=auth(token)).status_code == 404


def test_scan_requires_membership(client):
    burn_superadmin(client)
    t1, a1, _ = make_owner(client, "a12@corp.com", "Lco")
    t2, _, _ = make_owner(client, "a13@corp.com", "Mco")
    asset = client.post(f"/api/accounts/{a1}/assets", json={"name": "Private rig"},
                        headers=auth(t1)).get_json()["asset"]

    # A valid slug is not enough — the scanner must belong to the owning account.
    assert client.get(f"/api/assets/scan/{asset['qr_slug']}",
                      headers=auth(t2)).status_code == 403
    assert client.get(f"/api/assets/scan/{asset['qr_slug']}").status_code == 401


def test_cross_account_asset_isolation(client):
    burn_superadmin(client)
    t1, a1, _ = make_owner(client, "a14@corp.com", "Nco")
    t2, a2, _ = make_owner(client, "a15@corp.com", "Oco")
    asset = client.post(f"/api/accounts/{a1}/assets", json={"name": "Rig"},
                        headers=auth(t1)).get_json()["asset"]

    assert client.get(f"/api/accounts/{a2}/assets/{asset['id']}",
                      headers=auth(t2)).status_code == 404
    assert client.get(f"/api/accounts/{a1}/assets/{asset['id']}",
                      headers=auth(t2)).status_code == 403
