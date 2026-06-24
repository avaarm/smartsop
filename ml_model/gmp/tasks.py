"""Celery tasks for the long-running LLM operations.

These wrap the generator calls that can take 10-90s so they run on a worker
instead of blocking a web request. Registered via @shared_task so they bind to
whichever Celery app is set as default (see make_celery / gmp_server).
"""

import logging

from celery import shared_task

from .generator_provider import get_generator

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="gmp.preview_section")
def preview_section_task(self, doc_type: str, section_id: str, context: dict):
    """Generate one document section with the LLM."""
    logger.info("preview_section_task %s/%s", doc_type, section_id)
    return get_generator().preview_section(doc_type, section_id, context)


@shared_task(bind=True, name="gmp.autofill_from_paper")
def autofill_from_paper_task(self, pmcid: str, context: dict):
    """Extract GMP section data from a paper with the LLM."""
    logger.info("autofill_from_paper_task %s", pmcid)
    return get_generator().autofill_from_paper(pmcid, context)
