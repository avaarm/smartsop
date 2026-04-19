"""Consolidate per-upload protocol knowledge into a single consensus style.

The ProtocolAnalyzer stores one knowledge record per (upload × category).
When a user has uploaded five batch records, the database holds five
``formatting`` records, five ``terminology`` records, etc. — each with
slightly different values.

This module produces a single ``AccountStyle`` dict that the document
generator can feed into the LLM context and the Word engine, so the
output matches the **consensus** of the user's uploaded documents
rather than any one of them individually.

Two entry points:

  * ``consolidate_style(protocol_knowledge)`` — merges knowledge across
    all uploads (account-wide defaults).
  * ``consolidate_style_for_doc_type(uploads, doc_type)`` — same but
    filters to uploads whose ``doc_type`` matches. Preferred when we
    know what we're generating (e.g. only consolidate batch records
    when generating a batch record).

The consolidation strategy per field:

  * Single scalars (orientation, body_font.size_pt, shading hex):
    **majority vote** (most-common value across uploads).
  * Lists of dicts (heading_fonts, table_templates):
    **dedupe by name / level** and keep every unique entry.
  * Numeric tuples (margins, col_widths):
    **median** — robust against one outlier document.
  * Term dictionaries:
    **union**, with later uploads overwriting earlier values only on
    explicit conflict.
"""

from __future__ import annotations

import json
import logging
import statistics
from collections import Counter
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)


# ── Public API ─────────────────────────────────────────────────────

def consolidate_style(
    protocol_knowledge: dict,
    *,
    account_terms: Optional[dict] = None,
    account_style_notes: Optional[str] = None,
) -> dict:
    """Merge the ``protocol_knowledge`` dict (category → list of JSON dicts)
    from ``DataCollector.get_account_context`` into a single style spec.

    ``account_terms`` and ``account_style_notes`` are the user-declared
    values on the ``Account`` itself — always take precedence over any
    learned values when set.

    Returns a dict with keys:
        {
          "page": {"orientation", "size_inches", "margins_inches"},
          "body_font": {"name", "size_pt", "line_spacing", "space_after_pt"},
          "heading_fonts": [{"level", "name", "size_pt", "bold", ...}],
          "shading_roles": {"section_header", "label_cell", "alternating_rows"},
          "table_templates": [...],
          "terminology": {...},
          "procedural_rules": [...],
          "writing_style": {"voice", "tense", "person"},
          "sample_size": N,   # how many uploads contributed
        }
    """
    if not isinstance(protocol_knowledge, dict):
        protocol_knowledge = {}

    formatting_items = protocol_knowledge.get("formatting", []) or []
    tables_items = protocol_knowledge.get("table_templates", []) or []
    terminology_items = protocol_knowledge.get("terminology", []) or []
    rules_items = protocol_knowledge.get("procedural_rules", []) or []
    style_items = protocol_knowledge.get("writing_style", []) or []

    # Count unique "documents" as the max cardinality across categories — a
    # rough proxy for "how many uploads contributed" since one upload
    # typically produces one record per category.
    sample_size = max(
        len(formatting_items),
        len(tables_items),
        len(terminology_items),
        len(rules_items),
        len(style_items),
        1,
    )

    page = _merge_page([f.get("page") for f in formatting_items if isinstance(f, dict)])
    body_font = _merge_body_font(
        [f.get("body_font") for f in formatting_items if isinstance(f, dict)]
    )
    heading_fonts = _merge_heading_fonts(
        [f.get("heading_fonts", []) for f in formatting_items if isinstance(f, dict)]
    )
    shading_roles = _merge_shading_roles(
        [f.get("shading_roles") for f in formatting_items if isinstance(f, dict)]
    )
    table_templates = _merge_table_templates(tables_items)
    terminology = _merge_terminology(terminology_items, account_terms)
    procedural_rules = _merge_list_of_strings(
        [r.get("rules", []) for r in rules_items if isinstance(r, dict)]
    )
    writing_style = _merge_writing_style(style_items)

    return {
        "page": page,
        "body_font": body_font,
        "heading_fonts": heading_fonts,
        "shading_roles": shading_roles,
        "table_templates": table_templates,
        "terminology": terminology,
        "procedural_rules": procedural_rules,
        "writing_style": writing_style,
        "style_notes": account_style_notes or "",
        "sample_size": sample_size,
    }


