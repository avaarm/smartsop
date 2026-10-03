"""Render a protocol to a printable PDF — the audit artifact a safety or
quality director hands to an OSHA / ISO reviewer.

Uses reportlab (already a dependency). Kept dependency-light and defensive so a
malformed step can never crash the export.
"""

from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)
from xml.sax.saxutils import escape

COMPONENT_LABELS = {
    "ppe": "PPE required", "energy_source": "Energy source",
    "isolation_device": "Isolation device", "lockout_tag": "Lockout tag ID",
    "authorized_person": "Authorized person", "hazard_class": "Hazard class",
    "torque": "Torque spec", "pressure": "Pressure spec", "temperature": "Temperature",
    "expected_result": "Expected result", "return_to_service": "Return-to-service check",
    "verification_photo": "Verification photo required", "second_signature": "Second signature required",
}
STATUS_LABELS = {
    "draft": "Draft", "in_review": "In review", "approved": "Approved",
    "effective": "Effective", "retired": "Retired", "rejected": "Rejected",
}


def _fmt_duration(seconds):
    if not seconds:
        return ""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    parts = [f"{h}h" if h else "", f"{m}m" if m else "", f"{s}s" if s and not h else ""]
    return " ".join(p for p in parts if p) or f"{seconds}s"


def _component_text(comp):
    label = COMPONENT_LABELS.get(comp.get("type"), comp.get("type", ""))
    value = comp.get("value")
    if isinstance(value, bool):
        return f"{label}: {'required' if value else 'no'}"
    return f"{label}: {value}" if value else label


