"""Per-section output validators for LLM-generated content.

When the document generator asks Ollama/OpenAI/Anthropic to produce a
section, it gets back free-form JSON that must match an expected shape
before the Word engine can render it. These validators:

  1. Check the shape (type + required keys + per-element structure).
  2. Return a specific, human-readable ``error`` string when invalid.
  3. Keep the prompt writer honest — the format the validator enforces
     is the contract the prompt must teach.

The orchestrator in ``document_generator._generate_section_with_llm``
uses these to decide whether to accept the first response or retry once
with a correction prompt carrying the error back to the model.

Each validator returns ``(is_valid: bool, error: str)``.
"""

from __future__ import annotations

from typing import Any, Callable


ValidatorResult = tuple[bool, str]
Validator = Callable[[Any], ValidatorResult]


# ── Helpers ────────────────────────────────────────────────────────

def _is_non_empty_list(v: Any, min_len: int = 1) -> bool:
    return isinstance(v, list) and len(v) >= min_len


def _is_non_empty_str(v: Any) -> bool:
    return isinstance(v, str) and v.strip() != ""


def _is_list_of_strings(v: Any, min_len: int = 1) -> bool:
    return (
        isinstance(v, list)
        and len(v) >= min_len
        and all(isinstance(x, str) and x.strip() for x in v)
    )


# ── Section-type validators ────────────────────────────────────────

def _validate_procedure_steps(data: Any) -> ValidatorResult:
    """Shape enforced by PROCEDURE_STEPS_PROMPT.

    ``{"steps": [{"number": str, "title": str, "instructions": [...]}, ...]}``
    """
    if not isinstance(data, dict):
        return False, "response must be a JSON object"
    steps = data.get("steps")
    if not _is_non_empty_list(steps):
        return False, "missing or empty 'steps' array — must contain at least 1 step"
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            return False, f"steps[{i}] must be an object"
        if not _is_non_empty_str(step.get("number")):
            return False, f"steps[{i}].number must be a non-empty string (e.g. '5.1')"
        if not _is_non_empty_str(step.get("title")):
            return False, f"steps[{i}].title must be a non-empty string"
        instructions = step.get("instructions")
        if not _is_non_empty_list(instructions):
            return False, f"steps[{i}].instructions must be a non-empty array"
        for j, instr in enumerate(instructions):
            if not isinstance(instr, dict):
                return False, f"steps[{i}].instructions[{j}] must be an object"
            if not _is_non_empty_str(instr.get("text")):
                return False, (
                    f"steps[{i}].instructions[{j}].text must be a non-empty string"
                )
    return True, ""


def _validate_equipment_list(data: Any) -> ValidatorResult:
    """``{"equipment": [{"description": str, ...}, ...], "materials": [...]}``

    At least one of ``equipment`` or ``materials`` must be non-empty.
    """
    if not isinstance(data, dict):
        return False, "response must be a JSON object"
    equipment = data.get("equipment") or []
    materials = data.get("materials") or []
    if not isinstance(equipment, list):
        return False, "'equipment' must be an array"
    if not isinstance(materials, list):
        return False, "'materials' must be an array"
    if not equipment and not materials:
        return False, "at least one of 'equipment' or 'materials' must contain items"
    for i, e in enumerate(equipment):
        if not isinstance(e, dict) or not _is_non_empty_str(e.get("description")):
            return False, f"equipment[{i}].description must be a non-empty string"
    for i, m in enumerate(materials):
        if not isinstance(m, dict) or not _is_non_empty_str(m.get("description")):
            return False, f"materials[{i}].description must be a non-empty string"
    return True, ""


def _validate_references(data: Any) -> ValidatorResult:
    """``{"references": [{"doc_number": str, "title": str}, ...]}``"""
    if not isinstance(data, dict):
        return False, "response must be a JSON object"
    refs = data.get("references")
    if not _is_non_empty_list(refs):
        return False, "missing or empty 'references' array"
    for i, r in enumerate(refs):
        if not isinstance(r, dict):
            return False, f"references[{i}] must be an object"
        if not _is_non_empty_str(r.get("doc_number")):
            return False, f"references[{i}].doc_number must be a non-empty string"
        if not _is_non_empty_str(r.get("title")):
            return False, f"references[{i}].title must be a non-empty string"
    return True, ""


def _validate_attachments(data: Any) -> ValidatorResult:
    """``{"attachments": [{"doc_number": str, "title": str, "quantity": int}]}``"""
    if not isinstance(data, dict):
        return False, "response must be a JSON object"
    atts = data.get("attachments")
    if not _is_non_empty_list(atts):
        return False, "missing or empty 'attachments' array"
    for i, a in enumerate(atts):
        if not isinstance(a, dict):
            return False, f"attachments[{i}] must be an object"
        if not _is_non_empty_str(a.get("title")):
            return False, f"attachments[{i}].title must be a non-empty string"
    return True, ""


