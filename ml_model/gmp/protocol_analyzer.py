"""LLM-powered protocol analyzer for extracting knowledge from parsed documents.

Takes the output of ProtocolParser and runs focused LLM analysis passes
to extract terminology, rules, style, and structure patterns.
"""

import json
import logging
from typing import Optional

from .ollama_service import OllamaService

logger = logging.getLogger(__name__)

# ── Analysis Prompts ──

TERMINOLOGY_EXTRACTION_PROMPT = """Analyze this GMP protocol document and extract all domain-specific terminology.

DOCUMENT TEXT:
{text}

Return a JSON object with:
{{
  "terms": {{
    "ABBREVIATION": "Full meaning"
  }},
  "standard_phrases": [
    "Recurring phrases used as standard language in procedures"
  ],
  "units_and_formats": [
    "Any specific measurement units, date formats, or numbering conventions"
  ]
}}

Focus on:
- Abbreviations and acronyms (BSC, TSCD, CPF, etc.)
- Equipment-specific terms
- Process-specific terminology
- Standard phrases that appear multiple times
- Organization-specific naming conventions

Only include terms actually found in the document. Do not invent terms."""


PROCEDURAL_RULES_PROMPT = """Analyze this GMP protocol and extract the procedural rules and conventions it follows.

DOCUMENT TEXT:
{text}

SECTION STRUCTURE:
{sections}

Return a JSON object with:
{{
  "rules": [
    "Each rule as a clear statement, e.g., 'All BSC operations must be prefixed with [BSC]'"
  ],
  "verification_patterns": [
    "How verifications/checks are structured in this document"
  ],
  "documentation_requirements": [
    "What must be recorded, signed, or dated"
  ],
  "safety_conventions": [
    "Safety-related patterns (PPE, environmental monitoring, etc.)"
  ]
}}

Focus on patterns that repeat across multiple sections - these are the organization's conventions, not one-off instructions."""


WRITING_STYLE_PROMPT = """Analyze the writing style of this GMP protocol document.

SAMPLE PARAGRAPHS:
{sample_text}

Return a JSON object with:
{{
  "voice": "active or passive",
  "tense": "present imperative, present indicative, future, etc.",
  "person": "first, second, third, or impersonal",
  "sentence_patterns": [
    "Common sentence structures used, e.g., 'Verb + object + qualifier'"
  ],
  "formatting_conventions": [
    "How lists, notes, warnings, and references are formatted in text"
  ],
  "observations": [
    "Other notable style patterns"
  ]
}}

Be specific - cite actual phrases from the document as examples of each pattern."""


SECTION_STRUCTURE_PROMPT = """Analyze the section structure of this GMP protocol document.

SECTIONS FOUND:
{sections}

Return a JSON object with:
{{
  "numbering_scheme": "Description of how sections are numbered (e.g., '1.0, 1.1, 1.1.1')",
  "standard_sections": [
    {{
      "title": "Section name",
      "typical_position": 1,
      "is_mandatory": true,
      "purpose": "What this section covers"
    }}
  ],
  "hierarchy_depth": 3,
  "observations": [
    "Notable patterns in how sections are organized"
  ]
}}

Identify which sections appear to be standard/mandatory vs optional."""


FORMATTING_ANALYSIS_PROMPT = """You are extracting a **machine-readable formatting spec** from a GMP
protocol. The spec will be fed back into a document generator to
produce new documents that match this organization's exact format, so
favour concrete numeric values over prose.

DETERMINISTIC DATA (already measured from the file — prefer these
values over any guess):
Page setup: {page}
Per-role fonts (paragraph-style → font): {font_roles}
Global font histogram (top 10): {fonts}
Shading palette (cell background colors used): {shading_palette}
Header text: {headers}
Footer text: {footers}
Paragraph styles by frequency: {styles}
Table summaries: {tables}

Return ONLY a JSON object with this shape:
{{
  "page": {{
    "orientation": "landscape|portrait",
    "size_inches": [width, height],
    "margins_inches": {{"top": x, "right": x, "bottom": x, "left": x}}
  }},
  "body_font": {{"name": "Calibri", "size_pt": 11, "line_spacing": 1.0}},
  "heading_fonts": [
    {{"level": 1, "name": "Calibri", "size_pt": 14, "bold": true, "color_hex": "000000"}}
  ],
  "header_pattern": "short description of what appears in the page header (or null)",
  "footer_pattern": "short description of what appears in the page footer (or null)",
  "shading_roles": {{
    "section_header": "BFBFBF",
    "label_cell": "F2F2F2",
    "alternating_rows": null
  }},
  "table_conventions": [
    "Each convention as a concrete rule, e.g. 'Approval blocks use 3 columns of equal width with a BFBFBF header row'"
  ],
  "list_style": {{
    "bullets": "round|square|dash|none",
    "numbering": "1./a)/i)/X.X",
    "indent_inches": 0.25
  }},
  "observations": [
    "Other patterns that can be stated as a rule"
  ]
}}

Rules:
1. Copy numeric values (page size, margins, shading colors) directly
   from DETERMINISTIC DATA. Do not round or invent.
2. If a piece of data is missing, set the field to null — do NOT
   hallucinate a default.
3. Shading colors must be 6-char hex without the leading #."""


