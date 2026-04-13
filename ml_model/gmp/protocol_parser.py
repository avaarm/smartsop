"""Deterministic document parser for extracting structure, text, and formatting from protocols.

Parses .docx and .pdf files without LLM calls. Produces a structured dict
that the ProtocolAnalyzer can then feed to Ollama for knowledge extraction.
"""

import logging
import re
from pathlib import Path
from typing import Optional

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

        # Parse tables
        for i, table in enumerate(doc.tables):
            rows = len(table.rows)
            cols = len(table.columns) if table.rows else 0
            header_cells = []
            if rows > 0:
                header_cells = [cell.text.strip() for cell in table.rows[0].cells]

            tables_info.append({
                "index": i,
                "rows": rows,
                "columns": cols,
                "header_row": header_cells,
            })

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
            },
            "metadata": {
                "paragraph_count": len(full_text_parts),
                "table_count": len(tables_info),
                "section_count": len(sections),
            },
        }

    def _parse_pdf(self, file_path: str) -> dict:
        from PyPDF2 import PdfReader

        reader = PdfReader(file_path)
        full_text_parts = []
        sections = []
        current_section = None

        for page_num, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            for line in page_text.split("\n"):
                line = line.strip()
                if not line:
                    continue

                full_text_parts.append(line)

                # Detect section headings via numbering pattern
                heading_match = re.match(r'^(\d+(?:\.\d+)*)\s+(.+)', line)
                # Also detect ALL-CAPS short lines as potential headings
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

        return {
            "text": "\n".join(full_text_parts),
            "sections": sections,
            "formatting": {
                "fonts": [],  # PDF text extraction doesn't preserve fonts reliably
                "tables": [],
                "styles": [],
                "numbering_scheme": numbering_scheme,
            },
            "metadata": {
                "page_count": len(reader.pages),
                "paragraph_count": len(full_text_parts),
                "section_count": len(sections),
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
