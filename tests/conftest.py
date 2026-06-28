"""Shared pytest fixtures for the GMP backend.

Configures an isolated SQLite database and an eager Celery (no broker), stubs
the LLM-calling generator methods so tests never touch Ollama, and gives each
test a fresh database via the `client` fixture.
"""

import os
import tempfile

# Configure the environment BEFORE importing the app (module-level init reads it).
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
_res_fd, _res_path = tempfile.mkstemp(suffix=".db")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["CELERY_RESULT_BACKEND"] = f"db+sqlite:///{_res_path}"
os.environ.pop("CELERY_BROKER_URL", None)          # eager mode (no Redis)
os.environ["AUTH_RATELIMIT"] = "100000 per minute"  # don't trip limits in tests
os.environ["LLM_RATELIMIT"] = "100000 per minute"

import pytest  # noqa: E402

import gmp_server  # noqa: E402
from ml_model.gmp.database import db  # noqa: E402
from ml_model.gmp import generator_provider  # noqa: E402


class FakeGenerator:
    """Stubs only the methods that would otherwise call Ollama."""

    def preview_section(self, doc_type, section_id, context):
        return {"section_id": section_id, "content": f"AI content for {section_id}"}

    def autofill_from_paper(self, pmcid, context):
        return {"paper": {"pmcid": pmcid}, "section_data": {"equipment_list": []}, "notes": "stub"}

    def get_ollama_status(self):
        return {"available": True, "model": "test-llm", "models": ["test-llm"]}


@pytest.fixture(scope="session")
def app():
    gmp_server.app.config.update(TESTING=True)
    gen = generator_provider.get_generator()
    fake = FakeGenerator()
    gen.preview_section = fake.preview_section
    gen.autofill_from_paper = fake.autofill_from_paper
    gen.get_ollama_status = fake.get_ollama_status
    return gmp_server.app


@pytest.fixture()
def client(app):
    """A test client backed by a freshly-reset database."""
    with app.app_context():
        db.drop_all()
        db.create_all()
    return app.test_client()
