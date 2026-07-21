"""SOP controlled-document lifecycle: metadata, e-signatures, versioning."""

import pytest

from util import register, login, auth, burn_superadmin, make_owner

PW = "password123"


@pytest.fixture()
def sop(client):
    """Owner + a member, and a protocol with one step ready to submit."""
    burn_superadmin(client)
    owner_tok, acc_id, _ = make_owner(client, "owner@x.com", "Acme")
    register(client, "marco@x.com", name="Marco Member")
    client.post(f"/api/accounts/{acc_id}/members", headers=auth(owner_tok),
                json={"email": "marco@x.com", "role": "member"})
    member_tok = login(client, "marco@x.com").get_json()["token"]
    pid = client.post(f"/api/accounts/{acc_id}/protocols", headers=auth(owner_tok),
                      json={"title": "Gowning SOP"}).get_json()["protocol"]["id"]
    client.post(f"/api/accounts/{acc_id}/protocols/{pid}/steps", headers=auth(owner_tok),
                json={"title": "Don gown"})
    return client, owner_tok, member_tok, acc_id, pid


def _get(client, tok, acc_id, pid):
    return client.get(f"/api/accounts/{acc_id}/protocols/{pid}", headers=auth(tok)).get_json()["protocol"]


def test_set_sop_metadata(sop):
    client, owner_tok, _, acc_id, pid = sop
    res = client.put(f"/api/accounts/{acc_id}/protocols/{pid}", headers=auth(owner_tok),
                     json={"protocol_type": "gmp_sop", "sop_number": "SOP-001", "department": "QA",
                           "review_date": "2027-01-01"})
    p = res.get_json()["protocol"]
    assert p["protocol_type"] == "gmp_sop" and p["sop_number"] == "SOP-001"
    assert p["department"] == "QA" and p["review_date"] == "2027-01-01"


def test_invalid_type_rejected(sop):
    client, owner_tok, _, acc_id, pid = sop
    assert client.put(f"/api/accounts/{acc_id}/protocols/{pid}", headers=auth(owner_tok),
                      json={"protocol_type": "nope"}).status_code == 400


def test_submit_requires_steps(client):
    burn_superadmin(client)
    tok, acc_id, _ = make_owner(client, "o@x.com", "Acme")
    pid = client.post(f"/api/accounts/{acc_id}/protocols", headers=auth(tok),
                      json={"title": "Empty"}).get_json()["protocol"]["id"]
    assert client.post(f"/api/accounts/{acc_id}/protocols/{pid}/submit", headers=auth(tok)).status_code == 400


def test_full_approval_flow(sop):
    client, owner_tok, member_tok, acc_id, pid = sop

    # draft -> in_review
    assert client.post(f"/api/accounts/{acc_id}/protocols/{pid}/submit",
                       headers=auth(owner_tok)).status_code == 200
    assert _get(client, owner_tok, acc_id, pid)["status"] == "in_review"

    # member reviews (e-signature with password)
    r = client.post(f"/api/accounts/{acc_id}/protocols/{pid}/sign", headers=auth(member_tok),
                    json={"role": "reviewer", "decision": "approved", "password": PW})
    assert r.status_code == 200

    # owner approves -> approved
    r = client.post(f"/api/accounts/{acc_id}/protocols/{pid}/sign", headers=auth(owner_tok),
                    json={"role": "approver", "decision": "approved", "password": PW,
                          "meaning": "Approved for GMP use"})
    p = r.get_json()["protocol"]
    assert p["status"] == "approved"
    assert len(p["signoffs"]) == 2
    roles = {s["role"]: s for s in p["signoffs"]}
    assert roles["reviewer"]["signed_by"] == "Marco Member"
    assert roles["approver"]["meaning"] == "Approved for GMP use" and roles["approver"]["signed_at"]

    # make effective
    r = client.post(f"/api/accounts/{acc_id}/protocols/{pid}/make-effective", headers=auth(owner_tok),
                    json={"review_date": "2027-06-01"})
    p = r.get_json()["protocol"]
    assert p["status"] == "effective" and p["effective_date"]


