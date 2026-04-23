"""Multi-source literature search layer.

Sources (all free, all public APIs, all covered by the agent's OA-only policy):
  - OpenAlex               (full-text OA hits via primary_location)
  - Europe PMC             (full-text OA XML, life-sciences focused)
  - Semantic Scholar       (rich metadata, abstracts, relevance ranking)
  - Crossref               (widest metadata coverage, polite email required)
  - Unpaywall              (resolves Crossref DOIs to OA PDF URLs where available)

Deduplicates by DOI, then by lower-case title when DOI is missing. Returns
normalised paper dicts with a uniform schema the rest of the pipeline expects:
{source, id, doi, title, year, authors, venue, oa_url, license, abstract}
"""

from __future__ import annotations
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests

log = logging.getLogger("alder_ipm_sim.agent.search")

CONTACT_EMAIL = os.environ.get("AGENT_CONTACT_EMAIL", "alderipmsim-agent@github.io")
HEADERS = {"User-Agent": f"alderipmsim-agent/0.2 (mailto:{CONTACT_EMAIL})"}

OPENALEX_URL        = "https://api.openalex.org/works"
EUROPEPMC_URL       = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
CROSSREF_URL        = "https://api.crossref.org/works"
UNPAYWALL_URL       = "https://api.unpaywall.org/v2/"


# ────────────────────────────────── helpers ──
def _pause(sec: float = 0.5) -> None:
    time.sleep(sec)


def _safe_doi(x: Optional[str]) -> Optional[str]:
    if not x:
        return None
    return x.replace("https://doi.org/", "").strip().lower() or None


def _invert_abstract(idx: Optional[Dict[str, List[int]]]) -> Optional[str]:
    if not idx:
        return None
    words: List[str] = []
    for term, positions in idx.items():
        for p in positions:
            while len(words) <= p:
                words.append("")
            words[p] = term
    return " ".join(w for w in words if w) or None


