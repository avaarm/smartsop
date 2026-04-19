"""Rich DOCX structure extractor.

Goes beyond python-docx's built-in helpers to pull out the formatting
details that matter for faithful reproduction:

  * Page setup (orientation, margins, size in DXA)
  * Headers and footers (first-page + default) as text
  * Per-role font histograms (body, Heading 1, Heading 2, ...) so
    downstream analysis can state "body is Calibri 11pt" with
    confidence instead of guessing from a global top font.
  * Rich table extraction:
      - Column widths (DXA twips)
      - Per-cell shading (background fill colors, e.g. ``BFBFBF``)
      - Cell borders (top/left/bottom/right: style, size, color)
      - Horizontal merges (``w:gridSpan``)
      - Vertical merges (``w:vMerge``)
      - Header-row flag (``w:tblHeader``)
      - Per-cell text (first 200 chars)
  * Numbering scheme (already in parser, mirrored here for cohesion).

The output is pure JSON-serializable dicts so the ProtocolAnalyzer
can feed it to the LLM, and the frontend can render it verbatim in
the Formatting knowledge card.
"""

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from typing import Optional

logger = logging.getLogger(__name__)

# OOXML namespaces — every qualified tag under w:// lives here.
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}


def _qn(tag: str) -> str:
    """Return a `{ns}localname` Clark-notation tag for direct lxml lookups."""
    return f"{{{W_NS}}}{tag}"


def _attr(elem, tag: str) -> Optional[str]:
    """Read a ``w:*`` attribute off an element, returning None if absent."""
    return elem.get(_qn(tag)) if elem is not None else None


# ── Top-level extractor ────────────────────────────────────────────

def extract_docx_structure(file_path: str) -> dict:
    """Return a rich structure dict for ``file_path``.

    Shape:
        {
            "page": {"orientation", "width_dxa", "height_dxa",
                     "margins_dxa": {top, right, bottom, left}},
            "headers": {"default": "...", "first_page": "..."},
            "footers": {"default": "...", "first_page": "..."},
            "font_roles": {
                "body": {"name", "size_pt", "bold", "italic", "count"},
                "Heading 1": {...}, ...
            },
            "shading_palette": [{"color": "BFBFBF", "count": 12}, ...],
            "tables": [
                {
                    "index", "rows", "cols",
                    "col_widths_dxa": [int, ...],
                    "has_header_row": bool,
                    "cells": [[{"text", "shading", "gridSpan",
                                "vMerge", "borders"}, ...], ...]
                }
            ],
            "numbering_scheme": "X.X.X" | "X" | "mixed" | "none",
        }
    """
    from docx import Document

    doc = Document(file_path)

    return {
        "page": _extract_page_setup(doc),
        "headers": _extract_headers(doc),
        "footers": _extract_footers(doc),
        "font_roles": _extract_font_roles(doc),
        "tables": [_extract_table(t, idx) for idx, t in enumerate(doc.tables)],
        "shading_palette": _extract_shading_palette(doc),
    }


# ── Page setup ─────────────────────────────────────────────────────

def _extract_page_setup(doc) -> dict:
    """Read the first section's ``<w:sectPr>`` for page size + margins."""
    try:
        sect = doc.sections[0]
    except IndexError:
        return {}

    sect_pr = sect._sectPr
    pg_sz = sect_pr.find(_qn("pgSz"))
    pg_mar = sect_pr.find(_qn("pgMar"))

    orientation = "portrait"
    width_dxa = None
    height_dxa = None
    if pg_sz is not None:
        width_dxa = int(_attr(pg_sz, "w") or 0) or None
        height_dxa = int(_attr(pg_sz, "h") or 0) or None
        orient = _attr(pg_sz, "orient")
        if orient:
            orientation = orient
        elif width_dxa and height_dxa and width_dxa > height_dxa:
            orientation = "landscape"

    margins = {}
    if pg_mar is not None:
        for side in ("top", "right", "bottom", "left"):
            val = _attr(pg_mar, side)
            if val is not None:
                try:
                    margins[f"{side}_dxa"] = int(val)
                except ValueError:
                    pass

    return {
        "orientation": orientation,
        "width_dxa": width_dxa,
        "height_dxa": height_dxa,
        "margins_dxa": margins,
        "width_inches": round(width_dxa / 1440, 2) if width_dxa else None,
        "height_inches": round(height_dxa / 1440, 2) if height_dxa else None,
    }


