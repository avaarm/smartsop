"""Training data export and fine-tuning preparation utilities.

Exports collected prompt/completion pairs from the database into formats
compatible with common fine-tuning tools (Unsloth, Axolotl, OpenAI, Ollama).
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from .database import db, Account, TrainingExample, Document

logger = logging.getLogger(__name__)

EXPORT_DIR = Path(__file__).parent.parent.parent / "training_exports"


class TrainingExporter:
    """Exports account training data in various fine-tuning formats."""

    def __init__(self):
        self.export_dir = EXPORT_DIR
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_jsonl(self, account_id: int,
                     min_rating: Optional[int] = None,
                     source_filter: Optional[str] = None,
                     max_examples: Optional[int] = None) -> dict:
        """Export as JSONL (one JSON object per line) in Llama 3 chat format.

        This is the standard format for:
        - Unsloth / Axolotl LoRA fine-tuning
        - OpenAI fine-tuning API
        - Ollama Modelfile ADAPTER imports

        Each line:
        {"messages": [{"role":"system","content":"..."},{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}
        """
        query = TrainingExample.query.filter_by(account_id=account_id)
        if min_rating is not None:
            query = query.filter(TrainingExample.quality_rating >= min_rating)
        if source_filter:
            query = query.filter_by(source=source_filter)
        query = query.order_by(TrainingExample.created_at)
        if max_examples:
            query = query.limit(max_examples)

        examples = query.all()
        if not examples:
            return {"success": False, "error": "No training examples found", "count": 0}

        account = Account.query.get(account_id)
        slug = account.slug if account else str(account_id)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{slug}_training_{timestamp}.jsonl"
        filepath = self.export_dir / filename

        with open(filepath, "w") as f:
            for ex in examples:
                row = ex.to_training_format(include_system=True)
                f.write(json.dumps(row) + "\n")

        logger.info(f"Exported {len(examples)} examples to {filepath}")
        return {
            "success": True,
            "filename": filename,
            "filepath": str(filepath),
            "count": len(examples),
            "format": "jsonl",
        }

    def export_ollama_modelfile(self, account_id: int,
                                base_model: str = "llama3") -> dict:
        """Generate an Ollama Modelfile with account-specific system prompt.

        This doesn't fine-tune weights, but creates a custom model with
        the account's terminology, style notes, and reference SOPs baked
        into the system prompt. Fast to create and iterate on.

        Usage: ollama create myorg-gmp -f Modelfile
        """
        account = Account.query.get(account_id)
        if not account:
            return {"success": False, "error": "Account not found"}

        terminology = json.loads(account.terminology_json or "{}")
        reference_sops = json.loads(account.reference_sops_json or "[]")

        # Build the account-specific system prompt
        parts = [
            "You are a GMP documentation specialist for pharmaceutical and biotech manufacturing.",
            f"You work for {account.facility_name or 'a GMP facility'}.",
        ]
        if account.department:
            parts.append(f"Department: {account.department}.")
        if account.style_notes:
            parts.append(f"Style guidelines: {account.style_notes}")
        if terminology:
            term_lines = [f"- {k}: {v}" for k, v in terminology.items()]
            parts.append("Organization-specific terminology:\n" + "\n".join(term_lines))
        if reference_sops:
            sop_lines = [f"- {s}" for s in reference_sops[:20]]
            parts.append("Standard reference SOPs:\n" + "\n".join(sop_lines))

        parts.append(
            "Generate precise, regulatory-compliant content for GMP documents. "
            "Use the organization's terminology and reference SOPs where applicable. "
            "Follow 21 CFR Part 211 and ICH guidelines."
        )

        system_prompt = "\n\n".join(parts)

        # Build Modelfile
        modelfile = f'FROM {base_model}\n\nSYSTEM """\n{system_prompt}\n"""\n\nPARAMETER temperature 0.3\nPARAMETER num_predict 8192\n'

        slug = account.slug
        filename = f"{slug}_Modelfile"
        filepath = self.export_dir / filename

        with open(filepath, "w") as f:
            f.write(modelfile)

        logger.info(f"Generated Ollama Modelfile for account {account_id} at {filepath}")
        return {
            "success": True,
            "filename": filename,
            "filepath": str(filepath),
            "model_name": f"{slug}-gmp",
            "base_model": base_model,
            "instructions": f"Run: ollama create {slug}-gmp -f {filepath}",
        }

    def export_full_dataset(self, account_id: int) -> dict:
        """Export everything: documents + training examples + account config.

        Returns a JSON bundle that can be used to seed another instance
        or for comprehensive analysis.
        """
        account = Account.query.get(account_id)
        if not account:
            return {"success": False, "error": "Account not found"}

        documents = Document.query.filter_by(account_id=account_id).order_by(
            Document.created_at
        ).all()
        examples = TrainingExample.query.filter_by(account_id=account_id).order_by(
            TrainingExample.created_at
        ).all()

        bundle = {
            "exported_at": datetime.utcnow().isoformat(),
            "account": account.to_dict(),
            "documents": [d.to_dict() for d in documents],
            "training_examples": [e.to_dict() for e in examples],
            "stats": {
                "total_documents": len(documents),
                "total_examples": len(examples),
                "by_source": {
                    "ai": sum(1 for e in examples if e.source == "ai"),
                    "user_edited": sum(1 for e in examples if e.source == "user_edited"),
                    "manual": sum(1 for e in examples if e.source == "manual"),
                },
            },
        }

        slug = account.slug
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{slug}_full_export_{timestamp}.json"
        filepath = self.export_dir / filename

        with open(filepath, "w") as f:
            json.dump(bundle, f, indent=2)

        logger.info(f"Full export for account {account_id}: {len(documents)} docs, {len(examples)} examples")
        return {
            "success": True,
            "filename": filename,
            "filepath": str(filepath),
            "stats": bundle["stats"],
        }
