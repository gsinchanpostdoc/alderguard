# AlderIPM-Sim Literature Agent

A scheduled GitHub Action that continuously grows `alder-ipm-sim-web/data/metadatabase.json` with parameter values extracted from the open-access literature on the *Alnus glutinosa* – *Agelastica alni* – *Meigenia mutabilis* – insectivorous-bird system.

## What it does, in order

1. **Search (5 sources).** Queries **OpenAlex**, **Europe PMC**, **Semantic Scholar**, and **Crossref** in parallel for papers matching the query set in `agent/search_queries.json`. Each source's adapter returns a normalised paper record. Results are deduplicated by DOI (and by title for DOI-less hits). **Unpaywall** then resolves any remaining DOIs to an open-access PDF URL where one exists.
2. **Relevance rank (cheap).** For each candidate, title + abstract are sent to **Gemini 1.5 Flash** with a screening prompt (`agent/src/rank.py`). Flash returns `{relevant, score, reason}`. Obvious off-topic hits (wrong species, purely theoretical, unrelated medical studies) are dropped before any expensive call. The remaining papers are sorted by relevance score.
3. **Extract (quality).** Each surviving open-access paper is sent to **Gemini 1.5 Pro** with a structured prompt (`agent/prompts/extract.txt`) that asks it to identify any of the 23 AlderIPM-Sim parameter values reported in the paper, always paired with a verbatim `context_quote`. Extractions missing a quote, or with confidence < 0.5, are rejected.
4. **Merge.** Unit-normalised values are appended to `metadatabase.json` with `reviewed: false`, tagged with the source API (`openalex` / `europepmc` / `semanticscholar` / `crossref`), the rank score and reason, and a placeholder CI equal to ±20 % pending pooling. Paywalled hits go to `agent/backlog.jsonl` for your manual review; the agent never auto-extracts paywalled text.
5. **Publish.** `agent_state.last_run`, `n_papers_indexed`, and `n_unreviewed_values` are updated. The workflow commits `metadatabase.json` back to `main`. The Pages workflow redeploys `alder-ipm-sim-web/` automatically, so the header badge on the live site reflects the new numbers within a minute of each run.

## Why this design is honest

- **Reviewed vs unreviewed separation.** All agent-added values are flagged `reviewed: false`. The web app draws confidence bands from reviewed values by default and only mixes unreviewed values in when the user expands "Show auto-extracted studies" on the Sources modal. You can promote candidates to `reviewed: true` after spot-checking the `context_quote` against the PDF.
- **Open-access only.** The agent respects copyright; paywalled papers are never auto-extracted, only flagged for human review.
- **LLM hallucination mitigation.** The extraction prompt requires the LLM to quote the exact sentence from the paper that motivated each extraction. Entries missing a `context_quote` are rejected automatically.
- **Independent of your laptop.** The agent runs on GitHub's own compute. Closing your laptop does not stop it.

## Setup — one-time (choose ONE free LLM provider)

### Option A — Google AI Studio (Gemini) — *recommended, 1500 req/day free*

1. Open <https://aistudio.google.com/apikey>, sign in with any Google account.
2. Click **Create API key** → **Create API key in new project**. Copy the `AIza…` key that appears.
3. In the repo: <https://github.com/gsinchanpostdoc/alder-ipm-sim/settings/secrets/actions> → *New repository secret* → Name: **`GEMINI_API_KEY`** → paste the key → *Add secret*.

No billing, no credit card. The workflow uses `gemini-1.5-flash` by default, which has a 1500-request/day free tier (~ 50 papers/day through the full rank + extract pipeline).

### Option B — Groq — *also 100 % free, useful as fallback*

1. Sign up at <https://console.groq.com>. A Google or GitHub login works.
2. *API Keys* → *Create API Key*. Copy the `gsk_…` key.
3. Add it as GitHub secret **`GROQ_API_KEY`**.

Groq serves Llama 3.3 70B on a generous free tier (several thousand requests/day). The agent automatically falls back to Groq whenever Gemini is missing or rate-limited.

### Using both is the safest setup

Add **both** secrets. The agent prefers Gemini (higher quality for this task) and silently falls back to Groq on any 429 / quota error, so you never run out of free calls in a single run.

Neither path costs a cent. Enabling billing is optional and only raises ceilings.

The workflow at `.github/workflows/literature-agent.yml` runs on cron (daily at 03:00 UTC) and can be launched manually from the Actions tab via *Run workflow*.

## Cost

- **Gemini 1.5 Flash (ranking)** — 15 requests/min, 1 500 requests/day free. One request per candidate paper. The daily cap of 30 papers fits comfortably.
- **Gemini 1.5 Pro (extraction)** — 2 requests/min, 50 requests/day free. One request per *relevant* paper (after Flash filters the rest out). The 32-second throttle in `agent/src/extract.py` keeps the agent inside the RPM limit; the daily cap of 30 matches the RPD limit.
- **OpenAlex, Europe PMC, Semantic Scholar, Crossref, Unpaywall** — all open APIs, no fee. Semantic Scholar accepts an optional `S2_API_KEY` secret for higher rate limits; the agent works fine without one.

No credit card required at any step. Enabling paid billing on your AI Studio project raises the Pro quota by ~200× if you want to ingest thousands of papers.

## Reviewing candidate extractions

After each run, check `alder-ipm-sim-web/data/metadatabase.json` for entries with `reviewed: false`. For each one:

1. Open the `cite` key and find the paper in `citations`.
2. Compare the `context_quote` to the paper's text.
3. If the extraction is correct, edit the entry and change `reviewed: false` → `reviewed: true`, and add a `quality: "A" | "B" | "C"` tag reflecting study strength.
4. Commit the change. The web app updates on next deploy.

## Files in this directory

```
agent/
├── README.md                 # this file
├── requirements.txt          # Python dependencies
├── search_queries.json       # OpenAlex / Europe PMC query set (editable)
├── prompts/
│   └── extract.txt           # LLM extraction prompt
├── backlog.jsonl             # paywalled hits awaiting manual review
└── src/
    ├── run.py                # entry point (called by GitHub Action)
    ├── search.py             # OpenAlex + Europe PMC queries
    ├── fetch.py              # OA text retrieval
    ├── extract.py            # Gemini extraction call
    └── merge.py              # schema-safe append into metadatabase.json
```
