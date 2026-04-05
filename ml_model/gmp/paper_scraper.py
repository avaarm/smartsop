"""Paper scraper for auto-filling batch records from published methods sections.

Uses NCBI's PubMed Central E-utilities API (legitimate, rate-limited, free)
to search and fetch open-access papers, extracting their methods sections
for use as reference material when creating GMP batch records.

All papers scraped are from PMC's open-access subset, which permits
programmatic access and reuse under their terms of service.
"""

import logging
import time
import re
from dataclasses import dataclass, field, asdict
from typing import Optional
from xml.etree import ElementTree as ET

import requests

logger = logging.getLogger(__name__)


@dataclass
class Paper:
    """Metadata for a scientific paper."""
    pmcid: str
    pmid: Optional[str] = None
    title: str = ""
    authors: list[str] = field(default_factory=list)
    journal: str = ""
    year: str = ""
    abstract: str = ""
    doi: str = ""
    url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PaperMethods:
    """Extracted methods section from a paper."""
    paper: Paper
    methods_text: str
    sections: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "paper": self.paper.to_dict(),
            "methods_text": self.methods_text,
            "sections": self.sections,
        }


class PaperScraper:
    """Scrapes methods sections from open-access papers in PubMed Central.

    Uses NCBI E-utilities API with required tool identification per
    https://www.ncbi.nlm.nih.gov/books/NBK25497/. Respects the 3 req/sec
    rate limit (10/sec with API key).
    """

    EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    PMC_HTML_BASE = "https://www.ncbi.nlm.nih.gov/pmc/articles"

    # Methods section keywords (case-insensitive)
    METHODS_KEYWORDS = [
        "method",
        "materials and method",
        "experimental procedure",
        "experimental design",
        "protocol",
        "study design",
    ]

    def __init__(self, tool_name: str = "smartsop-gmp",
                 email: str = "gmp-builder@localhost",
                 api_key: Optional[str] = None,
                 rate_limit_delay: float = 0.34):
        self.tool_name = tool_name
        self.email = email
        self.api_key = api_key
        self.rate_limit_delay = rate_limit_delay  # 0.34s = ~3 req/s
        self._last_request_time = 0.0

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"{tool_name}/1.0 (mailto:{email})"
        })

    def _rate_limited_get(self, url: str, params: dict, timeout: int = 30):
        """Make a GET request respecting NCBI rate limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)

        params = dict(params)
        params["tool"] = self.tool_name
        params["email"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key

        resp = self.session.get(url, params=params, timeout=timeout)
        self._last_request_time = time.time()
        resp.raise_for_status()
        return resp

    def search(self, query: str, max_results: int = 10) -> list[Paper]:
        """Search PubMed Central for open-access papers matching the query.

        Args:
            query: Search terms (e.g., "CD8 enrichment CliniMACS Prodigy")
            max_results: Maximum number of results to return

        Returns:
            List of Paper objects with basic metadata
        """
        # Use PMC open access subset filter to ensure we only get papers
        # we can legally scrape and reuse
        search_query = f'({query}) AND "open access"[filter]'

        logger.info(f"Searching PMC: {search_query!r}")

        try:
            resp = self._rate_limited_get(
                f"{self.EUTILS_BASE}/esearch.fcgi",
                params={
                    "db": "pmc",
                    "term": search_query,
                    "retmax": max_results,
                    "retmode": "xml",
                    "sort": "relevance",
                },
            )
        except requests.RequestException as e:
            logger.error(f"PMC search failed: {e}")
            return []

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as e:
            logger.error(f"Failed to parse search response: {e}")
            return []

        pmcids = [id_elem.text for id_elem in root.findall(".//Id") if id_elem.text]
        if not pmcids:
            return []

        return self._fetch_summaries(pmcids)

    def _fetch_summaries(self, pmcids: list[str]) -> list[Paper]:
        """Fetch summary metadata for a list of PMC IDs."""
        try:
            resp = self._rate_limited_get(
                f"{self.EUTILS_BASE}/esummary.fcgi",
                params={
                    "db": "pmc",
                    "id": ",".join(pmcids),
                    "retmode": "xml",
                },
            )
        except requests.RequestException as e:
            logger.error(f"PMC esummary failed: {e}")
            return []

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as e:
            logger.error(f"Failed to parse summary response: {e}")
            return []

        papers = []
        for doc in root.findall(".//DocSum"):
            id_elem = doc.find("./Id")
            if id_elem is None or not id_elem.text:
                continue

            pmcid = f"PMC{id_elem.text}" if not id_elem.text.startswith("PMC") else id_elem.text
            paper = Paper(
                pmcid=pmcid,
                url=f"{self.PMC_HTML_BASE}/{pmcid}/",
            )

            for item in doc.findall("./Item"):
                name = item.get("Name", "")
                text = (item.text or "").strip()

                if name == "Title":
                    paper.title = self._clean_text(text)
                elif name == "AuthorList":
                    paper.authors = [
                        sub.text.strip()
                        for sub in item.findall("./Item")
                        if sub.text
                    ]
                elif name in ("Source", "FullJournalName"):
                    if text and not paper.journal:
                        paper.journal = text
                elif name == "PubDate":
                    paper.year = text[:4] if text else ""
                elif name == "DOI":
                    paper.doi = text
                elif name == "ArticleIds":
                    for sub in item.findall("./Item"):
                        sub_name = sub.get("Name", "")
                        if sub_name == "pmid":
                            paper.pmid = sub.text

            if paper.title:
                papers.append(paper)

        return papers

    def fetch_methods(self, pmcid: str) -> Optional[PaperMethods]:
        """Fetch the full paper and extract its methods section(s).

        Args:
            pmcid: PMC ID (e.g., "PMC1234567" or "1234567")

        Returns:
            PaperMethods object or None if methods section not found
        """
        pmcid_num = str(pmcid).replace("PMC", "").strip()
        pmcid_full = f"PMC{pmcid_num}"

        logger.info(f"Fetching methods for {pmcid_full}")

        try:
            resp = self._rate_limited_get(
                f"{self.EUTILS_BASE}/efetch.fcgi",
                params={
                    "db": "pmc",
                    "id": pmcid_num,
                    "retmode": "xml",
                },
                timeout=60,
            )
        except requests.RequestException as e:
            logger.error(f"PMC efetch failed for {pmcid_full}: {e}")
            return None

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as e:
            logger.error(f"Failed to parse full text for {pmcid_full}: {e}")
            return None

        # Some PMC articles are restricted; check for error response
        if root.tag == "pmc-articleset":
            article = root.find(".//article")
        else:
            article = root

        if article is None:
            logger.warning(f"No article element in PMC {pmcid_full}")
            return None

        paper = self._extract_metadata(article, pmcid_full)
        methods_sections = self._extract_methods_sections(article)

        if not methods_sections:
            logger.warning(f"No methods section found in {pmcid_full}")
            return None

        full_text = "\n\n".join(
            f"## {s['heading']}\n{s['text']}" for s in methods_sections
        )

        # Truncate to keep LLM context manageable (~4000 tokens)
        max_chars = 12000
        if len(full_text) > max_chars:
            full_text = full_text[:max_chars] + "\n\n[...truncated for length]"

        return PaperMethods(
            paper=paper,
            methods_text=full_text,
            sections=methods_sections,
        )

    def _extract_metadata(self, article: ET.Element, pmcid: str) -> Paper:
        """Extract paper metadata from article XML."""
        paper = Paper(pmcid=pmcid, url=f"{self.PMC_HTML_BASE}/{pmcid}/")

        title_elem = article.find(".//article-title")
        if title_elem is not None:
            paper.title = self._clean_text(self._element_text(title_elem))

        abstract_elem = article.find(".//abstract")
        if abstract_elem is not None:
            paper.abstract = self._clean_text(self._element_text(abstract_elem))[:1000]

        for contrib in article.findall(".//contrib[@contrib-type='author']"):
            surname = contrib.find(".//surname")
            given = contrib.find(".//given-names")
            parts = []
            if given is not None and given.text:
                parts.append(given.text.strip())
            if surname is not None and surname.text:
                parts.append(surname.text.strip())
            if parts:
                paper.authors.append(" ".join(parts))

        journal_elem = article.find(".//journal-title")
        if journal_elem is not None:
            paper.journal = self._clean_text(self._element_text(journal_elem))

        year_elem = article.find(".//pub-date/year")
        if year_elem is not None and year_elem.text:
            paper.year = year_elem.text

        doi_elem = article.find(".//article-id[@pub-id-type='doi']")
        if doi_elem is not None and doi_elem.text:
            paper.doi = doi_elem.text

        pmid_elem = article.find(".//article-id[@pub-id-type='pmid']")
        if pmid_elem is not None and pmid_elem.text:
            paper.pmid = pmid_elem.text

        return paper

    def _extract_methods_sections(self, article: ET.Element) -> list[dict]:
        """Find and extract all methods sections from the article body."""
        methods = []

        # Look for top-level sections in the body
        for sec in article.findall(".//body//sec"):
            title_elem = sec.find("./title")
            if title_elem is None:
                continue

            heading = self._clean_text(self._element_text(title_elem))
            heading_lower = heading.lower()

            # Match if any methods keyword is in the heading
            if not any(kw in heading_lower for kw in self.METHODS_KEYWORDS):
                continue

            # Collect all text content from this section
            text = self._section_text(sec)
            if text and len(text) > 50:
                methods.append({
                    "heading": heading,
                    "text": text,
                })

        return methods

    def _section_text(self, section: ET.Element) -> str:
        """Extract readable text from a section, preserving paragraph structure."""
        parts = []
        for elem in section.iter():
            if elem.tag == "title" and elem == section.find("./title"):
                continue  # Skip the main section title
            if elem.tag == "p":
                text = self._element_text(elem)
                if text.strip():
                    parts.append(text.strip())
            elif elem.tag in ("list-item", "td"):
                text = self._element_text(elem)
                if text.strip():
                    parts.append(f"- {text.strip()}")
        return "\n\n".join(parts)

    def _element_text(self, elem: ET.Element) -> str:
        """Recursively extract all text from an element."""
        parts = []
        if elem.text:
            parts.append(elem.text)
        for child in elem:
            parts.append(self._element_text(child))
            if child.tail:
                parts.append(child.tail)
        return "".join(parts)

    def _clean_text(self, text: str) -> str:
        """Normalize whitespace and clean up text."""
        if not text:
            return ""
        text = re.sub(r"\s+", " ", text)
        return text.strip()
