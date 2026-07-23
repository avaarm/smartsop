"""Regulatory template packs: gallery listing and instantiation."""

from ml_model.gmp.templates import TEMPLATES
from util import burn_superadmin, make_owner, auth


def test_gallery_lists_templates(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "t1@corp.com", "Tco")
    body = client.get(f"/api/accounts/{acc}/protocols/templates",
                      headers=auth(token)).get_json()
    assert body["success"]
    assert len(body["templates"]) == len(TEMPLATES)

    keys = {t["key"] for t in body["templates"]}
    assert "loto_1910_147" in keys
    # Summaries carry the standard + a step count, but not the step bodies.
    first = body["templates"][0]
    assert first["standard"] and first["step_count"] > 0
    assert "steps" not in first


def test_create_from_template(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "t2@corp.com", "Uco")
    res = client.post(f"/api/accounts/{acc}/protocols/from-template",
                      json={"key": "loto_1910_147"}, headers=auth(token))
    assert res.status_code == 201
    body = res.get_json()
    p = body["protocol"]

    assert body["template"]["standard"] == "OSHA 1910.147"
    assert p["title"] == "Lockout/Tagout — Machine Isolation"
    assert p["protocol_type"] == "sop"
    assert p["status"] == "draft"          # must still go through approval
    assert len(p["steps"]) == 10
    assert p["created_by"]                  # author recorded


def test_template_steps_carry_typed_components(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "t3@corp.com", "Vco")
    p = client.post(f"/api/accounts/{acc}/protocols/from-template",
                    json={"key": "loto_1910_147"}, headers=auth(token)
                    ).get_json()["protocol"]

    types = {c["type"] for s in p["steps"] for c in s["components"]}
    assert {"ppe", "energy_source", "lockout_tag", "isolation_device"} <= types

    # Flag components round-trip as booleans, not strings.
    flags = [c for s in p["steps"] for c in s["components"]
             if c["type"] in ("verification_photo", "second_signature")]
    assert flags and all(c["value"] is True for c in flags)

    # The verification step keeps its timer and warning.
    verify = next(s for s in p["steps"] if s["title"].startswith("Verify isolation"))
    assert verify["duration_seconds"] == 300
    assert "zero-energy" in verify["warning"]


def test_haccp_template_has_working_branch(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "t4@corp.com", "Wco")
    p = client.post(f"/api/accounts/{acc}/protocols/from-template",
                    json={"key": "haccp_ccp_monitoring"}, headers=auth(token)
                    ).get_json()["protocol"]

    branching = [s for s in p["steps"] if s["branch"]]
    assert len(branching) == 1
    branch = branching[0]["branch"]
    assert "critical limit" in branch["question"]
    actions = {o["action"] for o in branch["options"]}
    assert "goto" in actions
    goto = next(o for o in branch["options"] if o["action"] == "goto")
    assert goto["target"] == 6


def test_custom_title_overrides_template_name(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "t5@corp.com", "Xco")
    p = client.post(f"/api/accounts/{acc}/protocols/from-template",
                    json={"key": "arc_flash_nfpa_70e", "title": "SOP-014 Arc Flash — West Plant"},
                    headers=auth(token)).get_json()["protocol"]
    assert p["title"] == "SOP-014 Arc Flash — West Plant"


def test_unknown_template_404(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "t6@corp.com", "Yco")
    assert client.post(f"/api/accounts/{acc}/protocols/from-template",
                       json={"key": "nope"}, headers=auth(token)).status_code == 404
    assert client.post(f"/api/accounts/{acc}/protocols/from-template",
                       json={}, headers=auth(token)).status_code == 404


def test_templates_require_account_membership(client):
    burn_superadmin(client)
    t1, a1, _ = make_owner(client, "t7@corp.com", "Zco")
    t2, _, _ = make_owner(client, "t8@corp.com", "Qco")
    assert client.get(f"/api/accounts/{a1}/protocols/templates",
                      headers=auth(t2)).status_code == 403
    assert client.post(f"/api/accounts/{a1}/protocols/from-template",
                       json={"key": "loto_1910_147"}, headers=auth(t2)).status_code == 403


def test_instantiated_template_is_runnable(client):
    """The whole point: a fresh workspace can run a real procedure immediately."""
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "t9@corp.com", "Rco")
    h = auth(token)
    p = client.post(f"/api/accounts/{acc}/protocols/from-template",
                    json={"key": "confined_space_1910_146"}, headers=h
                    ).get_json()["protocol"]

    run = client.post(f"/api/accounts/{acc}/protocols/{p['id']}/runs",
                      json={"experiment_id": "WO-1"}, headers=h)
    assert run.status_code == 201
    steps = run.get_json()["run"]["steps"]
    assert len(steps) == len(p["steps"])
    # Components survive the run snapshot.
    assert any(s["components"] for s in steps)


def test_every_template_instantiates(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "t10@corp.com", "Sco")
    for t in TEMPLATES:
        res = client.post(f"/api/accounts/{acc}/protocols/from-template",
                          json={"key": t["key"]}, headers=auth(token))
        assert res.status_code == 201, f"{t['key']} failed to instantiate"
        p = res.get_json()["protocol"]
        assert len(p["steps"]) == len(t["steps"])
        # Steps land in the template's authored order.
        assert [s["order_index"] for s in p["steps"]] == list(range(len(t["steps"])))
