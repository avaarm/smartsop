"""Rich PDF structure extractor using pdfplumber.

Drop-in replacement for the old PyPDF2 path that could not see tables
or font information. pdfplumber exposes the underlying PDF layout
primitives (character bounding boxes, line graphics) so we can:

  * Detect real tabular data via ``page.extract_tables()`` (line-based
    strategy, falling back to text clustering)
  * Histogram fonts & sizes by character, so the analyzer can state
    "body font is Calibri 11pt" with real evidence
  * Report page dimensions in both points and inches

pdfplumber is a thin wrapper over pdfminer.six — pure Python, MIT
licensed, no Ghostscript/Java required.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Optional

logger = logging.getLogger(__name__)


def extract_pdf_structure(file_path: str) -> dict:
    """Return a rich structure dict for a PDF.

    Shape matches the DOCX version where possible:
        {
            "page": {"width_pt", "height_pt", "orientation", ...},
            "text": "full extracted text",
            "pages": [ { "index", "text", "tables": [...] }, ... ],
            "font_histogram": [{"name", "size_pt", "char_count"}],
            "tables": [
                {"page": N, "rows": R, "cols": C, "data": [[...]],
                 "bbox": [x0,y0,x1,y1]},
            ],
        }
    """
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber not installed — falling back to PyPDF2")
        return _fallback_pypdf2(file_path)

    font_counter: Counter = Counter()
    pages_out: list[dict] = []
    tables_out: list[dict] = []
    full_text_parts: list[str] = []

    with pdfplumber.open(file_path) as pdf:
        first_page = pdf.pages[0] if pdf.pages else None
        page_info: dict = {}
        if first_page is not None:
            w_pt = float(first_page.width or 0)
            h_pt = float(first_page.height or 0)
            page_info = {
                "width_pt": round(w_pt, 2),
                "height_pt": round(h_pt, 2),
                "width_inches": round(w_pt / 72, 2) if w_pt else None,
                "height_inches": round(h_pt / 72, 2) if h_pt else None,
                "orientation": "landscape" if w_pt > h_pt else "portrait",
                "count": len(pdf.pages),
            }

        for page_idx, page in enumerate(pdf.pages):
            # Text per page
            page_text = page.extract_text() or ""
            full_text_parts.append(page_text)

            # Font histogram (pdfplumber exposes characters with fontname/size)
            try:
                for char in (page.chars or []):
                    name = char.get("fontname") or "Default"
                    # Normalize font names — pdfminer often prefixes with subset
                    # tags like ``ABCDEF+Calibri``. Strip those for aggregation.
                    if "+" in name:
                        name = name.split("+", 1)[1]
                    size = round(float(char.get("size") or 0), 1)
                    font_counter[(name, size)] += 1
            except Exception as e:  # pragma: no cover - defensive
                logger.debug("char iteration failed on page %d: %s", page_idx, e)

            # Tables on this page
            page_tables: list[list[list[str]]] = []
            try:
                page_tables = page.extract_tables() or []
            except Exception as e:
                logger.debug("extract_tables failed on page %d: %s", page_idx, e)

            for t_idx, table in enumerate(page_tables):
                rows = [[(c or "").strip() for c in row] for row in table]
                tables_out.append({
                    "page": page_idx + 1,
                    "index": t_idx,
                    "rows": len(rows),
                    "cols": max((len(r) for r in rows), default=0),
                    "data": rows[:25],  # cap for payload size
                    "header_row": rows[0] if rows else [],
                })

            pages_out.append({
                "index": page_idx,
                "text_length": len(page_text),
                "table_count": len(page_tables),
            })

    # Condense font histogram to top ~20 entries
    fonts_top = [
        {"name": name, "size_pt": size, "char_count": count}
        for (name, size), count in font_counter.most_common(20)
    ]

    return {
        "page": page_info,
        "text": "\n".join(full_text_parts),
        "pages": pages_out,
        "font_histogram": fonts_top,
        "tables": tables_out,
    }


# ── Fallback for environments without pdfplumber ───────────────────

def _fallback_pypdf2(file_path: str) -> dict:
    from PyPDF2 import PdfReader

    reader = PdfReader(file_path)
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")

    return {
        "page": {"count": len(reader.pages)},
        "text": "\n".join(parts),
        "pages": [{"index": i, "text_length": len(parts[i])} for i in range(len(parts))],
        "font_histogram": [],
        "tables": [],
    }
