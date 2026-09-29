"""Render a document-format protocol back to a .docx.

The whole point of document-fidelity: a user uploads an approved batch record /
CMC section, fills in the project-specific fields ({{variables}}), and downloads
a Word file that looks exactly like the original the reviewer already approved —
because it *is* the original, with placeholders substituted run-safe.

Two paths:
- original_file present  → open it and replace {{tokens}} in place (byte-faithful
  formatting: same header table, fonts, approval block).
- blocks only (pasted text, no file) → rebuild a clean .docx from body_json.
"""

import io
import re

VAR_RE = re.compile(r"\{\{\s*([\w .\-/#]+?)\s*\}\}")


def _apply(text, variables):
    if not text or not variables:
        return text
    return VAR_RE.sub(lambda m: str(variables.get(m.group(1).strip(), m.group(0))), text)


def _replace_in_paragraph(paragraph, variables):
    """Substitute {{vars}} in a paragraph. A placeholder can span several runs,
    so when the paragraph text changes we collapse the substituted text into the
    first run and blank the rest — formatting outside var-bearing paragraphs is
    untouched."""
    if "{{" not in paragraph.text:
        return
    new = _apply(paragraph.text, variables)
    if new == paragraph.text:
        return
    if paragraph.runs:
        paragraph.runs[0].text = new
        for r in paragraph.runs[1:]:
            r.text = ""
    else:
        paragraph.text = new


def _walk_tables(tables, variables):
    for table in tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    _replace_in_paragraph(p, variables)
                if cell.tables:  # nested tables
                    _walk_tables(cell.tables, variables)


def _fill_original(data: bytes, variables) -> io.BytesIO:
    from docx import Document
    doc = Document(io.BytesIO(data))
    for p in doc.paragraphs:
        _replace_in_paragraph(p, variables)
    _walk_tables(doc.tables, variables)
    # Headers/footers too — page banners often carry Doc No / Lot fields.
    for section in doc.sections:
        for container in (section.header, section.footer):
            for p in container.paragraphs:
                _replace_in_paragraph(p, variables)
            _walk_tables(container.tables, variables)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


def _build_from_blocks(title, blocks, variables) -> io.BytesIO:
    from docx import Document
    doc = Document()
    if title:
        doc.add_heading(_apply(title, variables), level=0)
    for b in blocks or []:
        btype = b.get("type")
        if btype == "heading":
            doc.add_heading(_apply(b.get("text", ""), variables), level=min(max(b.get("level", 1), 1), 6))
        elif btype == "checkbox":
            mark = "☒" if b.get("checked") else "☐"
            doc.add_paragraph(f"{mark} {_apply(b.get('text', ''), variables)}")
        elif btype == "table":
            rows = b.get("rows", [])
            if not rows:
                continue
            ncols = max((len(r) for r in rows), default=0)
            if ncols == 0:
                continue
            table = doc.add_table(rows=len(rows), cols=ncols)
            table.style = "Table Grid"
            for ri, row in enumerate(rows):
                for ci in range(ncols):
                    table.rows[ri].cells[ci].text = _apply(row[ci] if ci < len(row) else "", variables)
        else:  # paragraph / unknown
            doc.add_paragraph(_apply(b.get("text", ""), variables))
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


def render_filled_docx(protocol, variables):
    """Return a BytesIO .docx for `protocol` with {{variables}} filled, or None
    if the protocol has no document content to render."""
    import json
    if protocol.original_file:
        return _fill_original(protocol.original_file, variables or {})
    blocks = []
    if protocol.body_json:
        try:
            blocks = json.loads(protocol.body_json)
        except ValueError:
            blocks = []
    if not blocks:
        return None
    return _build_from_blocks(protocol.title, blocks, variables or {})
