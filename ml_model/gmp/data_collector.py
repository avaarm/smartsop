"""Data collection service for capturing LLM generation I/O as training data.

Every section generation (AI fill, paper import, or manual edit) is captured
so that an account can later export its data for fine-tuning.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from .database import db, Account, Document, TrainingExample
from .prompts import GMP_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class DataCollector:
    """Captures document generation data for training and history."""

    # ── Document tracking ──

    def record_document(self, account_id: int, doc_type: str,
                        user_input: dict, result: dict) -> Optional[Document]:
        """Record a generated document in the database."""
        try:
            doc = Document(
                account_id=account_id,
                doc_type=doc_type,
                title=user_input.get("title", ""),
                product_name=user_input.get("product_name", ""),
                process_type=user_input.get("process_type", ""),
                description=user_input.get("description", ""),
                doc_number=user_input.get("doc_number", ""),
                revision=user_input.get("revision", "01"),
                sections_json=json.dumps(user_input.get("sections", {})),
                filename=result.get("filename", ""),
                file_path=result.get("file_path", ""),
            )
            db.session.add(doc)
            db.session.commit()
            logger.info(f"Recorded document {doc.id} for account {account_id}")
            return doc
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to record document: {e}")
            return None

    # ── Training data capture ──

    def record_section_generation(self, account_id: int, section_type: str,
                                  prompt: str, completion: str,
                                  context: dict,
                                  document_id: Optional[int] = None,
                                  source: str = "ai") -> Optional[TrainingExample]:
        """Capture a single section generation as a training example.

        Args:
            account_id: The account this data belongs to
            section_type: e.g. 'step_procedure', 'equipment_list'
            prompt: The full user prompt sent to the LLM
            completion: The LLM's response (or user-edited version)
            context: Dict with product_name, process_type, etc.
            document_id: Optional link to the parent document
            source: 'ai' (raw LLM output), 'user_edited', or 'manual'
        """
        try:
            example = TrainingExample(
                account_id=account_id,
                document_id=document_id,
                section_type=section_type,
                system_prompt=GMP_SYSTEM_PROMPT,
                user_prompt=prompt,
                completion=completion if isinstance(completion, str) else json.dumps(completion),
                source=source,
                product_name=context.get("product_name", ""),
                process_type=context.get("process_type", ""),
            )
            db.session.add(example)
            db.session.commit()
            logger.info(f"Recorded training example {example.id} ({source}) for account {account_id}")
            return example
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to record training example: {e}")
            return None

    def record_user_edit(self, account_id: int, section_type: str,
                         original_prompt: str, edited_content: str,
                         context: dict,
                         document_id: Optional[int] = None) -> Optional[TrainingExample]:
        """Record a user's edit to AI-generated content.

        User edits are the highest quality training signal - they show
        what the model SHOULD have produced.
        """
        return self.record_section_generation(
            account_id=account_id,
            section_type=section_type,
            prompt=original_prompt,
            completion=edited_content,
            context=context,
            document_id=document_id,
            source="user_edited",
        )

    def rate_example(self, example_id: int, rating: int) -> bool:
        """Rate a training example (1-5 quality score)."""
        try:
            example = TrainingExample.query.get(example_id)
            if example:
                example.quality_rating = max(1, min(5, rating))
                db.session.commit()
                return True
            return False
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to rate example {example_id}: {e}")
            return False

    # ── Export ──

    def export_training_data(self, account_id: int,
                             min_rating: Optional[int] = None,
                             source_filter: Optional[str] = None) -> list[dict]:
        """Export training examples in fine-tuning JSONL format.

        Args:
            account_id: Account to export data for
            min_rating: Only include examples with rating >= this value
            source_filter: Only include examples from this source ('ai', 'user_edited', 'manual')

        Returns:
            List of dicts in Llama 3 chat format:
            [{"messages": [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}]}]
        """
        query = TrainingExample.query.filter_by(account_id=account_id)

        if min_rating is not None:
            query = query.filter(TrainingExample.quality_rating >= min_rating)
        if source_filter:
            query = query.filter_by(source=source_filter)

        query = query.order_by(TrainingExample.created_at)
        return [ex.to_training_format() for ex in query.all()]

    def get_account_stats(self, account_id: int) -> dict:
        """Get data collection statistics for an account."""
        total = TrainingExample.query.filter_by(account_id=account_id).count()
        by_source = {}
        for source in ["ai", "user_edited", "manual"]:
            by_source[source] = TrainingExample.query.filter_by(
                account_id=account_id, source=source
            ).count()
        rated = TrainingExample.query.filter(
            TrainingExample.account_id == account_id,
            TrainingExample.quality_rating.isnot(None),
        ).count()
        docs = Document.query.filter_by(account_id=account_id).count()

        return {
            "total_examples": total,
            "by_source": by_source,
            "rated": rated,
            "documents_generated": docs,
        }

    # ── Account context for prompt enrichment ──

    def get_account_context(self, account_id: int) -> dict:
        """Build the account-specific context dict for LLM prompt injection.

        Returns terminology, reference SOPs, style notes, and recent
        high-quality completions to use as few-shot examples.
        """
        account = Account.query.get(account_id)
        if not account:
            return {}

        # Grab up to 3 recent high-rated examples as few-shot context
        few_shot = TrainingExample.query.filter(
            TrainingExample.account_id == account_id,
            TrainingExample.quality_rating >= 4,
        ).order_by(TrainingExample.created_at.desc()).limit(3).all()

        few_shot_examples = []
        for ex in few_shot:
            few_shot_examples.append({
                "section_type": ex.section_type,
                "prompt_snippet": ex.user_prompt[:200],
                "completion_snippet": ex.completion[:500],
            })

        return {
            "facility_name": account.facility_name,
            "department": account.department,
            "terminology": json.loads(account.terminology_json or "{}"),
            "style_notes": account.style_notes,
            "reference_sops": json.loads(account.reference_sops_json or "[]"),
            "few_shot_examples": few_shot_examples,
        }
