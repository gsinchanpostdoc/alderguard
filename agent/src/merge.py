"""Merge fresh extractions back into alder-ipm-sim-web/data/metadatabase.json.

Idempotent: duplicate (paper, param) pairs are skipped. Updates
agent_state counters and last_run. Reviewed flag is always False for
agent-written entries; human review promotes them later.
"""

from __future__ import annotations
import datetime as dt
import json
import logging
from pathlib import Path
from typing import Dict, List

log = logging.getLogger("alder_ipm_sim.agent.merge")

REPO_ROOT = Path(__file__).resolve().parents[2]
META_PATH = REPO_ROOT / "alder-ipm-sim-web" / "data" / "metadatabase.json"


def _load() -> Dict:
    return json.loads(META_PATH.read_text(encoding="utf-8"))


def _save(meta: Dict) -> None:
    META_PATH.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _citation_key(paper: Dict) -> str:
    # Prefer DOI; fall back to OpenAlex/PMC id.
    doi = (paper.get("doi") or "").replace("https://doi.org/", "")
    if doi:
        return "doi:" + doi.strip()
    return (paper.get("source") or "unknown") + ":" + str(paper.get("id") or paper.get("pmcid") or "")


def _existing_pair(values: List[Dict], cite: str, param: str) -> bool:
    return any(v.get("cite") == cite and v.get("param") == param for v in values)


def run(results: List[Dict]) -> Dict[str, int]:
    meta = _load()
    citations = meta.setdefault("citations", [])
    values = meta.setdefault("values", [])
    cite_keys = {c.get("key") for c in citations}

    new_values = 0
    new_papers = 0
    for item in results:
        paper = item["paper"]
        output = item["output"]
        if not output.get("extractions"):
            continue
        cite = _citation_key(paper)
        if cite not in cite_keys:
            citations.append({
                "key": cite,
                "authors": ", ".join(a for a in (paper.get("authors") or []) if a),
                "year": paper.get("year"),
                "title": paper.get("title"),
                "venue": paper.get("venue"),
                "doi": (paper.get("doi") or "").replace("https://doi.org/", "") or None,
                "license": paper.get("license") or "open-access",
                "url": paper.get("oa_url") or (("https://doi.org/" + paper["doi"]) if paper.get("doi") else None),
                "context": "Auto-indexed by AlderIPM-Sim literature agent.",
            })
            cite_keys.add(cite)
            new_papers += 1
        for ex in output["extractions"]:
            if _existing_pair(values, cite, ex["param"]):
                continue
            rank_info = paper.get("_rank") or {}
            values.append({
                "param": ex["param"],
                "value": ex["value"],
                "ci_low": ex["value"] * 0.8,   # placeholder until multiple extractions pool in
                "ci_high": ex["value"] * 1.2,
                "site_id": None,
                "cite": cite,
                "reviewed": False,
                "quality": "auto",
                "context_quote": ex["context_quote"],
                "confidence": ex["confidence"],
                "rank_score": rank_info.get("score"),
                "rank_reason": rank_info.get("reason"),
                "source_api": paper.get("source"),
            })
            new_values += 1

    state = meta.setdefault("agent_state", {})
    state["last_run"] = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    state["n_runs"] = int(state.get("n_runs", 0)) + 1
    state["n_papers_indexed"] = len(citations)
    state["n_reviewed_values"] = sum(1 for v in values if v.get("reviewed"))
    state["n_unreviewed_values"] = sum(1 for v in values if not v.get("reviewed"))
    state["updated"] = state["last_run"]

    _save(meta)
    return {"new_values": new_values, "new_papers": new_papers}
