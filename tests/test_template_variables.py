"""Template fill-in variables — {{placeholders}} substituted when starting a project."""

from util import burn_superadmin, make_owner, auth


def _template_with_vars(client, token, acc):
    h = auth(token)
    p = client.post(f"/api/accounts/{acc}/protocols",
                    json={"title": "{{product}} Batch Record",
                          "description": "Batch record for {{product}}, lot {{lot_number}}."},
                    headers=h).get_json()["protocol"]
    client.post(f"/api/accounts/{acc}/protocols/{p['id']}/steps",
                json={"section": "{{product}} — Manufacturing",
                      "title": "Charge reactor",
                      "description": "Charge {{batch_size}} of {{product}} to reactor R-{{reactor_no}}."},
                headers=h)
    return p["id"]


def test_detect_variables(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "v1@corp.com", "Vco")
    pid = _template_with_vars(client, token, acc)
    res = client.get(f"/api/accounts/{acc}/protocols/{pid}/template-variables", headers=auth(token))
    assert res.status_code == 200
    vars_ = res.get_json()["variables"]
    # Unique, in first-seen order across title, description, then steps.
    assert vars_ == ["product", "lot_number", "batch_size", "reactor_no"]


def test_use_with_variables_substitutes_everywhere(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "v2@corp.com", "Wco")
    h = auth(token)
    pid = _template_with_vars(client, token, acc)
    res = client.post(f"/api/accounts/{acc}/protocols/{pid}/copy", json={
        "title": "{{product}} Batch Record — Lot {{lot_number}}",
        "variables": {"product": "Acetaminophen", "lot_number": "L-2409",
                      "batch_size": "200 kg", "reactor_no": "3"},
    }, headers=h)
    assert res.status_code == 201
    doc = res.get_json()["protocol"]
    assert doc["title"] == "Acetaminophen Batch Record — Lot L-2409"
    assert doc["description"] == "Batch record for Acetaminophen, lot L-2409."
    step = doc["steps"][0]
    assert step["section"] == "Acetaminophen — Manufacturing"
    assert step["description"] == "Charge 200 kg of Acetaminophen to reactor R-3."
    assert doc["is_template"] is False   # the started project is working, not a template


def test_unknown_placeholder_left_intact(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "v3@corp.com", "Xco")
    h = auth(token)
    pid = _template_with_vars(client, token, acc)
    doc = client.post(f"/api/accounts/{acc}/protocols/{pid}/copy",
                      json={"variables": {"product": "Ibuprofen"}}, headers=h).get_json()["protocol"]
    # Provided one is filled; the rest remain as placeholders to complete later.
    assert "Ibuprofen" in doc["description"]
    assert "{{lot_number}}" in doc["description"]


def test_copy_without_variables_is_unchanged(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "v4@corp.com", "Yco")
    h = auth(token)
    pid = _template_with_vars(client, token, acc)
    doc = client.post(f"/api/accounts/{acc}/protocols/{pid}/copy", json={}, headers=h).get_json()["protocol"]
    # No variables supplied → placeholders preserved verbatim (nothing lost).
    assert "{{product}}" in doc["steps"][0]["description"]


def test_no_variables_returns_empty(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "v5@corp.com", "Zco")
    h = auth(token)
    p = client.post(f"/api/accounts/{acc}/protocols", json={"title": "Plain SOP"}, headers=h).get_json()["protocol"]
    res = client.get(f"/api/accounts/{acc}/protocols/{p['id']}/template-variables", headers=h)
    assert res.get_json()["variables"] == []
