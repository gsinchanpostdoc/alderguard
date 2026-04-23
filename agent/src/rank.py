"""LLM relevance ranker with rate-limit handling and persistent cache.

For each candidate paper we ask the LLM whether it plausibly reports
quantitative values for any of the 23 AlderIPM-Sim parameters. Output is
{relevant, score, reason}.

Behaviour updates over the initial version:
  - Per-paper **cache** on disk (agent/rank_cache.json). Once a paper's
    DOI or OpenAlex ID has been ranked, subsequent runs skip the LLM call.
  - **Groq throttle** — default 6 s between Groq calls to stay inside the
    free-tier 12000 tokens/min budget.
  - **429 handling** — on rate-limit, wait the Retry-After (or 30 s)
    and retry once. If still 429, the paper is marked `relevant: None`
    (unknown) and **skipped** instead of being silently passed through.
    A skipped paper remains in the cache as "deferred" so the next run
    will retry it when the budget resets.
  - **Gemini preferred, Groq fallback.** Same as before.
"""

from __future__ import annotations
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, Optional

log = logging.getLogger("alder_ipm_sim.agent.rank")

RANK_MODEL = os.environ.get("GEMINI_RANK_MODEL", "gemini-1.5-flash")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GEMINI_MIN_INTERVAL_S = float(os.environ.get("GEMINI_RANK_MIN_INTERVAL_S", "4"))
GROQ_MIN_INTERVAL_S = float(os.environ.get("GROQ_RANK_MIN_INTERVAL_S", "6"))
_last_gemini = 0.0
_last_groq = 0.0

HERE = Path(__file__).resolve().parent
CACHE_PATH = HERE.parent / "rank_cache.json"

RANK_PROMPT = """You are a screening assistant for an ecoepidemiological modelling project. You will be shown the title and abstract of a paper.

Your task: decide whether this paper is likely to report quantitative numerical values for any of these 23 parameters of the Alnus glutinosa (black alder) -- Agelastica alni (alder leaf beetle) -- Meigenia mutabilis (tachinid parasitoid) -- insectivorous bird system.

Parameters (summary): parasitoid attack rate, handling time, bird consumption rate, bird saturation, larval mortality (healthy or parasitised), parasitoid emergence rate, parasitoid conversion efficiency, adult parasitoid mortality, defoliation rate, larval season length, bird abundance index, beetle fecundity, beetle and parasitoid overwinter survival, canopy carrying capacity, canopy feedback strength, bird multiplier, max parasitoid release / larval removal / bird-habitat effort, defoliation threshold, viable capacity.

Relevant: (a) Alnus glutinosa ecology with measurements, (b) Agelastica alni biology / population dynamics / mortality / survival / fecundity, (c) Meigenia mutabilis or other tachinid parasitoids of leaf beetles, (d) insectivorous-bird predation rates on defoliating insects.

NOT relevant: taxonomy/catalogue papers, genome-only papers, papers about *mutabilis* homonyms (Lupinus mutabilis, Ulva mutabilis, Stachytarpheta mutabilis, Ootheca mutabilis, Juncus mutabilis, Trichodina mutabilis etc.), plant-volatile reviews, phytopathogen (Phytophthora) reviews, biopesticide screening without host-parasite rates, microbial ecology papers without insect parameters.

Return ONLY a JSON object in this exact shape:
{"relevant": true|false, "score": 0.0-1.0, "reason": "one short sentence"}

PAPER:
"""


# ────────────────────────── cache I/O ──
def _load_cache() -> Dict[str, Dict]:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        log.warning("Rank cache corrupt; starting empty.")
        return {}


def _save_cache(cache: Dict[str, Dict]) -> None:
    try:
        CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as e:
        log.warning("Could not write rank cache: %s", e)


def _cache_key(paper: Dict) -> Optional[str]:
    doi = (paper.get("doi") or "").lower().strip()
    if doi:
        return "doi:" + doi
    pid = paper.get("id") or paper.get("pmcid")
    if pid:
        return str(pid)
    return None


