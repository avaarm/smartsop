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


FORMATTING_ANALYSIS_PROMPT = """You are assembling a **machine-readable formatting spec** for a GMP
protocol so a generator can reproduce its exact look. Every numeric
value has already been measured — your job is to assemble them, NOT
to estimate.

DETERMINISTIC DATA (authoritative — copy values verbatim):
Page setup: {page}
Theme fonts (resolves +mj-lt / +mn-lt): {theme_fonts}
Per-role fonts (paragraph-style → dominant run font): {font_roles}
Per-role paragraph rhythm (spacing, indent, line-height, alignment): {paragraph_rhythm}
Numbering definitions (bullets, decimal, lowerLetter, etc): {numbering}
Global font histogram (top 10): {fonts}
Shading palette (cell background colors): {shading_palette}
Page header text (default/first_page/even_page): {headers}
Page footer text (default/first_page/even_page): {footers}
Paragraph styles by frequency: {styles}
Table summaries: {tables}

EXAMPLE of a good output (do NOT copy these numbers — yours must
come from DETERMINISTIC DATA):
{{
  "page": {{"orientation": "landscape", "size_inches": [11.0, 8.5],
           "margins_inches": {{"top": 0.75, "right": 0.5, "bottom": 0.5, "left": 0.5}}}},
  "body_font": {{"name": "Calibri", "size_pt": 11, "line_spacing": 1.15,
                 "space_after_pt": 6}},
  "heading_fonts": [
    {{"level": 1, "name": "Calibri", "size_pt": 14, "bold": true,
      "space_before_pt": 12, "space_after_pt": 6}}
  ],
  "header_pattern": "Company logo left, document title center, page N of M right",
  "footer_pattern": "Confidential | Controlled Document | {{date}}",
  "shading_roles": {{"section_header": "BFBFBF", "label_cell": "F2F2F2",
                     "alternating_rows": null}},
  "table_conventions": [
    "Approval blocks are 3-col tables with a BFBFBF header row",
    "Label/value rows use F2F2F2 in column 1 and white in column 2"
  ],
  "list_style": {{"bullets": "round", "numbering": "X.X", "indent_inches": 0.25}},
  "observations": [
    "All tables use a fixed layout (table-layout: fixed) with DXA-specified column widths",
    "Headings never use theme fonts directly — all runs specify Calibri explicitly"
  ]
}}

STRICT RULES:
1. ``page.orientation``, ``size_inches``, ``margins_inches`` must come
   from the Page setup block. Convert DXA → inches by dividing by 1440.
2. ``body_font`` must come from ``paragraph_rhythm["body"]`` +
   ``font_roles["body"]``; fall back to theme_fonts.minor if body
   says "Default".
3. ``heading_fonts`` — produce one entry per ``font_roles`` key that
   starts with "Heading". Use the matching paragraph_rhythm entry
   for space_before/space_after.
4. ``shading_roles.section_header`` is the most-used color in
   shading_palette when paired with bold text; ``label_cell`` is the
   second most-used or lighter variant (e.g. F2F2F2 next to BFBFBF).
5. Shading hex must be 6-char **without** the leading #.
6. Set a field to null when no deterministic evidence exists — never
   guess.
7. Output ONLY the JSON object, no prose before or after."""


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


# Minimum keys each category's JSON output must include. If the LLM returns
# something missing a required key we retry once with a strict correction
# instruction; still-missing keys are logged but not fatal.
_REQUIRED_KEYS: dict[str, set[str]] = {
    "terminology": {"terms"},
    "procedural_rules": {"rules"},
    "writing_style": {"voice"},
    "section_structure": {"numbering_scheme"},
    "formatting": {"body_font", "page"},
    "table_templates": {"templates"},
}

