"""Heuristic document-type classification for uploaded protocols.

Given a filename (and optionally the first N characters of the extracted text),
guess which template ID best matches the document. Template IDs line up with
the files in ``ml_model/gmp/templates/*.json``.

The matching is intentionally keyword-based and fast — no LLM call. It runs on
every upload to pre-populate the ``doc_type`` field; users can override in the
UI.
"""

from __future__ import annotations

import re
from typing import Optional


# Template ID → list of keyword patterns (lower-case, matched with word-boundary).
# Order matters for ties: first match wins, so put more-specific patterns first.
_TEMPLATE_RULES: list[tuple[str, list[str]]] = [
    # CMC modules — must come before generic "drug product / drug substance"
    ("cmc_drug_product", [r"cmc.*drug\s*product", r"3\.2\.p", r"module\s*3\.2\.p"]),
    ("cmc_drug_substance", [r"cmc.*drug\s*substance", r"3\.2\.s", r"module\s*3\.2\.s"]),

    # IND
    ("form_1571", [r"form\s*1571", r"ind\s*application", r"ind\s*form"]),

    # Clinical documents
    ("clinical_protocol", [r"clinical\s*(trial|study)\s*protocol", r"phase\s*[123i]+\s*protocol", r"study\s*protocol"]),
    ("crf_template", [r"\bcrf\b", r"case\s*report\s*form"]),
    ("informed_consent", [r"informed\s*consent", r"\bicf\b", r"consent\s*form"]),
    ("investigator_brochure", [r"investigator.*brochure", r"\bib\b"]),

    # Quality systems
    ("quality_agreement", [r"quality\s*agreement", r"contract\s*manufactur"]),
    ("quality_risk_assessment", [r"risk\s*assessment", r"\bich\s*q9\b", r"qra\b"]),
    ("tech_transfer", [r"tech(nology)?\s*transfer"]),

    # Validation
    ("cleaning_validation", [r"cleaning\s*validation"]),
    ("method_validation", [r"method\s*validation", r"analytical\s*method", r"\bamv\b"]),
    ("process_validation", [r"process\s*performance\s*qualification", r"\bppq\b", r"process\s*validation"]),
    ("stability_protocol", [r"stability\s*(protocol|study|program)"]),
    ("validation_protocol", [r"\biq\s*/?\s*oq\s*/?\s*pq\b", r"iq[\s/]oq[\s/]pq", r"validation\s*protocol"]),

    # Manufacturing / GMP
    ("annual_product_review", [r"annual\s*product\s*review", r"\bapr\b", r"apqr\b"]),
    ("batch_record", [r"batch\s*record", r"\bmbr\b", r"\bebr\b", r"batch\s*manufacturing"]),
    ("change_control_form", [r"change\s*control", r"\bccr\b", r"change\s*request"]),
    ("deviation_form", [r"deviation", r"nonconformance", r"non-conformance", r"\bncr\b"]),
    ("equipment_qualification", [r"equipment\s*qualification", r"\beq\b", r"installation\s*qualification", r"operational\s*qualification"]),
    ("investigation_report", [r"investigation\s*report", r"root\s*cause", r"rca\b"]),
    ("sop", [r"\bsop\b", r"standard\s*operating\s*procedure"]),
]


def _normalize(s: str) -> str:
    """Lower-case and collapse `_`, `-` and repeated whitespace to single spaces.

    Makes ``Fred_Hutch_Batch-Record.docx`` behave the same as
    ``fred hutch batch record docx`` so word-boundary patterns work.
    """
    if not s:
        return ""
    return re.sub(r"[\s_\-]+", " ", s.lower())


def infer_doc_type(filename: str, text_sample: Optional[str] = None) -> tuple[str, float]:
    """Return ``(template_id, confidence)`` for the given filename + optional text.

    The confidence is a coarse 0.0–1.0 value reflecting how strong the signal was:
      * filename match alone → 0.6
      * text-sample match alone → 0.4
      * filename + text match → 0.9
      * no match → ("", 0.0)
    """
    haystack_name = _normalize(filename)
    haystack_text = _normalize(text_sample[:4000]) if text_sample else ""

    for template_id, patterns in _TEMPLATE_RULES:
        name_hit = any(re.search(p, haystack_name) for p in patterns)
        text_hit = bool(haystack_text) and any(re.search(p, haystack_text) for p in patterns)
        if name_hit and text_hit:
            return template_id, 0.9
        if name_hit:
            return template_id, 0.6
        if text_hit:
            return template_id, 0.4

    return "", 0.0
