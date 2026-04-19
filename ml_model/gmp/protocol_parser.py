"""Deterministic document parser for extracting structure, text, and formatting from protocols.

Parses .docx and .pdf files without LLM calls. Produces a structured dict
that the ProtocolAnalyzer can then feed to Ollama for knowledge extraction.

For DOCX, the richer formatting details (page setup, per-role fonts,
cell shading/borders/merges) are extracted by ``docx_structure`` and
folded into the ``formatting`` result. For PDF, ``pdf_structure`` uses
pdfplumber for real table detection and char-level font histograms.
"""

import logging
import re
from pathlib import Path
from typing import Optional

from .docx_structure import extract_docx_structure
from .pdf_structure import extract_pdf_structure

logger = logging.getLogger(__name__)


class ProtocolParser:
    """Extracts raw content, structure, and formatting metadata from protocol documents."""

    def parse(self, file_path: str, file_type: str) -> dict:
        """Parse a document and return unified structure.

        Returns:
            {
                "text": "full extracted text",
                "sections": [{"number": "1.0", "title": "Purpose", "level": 1, "text": "..."}],
                "formatting": {"fonts": [...], "tables": [...], "styles": [...]},
                "metadata": {"page_count": N, "paragraph_count": N}
            }
        """
        file_type = file_type.lower().strip(".")
        if file_type == "docx":
            return self._parse_docx(file_path)
        elif file_type == "pdf":
            return self._parse_pdf(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

    def _parse_docx(self, file_path: str) -> dict:
        from docx import Document
        from docx.shared import Pt

        doc = Document(file_path)
        full_text_parts = []
        sections = []
        fonts_seen = {}
        styles_seen = {}
        tables_info = []
        current_section = None

        # Parse paragraphs
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue

            full_text_parts.append(text)

            # Detect headings
            style_name = para.style.name if para.style else ""
            is_heading = "heading" in style_name.lower()
            heading_match = re.match(r'^(\d+(?:\.\d+)*)\s+(.+)', text)

            if is_heading or heading_match:
                level = 1
                if is_heading:
                    # Extract level from style name (e.g., "Heading 2" -> level 2)
                    level_match = re.search(r'(\d+)', style_name)
                    if level_match:
                        level = int(level_match.group(1))
                elif heading_match:
                    # Infer level from numbering depth (1.0 = 1, 1.1 = 2, 1.1.1 = 3)
                    level = heading_match.group(1).count('.') + 1

                number = heading_match.group(1) if heading_match else ""
                title = heading_match.group(2) if heading_match else text

                current_section = {
                    "number": number,
                    "title": title,
                    "level": level,
                    "text": "",
                    "style": style_name,
                }
                sections.append(current_section)
            elif current_section:
                current_section["text"] += text + "\n"

            # Track fonts
            for run in para.runs:
                font = run.font
                font_name = font.name or "Default"
                font_size = font.size
                size_pt = round(font_size / Pt(1), 1) if font_size else None
                bold = font.bold
                italic = font.italic

                key = f"{font_name}_{size_pt}_{bold}_{italic}"
                if key not in fonts_seen:
                    fonts_seen[key] = {
                        "name": font_name,
                        "size_pt": size_pt,
                        "bold": bool(bold),
                        "italic": bool(italic),
                        "count": 0,
                    }
                fonts_seen[key]["count"] += 1

            # Track styles
            if style_name and style_name not in styles_seen:
                styles_seen[style_name] = {"name": style_name, "count": 0}
            if style_name:
                styles_seen[style_name]["count"] += 1

        # Rich structural extraction (page setup, per-role fonts, tables with
        # shading/borders/merges) — see ml_model/gmp/docx_structure.py
        try:
            rich = extract_docx_structure(file_path)
        except Exception as e:
            logger.warning("rich docx structure extraction failed: %s", e)
            rich = {}

        rich_tables = rich.get("tables", [])
        # Keep a compact table summary for the analyzer to fit in the prompt.
        tables_info = [
            {
                "index": t["index"],
                "rows": t["rows"],
                "columns": t["cols"],
                "col_widths_dxa": t.get("col_widths_dxa", []),
                "has_header_row": t.get("has_header_row", False),
                "header_row": [c.get("text", "") for c in (t["cells"][0] if t["cells"] else [])],
                "unique_shadings": sorted({
                    (c.get("shading") or "")
                    for row in t["cells"] for c in row
                    if c.get("shading")
                }),
                "max_grid_span": max(
                    (c.get("grid_span", 1) for row in t["cells"] for c in row),
                    default=1,
                ),
            }
            for t in rich_tables
        ]

        # Detect numbering scheme
        numbering_scheme = self._detect_numbering_scheme(sections)

        return {
            "text": "\n".join(full_text_parts),
            "sections": sections,
            "formatting": {
                "fonts": sorted(fonts_seen.values(), key=lambda f: -f["count"]),
                "tables": tables_info,
                "styles": sorted(styles_seen.values(), key=lambda s: -s["count"]),
                "numbering_scheme": numbering_scheme,
                # Rich fields (new):
                "page": rich.get("page", {}),
                "headers": rich.get("headers", {}),
                "footers": rich.get("footers", {}),
                "font_roles": rich.get("font_roles", {}),
                "shading_palette": rich.get("shading_palette", []),
                "tables_detailed": rich_tables,
            },
            "metadata": {
                "paragraph_count": len(full_text_parts),
                "table_count": len(tables_info),
                "section_count": len(sections),
            },
        }

    def _parse_pdf(self, file_path: str) -> dict:
        """Parse PDF with pdfplumber (chars + real tables) when available."""
        rich = extract_pdf_structure(file_path)
        full_text = rich.get("text", "")

        sections = []
        current_section = None
        full_text_parts = []
        for line in full_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            full_text_parts.append(line)

            heading_match = re.match(r'^(\d+(?:\.\d+)*)\s+(.+)', line)
            is_caps_heading = (
                len(line) < 80 and line.isupper() and not line.endswith(".")
            )

            if heading_match:
                number = heading_match.group(1)
                title = heading_match.group(2)
                level = number.count('.') + 1
                current_section = {
                    "number": number,
                    "title": title,
                    "level": level,
                    "text": "",
                }
                sections.append(current_section)
            elif is_caps_heading:
                current_section = {
                    "number": "",
                    "title": line.title(),
                    "level": 1,
                    "text": "",
                }
                sections.append(current_section)
            elif current_section:
                current_section["text"] += line + "\n"

        numbering_scheme = self._detect_numbering_scheme(sections)

        # Compact table summary (full table data lives in tables_detailed)
        detailed_tables = rich.get("tables", [])
        tables_info = [
            {
                "page": t.get("page"),
                "rows": t.get("rows"),
                "columns": t.get("cols"),
                "header_row": t.get("header_row", []),
            }
            for t in detailed_tables
        ]

        return {
            "text": full_text,
            "sections": sections,
            "formatting": {
                "fonts": rich.get("font_histogram", []),
                "tables": tables_info,
                "styles": [],
                "numbering_scheme": numbering_scheme,
                "page": rich.get("page", {}),
                "tables_detailed": detailed_tables,
            },
            "metadata": {
                "page_count": rich.get("page", {}).get("count", len(rich.get("pages", []))),
                "paragraph_count": len(full_text_parts),
                "section_count": len(sections),
                "table_count": len(detailed_tables),
            },
        }

    def _detect_numbering_scheme(self, sections: list[dict]) -> str:
        """Infer the numbering scheme from parsed sections."""
        numbers = [s["number"] for s in sections if s.get("number")]
        if not numbers:
            return "none"

        # Check patterns
        if all(re.match(r'^\d+\.\d+', n) for n in numbers):
            max_depth = max(n.count('.') for n in numbers) + 1
            return ".".join(["X"] * max_depth)  # e.g., "X.X.X"
        elif all(re.match(r'^\d+$', n) for n in numbers):
            return "X"
        return "mixed"
