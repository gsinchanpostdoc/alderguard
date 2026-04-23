"""Gemini extraction call.

Reads the extraction prompt from prompts/extract.txt, sends it alongside
the paper text, parses the returned JSON, and validates every extraction
carries a `context_quote`. Entries missing a quote are rejected.

Model default: gemini-1.5-pro (higher quality on dense scientific text and
tables). Override via the GEMINI_MODEL env var. Two retries on 429
rate-limit errors with exponential backoff so we stay inside the free-tier
quota (2 RPM, 32k TPM, 50 RPD) without losing runs.
"""

from __future__ import annotations
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("alder_ipm_sim.agent.extract")

HERE = Path(__file__).resolve().parent
PROMPT_PATH = HERE.parent / "prompts" / "extract.txt"

VALID_PARAMS = {
    "beta", "h", "c_B", "a_B", "mu_S", "mu_I", "delta", "eta", "mu_F",
    "kappa", "T", "B_index", "R_B", "sigma_A", "sigma_F", "K_0", "phi",
    "rho", "u_P_max", "u_C_max", "u_B_max", "D_crit", "K_min",
}

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
# Free-tier rate limit for gemini-1.5-flash is 15 RPM -> 4 s spacing; Pro is 2 RPM -> 32 s.
# The default below matches Flash; set GEMINI_MIN_INTERVAL_S=32 if you switch to Pro.
MIN_CALL_INTERVAL_S = float(os.environ.get("GEMINI_MIN_INTERVAL_S", "4.2"))
_last_call_ts = 0.0


def _throttle() -> None:
    global _last_call_ts
    elapsed = time.time() - _last_call_ts
    if elapsed < MIN_CALL_INTERVAL_S:
        time.sleep(MIN_CALL_INTERVAL_S - elapsed)
    _last_call_ts = time.time()


GROQ_MIN_INTERVAL_S = float(os.environ.get("GROQ_EXTRACT_MIN_INTERVAL_S", "8"))
_last_groq_ts = 0.0


def _groq_throttle() -> None:
    global _last_groq_ts
    elapsed = time.time() - _last_groq_ts
    if elapsed < GROQ_MIN_INTERVAL_S:
        time.sleep(GROQ_MIN_INTERVAL_S - elapsed)
    _last_groq_ts = time.time()


def _groq_retry_after(resp) -> int:
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
    return 30


def _groq_call(prompt: str, text: str, retries: int = 1) -> Optional[str]:
    """Fallback to Groq's free tier (Llama-3.3-70b). Handles 429 with wait+retry."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    import requests
    model_name = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    body = {
        "model": model_name,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": prompt},
            # Truncate to stay well inside Groq's 12K TPM budget per call.
            {"role": "user", "content": "PAPER TEXT:\n" + text[:18000]},
        ],
        "temperature": 0.0,
    }
    attempt = 0
    while attempt <= retries:
        _groq_throttle()
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=body,
                timeout=60,
            )
        except Exception as e:
            log.warning("Groq extraction exception: %s", e)
            return None
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        if r.status_code == 429 and attempt < retries:
            wait = _groq_retry_after(r)
            log.info("Groq extract 429; waiting %ds then retrying once.", wait)
            time.sleep(wait)
            attempt += 1
            continue
        log.warning("Groq HTTP %s: %s", r.status_code, r.text[:160])
        return None
    return None


def _gemini_call(prompt: str, text: str, retries: int = 2) -> Optional[str]:
    """Call Gemini with retry on rate-limit. Returns raw response string or None."""
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError:
        log.error("google-generativeai not installed; pip install google-generativeai")
        return None
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        DEFAULT_MODEL,
        generation_config={"response_mime_type": "application/json"},
    )

    attempt = 0
    backoff = 10
    while attempt <= retries:
        _throttle()
        try:
            resp = model.generate_content(prompt + "\n\nPAPER TEXT:\n" + text)
            return resp.text
        except Exception as e:
            msg = str(e).lower()
            if "429" in msg or "rate" in msg or "quota" in msg:
                log.warning("Rate-limited on attempt %d: %s. Backing off %ds.", attempt + 1, e, backoff)
                time.sleep(backoff)
                backoff *= 2
                attempt += 1
                continue
            log.warning("Gemini call failed: %s", e)
            return None
    log.warning("Exhausted Gemini retries.")
    return None


def _llm_call(prompt: str, text: str) -> Optional[str]:
    """Provider-agnostic call. Prefers Gemini; falls back to Groq if Gemini is unavailable."""
    result = _gemini_call(prompt, text)
    if result is not None:
        return result
    groq = _groq_call(prompt, text)
    if groq is not None:
        log.info("Gemini unavailable -> Groq fallback succeeded.")
        return groq
    if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("GROQ_API_KEY"):
        log.warning("Neither GEMINI_API_KEY nor GROQ_API_KEY set; skipping extraction.")
    return None


def _parse_json(raw: str) -> Optional[Dict]:
    if not raw:
        return None
    # Model may wrap JSON in backticks. Strip.
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```\s*$", "", raw.strip(), flags=re.MULTILINE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        log.warning("Could not parse JSON from Gemini: %s; raw=%s", e, cleaned[:200])
        return None


def extract(text: str, paper: Dict) -> Optional[Dict]:
    if not text:
        return None
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    raw = _llm_call(prompt, text)
    if not raw:
        return None
    parsed = _parse_json(raw)
    if not parsed:
        return None
    exts = parsed.get("extractions", [])
    if not isinstance(exts, list):
        return None
    clean: List[Dict] = []
    for e in exts:
        if not isinstance(e, dict):
            continue
        param = e.get("param")
        quote = e.get("context_quote") or ""
        value = e.get("value")
        if param not in VALID_PARAMS:
            continue
        if not quote or len(quote) < 10:
            # Reject extractions without a supporting quote.
            continue
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        conf = e.get("confidence")
        try:
            conf = float(conf) if conf is not None else 0.0
        except (TypeError, ValueError):
            conf = 0.0
        if conf < 0.5:
            continue
        clean.append({
            "param": param,
            "value": value,
            "units": e.get("units") or "",
            "context_quote": quote[:500],
            "page": e.get("page"),
            "confidence": conf,
            "site_hint": e.get("site_hint") or None,
            "study_type": e.get("study_type") or "unspecified",
        })
    return {"extractions": clean, "raw_response": raw[:2000]}
