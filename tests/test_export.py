"""Export a protocol as JSON and PDF."""

import json

from util import burn_superadmin, make_owner, auth


def _protocol(client, token, account_id):
    h = auth(token)
    p = client.post(f"/api/accounts/{account_id}/protocols",
                    json={"title": "Export Me", "description": "For the auditor."},
                    headers=h).get_json()["protocol"]
    client.post(f"/api/accounts/{account_id}/protocols/{p['id']}/steps",
                json={"title": "Isolate", "description": "Open the breaker.",
                      "duration_seconds": 120, "warning": "Arc flash risk.",
                      "components": [{"type": "ppe", "value": "Arc suit"},
                                     {"type": "verification_photo", "value": True}]},
                headers=h)
    return p["id"]


def test_export_json(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "e1@corp.com", "Eco")
    pid = _protocol(client, token, acc)
    res = client.get(f"/api/accounts/{acc}/protocols/{pid}/export.json", headers=auth(token))
    assert res.status_code == 200
    assert res.headers["Content-Type"].startswith("application/json")
    assert "attachment" in res.headers["Content-Disposition"]
    assert res.headers["Content-Disposition"].endswith('.json"')

    data = json.loads(res.data)
    assert data["title"] == "Export Me"
    assert data["steps"][0]["title"] == "Isolate"
    assert data["steps"][0]["components"][0]["type"] == "ppe"


def test_export_pdf(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "e2@corp.com", "Fco")
    pid = _protocol(client, token, acc)
    res = client.get(f"/api/accounts/{acc}/protocols/{pid}/export.pdf", headers=auth(token))
    assert res.status_code == 200
    assert res.headers["Content-Type"] == "application/pdf"
    assert "attachment" in res.headers["Content-Disposition"]
    # A real PDF starts with the %PDF magic bytes.
    assert res.data[:5] == b"%PDF-"
    assert len(res.data) > 500


def test_export_filename_uses_title_and_version(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "e3@corp.com", "Gco")
    pid = _protocol(client, token, acc)
    res = client.get(f"/api/accounts/{acc}/protocols/{pid}/export.json", headers=auth(token))
    assert 'filename="export-me-v1.json"' in res.headers["Content-Disposition"]


def test_export_bad_protocol_404(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "e4@corp.com", "Hco")
    assert client.get(f"/api/accounts/{acc}/protocols/99999/export.json",
                      headers=auth(token)).status_code == 404
    assert client.get(f"/api/accounts/{acc}/protocols/99999/export.pdf",
                      headers=auth(token)).status_code == 404


def test_export_cross_account_forbidden(client):
    burn_superadmin(client)
    t1, a1, _ = make_owner(client, "e5@corp.com", "Ico")
    t2, _, _ = make_owner(client, "e6@corp.com", "Jco")
    pid = _protocol(client, t1, a1)
    assert client.get(f"/api/accounts/{a1}/protocols/{pid}/export.pdf",
                      headers=auth(t2)).status_code == 403