# ────────────────────────────────── OpenAlex ──
def _openalex(query: str, per_page: int, min_year: int) -> List[Dict]:
    params = {
        "search": query,
        "per-page": per_page,
        "filter": f"from_publication_date:{min_year}-01-01,is_oa:true",
    }
    r = requests.get(OPENALEX_URL, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json().get("results", []) or []
    out: List[Dict] = []
    for w in data:
        if not isinstance(w, dict):
            continue
        loc = w.get("primary_location") or {}
        source_obj = loc.get("source") or {}
        oa_obj = w.get("open_access") or {}
        # authorships can be None or contain null author fields
        authors_raw = w.get("authorships") or []
        authors: List[str] = []
        for a in authors_raw[:6]:
            author_obj = (a or {}).get("author") or {}
            name = author_obj.get("display_name")
            if name:
                authors.append(name)
        out.append({
            "source": "openalex",
            "id": w.get("id"),
            "doi": _safe_doi(w.get("doi")),
            "title": w.get("title"),
            "year": w.get("publication_year"),
            "authors": authors,
            "venue": source_obj.get("display_name"),
            "oa_url": loc.get("pdf_url") or oa_obj.get("oa_url"),
            "license": loc.get("license") or "",
            "abstract": _invert_abstract(w.get("abstract_inverted_index")),
        })
    return out


# ────────────────────────────────── Europe PMC ──
def _europepmc(query: str, per_page: int, min_year: int) -> List[Dict]:
    params = {
        "query": f"({query}) AND OPEN_ACCESS:Y AND FIRST_PDATE:[{min_year}-01-01 TO 3000-01-01]",
        "format": "json",
        "pageSize": per_page,
        "resultType": "core",
    }
    r = requests.get(EUROPEPMC_URL, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    results = (r.json().get("resultList") or {}).get("result", [])
    out: List[Dict] = []
    for w in results:
        out.append({
            "source": "europepmc",
            "id": w.get("id"),
            "source_full": w.get("source"),
            "pmcid": w.get("pmcid"),
            "doi": _safe_doi(w.get("doi")),
            "title": w.get("title"),
            "year": int(w.get("pubYear")) if (w.get("pubYear") or "").isdigit() else None,
            "authors": [w.get("authorString")] if w.get("authorString") else [],
            "venue": w.get("journalTitle"),
            "oa_url": f"https://europepmc.org/article/{w.get('source')}/{w.get('id')}" if w.get("source") and w.get("id") else None,
            "license": w.get("license") or "",
            "abstract": w.get("abstractText"),
        })
    return out


# ────────────────────────────────── Semantic Scholar ──
def _semantic_scholar(query: str, per_page: int, min_year: int) -> List[Dict]:
    params = {
        "query": query,
        "limit": min(per_page, 100),
        "fields": "title,abstract,authors,year,venue,externalIds,openAccessPdf,isOpenAccess",
        "year": f"{min_year}-",
    }
    headers = dict(HEADERS)
    api_key = os.environ.get("S2_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    try:
        r = requests.get(SEMANTIC_SCHOLAR_URL, params=params, headers=headers, timeout=30)
    except requests.RequestException as e:
        log.warning("Semantic Scholar request failed: %s", e)
        return []
    if r.status_code != 200:
        log.warning("Semantic Scholar HTTP %s for query '%s'", r.status_code, query)
        return []
    out: List[Dict] = []
    for w in (r.json().get("data") or []):
        if not w.get("isOpenAccess"):
            continue
        ext = w.get("externalIds") or {}
        out.append({
            "source": "semanticscholar",
            "id": "S2:" + str(w.get("paperId", "")),
            "doi": _safe_doi(ext.get("DOI")),
            "title": w.get("title"),
            "year": w.get("year"),
            "authors": [a.get("name") for a in (w.get("authors") or [])][:6],
            "venue": w.get("venue"),
            "oa_url": (w.get("openAccessPdf") or {}).get("url"),
            "license": "",
            "abstract": w.get("abstract"),
        })
    return out


# ────────────────────────────────── Crossref ──
def _crossref(query: str, per_page: int, min_year: int) -> List[Dict]:
    params = {
        "query": query,
        "rows": min(per_page, 100),
        "filter": f"from-pub-date:{min_year}-01-01,has-abstract:true,type:journal-article",
        "mailto": CONTACT_EMAIL,
    }
    try:
        r = requests.get(CROSSREF_URL, params=params, headers=HEADERS, timeout=30)
    except requests.RequestException as e:
        log.warning("Crossref request failed: %s", e)
        return []
    if r.status_code != 200:
        log.warning("Crossref HTTP %s for query '%s'", r.status_code, query)
        return []
    items = (r.json().get("message") or {}).get("items") or []
    out: List[Dict] = []
    for w in items:
        authors = [f"{a.get('given','')} {a.get('family','')}".strip() for a in (w.get("author") or [])][:6]
        out.append({
            "source": "crossref",
            "id": w.get("DOI"),
            "doi": _safe_doi(w.get("DOI")),
            "title": (w.get("title") or [None])[0],
            "year": (w.get("published-print") or w.get("published-online") or {}).get("date-parts", [[None]])[0][0],
            "authors": authors,
            "venue": (w.get("container-title") or [None])[0],
            "oa_url": None,  # Resolved later via Unpaywall.
            "license": ", ".join([l.get("URL", "") for l in (w.get("license") or [])])[:120],
            "abstract": (w.get("abstract") or "").replace("<jats:p>", "").replace("</jats:p>", "") or None,
        })
    return out


# ────────────────────────────────── Unpaywall ──
def enrich_with_unpaywall(papers: List[Dict]) -> List[Dict]:
    """For any paper without an oa_url but with a DOI, query Unpaywall.

    Adds oa_url and license if Unpaywall reports an OA version. Skips silently
    on errors. Rate limit is 100k requests/day free.
    """
    for p in papers:
        if p.get("oa_url") or not p.get("doi"):
            continue
        try:
            r = requests.get(
                UNPAYWALL_URL + p["doi"],
                params={"email": CONTACT_EMAIL},
                headers=HEADERS,
                timeout=20,
            )
            if r.status_code != 200:
                continue
            data = r.json()
            best = data.get("best_oa_location") or {}
            if best.get("url"):
                p["oa_url"] = best.get("url_for_pdf") or best.get("url")
                p["license"] = p.get("license") or best.get("license") or "open-access"
        except requests.RequestException:
            continue
        _pause(0.1)
    return papers


# ────────────────────────────────── dedupe + orchestrate ──
def _dedupe(papers: List[Dict]) -> List[Dict]:
    seen_doi: set = set()
    seen_title: set = set()
    out: List[Dict] = []
    for p in papers:
        doi = (p.get("doi") or "").lower()
        title_key = (p.get("title") or "").strip().lower()[:160]
        if doi and doi in seen_doi:
            continue
        if not doi and title_key and title_key in seen_title:
            continue
        if doi:
            seen_doi.add(doi)
        if title_key:
            seen_title.add(title_key)
        out.append(p)
    return out


def run(config_path: Path) -> List[Dict]:
    cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
    per_query = cfg.get("per_query_limit", 25)
    min_year = cfg.get("min_year", 1990)

    all_papers: List[Dict] = []

    def _run_source(name: str, fn, queries: List[str]) -> None:
        for q in queries:
            try:
                rs = fn(q, per_query, min_year)
                log.info("  %s %-28s -> %d hits", name, q[:28], len(rs))
                all_papers.extend(rs)
            except Exception as e:
                log.warning("  %s query failed (%s): %s", name, q, e)
            _pause(0.4)

    # Source-specific queries: cfg may provide specialised keys; fall back to cfg['queries'].
    q_openalex = cfg.get("openalex") or cfg.get("queries") or []
    q_europepmc = cfg.get("europepmc") or cfg.get("queries") or []
    q_s2 = cfg.get("semantic_scholar") or cfg.get("queries") or cfg.get("openalex") or []
    q_cr = cfg.get("crossref") or cfg.get("queries") or cfg.get("openalex") or []

    _run_source("OpenAlex       ", _openalex, q_openalex)
    _run_source("Europe PMC     ", _europepmc, q_europepmc)
    _run_source("Semantic Scholar", _semantic_scholar, q_s2)
    _run_source("Crossref       ", _crossref, q_cr)

    log.info("Total raw hits across sources: %d", len(all_papers))
    deduped = _dedupe(all_papers)
    log.info("After DOI/title dedupe: %d", len(deduped))

    log.info("Enriching with Unpaywall...")
    enriched = enrich_with_unpaywall(deduped)
    n_oa = sum(1 for p in enriched if p.get("oa_url"))
    log.info("Papers with resolved OA URL: %d / %d", n_oa, len(enriched))
    return enriched
