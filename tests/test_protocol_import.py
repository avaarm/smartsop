"""Importing a protocol from pasted text or an uploaded file."""

import io

import pytest

from ml_model.gmp.protocol_import import split_into_steps
from util import auth, burn_superadmin, make_owner


# ── Parser unit tests ──

def test_split_numbered():
    steps = split_into_steps("1. Warm the medium\n2) Add cells\nStep 3: Incubate", "numbered")
    assert [s["description"] for s in steps] == ["Warm the medium", "Add cells", "Incubate"]


def test_split_numbered_continuation_lines():
    steps = split_into_steps("1. Warm the medium\n   to 37C\n2. Add cells", "numbered")
    assert steps[0]["description"] == "Warm the medium to 37C"
    assert len(steps) == 2


def test_split_lines():
    steps = split_into_steps("do a\n\ndo b\ndo c", "lines")
    assert [s["description"] for s in steps] == ["do a", "do b", "do c"]


def test_split_markdown_headings():
    steps = split_into_steps("# Prep\nGather tubes\n# Run\nStart the reaction", "markdown")
    assert steps[0]["title"] == "Prep" and "Gather tubes" in steps[0]["description"]
    assert steps[1]["title"] == "Run"


def test_numbered_falls_back_to_lines():
    steps = split_into_steps("just one line\nanother line", "numbered")
    assert len(steps) == 2  # no numbers → line split


# ── Endpoint tests ──

@pytest.fixture()
def owner(client):
    burn_superadmin(client)
    token, acc_id, _ = make_owner(client, "owner@x.com", "Acme")
    return client, token, acc_id


def test_import_from_text(owner):
    client, token, acc_id = owner
    res = client.post(f"/api/accounts/{acc_id}/protocols/import", headers=auth(token),
                      json={"title": "Thaw SOP", "mode": "numbered",
                            "text": "1. Retrieve vial\n2. Warm to 37C\n3. Transfer"})
    assert res.status_code == 201
    body = res.get_json()
    assert body["mode"] == "numbered" and body["step_count"] == 3
    p = body["protocol"]
    assert p["title"] == "Thaw SOP"
    assert [s["description"] for s in p["steps"]] == ["Retrieve vial", "Warm to 37C", "Transfer"]


def test_import_empty_rejected(owner):
    client, token, acc_id = owner
    assert client.post(f"/api/accounts/{acc_id}/protocols/import", headers=auth(token),
                       json={"text": "   "}).status_code == 400


def test_import_ai_falls_back_without_ollama(owner):
    # No Ollama in tests → ai mode degrades to the numbered splitter.
    client, token, acc_id = owner
    res = client.post(f"/api/accounts/{acc_id}/protocols/import", headers=auth(token),
                      json={"title": "AI", "mode": "ai", "text": "1. step one\n2. step two"})
    assert res.status_code == 201
    body = res.get_json()
    assert "AI unavailable" in body["mode"]
    assert body["step_count"] == 2


def test_import_txt_file_upload(owner):
    client, token, acc_id = owner
    data = {
        "title": "From file",
        "mode": "lines",
        "file": (io.BytesIO(b"alpha\nbeta\ngamma"), "procedure.txt"),
    }
    res = client.post(f"/api/accounts/{acc_id}/protocols/import", headers=auth(token),
                      data=data, content_type="multipart/form-data")
    assert res.status_code == 201
    assert res.get_json()["step_count"] == 3


def test_import_docx_file_upload(owner):
    from docx import Document
    doc = Document()
    for line in ["1. First", "2. Second"]:
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)

    client, token, acc_id = owner
    data = {"mode": "numbered", "file": (buf, "MySOP.docx")}
    res = client.post(f"/api/accounts/{acc_id}/protocols/import", headers=auth(token),
                      data=data, content_type="multipart/form-data")
    assert res.status_code == 201
    body = res.get_json()
    assert body["step_count"] == 2
    assert body["protocol"]["title"] == "MySOP"  # derived from filename


def test_import_requires_auth_and_scope(owner):
    client, token, acc_id = owner
    assert client.post(f"/api/accounts/{acc_id}/protocols/import",
                       json={"text": "1. x"}).status_code == 401
    b_tok, _, _ = make_owner(client, "b@x.com", "Beta")
    assert client.post(f"/api/accounts/{acc_id}/protocols/import", headers=auth(b_tok),
                       json={"text": "1. x"}).status_code == 403
