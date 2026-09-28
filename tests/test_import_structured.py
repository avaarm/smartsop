"""Structure-preserving import — headings, hierarchy, body, and tables kept 1-to-1."""

import io

from util import burn_superadmin, make_owner, auth


def _make_docx():
    from docx import Document
    d = Document()
    d.add_heading("3.2.S Drug Substance", level=1)
    d.add_heading("3.2.S.1 Nomenclature", level=2)
    d.add_paragraph("The drug substance is Acetaminophen.")
    d.add_paragraph("INN: paracetamol.")
    d.add_heading("3.2.S.2 Manufacture", level=2)
    d.add_paragraph("Manufactured by the following process.")
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text = "Property"; t.cell(0, 1).text = "Value"
    t.cell(1, 0).text = "Molecular weight"; t.cell(1, 1).text = "151.16"
    buf = io.BytesIO(); d.save(buf)
    return buf.getvalue()


def test_docx_import_preserves_structure(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "is1@corp.com", "Ico")
    data = {
        "file": (io.BytesIO(_make_docx()), "cmc_s.docx"),
        "mode": "structured",
    }
    res = client.post(f"/api/accounts/{acc}/protocols/import", data=data,
                      content_type="multipart/form-data", headers=auth(token))
    assert res.status_code == 201
    steps = res.get_json()["protocol"]["steps"]

    # The H1 becomes a section marker; both H2 headings are preserved as titles,
    # grouped under the H1 section — the outline survives 1-to-1.
    titles = [s["title"] for s in steps]
    sections = {s["section"] for s in steps}
    assert "3.2.S.1 Nomenclature" in titles
    assert "3.2.S.2 Manufacture" in titles
    assert "3.2.S Drug Substance" in sections

    nomen = next(s for s in steps if s["title"] == "3.2.S.1 Nomenclature")
    assert nomen["section"] == "3.2.S Drug Substance"
    # Full body under the heading is retained (both paragraphs).
    assert "Acetaminophen" in nomen["description"]
    assert "paracetamol" in nomen["description"]

    # The table's content is preserved (as text) — nothing dropped.
    manu = next(s for s in steps if s["title"] == "3.2.S.2 Manufacture")
    assert "Molecular weight" in manu["description"] and "151.16" in manu["description"]


def test_structured_is_default_for_file_import(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "is2@corp.com", "Jco")
    # No explicit mode → files default to structured extraction.
    data = {"file": (io.BytesIO(_make_docx()), "cmc.docx")}
    res = client.post(f"/api/accounts/{acc}/protocols/import", data=data,
                      content_type="multipart/form-data", headers=auth(token))
    assert res.status_code == 201
    assert res.get_json()["mode"] == "structured"
    assert any(s["title"] == "3.2.S.1 Nomenclature" for s in res.get_json()["protocol"]["steps"])


def test_structured_text_numbered_sections(client):
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "is3@corp.com", "Kco")
    text = ("3.2.P Drug Product\n"
            "3.2.P.1 Description\nA white tablet.\n"
            "3.2.P.2 Composition\nActive plus excipients.")
    res = client.post(f"/api/accounts/{acc}/protocols/import",
                      json={"title": "Drug Product", "text": text, "mode": "structured"},
                      headers=auth(token))
    assert res.status_code == 201
    steps = res.get_json()["protocol"]["steps"]
    titles = [s["title"] for s in steps]
    assert "3.2.P.1 Description" in titles and "3.2.P.2 Composition" in titles
    desc = next(s for s in steps if s["title"] == "3.2.P.1 Description")["description"]
    assert "white tablet" in desc


def test_plain_numbered_list_still_flattens_to_steps(client):
    """A simple numbered procedure (no hierarchy) is not mistaken for headings."""
    burn_superadmin(client)
    token, acc, _ = make_owner(client, "is4@corp.com", "Lco")
    res = client.post(f"/api/accounts/{acc}/protocols/import",
                      json={"title": "Simple", "text": "1. Do this\n2. Do that", "mode": "numbered"},
                      headers=auth(token))
    steps = res.get_json()["protocol"]["steps"]
    assert len(steps) == 2
    assert all(not s["section"] for s in steps)   # no false headings