# ────────────────────────── helpers ──
def _throttle(key: str) -> None:
    global _last_gemini, _last_groq
    if key == "gemini":
        elapsed = time.time() - _last_gemini
        if elapsed < GEMINI_MIN_INTERVAL_S:
            time.sleep(GEMINI_MIN_INTERVAL_S - elapsed)
        _last_gemini = time.time()
    elif key == "groq":
        elapsed = time.time() - _last_groq
        if elapsed < GROQ_MIN_INTERVAL_S:
            time.sleep(GROQ_MIN_INTERVAL_S - elapsed)
        _last_groq = time.time()


def _parse_json(raw: str) -> Optional[Dict]:
    if not raw:
        return None
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```\s*$", "", raw.strip(), flags=re.MULTILINE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


# ────────────────────────── providers ──
def _gemini(prompt: str) -> Optional[str]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        import google.generativeai as genai  # type: ignore
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(RANK_MODEL, generation_config={"response_mime_type": "application/json"})
        _throttle("gemini")
        resp = model.generate_content(prompt)
        return resp.text
    except ImportError:
        return None
    except Exception as e:
        msg = str(e).lower()
        if "429" in msg or "rate" in msg or "quota" in msg:
            log.info("Gemini rank rate-limited; deferring to Groq.")
            return None
        log.warning("Gemini rank failed: %s", e)
        return None


def _groq(prompt: str, retry: bool = True) -> Optional[str]:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    import requests
    _throttle("groq")
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
            },
            timeout=30,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        if r.status_code == 429 and retry:
            wait = _retry_after_seconds(r) or 30
            log.info("Groq rank 429; waiting %ds then retrying once.", wait)
            time.sleep(wait)
            return _groq(prompt, retry=False)
        log.warning("Groq rank HTTP %s: %s", r.status_code, r.text[:160])
        return None
    except Exception as e:
        log.warning("Groq rank exception: %s", e)
        return None


def _retry_after_seconds(resp) -> Optional[int]:
    """Pull a sensible wait time out of Groq's 429 response."""
    hdr = resp.headers.get("Retry-After")
    if hdr and hdr.isdigit():
        return int(hdr) + 1
    try:
        body = resp.json()
        msg = (body.get("error") or {}).get("message", "")
        m = re.search(r"try again in ([\d.]+)s", msg)
        if m:
            return int(float(m.group(1))) + 1
    except Exception:
        pass
    return None


# ────────────────────────── public ──
def rank(paper: Dict) -> Dict:
    title = (paper.get("title") or "").strip()
    abstract = (paper.get("abstract") or "").strip()
    if not title:
        return {"relevant": False, "score": 0.0, "reason": "No title."}

    cache = _load_cache()
    ckey = _cache_key(paper)
    if ckey and ckey in cache and cache[ckey].get("status") == "done":
        cached = cache[ckey]
        return {"relevant": cached["relevant"], "score": cached["score"], "reason": cached.get("reason", "cached") + " (cached)"}

    if not abstract:
        result = {"relevant": True, "score": 0.4, "reason": "No abstract; pass-through."}
        if ckey:
            cache[ckey] = {**result, "status": "done"}
            _save_cache(cache)
        return result

    body = f"Title: {title}\n\nAbstract: {abstract[:2500]}"
    raw = _gemini(RANK_PROMPT + body)
    if raw is None:
        raw = _groq(RANK_PROMPT + body)
    if raw is None:
        # Rate-limited on both. Mark deferred (not relevant this run) so we skip
        # extraction; the cache entry uses status=deferred so next run retries.
        if ckey:
            cache[ckey] = {"status": "deferred", "relevant": False, "score": 0.0, "reason": "rate-limited"}
            _save_cache(cache)
        return {"relevant": False, "score": 0.0, "reason": "Rate-limited; deferred to next run."}

    parsed = _parse_json(raw)
    if not parsed:
        return {"relevant": False, "score": 0.0, "reason": "Rank parse failed."}

    result = {
        "relevant": bool(parsed.get("relevant")),
        "score": float(parsed.get("score") or 0.0),
        "reason": str(parsed.get("reason") or "")[:200],
    }
    if ckey:
        cache[ckey] = {**result, "status": "done"}
        _save_cache(cache)
    return result
