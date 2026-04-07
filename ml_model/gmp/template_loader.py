"""Template loader for GMP document templates."""

import json
import os
import logging
from pathlib import Path
from typing import Optional

from .template_schema import DocumentTemplate, DocumentType

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


class TemplateLoader:
    """Loads and validates GMP document templates from JSON files."""

    def __init__(self, templates_dir: Optional[str] = None):
        self.templates_dir = Path(templates_dir) if templates_dir else TEMPLATES_DIR
        self._cache: dict[str, DocumentTemplate] = {}

    def load_template(self, template_id: str) -> DocumentTemplate:
        """Load a template by ID from the templates directory.

        Args:
            template_id: Template filename without extension (e.g. 'batch_record')

        Returns:
            Validated DocumentTemplate instance
        """
        if template_id in self._cache:
            return self._cache[template_id]

        filepath = self.templates_dir / f"{template_id}.json"
        if not filepath.exists():
            raise FileNotFoundError(
                f"Template not found: {filepath}. "
                f"Available: {self.list_templates()}"
            )

        with open(filepath, "r") as f:
            raw = json.load(f)

        template = DocumentTemplate(**raw)
        self._cache[template_id] = template
        logger.info(f"Loaded template: {template.name} ({template.id})")
        return template

    def list_templates(self) -> list[dict]:
        """List all available templates.

        Returns:
            List of dicts with id, name, doc_type for each template
        """
        templates = []
        if not self.templates_dir.exists():
            return templates

        for filepath in sorted(self.templates_dir.glob("*.json")):
            try:
                with open(filepath, "r") as f:
                    raw = json.load(f)
                templates.append({
                    "id": raw.get("id", filepath.stem),
                    "name": raw.get("name", filepath.stem),
                    "doc_type": raw.get("doc_type", "unknown"),
                })
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Skipping invalid template {filepath}: {e}")

        return templates

    def get_templates_by_type(self, doc_type: DocumentType) -> list[DocumentTemplate]:
        """Load all templates of a given document type."""
        results = []
        for info in self.list_templates():
            if info["doc_type"] == doc_type.value:
                try:
                    results.append(self.load_template(info["id"]))
                except Exception as e:
                    logger.warning(f"Failed to load template {info['id']}: {e}")
        return results

    def reload(self):
        """Clear the template cache and force reload."""
        self._cache.clear()
