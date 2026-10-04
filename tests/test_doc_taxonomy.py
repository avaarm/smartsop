"""Facility document taxonomy + built-in 'what do you want to write?' templates."""

import io

from docx import Document

from util import burn_superadmin, make_owner, auth


def test_doc_categories_listed_with_counts(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "tx1@corp.com", "Tco")
    res = client.get(f"/api/accounts/{acc}/protocols/doc-categories", headers=auth(token))
    assert res.status_code == 200
    cats = res.get_json()["categories"]
    codes = {c["code"] for c in cats}
    # The facility's standard categories are present.
    for code in ("BR", "EQ", "QA", "QC", "TM", "VP"):
        assert code in codes
    br = next(c for c in cats if c["code"] == "BR")
    assert br["kind"] == "record"
    assert br["template_count"] == 0 and br["effective_count"] == 0
    assert br["examples"]                       # tasks drive the picker


def test_doc_template_gallery_and_category_filter(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "tx2@corp.com", "Tco")
    res = client.get(f"/api/accounts/{acc}/protocols/doc-templates", headers=auth(token))
    keys = {t["key"] for t in res.get_json()["templates"]}
    assert {"br_production", "br_formulation", "mps", "tm_test_method"} <= keys

    res = client.get(f"/api/accounts/{acc}/protocols/doc-templates?category=BR", headers=auth(token))
    cats = {t["doc_category"] for t in res.get_json()["templates"]}
    assert cats == {"BR"}


def test_create_from_doc_template_builds_structured_document(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "tx3@corp.com", "Tco")
    res = client.post(f"/api/accounts/{acc}/protocols/from-doc-template",
                      json={"key": "br_production",
                            "variables": {"product": "CAR-T", "lot_number": "L-42"}},
                      headers=auth(token))
    assert res.status_code == 201
    p = res.get_json()["protocol"]
    assert p["doc_format"] == "document"
    assert p["doc_category"] == "BR"
    assert p["title"] == "CAR-T Production Batch Record"      # variable filled into title

    headings = [b["text"] for b in p["body"] if b["type"] == "heading"]
    # DC-004 mandated sections are present.
    assert "1. REFERENCES" in headings
    assert "2. ATTACHMENTS" in headings
    assert "4. PROCESS FLOW" in headings
    assert "5. EQUIPMENT / MATERIALS LIST" in headings

    cells = [c for b in p["body"] if b["type"] == "table" for row in b["rows"] for c in row]
    assert "L-42" in cells                                    # variable filled into a cell
    assert not any("{{lot_number}}" in c for c in cells)


def test_import_accepts_doc_category_and_product_code(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "tx4@corp.com", "Tco")
    d = Document(); d.add_heading("Batch Record", level=1)
    buf = io.BytesIO(); d.save(buf); buf.seek(0)
    data = {"file": (buf, "BR-B090.docx"), "doc_category": "BR", "product_code": "B090"}
    res = client.post(f"/api/accounts/{acc}/protocols/import", data=data,
                      content_type="multipart/form-data", headers=auth(token))
    assert res.status_code == 201
    p = res.get_json()["protocol"]
    assert p["doc_category"] == "BR"
    assert p["product_code"] == "B090"

    # Counts reflect it once it's effective — but at least it groups by category.
    res = client.get(f"/api/accounts/{acc}/protocols/doc-categories", headers=auth(token))
    # (imported doc is a draft, not effective, so effective_count stays 0)
    br = next(c for c in res.get_json()["categories"] if c["code"] == "BR")
    assert br["effective_count"] == 0


def test_invalid_doc_category_is_ignored(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "tx5@corp.com", "Tco")
    res = client.post(f"/api/accounts/{acc}/protocols/import",
                      json={"title": "X", "text": "1. a\n2. b", "mode": "numbered",
                            "doc_category": "ZZ"}, headers=auth(token))
    assert res.status_code == 201
    assert res.get_json()["protocol"]["doc_category"] == ""


# ── Auto document numbering (DC-002 style) ──────────────────────────────────