# ── Headers and footers ────────────────────────────────────────────

def _extract_headers(doc) -> dict:
    """Return header text keyed by kind (default / first_page / even_page)."""
    out = {}
    for sect in doc.sections:
        for kind, header in (
            ("default", sect.header),
            ("first_page", sect.first_page_header),
            ("even_page", sect.even_page_header),
        ):
            try:
                text = "\n".join(p.text for p in header.paragraphs if p.text.strip())
            except Exception:
                text = ""
            if text and kind not in out:
                out[kind] = text[:1000]
    return out


def _extract_footers(doc) -> dict:
    out = {}
    for sect in doc.sections:
        for kind, footer in (
            ("default", sect.footer),
            ("first_page", sect.first_page_footer),
            ("even_page", sect.even_page_footer),
        ):
            try:
                text = "\n".join(p.text for p in footer.paragraphs if p.text.strip())
            except Exception:
                text = ""
            if text and kind not in out:
                out[kind] = text[:1000]
    return out


# ── Fonts by role ──────────────────────────────────────────────────

def _extract_font_roles(doc) -> dict:
    """Aggregate font usage grouped by paragraph style (role).

    E.g., text in paragraphs styled "Heading 1" vs "Normal" vs "Body Text"
    typically uses different fonts/sizes — we produce one summary per role
    rather than a single global histogram.
    """
    from docx.shared import Pt

    role_fonts: dict[str, Counter] = defaultdict(Counter)
    role_totals: Counter = Counter()

    for para in doc.paragraphs:
        if not para.text.strip():
            continue
        style_name = (para.style.name if para.style else "Normal") or "Normal"
        role_key = _canonicalize_role(style_name)
        role_totals[role_key] += 1
        for run in para.runs:
            f = run.font
            name = f.name or "Default"
            size_pt = None
            try:
                if f.size is not None:
                    size_pt = round(f.size / Pt(1), 1)
            except Exception:
                pass
            key = (name, size_pt, bool(f.bold), bool(f.italic))
            role_fonts[role_key][key] += len(run.text or "")

    out = {}
    for role, counter in role_fonts.items():
        if not counter:
            continue
        (name, size_pt, bold, italic), count = counter.most_common(1)[0]
        out[role] = {
            "name": name,
            "size_pt": size_pt,
            "bold": bold,
            "italic": italic,
            "sample_char_count": count,
            "paragraph_count": role_totals[role],
        }
    return out


def _canonicalize_role(style_name: str) -> str:
    """Map verbose style names down to friendly role keys."""
    name = style_name.strip()
    lower = name.lower()
    if lower in ("normal", "body text", "default paragraph font", ""):
        return "body"
    if lower.startswith("heading"):
        # "Heading 1", "Heading 2 Char" → "Heading 1", "Heading 2"
        m = re.search(r"heading\s*(\d+)", lower)
        if m:
            return f"Heading {m.group(1)}"
        return "Heading"
    if lower.startswith("title"):
        return "Title"
    if "caption" in lower:
        return "Caption"
    if "footer" in lower:
        return "Footer"
    if "header" in lower:
        return "Header"
    if "list" in lower:
        return "List"
    if "toc" in lower:
        return "TOC"
    return name  # preserve custom style names verbatim


# ── Tables ─────────────────────────────────────────────────────────

def _extract_table(table, idx: int) -> dict:
    """Return a rich spec for a single ``docx.Table`` object."""
    tbl_el = table._tbl
    col_widths = _extract_col_widths(tbl_el)

    cells: list[list[dict]] = []
    for row in table.rows:
        row_data = []
        for cell in row.cells:
            row_data.append(_extract_cell(cell))
        cells.append(row_data)

    # Detect the typical "header row" — when row 0 has shading on all cells,
    # or when <w:tblHeader/> is set on its <w:trPr>.
    has_header_row = _detect_header_row(table)

    return {
        "index": idx,
        "rows": len(table.rows),
        "cols": len(col_widths) or (len(table.columns) if table.rows else 0),
        "col_widths_dxa": col_widths,
        "has_header_row": has_header_row,
        "cells": cells,
    }