def document_to_pdf(protocol_dict) -> BytesIO:
    """Render a document-format protocol (body blocks: headings, paragraphs,
    tables, checkboxes) to a PDF that mirrors the original document's layout —
    the audit artifact for a controlled document, not a step list."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        title=protocol_dict.get("title", "Document"),
    )
    styles = getSampleStyleSheet()
    h_title = ParagraphStyle("dt", parent=styles["Title"], fontSize=16, spaceAfter=6, alignment=TA_LEFT)
    h_levels = {
        1: ParagraphStyle("dh1", parent=styles["Heading1"], fontSize=13, spaceBefore=10, spaceAfter=3),
        2: ParagraphStyle("dh2", parent=styles["Heading2"], fontSize=12, spaceBefore=8, spaceAfter=2),
        3: ParagraphStyle("dh3", parent=styles["Heading3"], fontSize=11, spaceBefore=6, spaceAfter=2),
    }
    body = ParagraphStyle("db", parent=styles["Normal"], fontSize=9.5, leading=13)
    cell = ParagraphStyle("dc", parent=styles["Normal"], fontSize=8.5, leading=11)
    meta = ParagraphStyle("dm", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#666"))

    def p(text, style):
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)

    meta_bits = []
    if protocol_dict.get("document_number"):
        meta_bits.append(protocol_dict["document_number"])
    meta_bits.append(f"Rev {max(0, protocol_dict.get('version', 1) - 1):02d}")
    meta_bits.append(STATUS_LABELS.get(protocol_dict.get("status"), protocol_dict.get("status", "")))
    if protocol_dict.get("effective_date"):
        meta_bits.append(f"Effective {protocol_dict['effective_date']}")

    flow = [p(protocol_dict.get("title") or "Untitled document", h_title),
            p(" · ".join(str(b) for b in meta_bits if b), meta),
            Spacer(1, 4),
            HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#ccc")),
            Spacer(1, 6)]

    for b in protocol_dict.get("body", []) or []:
        btype = b.get("type")
        if btype == "heading":
            flow.append(p(b.get("text", ""), h_levels.get(min(b.get("level", 1), 3), h_levels[3])))
        elif btype == "checkbox":
            mark = "☒" if b.get("checked") else "☐"
            flow.append(p(f"{mark} {b.get('text', '')}", body))
        elif btype == "table":
            rows = b.get("rows", [])
            if not rows:
                continue
            ncols = max((len(r) for r in rows), default=0)
            if ncols == 0:
                continue
            data = [[p(r[c] if c < len(r) else "", cell) for c in range(ncols)] for r in rows]
            avail = 7.0 * inch
            t = Table(data, colWidths=[avail / ncols] * ncols)
            t.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bbb")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f2f4")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            flow.append(Spacer(1, 4))
            flow.append(t)
            flow.append(Spacer(1, 4))
        else:
            flow.append(p(b.get("text", ""), body))

    doc.build(flow)
    buf.seek(0)
    return buf


def protocol_to_pdf(protocol_dict) -> BytesIO:
    """Render a protocol dict (from Protocol.to_dict(include_steps=True))."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.9 * inch, rightMargin=0.9 * inch,
        topMargin=0.85 * inch, bottomMargin=0.85 * inch,
        title=protocol_dict.get("title", "Protocol"),
    )

    styles = getSampleStyleSheet()
    h_title = ParagraphStyle("t", parent=styles["Title"], fontSize=18, spaceAfter=4, alignment=TA_LEFT)
    h_meta = ParagraphStyle("m", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#666"))
    h_step = ParagraphStyle("s", parent=styles["Heading3"], fontSize=12, spaceBefore=12, spaceAfter=2)
    body = ParagraphStyle("b", parent=styles["Normal"], fontSize=10, leading=14)
    warn = ParagraphStyle("w", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#b00"),
                          leftIndent=6, spaceBefore=3)
    comp = ParagraphStyle("c", parent=styles["Normal"], fontSize=9,
                          textColor=colors.HexColor("#333"), leftIndent=6, spaceBefore=2)

    def p(text, style):
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)

    flow = [p(protocol_dict.get("title") or "Untitled protocol", h_title)]

    # Control metadata line.
    meta_bits = []
    if protocol_dict.get("document_number"):
        meta_bits.append(protocol_dict["document_number"])
    if protocol_dict.get("sop_number"):
        meta_bits.append(f"SOP {protocol_dict['sop_number']}")
    meta_bits.append(f"v{protocol_dict.get('version', 1)}")
    meta_bits.append(STATUS_LABELS.get(protocol_dict.get("status"), protocol_dict.get("status", "")))
    if protocol_dict.get("department"):
        meta_bits.append(protocol_dict["department"])
    if protocol_dict.get("effective_date"):
        meta_bits.append(f"Effective {protocol_dict['effective_date']}")
    flow.append(p(" · ".join(str(b) for b in meta_bits if b), h_meta))
    flow.append(Spacer(1, 6))
    flow.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#ccc")))

    if protocol_dict.get("description"):
        flow.append(Spacer(1, 8))
        flow.append(p(protocol_dict["description"], body))

    for i, step in enumerate(protocol_dict.get("steps", []), start=1):
        title = step.get("title") or ""
        flow.append(p(f"{i}. {title}", h_step))
        if step.get("description"):
            flow.append(p(step["description"], body))
        dur = _fmt_duration(step.get("duration_seconds"))
        if dur:
            flow.append(p(f"Timer: {dur}", comp))
        for c in step.get("components", []):
            if isinstance(c, dict):
                flow.append(p("• " + _component_text(c), comp))
        if step.get("warning"):
            flow.append(p("⚠ " + step["warning"], warn))

    # Signature block (audit trail).
    signoffs = protocol_dict.get("signoffs", [])
    if signoffs:
        flow.append(Spacer(1, 14))
        flow.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#ccc")))
        flow.append(p("Signatures", h_step))
        rows = [["Role", "Decision", "Signed by", "When"]]
        for s in signoffs:
            rows.append([
                s.get("role", ""), s.get("decision", ""),
                s.get("signed_by", ""), (s.get("signed_at") or "")[:19].replace("T", " "),
            ])
        table = Table(rows, colWidths=[1.2 * inch, 1.2 * inch, 2.0 * inch, 2.0 * inch])
        table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#666")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#ccc")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        flow.append(table)

    doc.build(flow)
    buf.seek(0)
    return buf
