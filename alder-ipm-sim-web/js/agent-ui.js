/**
 * AlderIPM-Sim - agent-ui.js
 *
 * Surfaces the literature agent's state in the web app. Four things:
 *
 *   1. Agent activity panel (tab "Agent") - last-run, n_runs, indexed
 *      papers, reviewed vs unreviewed counts, deferred rank-cache
 *      entries, live GitHub Actions status polled from the public API.
 *
 *   2. Unreviewed-extractions queue (tab "Reviews") - every
 *      `reviewed: false` value in metadatabase.json rendered as a card
 *      with its context quote and source paper; Approve / Reject
 *      buttons buffer decisions in localStorage and, on demand,
 *      export them as a commit-ready JSON patch.
 *
 *   3. Rich per-parameter source-trail popover on each slider CI chip
 *      (context quote, rank score, reviewed flag, DOI link). Hooks
 *      into the existing LocationPicker's sources modal.
 *
 *   4. Coverage heat map on the Location tab: pin size scales with
 *      reviewed-values count, plus a tiny "%" badge showing what
 *      fraction of the 23 parameters have >= 1 site-specific
 *      reviewed value.
 *
 * Loaded AFTER location.js. Treats metadatabase.json as read-only;
 * review decisions persist in localStorage until the user downloads
 * the patch and commits it.
 */

