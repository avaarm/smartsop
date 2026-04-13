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
from .paper_scraper import PaperScraper, Paper, PaperMethods
from .data_collector import DataCollector

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
        self.paper_scraper = PaperScraper()
        self.data_collector = DataCollector()
        self.generated_docs_dir = GENERATED_DOCS_DIR
        self.generated_docs_dir.mkdir(parents=True, exist_ok=True)

    # ── Paper Scraping ──

    def search_papers(self, query: str, max_results: int = 10) -> list[dict]:
        """Search PubMed Central for open-access papers."""
        papers = self.paper_scraper.search(query, max_results)
        return [p.to_dict() for p in papers]

    def fetch_paper_methods(self, pmcid: str) -> Optional[dict]:
        """Fetch and return the methods section of a paper."""
        result = self.paper_scraper.fetch_methods(pmcid)
        if result is None:
            return None
        return result.to_dict()

    def extract_gmp_from_paper(self, pmcid: str, context: dict) -> dict:
        """Extract GMP-structured data from a paper's methods section using LLM.

        Args:
            pmcid: PMC ID of the paper
            context: Dict with product_name, process_type

        Returns:
            Structured data with equipment, materials, procedure_steps, references
        """
        methods = self.paper_scraper.fetch_methods(pmcid)
        if methods is None:
            raise ValueError(f"Could not fetch methods for {pmcid}")

        if not self.ollama.check_health():
            raise RuntimeError("Ollama not available for paper extraction")

        from .prompts import PAPER_METHODS_EXTRACTION_PROMPT

        prompt = PAPER_METHODS_EXTRACTION_PROMPT.format(
            paper_title=methods.paper.title,
            paper_journal=methods.paper.journal,
            paper_year=methods.paper.year,
            paper_authors=", ".join(methods.paper.authors[:5]),
            product_name=context.get("product_name", ""),
            process_type=context.get("process_type", ""),
            methods_text=methods.methods_text,
        )

        try:
            structured = self.ollama.generate_json(prompt, temperature=0.2)
        except Exception as e:
            logger.error(f"LLM extraction failed for {pmcid}: {e}")
            raise RuntimeError(f"Failed to extract GMP data: {e}")

        # Return structured data plus paper metadata
        return {
            "paper": methods.paper.to_dict(),
            "extracted": structured,
        }

    def autofill_from_paper(self, pmcid: str, context: dict) -> dict:
        """Extract data from a paper and map it to template section IDs.

        Returns a dict keyed by section_id that can be merged directly into
        the document builder's sectionData state.
        """
        result = self.extract_gmp_from_paper(pmcid, context)
        extracted = result.get("extracted", {})

        # Map extracted fields onto template section IDs
        section_data = {}

        if extracted.get("equipment"):
            section_data["equipment_list"] = {"equipment": extracted["equipment"]}

        if extracted.get("materials"):
            section_data["materials_list"] = {"materials": extracted["materials"]}

        if extracted.get("procedure_steps"):
            # Map procedure steps to Day 0 processing section
            section_data["day0_processing"] = {
                "title": "Day 0 Processing (from literature)",
                "steps": extracted["procedure_steps"],
            }

        if extracted.get("references"):
            # Merge with paper citation
            refs = list(extracted["references"])
            paper = result["paper"]
            refs.append({
                "doc_number": paper.get("doi", paper.get("pmcid", "")),
                "title": f"{paper.get('title', '')} ({paper.get('journal', '')}, {paper.get('year', '')})",
            })
            section_data["references"] = {"references": refs}

        return {
            "paper": result["paper"],
            "section_data": section_data,
            "notes": extracted.get("notes", ""),
        }

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

        # Whether to auto-fill missing sections via LLM (opt-in, off by default)
        # During Generate, we do NOT call LLM implicitly because it takes 10-50s
        # per section and can cause browser timeouts. Users should explicitly
        # click "Fill with AI" on the sections they want, or use the
        # /api/gmp/preview endpoint for parallel pre-generation.
        auto_fill_llm = user_input.get("auto_fill_llm", False)

        # Build content for each section (no LLM calls unless explicitly requested)
        preview_sections = []
        for section_def in template.sections:
            section_id = section_def.id
            section_data = user_sections.get(section_id, {})

            # Optional: auto-fill missing LLM sections (slow, opt-in only)
            if auto_fill_llm and section_def.llm_prompt and not section_data:
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

        result = {
            "doc_id": doc_id,
            "file_path": str(file_path),
            "filename": filename,
            "download_url": f"/api/download/{filename}",
            "preview_sections": preview_sections,
            "content_data": data,
        }

        # Record document in database if account is provided
        account_id = user_input.get("account_id")
        if account_id:
            doc_record = self.data_collector.record_document(
                account_id=account_id,
                doc_type=doc_type,
                user_input=user_input,
                result=result,
            )
            if doc_record:
                result["document_record_id"] = doc_record.id

        return result

    def preview_section(self, doc_type: str, section_id: str,
                        context: dict) -> dict:
        """Generate a preview for a single section using the LLM.

        Args:
            doc_type: Template ID
            section_id: Section to preview
            context: LLM context dict (may include account_id)

        Returns:
            Dict with generated section data
        """
        template = self.template_loader.load_template(doc_type)
        section_def = next(
            (s for s in template.sections if s.id == section_id), None
        )
        if not section_def:
            raise ValueError(f"Section '{section_id}' not found in template '{doc_type}'")

        # Inject account context if account_id is provided
        account_id = context.get("account_id")
        enriched_context = dict(context)
        if account_id:
            acct_ctx = self.data_collector.get_account_context(account_id)
            if acct_ctx.get("facility_name"):
                enriched_context.setdefault("facility_name", acct_ctx["facility_name"])
            if acct_ctx.get("style_notes"):
                enriched_context["_style_notes"] = acct_ctx["style_notes"]
            if acct_ctx.get("reference_sops"):
                enriched_context["_reference_sops"] = acct_ctx["reference_sops"]
            if acct_ctx.get("terminology"):
                enriched_context["_terminology"] = acct_ctx["terminology"]
            if acct_ctx.get("protocol_knowledge"):
                enriched_context["_protocol_knowledge"] = acct_ctx["protocol_knowledge"]

        result = self._generate_section_with_llm(section_def, enriched_context)

        # Capture training data
        if account_id and result:
            prompt = section_def.llm_prompt or section_def.type.value
            self.data_collector.record_section_generation(
                account_id=account_id,
                section_type=section_def.type.value,
                prompt=prompt.format(**{k: v for k, v in enriched_context.items() if not k.startswith("_")}),
                completion=result,
                context=context,
                source="ai",
            )

        return result

    def _generate_section_with_llm(self, section_def, context: dict) -> dict:
        """Generate section content using the LLM.

        Maps section types to appropriate prompt types and parses the response.
        If context contains account-specific keys (_style_notes, _terminology,
        _reference_sops), they are appended to the system prompt so the LLM
        produces account-tailored output.
        """
        # Check if Ollama is available
        if not self.ollama.check_health():
            logger.warning("Ollama not available, returning empty section data")
            return {}

        # Build account-aware system prompt supplement
        system_supplement = self._build_account_supplement(context)
        # Strip private keys before formatting prompt templates
        clean_ctx = {k: v for k, v in context.items() if not k.startswith("_")}

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
                        section_def.llm_prompt.format(**clean_ctx),
                        system_prompt=system_supplement or None,
                        temperature=0.3,
                    )
                    return {"text": raw}
                except Exception as e:
                    logger.error(f"LLM generation failed for {section_def.id}: {e}")
                    return {}
            return {}

        try:
            raw = self.ollama.generate_section_content(
                prompt_type, clean_ctx, custom_prompt=None,
            )
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

    @staticmethod
    def _build_account_supplement(context: dict) -> str:
        """Build an account-specific system prompt supplement from context."""
        parts = []
        if context.get("_style_notes"):
            parts.append(f"Follow these style guidelines: {context['_style_notes']}")
        if context.get("_terminology"):
            terms = context["_terminology"]
            if isinstance(terms, dict) and terms:
                lines = [f"- {k}: {v}" for k, v in terms.items()]
                parts.append("Use this organization-specific terminology:\n" + "\n".join(lines))
        if context.get("_reference_sops"):
            sops = context["_reference_sops"]
            if isinstance(sops, list) and sops:
                lines = [f"- {s}" for s in sops[:15]]
                parts.append("Reference these organization SOPs where applicable:\n" + "\n".join(lines))

        # Inject extracted protocol knowledge
        pk = context.get("_protocol_knowledge", {})
        if pk.get("writing_style"):
            for ws in pk["writing_style"]:
                voice = ws.get("voice", "")
                tense = ws.get("tense", "")
                if voice or tense:
                    parts.append(f"Writing style: use {voice} voice, {tense}.")
                for pattern in ws.get("sentence_patterns", [])[:3]:
                    parts.append(f"Sentence pattern: {pattern}")
        if pk.get("terminology"):
            for t in pk["terminology"]:
                terms = t.get("terms", {})
                if terms:
                    lines = [f"- {k}: {v}" for k, v in list(terms.items())[:20]]
                    parts.append("Extracted terminology:\n" + "\n".join(lines))
        if pk.get("procedural_rules"):
            for pr in pk["procedural_rules"]:
                rules = pr.get("rules", [])
                if rules:
                    lines = [f"- {r}" for r in rules[:10]]
                    parts.append("Follow these procedural conventions:\n" + "\n".join(lines))

        return "\n\n".join(parts)

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