TABLE_TEMPLATES_PROMPT = """Extract **reusable table templates** from this protocol — tables
whose row/column structure and shading pattern appear to be a
convention the organization reuses (approval blocks, signature
tables, equipment lists, checklists, step-procedures, etc.).

DETERMINISTIC TABLE DATA (rows×cols, column widths, shading, header
rows are measured from the file — trust these numbers):
{tables_detailed}

Return ONLY a JSON object:
{{
  "templates": [
    {{
      "name": "Approval block",
      "purpose": "Signatures and dates for reviewers/approvers",
      "rows": 4,
      "cols": 3,
      "col_widths_dxa": [4320, 4320, 4320],
      "has_header_row": true,
      "header_shading_hex": "BFBFBF",
      "label_shading_hex": "F2F2F2",
      "header_row_text": ["Role", "Signature", "Date"],
      "fixed_row_text": [["Author"], ["Reviewer"], ["Approver"]],
      "notes": "Appears once, usually on page 1"
    }}
  ]
}}

Rules:
1. Only include tables whose structure is likely to be reused. A
   unique free-form table with body text is NOT a template.
2. ``header_shading_hex`` and ``label_shading_hex`` must be 6-char
   hex without #. Use null if no shading is present.
3. Preserve numeric ``col_widths_dxa`` verbatim from the input.
4. ``name`` should be inferred from header-row text or first-column
   labels (e.g., "Equipment List", "Step Procedure")."""


