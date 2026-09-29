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
