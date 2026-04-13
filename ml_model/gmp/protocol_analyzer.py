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


FORMATTING_ANALYSIS_PROMPT = """Analyze the formatting patterns in this GMP protocol document.

FORMATTING DATA:
Fonts: {fonts}
Table structures: {tables}
Styles used: {styles}

Return a JSON object with:
{{
  "primary_font": {{
    "name": "Font name",
    "body_size": 11,
    "heading_size": 14
  }},
  "table_patterns": [
    "Description of how tables are structured and used"
  ],
  "style_hierarchy": [
    "How heading styles are used"
  ],
  "observations": [
    "Other formatting patterns worth preserving"
  ]
}}"""


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

        # Run each analysis pass
        analyses = [
            ("terminology", TERMINOLOGY_EXTRACTION_PROMPT, {"text": truncated_text}),
            ("procedural_rules", PROCEDURAL_RULES_PROMPT, {"text": truncated_text, "sections": sections_str}),
            ("writing_style", WRITING_STYLE_PROMPT, {"sample_text": self._get_sample_paragraphs(text)}),
            ("section_structure", SECTION_STRUCTURE_PROMPT, {"sections": sections_str}),
            ("formatting", FORMATTING_ANALYSIS_PROMPT, {
                "fonts": json.dumps(formatting.get("fonts", [])[:10]),
                "tables": json.dumps(formatting.get("tables", [])[:10]),
                "styles": json.dumps(formatting.get("styles", [])[:10]),
            }),
        ]

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
            font = knowledge.get("primary_font", {})
            return f"Primary font: {font.get('name', 'unknown')} {font.get('body_size', '')}pt"

        return "Knowledge extracted"