def _extract_col_widths(tbl_el) -> list[int]:
    widths: list[int] = []
    grid = tbl_el.find(_qn("tblGrid"))
    if grid is None:
        return widths
    for col in grid.findall(_qn("gridCol")):
        w = _attr(col, "w")
        try:
            widths.append(int(w))
        except (TypeError, ValueError):
            widths.append(0)
    return widths


def _detect_header_row(table) -> bool:
    if not table.rows:
        return False
    first_row = table.rows[0]
    tr_pr = first_row._tr.find(_qn("trPr"))
    if tr_pr is not None and tr_pr.find(_qn("tblHeader")) is not None:
        return True
    # Fallback heuristic: every cell in row 0 has the same shading.
    shades = [_extract_cell_shading(c._tc) for c in first_row.cells]
    if shades and all(shades) and len(set(shades)) == 1:
        return True
    return False


def _extract_cell(cell) -> dict:
    """Extract a single cell's text + formatting metadata."""
    tc = cell._tc
    tc_pr = tc.find(_qn("tcPr"))
    text = (cell.text or "").strip()

    return {
        "text": text[:200],
        "shading": _extract_cell_shading(tc),
        "grid_span": _extract_grid_span(tc_pr),
        "v_merge": _extract_v_merge(tc_pr),
        "borders": _extract_cell_borders(tc_pr),
        "alignment": _extract_cell_alignment(tc_pr, cell),
    }


def _extract_cell_shading(tc_el) -> Optional[str]:
    """Return the fill color (hex, no #) or None."""
    tc_pr = tc_el.find(_qn("tcPr"))
    if tc_pr is None:
        return None
    shd = tc_pr.find(_qn("shd"))
    if shd is None:
        return None
    fill = _attr(shd, "fill")
    if fill in (None, "auto", ""):
        return None
    return fill.upper()


def _extract_grid_span(tc_pr) -> int:
    if tc_pr is None:
        return 1
    gs = tc_pr.find(_qn("gridSpan"))
    if gs is None:
        return 1
    val = _attr(gs, "val")
    try:
        return int(val) if val else 1
    except ValueError:
        return 1


def _extract_v_merge(tc_pr) -> Optional[str]:
    """Return 'restart', 'continue', or None."""
    if tc_pr is None:
        return None
    vm = tc_pr.find(_qn("vMerge"))
    if vm is None:
        return None
    return _attr(vm, "val") or "continue"


def _extract_cell_borders(tc_pr) -> dict:
    if tc_pr is None:
        return {}
    borders = tc_pr.find(_qn("tcBorders"))
    if borders is None:
        return {}
    out = {}
    for side in ("top", "left", "bottom", "right"):
        b = borders.find(_qn(side))
        if b is not None:
            out[side] = {
                "val": _attr(b, "val"),
                "sz": _attr(b, "sz"),
                "color": (_attr(b, "color") or "").upper() or None,
            }
    return out


def _extract_cell_alignment(tc_pr, cell) -> dict:
    out = {}
    if tc_pr is not None:
        v_align = tc_pr.find(_qn("vAlign"))
        if v_align is not None:
            out["vertical"] = _attr(v_align, "val")
    # Horizontal alignment is per-paragraph; take the first paragraph's
    # <w:jc val="..."/> if present as a hint.
    try:
        first_para = cell.paragraphs[0]
        jc = first_para._p.find(_qn("pPr"))
        if jc is not None:
            jc_el = jc.find(_qn("jc"))
            if jc_el is not None:
                out["horizontal"] = _attr(jc_el, "val")
    except (IndexError, AttributeError):
        pass
    return out


# ── Shading palette across all tables ──────────────────────────────

def _extract_shading_palette(doc) -> list[dict]:
    """Histogram of unique cell-shading colors used across all tables.

    Useful signal — e.g., ``[{"color":"BFBFBF","count":12}]`` tells the
    analyzer "this org uses BFBFBF as its section-header grey".
    """
    counter: Counter = Counter()
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                shd = _extract_cell_shading(cell._tc)
                if shd:
                    counter[shd] += 1
    return [{"color": c, "count": n} for c, n in counter.most_common(10)]