def test_signature_requires_correct_password(sop):
    client, owner_tok, _, acc_id, pid = sop
    client.post(f"/api/accounts/{acc_id}/protocols/{pid}/submit", headers=auth(owner_tok))
    r = client.post(f"/api/accounts/{acc_id}/protocols/{pid}/sign", headers=auth(owner_tok),
                    json={"role": "approver", "decision": "approved", "password": "WRONG"})
    assert r.status_code == 401
    assert _get(client, owner_tok, acc_id, pid)["status"] == "in_review"  # unchanged


def test_member_cannot_approve(sop):
    client, owner_tok, member_tok, acc_id, pid = sop
    client.post(f"/api/accounts/{acc_id}/protocols/{pid}/submit", headers=auth(owner_tok))
    r = client.post(f"/api/accounts/{acc_id}/protocols/{pid}/sign", headers=auth(member_tok),
                    json={"role": "approver", "decision": "approved", "password": PW})
    assert r.status_code == 403


def test_rejection_sets_rejected(sop):
    client, owner_tok, _, acc_id, pid = sop
    client.post(f"/api/accounts/{acc_id}/protocols/{pid}/submit", headers=auth(owner_tok))
    r = client.post(f"/api/accounts/{acc_id}/protocols/{pid}/sign", headers=auth(owner_tok),
                    json={"role": "approver", "decision": "rejected", "password": PW,
                          "comment": "Missing PPE step"})
    assert r.get_json()["protocol"]["status"] == "rejected"


def test_make_effective_requires_manager_and_approved(sop):
    client, owner_tok, member_tok, acc_id, pid = sop
    # not approved yet
    assert client.post(f"/api/accounts/{acc_id}/protocols/{pid}/make-effective",
                       headers=auth(owner_tok)).status_code == 400


def test_new_version_clones_and_supersedes(sop):
    client, owner_tok, member_tok, acc_id, pid = sop
    # take v1 all the way to effective
    client.post(f"/api/accounts/{acc_id}/protocols/{pid}/submit", headers=auth(owner_tok))
    client.post(f"/api/accounts/{acc_id}/protocols/{pid}/sign", headers=auth(owner_tok),
                json={"role": "approver", "decision": "approved", "password": PW})
    client.post(f"/api/accounts/{acc_id}/protocols/{pid}/make-effective", headers=auth(owner_tok))

    # new version clones steps, bumps version, supersedes v1
    r = client.post(f"/api/accounts/{acc_id}/protocols/{pid}/new-version", headers=auth(owner_tok))
    assert r.status_code == 201
    v2 = r.get_json()["protocol"]
    assert v2["version"] == 2 and v2["status"] == "draft" and v2["supersedes_id"] == pid
    assert v2["step_count"] == 1

    # releasing v2 retires v1
    client.post(f"/api/accounts/{acc_id}/protocols/{v2['id']}/submit", headers=auth(owner_tok))
    client.post(f"/api/accounts/{acc_id}/protocols/{v2['id']}/sign", headers=auth(owner_tok),
                json={"role": "approver", "decision": "approved", "password": PW})
    client.post(f"/api/accounts/{acc_id}/protocols/{v2['id']}/make-effective", headers=auth(owner_tok))
    assert _get(client, owner_tok, acc_id, pid)["status"] == "retired"
    assert _get(client, owner_tok, acc_id, v2["id"])["status"] == "effective"


def test_lifecycle_is_account_scoped(sop):
    client, owner_tok, _, acc_id, pid = sop
    b_tok, b_id, _ = make_owner(client, "b@x.com", "Beta")
    assert client.post(f"/api/accounts/{acc_id}/protocols/{pid}/submit", headers=auth(b_tok)).status_code == 403
