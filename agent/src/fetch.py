"""Fetch open-access full-text for a paper record.

Returns (text, license_label) or (None, None) if not reachable. Respects
copyright: only OA-licensed text is returned.
"""

from __future__ import annotations
import logging
from typing import Optional, Tuple, Dict

import requests

log = logging.getLogger("alder_ipm_sim.agent.fetch")
HEADERS = {"User-Agent": "alderipmsim-agent/0.1"}
MAX_BYTES = 1_500_000  # cap per paper to keep Gemini prompt within context window


def _europepmc_fulltext(pmcid: str) -> Optional[str]:
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code == 200 and r.text:
            return r.text[:MAX_BYTES]
    except Exception as e:
        log.warning("EuropePMC fulltext fetch failed: %s", e)
    return None


def _openalex_pdf(url: str) -> Optional[str]:
    # We do not parse PDFs locally (pdfminer is heavy). Skip; the LLM can't read PDFs directly.
    # Abstract-only fallback happens in the caller.
    return None


def fetch(paper: Dict) -> Tuple[Optional[str], Optional[str]]:
    """Retrieve OA full text.

    Priority: Europe PMC full-text XML (if pmcid) > paper.abstract > None.
    """
    pmcid = paper.get("pmcid")
    if pmcid:
        t = _europepmc_fulltext(pmcid)
        if t:
            return t, paper.get("license") or "open-access"
    # Fallback: abstract only. LLM still extracts if the key numbers appear there.
    if paper.get("abstract"):
        return paper["abstract"][:MAX_BYTES], paper.get("license") or "abstract"
    return None, None