def _validate_general_instructions(data: Any) -> ValidatorResult:
    """``{"instructions": [str, str, ...]}``  min 3 items."""
    if not isinstance(data, dict):
        return False, "response must be a JSON object"
    if not _is_list_of_strings(data.get("instructions"), min_len=3):
        return False, "'instructions' must be an array of at least 3 non-empty strings"
    return True, ""


def _validate_review_checklist(data: Any) -> ValidatorResult:
    """``{"checklist_items": [str, ...]}`` min 4 items."""
    if not isinstance(data, dict):
        return False, "response must be a JSON object"
    if not _is_list_of_strings(data.get("checklist_items"), min_len=4):
        return False, (
            "'checklist_items' must be an array of at least 4 non-empty strings"
        )
    return True, ""


def _validate_flowchart(data: Any) -> ValidatorResult:
    """``{"steps": [{"id": str, "label": str, "type": one_of_{start,action,decision,end}, "next": [...]}]}``

    Must have exactly one ``start`` and at least one ``end``. Decision
    nodes need at least 2 outgoing edges.
    """
    if not isinstance(data, dict):
        return False, "response must be a JSON object"
    steps = data.get("steps")
    if not _is_non_empty_list(steps, min_len=2):
        return False, "'steps' must contain at least 2 nodes"
    allowed_types = {"start", "action", "decision", "end"}
    ids: set[str] = set()
    start_count = 0
    end_count = 0
    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            return False, f"steps[{i}] must be an object"
        if not _is_non_empty_str(s.get("id")):
            return False, f"steps[{i}].id must be a non-empty string"
        if s["id"] in ids:
            return False, f"duplicate step id: {s['id']}"
        ids.add(s["id"])
        if not _is_non_empty_str(s.get("label")):
            return False, f"steps[{i}].label must be a non-empty string"
        t = s.get("type")
        if t not in allowed_types:
            return False, (
                f"steps[{i}].type must be one of {sorted(allowed_types)}, got {t!r}"
            )
        if t == "start":
            start_count += 1
        elif t == "end":
            end_count += 1
        nxt = s.get("next")
        if not isinstance(nxt, list):
            return False, f"steps[{i}].next must be an array (use [] for end nodes)"
        if t == "decision" and len(nxt) < 2:
            return False, f"steps[{i}] decision needs at least 2 outgoing edges"
        if t == "end" and len(nxt) != 0:
            return False, f"steps[{i}] end node must have empty 'next'"
    if start_count != 1:
        return False, f"must have exactly one 'start' node, found {start_count}"
    if end_count == 0:
        return False, "must have at least one 'end' node"
    # Validate all targets resolve
    for i, s in enumerate(steps):
        for j, edge in enumerate(s.get("next") or []):
            target = edge.get("target_id") if isinstance(edge, dict) else None
            if not _is_non_empty_str(target) or target not in ids:
                return False, (
                    f"steps[{i}].next[{j}].target_id must reference an existing step id"
                )
    return True, ""


def _validate_deviation_description(data: Any) -> ValidatorResult:
    if not isinstance(data, dict):
        return False, "response must be a JSON object"
    for key in ("description", "impact_assessment"):
        if not _is_non_empty_str(data.get(key)):
            return False, f"'{key}' must be a non-empty string"
    return True, ""


def _validate_capa(data: Any) -> ValidatorResult:
    if not isinstance(data, dict):
        return False, "response must be a JSON object"
    if not _is_non_empty_list(data.get("corrective_actions")):
        return False, "'corrective_actions' must be a non-empty array"
    if not _is_non_empty_list(data.get("preventive_actions")):
        return False, "'preventive_actions' must be a non-empty array"
    return True, ""


def _validate_change_control(data: Any) -> ValidatorResult:
    if not isinstance(data, dict):
        return False, "response must be a JSON object"
    for key in ("change_description", "justification"):
        if not _is_non_empty_str(data.get(key)):
            return False, f"'{key}' must be a non-empty string"
    return True, ""


# ── Registry ───────────────────────────────────────────────────────

SECTION_VALIDATORS: dict[str, Validator] = {
    "procedure_steps": _validate_procedure_steps,
    "equipment_list": _validate_equipment_list,
    "references": _validate_references,
    "attachments": _validate_attachments,
    "general_instructions": _validate_general_instructions,
    "review_checklist": _validate_review_checklist,
    "flowchart": _validate_flowchart,
    "deviation_description": _validate_deviation_description,
    "capa": _validate_capa,
    "change_control": _validate_change_control,
}


def validate_section(section_type: str, data: Any) -> ValidatorResult:
    """Validate ``data`` against the expected shape for ``section_type``.

    Unknown section types pass through silently (``True, ""``) — they
    came from a template we don't have a contract for, so we trust the
    LLM's output rather than blocking.
    """
    validator = SECTION_VALIDATORS.get(section_type)
    if validator is None:
        return True, ""
    try:
        return validator(data)
    except Exception as e:
        return False, f"validator raised: {e}"