def test_document_number_auto_increments_per_category(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "num1@corp.com", "Nco")

    def create(key):
        return client.post(f"/api/accounts/{acc}/protocols/from-doc-template",
                           json={"key": key}, headers=auth(token)).get_json()["protocol"]

    a = create("eq_operation")   # EQ
    b = create("eq_operation")   # EQ
    t = create("tm_test_method")  # TM
    assert a["document_number"] == "EQ-001"
    assert b["document_number"] == "EQ-002"      # increments within the category
    assert t["document_number"] == "TM-001"      # separate sequence per category


def test_setting_category_assigns_number(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "num2@corp.com", "Nco")
    p = client.post(f"/api/accounts/{acc}/protocols",
                    json={"title": "Blank"}, headers=auth(token)).get_json()["protocol"]
    assert p["document_number"] == ""
    res = client.put(f"/api/accounts/{acc}/protocols/{p['id']}",
                     json={"doc_category": "QA"}, headers=auth(token))
    assert res.get_json()["protocol"]["document_number"] == "QA-001"


def test_new_version_keeps_number_copy_does_not(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "num3@corp.com", "Nco")
    p = client.post(f"/api/accounts/{acc}/protocols/from-doc-template",
                    json={"key": "eq_operation"}, headers=auth(token)).get_json()["protocol"]
    assert p["document_number"] == "EQ-001"

    ver = client.post(f"/api/accounts/{acc}/protocols/{p['id']}/new-version",
                      headers=auth(token)).get_json()["protocol"]
    assert ver["document_number"] == "EQ-001"    # same controlled doc, new revision

    copy = client.post(f"/api/accounts/{acc}/protocols/{p['id']}/copy",
                       headers=auth(token)).get_json()["protocol"]
    assert copy["document_number"] == ""         # a fork is a new, unnumbered doc


# ── Document register ───────────────────────────────────────────────────────

def test_register_groups_by_protocol_and_category(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "reg1@corp.com", "Rco")
    # A batch record with a protocol/part number, and a procedure.
    client.post(f"/api/accounts/{acc}/protocols/import",
                json={"title": "B090 Production BR", "text": "Batch record", "mode": "numbered",
                      "doc_category": "BR", "product_code": "B090"}, headers=auth(token))
    client.post(f"/api/accounts/{acc}/protocols/from-doc-template",
                json={"key": "eq_operation"}, headers=auth(token))

    res = client.get(f"/api/accounts/{acc}/protocols/register?status=all", headers=auth(token))
    assert res.status_code == 200
    data = res.get_json()
    br_groups = {g["group"] for g in data["batch_records"]}
    assert "B090" in br_groups
    proc_codes = {g["code"] for g in data["procedures"]}
    assert "EQ" in proc_codes
    eq = next(g for g in data["procedures"] if g["code"] == "EQ")
    assert eq["name"] == "Equipment"
    assert eq["items"][0]["document_number"] == "EQ-001"


def test_register_effective_default_excludes_drafts(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "reg2@corp.com", "Rco")
    client.post(f"/api/accounts/{acc}/protocols/from-doc-template",
                json={"key": "eq_operation"}, headers=auth(token))
    res = client.get(f"/api/accounts/{acc}/protocols/register", headers=auth(token))
    data = res.get_json()
    # The doc is a draft, so the effective register is empty.
    assert data["batch_records"] == [] and data["procedures"] == []


def test_doc_template_autofills_assigned_document_number(client):
    """The auto-assigned controlled number fills {{document_number}} in the body,
    so the rendered document shows BR-001 (not a placeholder) and it's no longer
    a manual fill-in field."""
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "tx8@corp.com", "Tco")
    p = client.post(f"/api/accounts/{acc}/protocols/from-doc-template",
                    json={"key": "br_production"}, headers=auth(token)).get_json()["protocol"]
    assert p["document_number"] == "BR-001"
    cells = [c for b in p["body"] if b["type"] == "table" for row in b["rows"] for c in row]
    assert "BR-001" in cells
    assert not any("{{document_number}}" in c for c in cells)
    res = client.get(f"/api/accounts/{acc}/protocols/{p['id']}/template-variables", headers=auth(token))
    assert "document_number" not in res.get_json()["variables"]
