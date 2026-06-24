"""Process-wide GMPDocumentGenerator singleton.

Shared by the HTTP routes and the Celery tasks so both reuse one generator
(and its loaded templates / Ollama client) instead of constructing their own.
"""

import os

from .document_generator import GMPDocumentGenerator

_generator = None


def get_generator() -> GMPDocumentGenerator:
    global _generator
    if _generator is None:
        ollama_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        _generator = GMPDocumentGenerator(ollama_url=ollama_url)
    return _generator
