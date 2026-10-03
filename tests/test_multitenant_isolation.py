"""Multi-tenant isolation for the newer document endpoints — a GMP app must never
leak one workspace's controlled documents to another."""

import io

from docx import Document

from util import burn_superadmin, make_owner, auth


def _make_doc(client, token, acc):
    d = Document(); d.add_heading("Confidential Batch Record", level=1)
    buf = io.BytesIO(); d.save(buf); buf.seek(0)
    data = {"file": (buf, "secret.docx"), "doc_category": "BR", "product_code": "B999"}
    return client.post(f"/api/accounts/{acc}/protocols/import", data=data,
                       content_type="multipart/form-data", headers=auth(token)).get_json()["protocol"]


def test_new_endpoints_reject_non_members(client):
    burn_superadmin(client)
    tok_a, acc_a, _ = make_owner(client, "mt-a@corp.com", "Alpha Labs")
    tok_b, acc_b, _ = make_owner(client, "mt-b@corp.com", "Beta Labs")
    doc = _make_doc(client, tok_a, acc_a)
    pid = doc["id"]

    # B is not a member of A's account → 403 on every document endpoint.
    hdr_b = auth(tok_b)
    assert client.get(f"/api/accounts/{acc_a}/protocols/{pid}/original", headers=hdr_b).status_code == 403
    assert client.post(f"/api/accounts/{acc_a}/protocols/{pid}/render.docx",
                       json={"variables": {}}, headers=hdr_b).status_code == 403
    assert client.get(f"/api/accounts/{acc_a}/protocols/{pid}/export.pdf", headers=hdr_b).status_code == 403
    assert client.get(f"/api/accounts/{acc_a}/protocols/doc-categories", headers=hdr_b).status_code == 403
    assert client.get(f"/api/accounts/{acc_a}/protocols/register", headers=hdr_b).status_code == 403
    assert client.put(f"/api/accounts/{acc_a}/protocols/{pid}",
                      json={"doc_category": "QA"}, headers=hdr_b).status_code == 403


def test_cross_account_protocol_id_is_not_found(client):
    burn_superadmin(client)
    tok_a, acc_a, _ = make_owner(client, "mt-c@corp.com", "Gamma Labs")
    tok_b, acc_b, _ = make_owner(client, "mt-d@corp.com", "Delta Labs")
    pid = _make_doc(client, tok_a, acc_a)["id"]

    # B references A's protocol id under B's own (accessible) account → 404.
    hdr_b = auth(tok_b)
    assert client.get(f"/api/accounts/{acc_b}/protocols/{pid}/original", headers=hdr_b).status_code == 404
    assert client.post(f"/api/accounts/{acc_b}/protocols/{pid}/render.docx",
                       json={"variables": {}}, headers=hdr_b).status_code == 404
    assert client.put(f"/api/accounts/{acc_b}/protocols/{pid}",
                      json={"title": "hijack"}, headers=hdr_b).status_code == 404


def test_register_only_shows_own_account(client):
    burn_superadmin(client)
    tok_a, acc_a, _ = make_owner(client, "mt-e@corp.com", "Epsilon Labs")
    tok_b, acc_b, _ = make_owner(client, "mt-f@corp.com", "Zeta Labs")
    _make_doc(client, tok_a, acc_a)   # A's batch record (product B999)

    # B's register (all statuses) must not contain A's protocol/product.
    reg_b = client.get(f"/api/accounts/{acc_b}/protocols/register?status=all", headers=auth(tok_b)).get_json()
    groups = reg_b["batch_records"] + reg_b["procedures"]
    assert all("B999" != g.get("group") for g in reg_b["batch_records"])
    assert all(not g["items"] for g in groups)   # B has no documents at all
