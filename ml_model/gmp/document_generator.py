"""GMP Document Generation Orchestrator.

Coordinates template loading, LLM content generation, and Word document
production to create complete GMP-compliant documents.
"""

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from .template_schema import DocumentTemplate, SectionType
from .template_loader import TemplateLoader
from .word_engine import GMPWordEngine
from .ollama_service import OllamaService

logger = logging.getLogger(__name__)

GENERATED_DOCS_DIR = Path(__file__).parent.parent.parent / "generated_docs"


class GMPDocumentGenerator:
    """Orchestrates GMP document generation from user input + LLM assistance."""

    def __init__(self, ollama_url: str = "http://localhost:11434",
                 ollama_model: str = "llama3",
                 templates_dir: Optional[str] = None):
        self.template_loader = TemplateLoader(templates_dir)
        self.word_engine = GMPWordEngine()
        self.ollama = OllamaService(base_url=ollama_url, model=ollama_model)
        self.generated_docs_dir = GENERATED_DOCS_DIR
        self.generated_docs_dir.mkdir(parents=True, exist_ok=True)

    def generate_document(self, doc_type: str, user_input: dict) -> dict:
        """Generate a complete GMP document.

        Args:
            doc_type: Template ID (e.g. 'batch_record', 'sop')
            user_input: Dict with user-provided data:
                - title: Document title
                - product_name: Product being manufactured
                - process_type: Type of process
                - description: Process description
                - doc_number: Optional document number
                - sections: Optional dict of pre-filled section data

        Returns:
            Dict with:
                - doc_id: Unique document identifier
                - file_path: Path to generated DOCX
                - filename: Just the filename
                - download_url: URL path for download
                - preview_sections: List of section summaries
                - content_data: The full structured data used
        """
        # Load template
        template = self.template_loader.load_template(doc_type)

        # Generate document metadata
        doc_id = str(uuid.uuid4())[:8].upper()
        doc_number = user_input.get("doc_number", f"BR-{doc_id}")
        timestamp = datetime.now()

        # Build base data
        data = {
            "doc_id": doc_id,
            "doc_number": doc_number,
            "doc_title": user_input.get("title", template.name),
            "effective_date": timestamp.strftime("%d%b%Y").upper(),
            "revision": user_input.get("revision", "01"),
            "product_name": user_input.get("product_name", ""),
            "process_type": user_input.get("process_type", ""),
        }

        # Context for LLM prompts
        llm_context = {
            "product_name": user_input.get("product_name", "Cell Product"),
            "process_type": user_input.get("process_type", "Cell Processing"),
            "description": user_input.get("description", ""),
            "doc_type": doc_type,
        }

        # Pre-filled section data from user
        user_sections = user_input.get("sections", {})

        # Generate content for each section
        preview_sections = []
        for section_def in template.sections:
            section_id = section_def.id
            section_data = user_sections.get(section_id, {})

            # If section has an LLM prompt and user hasn't pre-filled it
            if section_def.llm_prompt and not section_data:
                section_data = self._generate_section_with_llm(
                    section_def, llm_context
                )

            # Use default data from template if nothing else
            if not section_data and section_def.default_data:
                section_data = section_def.default_data

            data[section_id] = section_data
            preview_sections.append({
                "id": section_id,
                "title": section_def.title,
                "type": section_def.type.value,
                "has_content": bool(section_data),
            })

        # Generate DOCX
        docx_bytes = self.word_engine.generate(template, data)

        # Save to disk
        safe_title = "".join(
            c if c.isalnum() or c in "-_ " else ""
            for c in user_input.get("title", "document")
        ).strip().replace(" ", "_")
        filename = f"{safe_title}_{timestamp.strftime('%Y%m%d_%H%M%S')}.docx"
        file_path = self.generated_docs_dir / filename

        with open(file_path, "wb") as f:
            f.write(docx_bytes)

        logger.info(f"Generated GMP document: {filename} ({doc_type})")

        return {
            "doc_id": doc_id,
            "file_path": str(file_path),
            "filename": filename,
            "download_url": f"/api/download/{filename}",
            "preview_sections": preview_sections,
            "content_data": data,
        }

    def preview_section(self, doc_type: str, section_id: str,
                        context: dict) -> dict:
        """Generate a preview for a single section using the LLM.

        Args:
            doc_type: Template ID
            section_id: Section to preview
            context: LLM context dict

        Returns:
            Dict with generated section data
        """
        template = self.template_loader.load_template(doc_type)
        section_def = next(
            (s for s in template.sections if s.id == section_id), None
        )
        if not section_def:
            raise ValueError(f"Section '{section_id}' not found in template '{doc_type}'")

        return self._generate_section_with_llm(section_def, context)

    def _generate_section_with_llm(self, section_def, context: dict) -> dict:
        """Generate section content using the LLM.

        Maps section types to appropriate prompt types and parses the response.
        """
        # Check if Ollama is available
        if not self.ollama.check_health():
            logger.warning("Ollama not available, returning empty section data")
            return {}

        section_type_to_prompt = {
            SectionType.STEP_PROCEDURE: "procedure_steps",
            SectionType.EQUIPMENT_LIST: "equipment_list",
            SectionType.MATERIALS_LIST: "equipment_list",
            SectionType.REFERENCES: "references",
            SectionType.ATTACHMENTS: "attachments",
            SectionType.GENERAL_INSTRUCTIONS: "general_instructions",
            SectionType.CHECKLIST: "review_checklist",
            SectionType.REVIEW: "review_checklist",
            SectionType.FLOWCHART: "flowchart",
        }

        prompt_type = section_type_to_prompt.get(section_def.type)
        if not prompt_type:
            # Use custom LLM prompt from template if available
            if section_def.llm_prompt:
                try:
                    raw = self.ollama.generate(
                        section_def.llm_prompt.format(**context),
                        temperature=0.3,
                    )
                    return {"text": raw}
                except Exception as e:
                    logger.error(f"LLM generation failed for {section_def.id}: {e}")
                    return {}
            return {}

        try:
            raw = self.ollama.generate_section_content(prompt_type, context)
            # Try to parse as JSON for structured sections
            try:
                parsed = json.loads(raw)
                return parsed
            except json.JSONDecodeError:
                # Return as text if not JSON
                return {"text": raw}
        except Exception as e:
            logger.error(f"LLM generation failed for {section_def.id}: {e}")
            return {}

    def get_ollama_status(self) -> dict:
        """Check Ollama service status and available models."""
        healthy = self.ollama.check_health()
        models = self.ollama.list_models() if healthy else []
        return {
            "available": healthy,
            "model": self.ollama.model,
            "models": [m.get("name", "") for m in models],
        }

    def list_templates(self) -> list[dict]:
        """List all available document templates."""
        return self.template_loader.list_templates()

    def get_template_schema(self, template_id: str) -> dict:
        """Get the full template schema for form building."""
        template = self.template_loader.load_template(template_id)
        return template.model_dump()
