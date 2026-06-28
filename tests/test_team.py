"""Team membership management: add, role changes, removal, and guardrails."""

import pytest

from util import register, login, auth, burn_superadmin, make_owner


@pytest.fixture()
def team(client):
    """Owner with an account, plus two registered (not-yet-member) users."""
    burn_superadmin(client)
    owner_tok, acc_id, owner = make_owner(client, "owner@x.com", "Acme")
    register(client, "bob@x.com")
    register(client, "carol@x.com")
    return client, owner_tok, acc_id, owner


def test_initial_member_is_owner(team):
    client, owner_tok, acc_id, _ = team
    members = client.get(f"/api/accounts/{acc_id}/members", headers=auth(owner_tok)).get_json()["members"]
    assert len(members) == 1 and members[0]["role"] == "owner"


def test_add_member(team):
    client, owner_tok, acc_id, _ = team
    res = client.post(f"/api/accounts/{acc_id}/members", headers=auth(owner_tok),
                      json={"email": "bob@x.com", "role": "member"})
    assert res.status_code == 201
    assert res.get_json()["member"]["role"] == "member"


def test_add_unknown_email_404(team):
    client, owner_tok, acc_id, _ = team
    assert client.post(f"/api/accounts/{acc_id}/members", headers=auth(owner_tok),
                       json={"email": "ghost@nowhere.com"}).status_code == 404


def test_add_duplicate_member_409(team):
    client, owner_tok, acc_id, _ = team
    client.post(f"/api/accounts/{acc_id}/members", headers=auth(owner_tok), json={"email": "bob@x.com"})
    assert client.post(f"/api/accounts/{acc_id}/members", headers=auth(owner_tok),
                       json={"email": "bob@x.com"}).status_code == 409


def test_member_cannot_manage(team):
    client, owner_tok, acc_id, _ = team
    bob = client.post(f"/api/accounts/{acc_id}/members", headers=auth(owner_tok),
                      json={"email": "bob@x.com", "role": "member"}).get_json()["member"]
    bob_tok = login(client, "bob@x.com").get_json()["token"]
    assert client.post(f"/api/accounts/{acc_id}/members", headers=auth(bob_tok),
                       json={"email": "carol@x.com"}).status_code == 403


def test_admin_can_add_but_not_grant_owner(team):
    client, owner_tok, acc_id, _ = team
    bob = client.post(f"/api/accounts/{acc_id}/members", headers=auth(owner_tok),
                      json={"email": "bob@x.com", "role": "admin"}).get_json()["member"]
    bob_tok = login(client, "bob@x.com").get_json()["token"]
    assert client.post(f"/api/accounts/{acc_id}/members", headers=auth(bob_tok),
                       json={"email": "carol@x.com", "role": "member"}).status_code == 201
    assert client.post(f"/api/accounts/{acc_id}/members", headers=auth(bob_tok),
                       json={"email": "carol@x.com", "role": "owner"}).status_code in (403, 409)


def test_cannot_demote_or_remove_last_owner(team):
    client, owner_tok, acc_id, owner = team
    owner_id = owner["id"]
    assert client.patch(f"/api/accounts/{acc_id}/members/{owner_id}", headers=auth(owner_tok),
                        json={"role": "admin"}).status_code == 400
    assert client.delete(f"/api/accounts/{acc_id}/members/{owner_id}",
                         headers=auth(owner_tok)).status_code == 400


def test_remove_member_revokes_access(team):
    client, owner_tok, acc_id, _ = team
    bob = client.post(f"/api/accounts/{acc_id}/members", headers=auth(owner_tok),
                      json={"email": "bob@x.com", "role": "member"}).get_json()["member"]
    bob_tok = login(client, "bob@x.com").get_json()["token"]
    assert client.get(f"/api/accounts/{acc_id}/members", headers=auth(bob_tok)).status_code == 200
    assert client.delete(f"/api/accounts/{acc_id}/members/{bob['user_id']}",
                         headers=auth(owner_tok)).status_code == 200
    assert client.get(f"/api/accounts/{acc_id}/members", headers=auth(bob_tok)).status_code == 403