def consolidate_style_for_doc_type(
    uploads: Iterable[dict],
    doc_type: str,
    *,
    account_terms: Optional[dict] = None,
    account_style_notes: Optional[str] = None,
) -> dict:
    """Like ``consolidate_style`` but builds the knowledge dict by reading
    active knowledge off each upload, filtered to uploads of ``doc_type``.

    ``uploads`` is expected to yield ``ProtocolUpload.to_dict()`` shaped
    records with a ``knowledge`` list on each.
    """
    filtered: list[dict] = [u for u in uploads if u.get("doc_type") == doc_type]
    if not filtered and doc_type:
        # Fall back to all uploads — better to apply any learned style than
        # none when the user has no exact-match uploads yet.
        filtered = list(uploads)

    by_category: dict[str, list] = {}
    for u in filtered:
        for k in u.get("knowledge", []) or []:
            if not k.get("is_active", True):
                continue
            cat = k.get("category")
            if not cat:
                continue
            try:
                payload = json.loads(k.get("knowledge_json") or "{}")
            except (TypeError, ValueError):
                continue
            by_category.setdefault(cat, []).append(payload)

    return consolidate_style(
        by_category,
        account_terms=account_terms,
        account_style_notes=account_style_notes,
    )


# ── Field-level mergers ────────────────────────────────────────────

def _merge_page(pages: list[Optional[dict]]) -> dict:
    pages = [p for p in pages if isinstance(p, dict)]
    if not pages:
        return {}

    orientation = _majority([p.get("orientation") for p in pages])
    size_inches = _median_tuple([p.get("size_inches") for p in pages])
    margins = _median_margins([p.get("margins_inches") for p in pages])

    out: dict = {}
    if orientation:
        out["orientation"] = orientation
    if size_inches:
        out["size_inches"] = size_inches
    if margins:
        out["margins_inches"] = margins
    return out


def _merge_body_font(fonts: list[Optional[dict]]) -> dict:
    fonts = [f for f in fonts if isinstance(f, dict)]
    if not fonts:
        return {}
    return {
        "name": _majority([f.get("name") for f in fonts]),
        "size_pt": _median_numeric([f.get("size_pt") for f in fonts]),
        "line_spacing": _median_numeric([f.get("line_spacing") for f in fonts]),
        "space_after_pt": _median_numeric([f.get("space_after_pt") for f in fonts]),
    }


def _merge_heading_fonts(groups: list[list]) -> list[dict]:
    """Merge per-level heading-font specs across documents.

    Keys by ``level`` (1 / 2 / 3 …). Within a level, takes the majority
    font name and bold flag, and the median size_pt.
    """
    by_level: dict[int, list[dict]] = {}
    for g in groups:
        if not isinstance(g, list):
            continue
        for item in g:
            if not isinstance(item, dict):
                continue
            lvl = item.get("level")
            if lvl is None:
                continue
            by_level.setdefault(lvl, []).append(item)

    merged = []
    for lvl, items in sorted(by_level.items(), key=lambda kv: (kv[0] or 0)):
        merged.append({
            "level": lvl,
            "name": _majority([i.get("name") for i in items]),
            "size_pt": _median_numeric([i.get("size_pt") for i in items]),
            "bold": _majority_bool([i.get("bold") for i in items]),
            "space_before_pt": _median_numeric([i.get("space_before_pt") for i in items]),
            "space_after_pt": _median_numeric([i.get("space_after_pt") for i in items]),
        })
    return merged


def _merge_shading_roles(items: list[Optional[dict]]) -> dict:
    items = [i for i in items if isinstance(i, dict)]
    if not items:
        return {}
    roles = ("section_header", "label_cell", "alternating_rows")
    out = {}
    for role in roles:
        out[role] = _majority([i.get(role) for i in items], ignore_empty=True)
    return out


def _merge_table_templates(table_items: list[dict]) -> list[dict]:
    """Dedupe by case-insensitive template ``name``. Median col widths."""
    by_name: dict[str, list[dict]] = {}
    for t in table_items:
        if not isinstance(t, dict):
            continue
        for tpl in t.get("templates", []) or []:
            if not isinstance(tpl, dict):
                continue
            key = (tpl.get("name") or "").strip().lower()
            if not key:
                continue
            by_name.setdefault(key, []).append(tpl)

    out = []
    for key, tpls in by_name.items():
        # Keep the first occurrence as the "canonical" record, then
        # overwrite the numeric columns with the median across all copies.
        base = dict(tpls[0])
        base["col_widths_dxa"] = _median_tuple(
            [t.get("col_widths_dxa") for t in tpls]
        ) or base.get("col_widths_dxa", [])
        base["rows"] = _majority_int([t.get("rows") for t in tpls]) or base.get("rows")
        base["cols"] = _majority_int([t.get("cols") for t in tpls]) or base.get("cols")
        base["header_shading_hex"] = _majority(
            [t.get("header_shading_hex") for t in tpls], ignore_empty=True
        )
        base["occurrence_count"] = len(tpls)
        out.append(base)
    return out