class ProtocolAnalyzer:
    """Runs LLM analysis passes on parsed protocol content to extract knowledge."""

    def __init__(self, ollama: OllamaService):
        self.ollama = ollama

    def analyze(self, parsed_data: dict) -> list[dict]:
        """Run all analysis passes and return knowledge records.

        Args:
            parsed_data: Output from ProtocolParser.parse()

        Returns:
            List of dicts, each with:
                category: str (terminology, procedural_rules, writing_style, section_structure, formatting)
                knowledge_json: str (JSON string)
                summary: str (human-readable summary)
                confidence: float (0-1)
        """
        results = []
        text = parsed_data.get("text", "")
        sections = parsed_data.get("sections", [])
        formatting = parsed_data.get("formatting", {})

        if not text:
            return results

        # Truncate text to fit LLM context (~6000 tokens ~ 24000 chars)
        truncated_text = text[:24000]
        sections_str = json.dumps(
            [{"number": s.get("number", ""), "title": s.get("title", ""), "level": s.get("level", 1)}
             for s in sections],
            indent=2
        )

        # Build rich formatting context from the deterministic parse.
        formatting_ctx = {
            "page": json.dumps(formatting.get("page", {})),
            "font_roles": json.dumps(formatting.get("font_roles", {})),
            "fonts": json.dumps(formatting.get("fonts", [])[:10]),
            "shading_palette": json.dumps(formatting.get("shading_palette", [])),
            "headers": json.dumps(formatting.get("headers", {})),
            "footers": json.dumps(formatting.get("footers", {})),
            "styles": json.dumps(formatting.get("styles", [])[:10]),
            "tables": json.dumps(formatting.get("tables", [])[:10]),
        }

        # Compact table details for table-templates pass — drop individual
        # cell text (already summarised by header_row) to keep prompt small.
        def _compact_table(t: dict) -> dict:
            return {
                "rows": t.get("rows"),
                "cols": t.get("cols"),
                "col_widths_dxa": t.get("col_widths_dxa", []),
                "has_header_row": t.get("has_header_row"),
                "header_row_text": [c.get("text", "") for c in (t.get("cells") or [[]])[0]],
                "shading_by_row": [
                    sorted({(c.get("shading") or "") for c in row if c.get("shading")})
                    for row in (t.get("cells") or [])
                ][:6],
            }

        compact_tables = [
            _compact_table(t) for t in formatting.get("tables_detailed", [])[:8]
        ]

        # Run each analysis pass
        analyses = [
            ("terminology", TERMINOLOGY_EXTRACTION_PROMPT, {"text": truncated_text}),
            ("procedural_rules", PROCEDURAL_RULES_PROMPT, {"text": truncated_text, "sections": sections_str}),
            ("writing_style", WRITING_STYLE_PROMPT, {"sample_text": self._get_sample_paragraphs(text)}),
            ("section_structure", SECTION_STRUCTURE_PROMPT, {"sections": sections_str}),
            ("formatting", FORMATTING_ANALYSIS_PROMPT, formatting_ctx),
        ]
        if compact_tables:
            analyses.append(
                ("table_templates", TABLE_TEMPLATES_PROMPT, {
                    "tables_detailed": json.dumps(compact_tables, indent=2),
                })
            )

        for category, prompt_template, context in analyses:
            try:
                prompt = prompt_template.format(**context)
                knowledge = self.ollama.generate_json(prompt, temperature=0.2)

                summary = self._summarize_knowledge(category, knowledge)
                results.append({
                    "category": category,
                    "knowledge_json": json.dumps(knowledge),
                    "summary": summary,
                    "confidence": 0.8,  # Could be improved with self-assessment
                })
                logger.info(f"Extracted {category} knowledge")
            except Exception as e:
                logger.error(f"Failed to extract {category}: {e}")
                results.append({
                    "category": category,
                    "knowledge_json": "{}",
                    "summary": f"Extraction failed: {str(e)}",
                    "confidence": 0.0,
                })

        return results

    def _get_sample_paragraphs(self, text: str, max_chars: int = 8000) -> str:
        """Get representative paragraphs for style analysis."""
        paragraphs = [p.strip() for p in text.split("\n") if len(p.strip()) > 50]
        sample = []
        total = 0
        # Take every Nth paragraph to get a spread across the document
        step = max(1, len(paragraphs) // 20)
        for i in range(0, len(paragraphs), step):
            if total + len(paragraphs[i]) > max_chars:
                break
            sample.append(paragraphs[i])
            total += len(paragraphs[i])
        return "\n\n".join(sample)

    def _summarize_knowledge(self, category: str, knowledge: dict) -> str:
        """Generate a human-readable summary of extracted knowledge."""
        if category == "terminology":
            terms = knowledge.get("terms", {})
            phrases = knowledge.get("standard_phrases", [])
            return f"Extracted {len(terms)} terms and {len(phrases)} standard phrases"

        elif category == "procedural_rules":
            rules = knowledge.get("rules", [])
            return f"Identified {len(rules)} procedural rules and conventions"

        elif category == "writing_style":
            voice = knowledge.get("voice", "unknown")
            tense = knowledge.get("tense", "unknown")
            return f"Style: {voice} voice, {tense}"

        elif category == "section_structure":
            sections = knowledge.get("standard_sections", [])
            scheme = knowledge.get("numbering_scheme", "unknown")
            return f"{len(sections)} standard sections, numbering: {scheme}"

        elif category == "formatting":
            body = knowledge.get("body_font") or {}
            page = knowledge.get("page") or {}
            bits = []
            if body.get("name"):
                bits.append(f"body {body['name']} {body.get('size_pt') or ''}pt".strip())
            if page.get("orientation"):
                bits.append(page["orientation"])
            shading = knowledge.get("shading_roles") or {}
            active_shades = [v for v in shading.values() if v]
            if active_shades:
                bits.append(f"shading {', '.join(active_shades[:3])}")
            return " · ".join(bits) or "Formatting spec extracted"

        elif category == "table_templates":
            templates = knowledge.get("templates", [])
            if not templates:
                return "No reusable table templates detected"
            names = [t.get("name", "unnamed") for t in templates[:3]]
            suffix = f" (+{len(templates) - 3} more)" if len(templates) > 3 else ""
            return f"{len(templates)} template(s): {', '.join(names)}{suffix}"

        return "Knowledge extracted"
