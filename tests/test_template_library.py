"""Org template library — save your own docs as reusable, categorized templates."""

import io

from util import burn_superadmin, make_owner, auth


def _protocol(client, token, acc, title="Batch Record BR-100"):
    h = auth(token)
    p = client.post(f"/api/accounts/{acc}/protocols",
                    json={"title": title, "description": "For product X."}, headers=h).get_json()["protocol"]
    client.post(f"/api/accounts/{acc}/protocols/{p['id']}/steps",
                json={"title": "Charge reactor", "description": "Add 200 L WFI."}, headers=h)
    return p["id"]


def test_save_as_template_keeps_original_working(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "tl1@corp.com", "Tco")
    pid = _protocol(client, token, acc)
    res = client.post(f"/api/accounts/{acc}/protocols/{pid}/save-as-template",
                      json={"category": "Batch Record"}, headers=auth(token))
    assert res.status_code == 201
    tpl = res.get_json()["template"]
    assert tpl["is_template"] is True
    assert tpl["template_category"] == "Batch Record"
    assert tpl["id"] != pid
    assert [s["title"] for s in tpl["steps"]] == ["Charge reactor"]  # structure carried over

    # The original is untouched and still a working document.
    original = client.get(f"/api/accounts/{acc}/protocols/{pid}", headers=auth(token)).get_json()["protocol"]
    assert original["is_template"] is False


def test_working_list_excludes_templates(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "tl2@corp.com", "Uco")
    h = auth(token)
    pid = _protocol(client, token, acc)                 # 1 working doc
    client.post(f"/api/accounts/{acc}/protocols/{pid}/save-as-template",
                json={"category": "Batch Record"}, headers=h)

    working = client.get(f"/api/accounts/{acc}/protocols", headers=h).get_json()
    assert working["total"] == 1 and all(not p["is_template"] for p in working["protocols"])

    templates = client.get(f"/api/accounts/{acc}/protocols?templates=true", headers=h).get_json()
    assert templates["total"] == 1 and all(p["is_template"] for p in templates["protocols"])
    assert templates["protocols"][0]["template_category"] == "Batch Record"


def test_new_project_from_template_is_a_working_doc(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "tl3@corp.com", "Vco")
    h = auth(token)
    pid = _protocol(client, token, acc)
    tpl = client.post(f"/api/accounts/{acc}/protocols/{pid}/save-as-template",
                      json={"category": "Batch Record"}, headers=h).get_json()["template"]

    # "New from template" = fork the template; the result is editable working work.
    started = client.post(f"/api/accounts/{acc}/protocols/{tpl['id']}/copy",
                          json={"title": "Batch Record BR-205 (Product Y)"}, headers=h)
    assert started.status_code == 201
    newdoc = started.get_json()["protocol"]
    assert newdoc["is_template"] is False
    assert newdoc["title"] == "Batch Record BR-205 (Product Y)"
    assert [s["title"] for s in newdoc["steps"]] == ["Charge reactor"]   # wording carried over
    # It shows in the working list, not the template library.
    working = client.get(f"/api/accounts/{acc}/protocols", headers=h).get_json()
    assert any(p["id"] == newdoc["id"] for p in working["protocols"])


def test_import_as_template(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "tl4@corp.com", "Wco")
    body = {
        "title": "CMC Module 3.2.S Drug Substance",
        "text": "1. Nomenclature\n2. Structure\n3. General properties",
        "mode": "numbered",
        "as_template": True,
        "category": "CMC",
    }
    res = client.post(f"/api/accounts/{acc}/protocols/import", json=body, headers=auth(token))
    assert res.status_code == 201
    p = res.get_json()["protocol"]
    assert p["is_template"] is True and p["template_category"] == "CMC"
    # It lands in the template library, not the working list.
    templates = client.get(f"/api/accounts/{acc}/protocols?templates=true", headers=auth(token)).get_json()
    assert any(t["title"].startswith("CMC Module 3") for t in templates["protocols"])


def test_import_file_as_template(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "tl5@corp.com", "Xco")
    data = {
        "file": (io.BytesIO(b"1. Purpose\n2. Scope\n3. Procedure"), "stability_protocol.txt"),
        "mode": "numbered",
        "as_template": "true",
        "category": "Stability Protocol",
    }
    res = client.post(f"/api/accounts/{acc}/protocols/import", data=data,
                      content_type="multipart/form-data", headers=auth(token))
    assert res.status_code == 201
    p = res.get_json()["protocol"]
    assert p["is_template"] is True and p["template_category"] == "Stability Protocol"


def test_default_category_when_omitted(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "tl6@corp.com", "Yco")
    pid = _protocol(client, token, acc)
    tpl = client.post(f"/api/accounts/{acc}/protocols/{pid}/save-as-template",
                      json={}, headers=auth(token)).get_json()["template"]
    assert tpl["template_category"] == "General"


def test_template_cross_account_isolation(client):
    burn_superadmin(client)
    t1, a1, _ = make_owner(client, "tl7@corp.com", "Zco")
    t2, a2, _ = make_owner(client, "tl8@corp.com", "Qco")
    pid = _protocol(client, t1, a1)
    client.post(f"/api/accounts/{a1}/protocols/{pid}/save-as-template",
                json={"category": "Batch Record"}, headers=auth(t1))
    # Account 2 sees none of account 1's templates.
    assert client.get(f"/api/accounts/{a2}/protocols?templates=true",
                      headers=auth(t2)).get_json()["total"] == 0