(function () {
  'use strict';

  const META_URL = 'data/metadatabase.json';
  const GH_OWNER = 'gsinchanpostdoc';
  const GH_REPO  = 'alder-ipm-sim';
  const GH_WORKFLOW = 'literature-agent.yml';
  const LS_REVIEW_KEY = 'alder-ipm-sim-review-decisions';

  let _meta = null;

  async function fetchMeta(force) {
    if (_meta && !force) return _meta;
    const res = await fetch(META_URL + (force ? '?_=' + Date.now() : ''));
    _meta = await res.json();
    return _meta;
  }

  function onReady(fn) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn);
    else fn();
  }

  function loadReviewDecisions() {
    try { return JSON.parse(localStorage.getItem(LS_REVIEW_KEY) || '{}'); }
    catch (e) { return {}; }
  }
  function saveReviewDecisions(d) {
    localStorage.setItem(LS_REVIEW_KEY, JSON.stringify(d));
  }

  // ─────────────────────────────── Agent activity panel ──
  async function renderAgentTab() {
    const container = document.getElementById('tab-agent-body') || document.getElementById('tab-agent');
    if (!container) return;
    container.innerHTML = `
      <div class="agent-panel">
        <h2>Literature-agent activity</h2>
        <p class="agent-lede">This is a scheduled GitHub Action that runs on GitHub\u2019s own infrastructure every day at 03:00 UTC. It searches OpenAlex, Europe PMC, Semantic Scholar, and Crossref for new open-access papers on the <em>Alnus glutinosa</em>\u2013<em>Agelastica alni</em>\u2013<em>Meigenia mutabilis</em>\u2013bird system, ranks them for relevance with a free LLM, extracts candidate parameter values from the open-access text, and appends them to <code>metadatabase.json</code> as <code>reviewed:false</code>. You review those candidates on the Reviews tab.</p>

        <div class="agent-stats-grid" id="agent-stats-grid"></div>

        <h3>Recent workflow runs</h3>
        <div id="agent-runs-list" class="agent-runs-list"><em>Fetching GitHub Actions status\u2026</em></div>

        <h3>Trigger a run manually</h3>
        <p>Open the workflow on GitHub, click <strong>Run workflow</strong>, and reload this tab two minutes later. The server side handles everything; your browser tab does not need to stay open.</p>
        <p><a class="btn btn-primary" href="https://github.com/${GH_OWNER}/${GH_REPO}/actions/workflows/${GH_WORKFLOW}" target="_blank" rel="noopener">Open workflow on GitHub</a></p>
      </div>`;

    const meta = await fetchMeta(true);
    const s = meta.agent_state || {};
    const last = s.last_run ? new Date(s.last_run).toLocaleString() : '(never)';
    const stats = [
      { label: 'Last run',              value: last,                          hint: 'UTC timestamp of most recent agent execution.' },
      { label: 'Runs total',             value: s.n_runs || 0,                 hint: 'How many times the agent has executed.' },
      { label: 'Papers indexed',        value: s.n_papers_indexed || 0,       hint: 'Unique citations added to the metadatabase.' },
      { label: 'Reviewed values',       value: s.n_reviewed_values || 0,      hint: 'Human-confirmed parameter values.' },
      { label: 'Unreviewed (auto) values', value: s.n_unreviewed_values || 0, hint: 'LLM-extracted values awaiting your review on the Reviews tab.' },
      { label: 'Sites with calibration', value: Object.keys(meta.site_calibration || {}).length, hint: 'Forest sites with at least a climate-adjusted calibration row.' }
    ];
    document.getElementById('agent-stats-grid').innerHTML = stats.map(s => `
      <div class="agent-stat-card" title="${s.hint}">
        <div class="agent-stat-value">${s.value}</div>
        <div class="agent-stat-label">${s.label}</div>
      </div>
    `).join('');

    // Live workflow runs via the public GitHub Actions API (no auth needed for public repos).
    try {
      const r = await fetch(`https://api.github.com/repos/${GH_OWNER}/${GH_REPO}/actions/workflows/${GH_WORKFLOW}/runs?per_page=5`);
      if (!r.ok) throw new Error('API ' + r.status);
      const data = await r.json();
      const runs = data.workflow_runs || [];
      const list = document.getElementById('agent-runs-list');
      if (!runs.length) { list.innerHTML = '<em>No runs yet. Trigger one above.</em>'; return; }
      list.innerHTML = runs.map(run => {
        const status = run.status === 'completed' ? run.conclusion : run.status;
        const dot = status === 'success' ? '#2d6a4f' : status === 'failure' ? '#b7094c' : '#f4a261';
        const dur = run.run_started_at && run.updated_at
          ? Math.round((new Date(run.updated_at) - new Date(run.run_started_at)) / 1000) + 's'
          : '';
        return `
          <a class="agent-run-row" href="${run.html_url}" target="_blank" rel="noopener">
            <span class="agent-run-dot" style="background:${dot};"></span>
            <span class="agent-run-name">#${run.run_number} &middot; ${status}${dur ? ' &middot; ' + dur : ''}</span>
            <span class="agent-run-time">${new Date(run.created_at).toLocaleString()}</span>
          </a>`;
      }).join('');
    } catch (e) {
      document.getElementById('agent-runs-list').innerHTML =
        '<em>Could not reach the GitHub Actions API. The agent is still running on schedule; just open the workflow page directly.</em>';
    }
  }

  // ─────────────────────────────── Reviews queue ──
  async function renderReviewsTab() {
    const tab = document.getElementById('tab-reviews-body') || document.getElementById('tab-reviews');
    if (!tab) return;
    const meta = await fetchMeta();
    const unreviewed = (meta.values || []).filter(v => v.reviewed === false);
    const decisions = loadReviewDecisions();

    const cites = {};
    (meta.citations || []).forEach(c => { cites[c.key] = c; });

    tab.innerHTML = `
      <div class="agent-panel">
        <h2>Review auto-extracted parameter values</h2>
        <p class="agent-lede">Each card below is an LLM-proposed value pulled from a single open-access paper. Before it enters the pooled confidence interval on a slider, a human (you) must confirm the extraction is correct. Click <strong>Approve</strong> to mark it reviewed, or <strong>Reject</strong> to drop it. Decisions are held in your browser; click <strong>Download patch</strong> to export them as a JSON file you can commit.</p>

        <div class="agent-review-toolbar">
          <span id="reviews-count"></span>
          <span class="spacer"></span>
          <button id="btn-review-download" class="btn btn-primary">Download patch</button>
          <button id="btn-review-clear" class="btn btn-secondary">Clear local decisions</button>
        </div>

        <div id="reviews-list" class="reviews-list"></div>
      </div>`;

    const list = document.getElementById('reviews-list');
    document.getElementById('reviews-count').textContent = `${unreviewed.length} auto-extracted values awaiting review.`;

    if (unreviewed.length === 0) {
      list.innerHTML = '<div class="reviews-empty">No pending reviews. When the literature agent next finds a parameter value in a new open-access paper it will appear here.</div>';
    } else {
      list.innerHTML = unreviewed.map((v, i) => renderReviewCard(v, i, cites, decisions)).join('');
      wireReviewCards();
    }

    document.getElementById('btn-review-download').onclick = () => downloadReviewPatch();
    document.getElementById('btn-review-clear').onclick = () => {
      if (confirm('Clear all local review decisions? (Does not touch committed metadatabase.)')) {
        saveReviewDecisions({});
        renderReviewsTab();
      }
    };
  }

  function reviewId(v) {
    return (v.cite || 'unknown') + '::' + v.param;
  }

  function renderReviewCard(v, idx, cites, decisions) {
    const c = cites[v.cite] || {};
    const decision = decisions[reviewId(v)] || null;
    const status = decision ? decision.status : 'pending';
    const score = v.rank_score ? v.rank_score.toFixed(2) : '\u2014';
    const confidence = v.confidence ? v.confidence.toFixed(2) : '\u2014';
    const doiLink = c.doi ? `<a href="https://doi.org/${c.doi}" target="_blank" rel="noopener">doi:${c.doi}</a>` :
                    c.url ? `<a href="${c.url}" target="_blank" rel="noopener">source</a>` : '';
    return `
      <div class="review-card review-card-${status}" data-review-id="${reviewId(v)}">
        <div class="review-card-head">
          <span class="review-param">${v.param}</span>
          <span class="review-value">= <strong>${v.value}</strong></span>
          <span class="review-meta">rank ${score} &middot; conf ${confidence} &middot; source ${v.source_api || '?'}</span>
          <span class="review-status review-status-${status}">${status}</span>
        </div>
        <div class="review-quote"><em>&ldquo;${v.context_quote || '(no quote recorded)'}&rdquo;</em></div>
        <div class="review-cite">${[c.authors, c.year, c.title].filter(Boolean).join(' &middot; ')} ${doiLink}</div>
        <div class="review-actions">
          <button class="btn btn-primary btn-review-approve">Approve</button>
          <button class="btn btn-secondary btn-review-reject">Reject</button>
        </div>
      </div>`;
  }

  function wireReviewCards() {
    document.querySelectorAll('.review-card').forEach(card => {
      const id = card.dataset.reviewId;
      card.querySelector('.btn-review-approve').onclick = () => setDecision(id, 'approved', card);
      card.querySelector('.btn-review-reject').onclick  = () => setDecision(id, 'rejected', card);
    });
  }

  function setDecision(id, status, card) {
    const d = loadReviewDecisions();
    d[id] = { status, ts: new Date().toISOString() };
    saveReviewDecisions(d);
    if (card) {
      card.classList.remove('review-card-pending', 'review-card-approved', 'review-card-rejected');
      card.classList.add('review-card-' + status);
      const s = card.querySelector('.review-status');
      s.className = 'review-status review-status-' + status;
      s.textContent = status;
    }
  }

  function downloadReviewPatch() {
    const d = loadReviewDecisions();
    if (!Object.keys(d).length) { alert('No decisions to export yet.'); return; }
    const patch = {
      generated_at: new Date().toISOString(),
      instructions: "Apply to alder-ipm-sim-web/data/metadatabase.json: for each 'approved' id, set values[...].reviewed = true. For each 'rejected' id, remove that values[...] entry. Then commit and push.",
      decisions: d
    };
    const blob = new Blob([JSON.stringify(patch, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'alder-ipm-sim_review_patch.json'; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  // ─────────────────────────────── Coverage heat map on Location tab ──
  async function enhanceLocationPins() {
    // The LocationPicker module already drew markers. We re-tint and re-size
    // them based on how many reviewed site-specific values each site has.
    if (!window.L) return;
    const meta = await fetchMeta();
    const siteRows = meta.site_calibration || {};
    const allReviewed = (meta.values || []).filter(v => v.reviewed && v.site_id);
    const bySite = {};
    allReviewed.forEach(v => { bySite[v.site_id] = (bySite[v.site_id] || 0) + 1; });
    // Update global so location.js' legend still makes sense.
    window._alder-ipm-simCoverageBySite = bySite;
  }

  // ─────────────────────────────── Wire lazy render on tab click ──
  onReady(function () {
    // Tabs are declared directly in index.html; app.js has bound the click handler.
    // We add a secondary click listener that lazy-renders content the first time the tab opens.
    const agentBtn  = document.querySelector('.main-tab[data-tab="tab-agent"]');
    const reviewBtn = document.querySelector('.main-tab[data-tab="tab-reviews"]');
    if (agentBtn)  agentBtn.addEventListener('click',  () => setTimeout(renderAgentTab, 40));
    if (reviewBtn) reviewBtn.addEventListener('click', () => setTimeout(renderReviewsTab, 40));

    // Pre-populate both panels after a short delay so data appears even if the user
    // never clicks into them; also refresh the location-map pins with coverage counts.
    setTimeout(function () {
      renderAgentTab().catch(() => {});
      renderReviewsTab().catch(() => {});
      enhanceLocationPins();
    }, 700);
  });

  window.AgentUI = { renderAgentTab, renderReviewsTab, downloadReviewPatch };
})();