# Passes that must copy deterministic numbers verbatim — run at temp=0.
_DETERMINISTIC_CATEGORIES: set[str] = {"formatting", "table_templates"}


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
        # Everything we pass in has already been measured from the file, so
        # the LLM's job is to assemble it into the target spec, not guess.
        formatting_ctx = {
            "page": json.dumps(formatting.get("page", {})),
            "font_roles": json.dumps(formatting.get("font_roles", {})),
            "fonts": json.dumps(formatting.get("fonts", [])[:10]),
            "shading_palette": json.dumps(formatting.get("shading_palette", [])),
            "headers": json.dumps(formatting.get("headers", {})),
            "footers": json.dumps(formatting.get("footers", {})),
            "styles": json.dumps(formatting.get("styles", [])[:10]),
            "tables": json.dumps(formatting.get("tables", [])[:10]),
            "paragraph_rhythm": json.dumps(formatting.get("paragraph_rhythm", {})),
            "numbering": json.dumps(formatting.get("numbering", {})),
            "theme_fonts": json.dumps(formatting.get("theme_fonts", {})),
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
                knowledge = self._generate_with_retry(category, prompt)

                summary = self._summarize_knowledge(category, knowledge)
                confidence = self._compute_confidence(category, knowledge, formatting)
                results.append({
                    "category": category,
                    "knowledge_json": json.dumps(knowledge),
                    "summary": summary,
                    "confidence": confidence,
                })
                logger.info("Extracted %s (confidence=%.2f)", category, confidence)
            except Exception as e:
                logger.error(f"Failed to extract {category}: {e}")
                results.append({
                    "category": category,
                    "knowledge_json": "{}",
                    "summary": f"Extraction failed: {str(e)}",
                    "confidence": 0.0,
                })

        return results

    def _generate_with_retry(self, category: str, prompt: str) -> dict:
        """Generate JSON, validate against the category's required keys, and
        retry once with a stricter correction if the first attempt is missing
        required fields.

        Deterministic passes (formatting, table_templates) run at
        ``temperature=0.0`` so the LLM copies numeric values verbatim
        instead of paraphrasing or rounding them.
        """
        temp = 0.0 if category in _DETERMINISTIC_CATEGORIES else 0.2
        result = self.ollama.generate_json(prompt, temperature=temp)

        missing = _REQUIRED_KEYS.get(category, set()) - set(result.keys())
        if not missing:
            return result

        logger.info(
            "%s output missing required keys %s — retrying with correction",
            category, sorted(missing),
        )
        correction = (
            prompt
            + "\n\n---\nThe previous attempt was missing the required keys: "
            + ", ".join(sorted(missing))
            + ". Return a JSON object that includes EVERY required key. "
            + "If you have no evidence for a key, set it to null or []."
        )
        try:
            result2 = self.ollama.generate_json(correction, temperature=max(temp, 0.0))
        except Exception as e:
            logger.warning("Retry for %s failed: %s — returning partial result", category, e)
            return result
        # Prefer the retry only if it closed at least one gap
        still_missing = _REQUIRED_KEYS.get(category, set()) - set(result2.keys())
        if len(still_missing) < len(missing):
            return result2
        return result

    def _compute_confidence(self, category: str, knowledge: dict, formatting: dict) -> float:
        """Return a 0–1 confidence score reflecting how much deterministic
        evidence backed the output (vs how much the LLM had to guess).

        For structural passes (formatting, table_templates) we look at how
        much concrete signal was available in the parse (page setup,
        shading palette, detailed tables, etc.). For content passes we
        return a modest baseline of 0.7 since the LLM drives the output.
        """
        if category == "formatting":
            signals = [
                bool(formatting.get("page")),
                bool(formatting.get("font_roles")),
                bool(formatting.get("shading_palette")),
                bool(formatting.get("paragraph_rhythm")),
                bool(formatting.get("theme_fonts")),
                bool(formatting.get("numbering", {}).get("lists")),
            ]
            have = sum(signals)
            # Require at least half of the signals + required keys present
            required_present = _REQUIRED_KEYS.get(category, set()).issubset(knowledge.keys())
            return round(0.5 + 0.08 * have + (0.1 if required_present else 0.0), 2)

        if category == "table_templates":
            templates = knowledge.get("templates", [])
            detailed = formatting.get("tables_detailed", [])
            if not detailed:
                return 0.4  # we asked the LLM but had no real table data
            ratio = min(1.0, len(templates) / max(1, len(detailed)))
            return round(0.6 + 0.3 * ratio, 2)

        if category in ("section_structure", "writing_style", "procedural_rules", "terminology"):
            # LLM-driven — confidence is baseline, plus bonus if key is present.
            required_present = _REQUIRED_KEYS.get(category, set()).issubset(knowledge.keys())
            return 0.75 if required_present else 0.55

        return 0.7

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
