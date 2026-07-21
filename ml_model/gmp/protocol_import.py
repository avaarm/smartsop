"""Import a protocol from pasted text or an uploaded file.

Two paths, mirroring protocols.io's "Pasting new data" + AI importer:

- Deterministic splitting (numbered / lines / markdown) — no LLM needed.
- AI structuring — when Ollama is reachable, ask the model to turn freeform
  prose into titled steps; falls back to the numbered splitter on any failure.
"""

import io
import re
import logging

logger = logging.getLogger(__name__)

MAX_STEPS = 500

_NUMBERED = re.compile(r"^\s*(?:step\s*)?(\d+)\s*[.):]\s+(.*)", re.IGNORECASE)
_MD_HEADING = re.compile(r"^\s*#{1,6}\s+(.*)")
_BULLET = re.compile(r"^\s*[-*•]\s+(.*)")


def extract_text(filename: str, data: bytes) -> str:
    """Extract plain text from an uploaded .docx / .pdf / .txt / .md file."""
    name = (filename or "").lower()
    if name.endswith(".docx"):
        from docx import Document
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError:
            from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    # .txt, .md, or unknown — decode as text
    return data.decode("utf-8", errors="replace")


def _clean(steps):
    out = []
    for s in steps:
        title = (s.get("title") or "").strip()[:500]
        desc = (s.get("description") or "").strip()
        if title or desc:
            out.append({
                "title": title,
                "description": desc,
                "duration_seconds": s.get("duration_seconds"),
                "warning": (s.get("warning") or "").strip(),
            })
    return out[:MAX_STEPS]


def split_into_steps(text: str, mode: str = "numbered"):
    """Split text into [{title, description}] using a deterministic strategy."""
    lines = (text or "").splitlines()

    if mode == "lines":
        return _clean([{"description": ln.strip()} for ln in lines if ln.strip()])

    if mode == "markdown":
        steps, current = [], None
        for ln in lines:
            heading = _MD_HEADING.match(ln)
            numbered = _NUMBERED.match(ln)
            bullet = _BULLET.match(ln)
            if heading:
                current = {"title": heading.group(1).strip(), "description": ""}
                steps.append(current)
            elif numbered:
                current = {"title": "", "description": numbered.group(2).strip()}
                steps.append(current)
            elif bullet:
                current = {"title": "", "description": bullet.group(1).strip()}
                steps.append(current)
            elif ln.strip() and current is not None:
                current["description"] = (current["description"] + "\n" + ln.strip()).strip()
            elif ln.strip():
                current = {"title": "", "description": ln.strip()}
                steps.append(current)
        return _clean(steps)

    # default: numbered — "1. foo", "2) bar", "Step 3: baz"; continuation lines append.
    steps, current, matched = [], None, False
    for ln in lines:
        m = _NUMBERED.match(ln)
        if m:
            matched = True
            current = {"title": "", "description": m.group(2).strip()}
            steps.append(current)
        elif ln.strip() and current is not None:
            current["description"] = (current["description"] + " " + ln.strip()).strip()
    if not matched:
        # No numbered list found — fall back to one step per line.
        return split_into_steps(text, "lines")
    return _clean(steps)


AI_SYSTEM = (
    "You convert a lab procedure into structured steps. Return ONLY a JSON object "
    '{"steps": [{"title": str, "description": str, "duration_minutes": number|null, '
    '"warning": str}]}. Keep each step atomic and preserve the original order.'
)


def ai_structure(text: str, ollama):
    """Use the LLM to structure text into steps. Returns list or None on failure."""
    try:
        if ollama is None or not ollama.check_health():
            return None
        result = ollama.generate_json(
            prompt=f"Convert this procedure into steps:\n\n{text[:8000]}",
            system_prompt=AI_SYSTEM,
        )
        raw = result.get("steps") if isinstance(result, dict) else result
        if not isinstance(raw, list):
            return None
        steps = []
        for s in raw:
            if not isinstance(s, dict):
                continue
            mins = s.get("duration_minutes")
            steps.append({
                "title": s.get("title", ""),
                "description": s.get("description", ""),
                "duration_seconds": int(mins * 60) if isinstance(mins, (int, float)) and mins else None,
                "warning": s.get("warning", ""),
            })
        return _clean(steps) or None
    except Exception as e:  # noqa: BLE001 — degrade gracefully to deterministic split
        logger.warning("AI structuring failed, falling back to split: %s", e)
        return None
