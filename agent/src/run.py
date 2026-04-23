"""Agent entry point. Called by the GitHub Actions cron workflow.

Sequence: search -> fetch -> extract -> merge.
"""

from __future__ import annotations
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("alder_ipm_sim.agent")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import search
import rank
import fetch
import extract
import merge

CONFIG = HERE.parent / "search_queries.json"
BACKLOG = HERE.parent / "backlog.jsonl"
DAILY_PAPER_CAP = int(os.environ.get("AGENT_DAILY_CAP", "15"))


def main() -> None:
    log.info("AlderIPM-Sim literature agent starting.")
    papers = search.run(CONFIG)
    log.info("Found %d candidate papers (after dedup + Unpaywall).", len(papers))

    # LLM relevance ranking. Cheap Flash call on title+abstract lets us reject
    # obviously off-topic hits before spending Pro tokens on full extraction.
    ranked: list = []
    for i, p in enumerate(papers, 1):
        decision = rank.rank(p)
        p["_rank"] = decision
        log.info("[rank %d/%d] relevant=%s score=%.2f %s",
                 i, len(papers), decision.get("relevant"), decision.get("score", 0.0),
                 (p.get("title") or "")[:60])
        if decision.get("relevant"):
            ranked.append(p)
    log.info("After LLM relevance filter: %d / %d kept.", len(ranked), len(papers))

    # Sort by rank score descending, then cap at the per-run daily budget.
    ranked.sort(key=lambda p: (p.get("_rank") or {}).get("score", 0.0), reverse=True)
    ranked = ranked[:DAILY_PAPER_CAP]

    results = []
    backlog_entries = []
    for i, p in enumerate(ranked, 1):
        log.info("[extract %d/%d] %s", i, len(ranked), (p.get("title") or "")[:80])
        text, _ = fetch.fetch(p)
        if not text:
            backlog_entries.append(p)
            continue
        extracted = extract.extract(text, p)
        if not extracted:
            continue
        results.append({"paper": p, "output": extracted})

    if backlog_entries:
        with BACKLOG.open("a", encoding="utf-8") as f:
            for p in backlog_entries:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        log.info("Added %d papers to backlog.", len(backlog_entries))

    summary = merge.run(results)
    log.info("Done: +%d values, +%d papers.", summary["new_values"], summary["new_papers"])


if __name__ == "__main__":
    main()