def _merge_terminology(
    term_items: list[dict],
    account_terms: Optional[dict] = None,
) -> dict:
    """Union of all term dictionaries; account_terms wins on conflict."""
    merged: dict[str, str] = {}
    for t in term_items:
        if not isinstance(t, dict):
            continue
        extracted = t.get("terms") or {}
        if isinstance(extracted, dict):
            for k, v in extracted.items():
                if v:
                    merged.setdefault(str(k).strip(), str(v).strip())
    # Account-level terms are authoritative — overwrite even if a conflicting
    # value was learned from a protocol.
    if isinstance(account_terms, dict):
        for k, v in account_terms.items():
            if v:
                merged[str(k).strip()] = str(v).strip()
    return merged


def _merge_list_of_strings(lists: list) -> list[str]:
    """Flatten + dedupe string lists, preserving first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for lst in lists:
        if not isinstance(lst, list):
            continue
        for s in lst:
            if not isinstance(s, str):
                continue
            key = s.strip()
            if not key or key.lower() in seen:
                continue
            seen.add(key.lower())
            out.append(key)
    return out


def _merge_writing_style(style_items: list[dict]) -> dict:
    out = {}
    for key in ("voice", "tense", "person"):
        out[key] = _majority(
            [s.get(key) for s in style_items if isinstance(s, dict)],
            ignore_empty=True,
        )
    return out


# ── Primitive mergers ──────────────────────────────────────────────

def _majority(values: Iterable[Any], *, ignore_empty: bool = True) -> Any:
    """Return the most-common non-null value, or None."""
    counter = Counter()
    for v in values:
        if v is None:
            continue
        if ignore_empty and v == "":
            continue
        # Make dicts/lists hashable by jsonifying
        key = v if isinstance(v, (str, int, float, bool)) else json.dumps(v, sort_keys=True)
        counter[key] += 1
    if not counter:
        return None
    top = counter.most_common(1)[0][0]
    # Unwrap JSON if we wrapped earlier
    if isinstance(top, str) and top.startswith(("{", "[")):
        try:
            return json.loads(top)
        except ValueError:
            return top
    return top


def _majority_bool(values: Iterable[Any]) -> Optional[bool]:
    trues = 0
    falses = 0
    for v in values:
        if v is True:
            trues += 1
        elif v is False:
            falses += 1
    if trues == 0 and falses == 0:
        return None
    return trues >= falses


def _majority_int(values: Iterable[Any]) -> Optional[int]:
    ints = [int(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not ints:
        return None
    return int(statistics.median(ints))


def _median_numeric(values: Iterable[Any]) -> Optional[float]:
    nums = [float(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not nums:
        return None
    m = statistics.median(nums)
    # Keep ints as ints for cleaner payload
    return int(m) if m == int(m) else round(m, 2)


def _median_tuple(tuples: Iterable[Any]) -> Optional[list]:
    """Element-wise median across same-length lists."""
    lists = [t for t in tuples if isinstance(t, (list, tuple)) and t]
    if not lists:
        return None
    # Take the most-common length; tuples of other lengths are ignored.
    length_counter = Counter(len(t) for t in lists)
    target_len, _ = length_counter.most_common(1)[0]
    aligned = [t for t in lists if len(t) == target_len]
    if not aligned:
        return None
    out = []
    for i in range(target_len):
        col = [t[i] for t in aligned if isinstance(t[i], (int, float))]
        if not col:
            out.append(None)
            continue
        m = statistics.median(col)
        out.append(int(m) if m == int(m) else round(m, 2))
    return out


def _median_margins(margins: Iterable[Any]) -> Optional[dict]:
    """Median-merge ``{"top":x, "right":x, "bottom":x, "left":x}`` dicts."""
    mg = [m for m in margins if isinstance(m, dict)]
    if not mg:
        return None
    out = {}
    for side in ("top", "right", "bottom", "left"):
        vals = [m.get(side) for m in mg if isinstance(m.get(side), (int, float))]
        if not vals:
            continue
        m = statistics.median(vals)
        out[side] = int(m) if m == int(m) else round(m, 2)
    return out or None
