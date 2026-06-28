"""Document review/approval workflow, audit trail, and history pagination."""

import pytest

from util import login, auth, burn_superadmin, make_owner


def _make_doc(app, account_id, title="D", status="generated"):
    from ml_model.gmp.database import db, Document
    with app.app_context():
        doc = Document(account_id=account_id, doc_type="sop", title=title, status=status)
        db.session.add(doc)
        db.session.commit()
        return doc.id


@pytest.fixture()
def account_with_member(client):
    burn_superadmin(client)
    owner_tok, acc_id, _ = make_owner(client, "owner@x.com", "Acme")
    from util import register
    register(client, "marco@x.com", name="Marco Member")
    client.post(f"/api/accounts/{acc_id}/members", headers=auth(owner_tok),
                json={"email": "marco@x.com", "role": "member"})
    member_tok = login(client, "marco@x.com").get_json()["token"]
    return client, owner_tok, member_tok, acc_id


def _doc(client, acc_id, tok):
    return client.get(f"/api/accounts/{acc_id}/documents", headers=auth(tok)).get_json()["documents"][0]


def test_member_can_review_not_approve(account_with_member, app):
    client, owner_tok, member_tok, acc_id = account_with_member
    did = _make_doc(app, acc_id, title="SOP")

    r = client.patch(f"/api/accounts/{acc_id}/documents/{did}/status",
                     headers=auth(member_tok), json={"status": "reviewed"})
    assert r.status_code == 200 and r.get_json()["document"]["status"] == "reviewed"
    assert client.patch(f"/api/accounts/{acc_id}/documents/{did}/status",
                        headers=auth(member_tok), json={"status": "approved"}).status_code == 403


def test_audit_trail_stamped(account_with_member, app):
    client, owner_tok, member_tok, acc_id = account_with_member
    did = _make_doc(app, acc_id)

    client.patch(f"/api/accounts/{acc_id}/documents/{did}/status",
                 headers=auth(member_tok), json={"status": "reviewed"})
    doc = _doc(client, acc_id, owner_tok)
    assert doc["reviewed_by"] == "Marco Member" and doc["reviewed_at"]
    assert doc["approved_by"] is None

    client.patch(f"/api/accounts/{acc_id}/documents/{did}/status",
                 headers=auth(owner_tok), json={"status": "approved"})
    doc = _doc(client, acc_id, owner_tok)
    assert doc["approved_by"] and doc["approved_at"]
    assert doc["reviewed_by"] == "Marco Member"  # preserved


def test_reopen_clears_signoffs(account_with_member, app):
    client, owner_tok, member_tok, acc_id = account_with_member
    did = _make_doc(app, acc_id, status="approved")
    client.patch(f"/api/accounts/{acc_id}/documents/{did}/status",
                 headers=auth(owner_tok), json={"status": "approved"})
    client.patch(f"/api/accounts/{acc_id}/documents/{did}/status",
                 headers=auth(owner_tok), json={"status": "generated"})
    doc = _doc(client, acc_id, owner_tok)
    assert doc["reviewed_by"] is None and doc["approved_by"] is None


def test_approved_doc_locked_for_member(account_with_member, app):
    client, owner_tok, member_tok, acc_id = account_with_member
    did = _make_doc(app, acc_id)
    client.patch(f"/api/accounts/{acc_id}/documents/{did}/status",
                 headers=auth(owner_tok), json={"status": "approved"})
    assert client.patch(f"/api/accounts/{acc_id}/documents/{did}/status",
                        headers=auth(member_tok), json={"status": "reviewed"}).status_code == 403


def test_invalid_status_rejected(account_with_member, app):
    client, owner_tok, _, acc_id = account_with_member
    did = _make_doc(app, acc_id)
    assert client.patch(f"/api/accounts/{acc_id}/documents/{did}/status",
                        headers=auth(owner_tok), json={"status": "bogus"}).status_code == 400


def test_documents_pagination(account_with_member, app):
    client, owner_tok, _, acc_id = account_with_member
    for i in range(25):
        _make_doc(app, acc_id, title=f"Doc {i}")
    page1 = client.get(f"/api/accounts/{acc_id}/documents?per_page=20", headers=auth(owner_tok)).get_json()
    assert len(page1["documents"]) == 20
    assert page1["total"] == 25 and page1["pages"] == 2
    page2 = client.get(f"/api/accounts/{acc_id}/documents?per_page=20&page=2",
                       headers=auth(owner_tok)).get_json()
    assert len(page2["documents"]) == 5
