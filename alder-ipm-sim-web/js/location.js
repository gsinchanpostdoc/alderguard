/**
 * AlderIPM-Sim - location.js
 *
 * Location picker + per-site parameter calibration.
 *   - Renders a Leaflet map of Europe on the Location tab.
 *   - Draws a marker for every site in data/alder_sites.json, coloured by
 *     coverage level (seed / partial / complete) from data/metadatabase.json.
 *   - Clicking a marker loads the site-calibrated parameters, renders 95 %
 *     CI bands + citation chips on every slider, and shows a summary card
 *     with climate context + "Use calibrated" / "Keep custom" actions.
 *   - Header badge displays live metadatabase stats.
 *
 * Leaflet is loaded lazily from unpkg.com CDN when the Location tab opens.
 * Data files (alder_sites.json, metadatabase.json) are fetched once and
 * cached on window._alder-ipm-simLocationCache.
 */

(function () {
  'use strict';

  const SITES_URL = 'data/alder_sites.json';
  const META_URL  = 'data/metadatabase.json';

  const LEAFLET_CSS = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
  const LEAFLET_JS  = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';

  const COVERAGE_COLOR = {
    seed:     '#9ca3af',   // grey
    partial:  '#f4a261',   // amber
    complete: '#2d6a4f'    // green
  };

  // ────────────────────────────── Data fetch ──
  let _sitesPromise = null;
  let _metaPromise  = null;
  function fetchSites() {
    if (!_sitesPromise) _sitesPromise = fetch(SITES_URL).then(r => r.json());
    return _sitesPromise;
  }
  function fetchMeta() {
    if (!_metaPromise) _metaPromise = fetch(META_URL).then(r => r.json());
    return _metaPromise;
  }

  // ────────────────────────────── Leaflet lazy-load ──
  let _leafletReady = null;
  function ensureLeaflet() {
    if (_leafletReady) return _leafletReady;
    _leafletReady = new Promise((resolve, reject) => {
      // CSS
      if (!document.querySelector('link[data-leaflet]')) {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = LEAFLET_CSS;
        link.setAttribute('data-leaflet', 'true');
        document.head.appendChild(link);
      }
      // JS
      if (window.L) return resolve(window.L);
      const s = document.createElement('script');
      s.src = LEAFLET_JS;
      s.onload = () => resolve(window.L);
      s.onerror = () => reject(new Error('Failed to load Leaflet from CDN'));
      document.head.appendChild(s);
    });
    return _leafletReady;
  }

  // ────────────────────────────── Map render ──
  let _map = null;
  let _markers = [];
  async function renderMap() {
    const container = document.getElementById('loc-map');
    if (!container) return;
    if (_map) return;  // already rendered

    const [L, sites, meta] = await Promise.all([ensureLeaflet(), fetchSites(), fetchMeta()]);
    _map = L.map(container, { scrollWheelZoom: false }).setView([50.5, 12.0], 4);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 10
    }).addTo(_map);
    // Enable scroll-zoom after first click (prevents accidental zoom while scrolling the page).
    container.addEventListener('click', () => _map.scrollWheelZoom.enable(), { once: true });

    // Count reviewed site-specific values per site for heat-map sizing.
    const perSite = {};
    (meta.values || []).forEach(v => {
      if (v.reviewed && v.site_id) perSite[v.site_id] = (perSite[v.site_id] || 0) + 1;
    });
    const maxPerSite = Math.max(1, ...Object.values(perSite));
    const totalParams = 23;

    sites.sites.forEach(site => {
      const cov = (meta.site_calibration && meta.site_calibration[site.id] && meta.site_calibration[site.id].coverage) || 'seed';
      const color = COVERAGE_COLOR[cov] || COVERAGE_COLOR.seed;
      const n = perSite[site.id] || 0;
      const radius = 7 + 7 * (n / maxPerSite);           // 7..14 px
      const pct = Math.round(100 * n / totalParams);
      const marker = L.circleMarker([site.lat, site.lon], {
        radius,
        fillColor: color, color: '#fff', weight: 2,
        opacity: 1, fillOpacity: 0.82 + 0.18 * (n / maxPerSite)
      }).addTo(_map);
      marker.bindTooltip(
        `<strong>${site.name}</strong><br>${site.country}` +
        `<br><em>Coverage: ${cov}</em>` +
        `<br>${n}/${totalParams} parameters with reviewed values (${pct}%)`,
        { sticky: true }
      );
      marker.on('click', () => selectSite(site, meta));
      _markers.push({ site, marker, cov, n });
    });

    // Auto-fit to markers.
    if (_markers.length) {
      const bounds = L.latLngBounds(_markers.map(m => [m.site.lat, m.site.lon]));
      _map.fitBounds(bounds.pad(0.15), { animate: false });
    }
  }

  // ────────────────────────────── Site selection ──
  let _currentSite = null;
  async function selectSite(site, metaCached) {
    _currentSite = site;
    const meta = metaCached || await fetchMeta();
    const calib = buildSiteCalibration(site, meta);
    renderSiteCard(site, calib);
    applyCIBands(calib);          // CI bands + citation chips on sliders
    // Expose globally so the friendly banner can mention it.
    window._alder-ipm-simSelectedSite = { site, calib };
  }

  function buildSiteCalibration(site, meta) {
    // For each parameter, compute { mean, ci_low, ci_high, n, sources, reviewed_n, unreviewed_n, site_specific }
    // by starting from the pooled reviewed value and overlaying any per-site adjustments.
    const calib = {};
    const pooled = {};
    meta.values.forEach(v => {
      if (!pooled[v.param]) pooled[v.param] = [];
      pooled[v.param].push(v);
    });
    const siteRow = meta.site_calibration && meta.site_calibration[site.id];

    Object.keys(pooled).forEach(param => {
      const entries = pooled[param];
      const reviewed = entries.filter(e => e.reviewed);
      const chosen = reviewed.length ? reviewed : entries;
      const meanVal = chosen.reduce((a, b) => a + b.value, 0) / chosen.length;
      const loVal = Math.min.apply(null, chosen.map(e => e.ci_low));
      const hiVal = Math.max.apply(null, chosen.map(e => e.ci_high));
      const sources = [...new Set(chosen.map(e => e.cite))];

      let adjusted = meanVal;
      let note = null;
      if (siteRow && siteRow.climate_driven && siteRow.climate_driven[param]) {
        const adj = siteRow.climate_driven[param];
        adjusted = meanVal + (adj.adjust || 0);
        note = adj.reason || null;
      }

      calib[param] = {
        pooled_mean: meanVal,
        mean: adjusted,
        ci_low: loVal,
        ci_high: hiVal,
        n: chosen.length,
        n_reviewed: reviewed.length,
        n_unreviewed: entries.length - reviewed.length,
        sources,
        climate_note: note
      };
    });
    calib._sources_lookup = {};
    (meta.citations || []).forEach(c => { calib._sources_lookup[c.key] = c; });
    return calib;
  }

  // ────────────────────────────── UI: site card + actions ──
  function renderSiteCard(site, calib) {
    const card = document.getElementById('loc-site-card');
    if (!card) return;
    card.style.display = 'block';
    card.innerHTML = `
      <div class="loc-card-head">
        <div>
          <h3>${site.name}</h3>
          <div class="loc-sub">${site.country} &middot; ${site.region} &middot; ${site.lat.toFixed(2)}\u00b0 N, ${site.lon.toFixed(2)}\u00b0 E</div>
        </div>
        <div class="loc-climate">
          <span class="loc-climate-item"><span class="loc-num">${site.climate.winter_T_C.toFixed(1)} \u00b0C</span><span class="loc-lbl">Winter mean</span></span>
          <span class="loc-climate-item"><span class="loc-num">${site.climate.season_days}</span><span class="loc-lbl">Season days</span></span>
          <span class="loc-climate-item"><span class="loc-num">${site.climate.annual_precip_mm}</span><span class="loc-lbl">mm/yr</span></span>
        </div>
      </div>
      <p class="loc-advice">Calibrated parameters below mirror the pooled reviewed literature, adjusted for the local climate. Review the confidence intervals on each slider in the Parameters tab &mdash; override any value you are not satisfied with by dragging the slider.</p>
      <div class="loc-actions">
        <button class="btn btn-primary" id="loc-btn-apply">Apply calibrated parameters</button>
        <button class="btn btn-secondary" id="loc-btn-keep">Keep my custom values</button>
        <button class="btn btn-secondary" id="loc-btn-jump">Go to Parameters tab</button>
      </div>`;

    document.getElementById('loc-btn-apply').addEventListener('click', () => applyCalibrationToSliders(calib));
    document.getElementById('loc-btn-keep').addEventListener('click', () => {
      document.getElementById('loc-site-card').classList.add('loc-deemphasised');
    });
    document.getElementById('loc-btn-jump').addEventListener('click', () => {
      const tab = document.querySelector('.main-tab[data-tab="tab-parameters"]');
      if (tab) tab.click();
    });
  }

  function applyCalibrationToSliders(calib) {
    Object.keys(calib).forEach(param => {
      if (param.startsWith('_')) return;
      const slider = document.getElementById('slider-' + param);
      if (!slider) return;
      const val = calib[param].mean;
      // Clamp into slider min/max just in case.
      const min = parseFloat(slider.min), max = parseFloat(slider.max);
      slider.value = Math.max(min, Math.min(max, val));
      slider.dispatchEvent(new Event('input'));
    });
    const tab = document.querySelector('.main-tab[data-tab="tab-parameters"]');
    if (tab) tab.click();
  }

  // ────────────────────────────── UI: slider CI bands + citation chips ──
  function applyCIBands(calib) {
    if (typeof PARAM_REGISTRY === 'undefined') return;
    Object.keys(PARAM_REGISTRY).forEach(param => {
      const row = document.querySelector('.param-slider-row[data-param-key="' + param + '"]');
      if (!row) return;
      const slider = document.getElementById('slider-' + param);
      if (!slider) return;
      const info = calib[param];
      if (!info) return;
      const labelLine = row.querySelector('.param-label-line');
      // Remove any prior CI chip.
      const prior = labelLine.querySelector('.param-ci-chip');
      if (prior) prior.remove();
      const chip = document.createElement('span');
      chip.className = 'param-ci-chip';
      chip.title =
        'Literature-pooled 95% CI: [' + info.ci_low.toPrecision(3) + ', ' + info.ci_high.toPrecision(3) + ']\n' +
        'n = ' + info.n + ' studies (' + info.n_reviewed + ' reviewed' + (info.n_unreviewed ? ', ' + info.n_unreviewed + ' auto-extracted' : '') + ')\n' +
        'Sources: ' + info.sources.join(', ') +
        (info.climate_note ? '\nClimate adjustment: ' + info.climate_note : '');
      chip.innerHTML = 'CI [' + info.ci_low.toPrecision(2) + ', ' + info.ci_high.toPrecision(2) + '] <span class="param-ci-n">n=' + info.n + '</span>';
      chip.addEventListener('click', () => openSourcesModal(param, info, calib._sources_lookup));
      labelLine.appendChild(chip);

      // CI track behind the slider: position it using the min/max of the slider control.
      const controlLine = row.querySelector('.param-control-line');
      if (!controlLine) return;
      let track = controlLine.querySelector('.param-ci-track');
      if (!track) {
        track = document.createElement('div');
        track.className = 'param-ci-track';
        track.innerHTML = '<div class="param-ci-fill"></div>';
        controlLine.insertBefore(track, controlLine.firstChild);
      }
      const min = parseFloat(slider.min), max = parseFloat(slider.max);
      const lo = Math.max(0, (info.ci_low - min) / (max - min));
      const hi = Math.min(1, (info.ci_high - min) / (max - min));
      const fill = track.querySelector('.param-ci-fill');
      fill.style.left  = (lo * 100).toFixed(2) + '%';
      fill.style.width = Math.max(0, (hi - lo) * 100).toFixed(2) + '%';
    });
  }

  // ────────────────────────────── Sources modal ──
  async function openSourcesModal(param, info, sourcesLookup) {
    const prior = document.querySelector('.loc-sources-overlay');
    if (prior) prior.remove();

    // Reload metadata for per-study detail (context quotes, rank scores, review flags).
    let allValues = [];
    try {
      const r = await fetch('data/metadatabase.json?_=' + Date.now());
      const m = await r.json();
      allValues = (m.values || []).filter(v => v.param === param);
    } catch (e) { /* fall through */ }

    const studies = info.sources.map(k => {
      const c = sourcesLookup[k] || { key: k };
      const details = allValues.filter(v => v.cite === k);
      return { cite: k, c, details };
    });

    const overlay = document.createElement('div');
    overlay.className = 'loc-sources-overlay';
    overlay.innerHTML = `
      <div class="loc-sources-modal">
        <div class="loc-sources-head">
          <h3>Literature behind <code>${param}</code></h3>
          <button class="loc-sources-close" aria-label="Close">&times;</button>
        </div>
        <div class="loc-sources-body">
          <p><strong>Pooled estimate:</strong> ${info.mean.toPrecision(4)} &middot; <strong>95% CI:</strong> [${info.ci_low.toPrecision(3)}, ${info.ci_high.toPrecision(3)}]</p>
          <p><strong>Evidence base:</strong> ${info.n} studies (${info.n_reviewed} reviewed${info.n_unreviewed ? ', ' + info.n_unreviewed + ' auto-extracted' : ''}).</p>
          ${info.climate_note ? '<p><em>Climate adjustment:</em> ' + info.climate_note + '</p>' : ''}
          <h4>Studies</h4>
          <ul class="loc-sources-list">
            ${studies.map(s => {
              const c = s.c;
              const link = c.doi ? `<a href="https://doi.org/${c.doi}" target="_blank" rel="noopener">doi:${c.doi}</a>` :
                           c.url ? `<a href="${c.url}" target="_blank" rel="noopener">link</a>` : '';
              const header = (c.authors || s.cite) + ' (' + (c.year || '—') + '). <em>' + (c.title || '') + '</em>. ' + (c.venue || '') + ' ' + link;
              const detail = s.details.map(v => {
                const tag = v.reviewed
                  ? '<span class="study-tag study-tag-reviewed">reviewed</span>'
                  : '<span class="study-tag study-tag-auto">auto-extracted, unreviewed</span>';
                const rk = v.rank_score != null ? ` &middot; rank ${(+v.rank_score).toFixed(2)}` : '';
                const q  = v.context_quote ? `<blockquote class="study-quote">&ldquo;${v.context_quote}&rdquo;</blockquote>` : '';
                return `
                  <div class="study-detail">
                    <div>value = <strong>${v.value}</strong>${rk} ${tag}</div>
                    ${q}
                  </div>`;
              }).join('');
              return '<li>' + header + detail + '</li>';
            }).join('')}
          </ul>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('.loc-sources-close').addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
  }

  // ────────────────────────────── Header metadatabase badge ──
  async function renderHeaderBadge() {
    const meta = await fetchMeta();
    const host = document.querySelector('.header-actions');
    if (!host || document.getElementById('meta-badge')) return;
    const s = meta.agent_state || {};
    const badge = document.createElement('button');
    badge.id = 'meta-badge';
    badge.className = 'btn meta-badge';
    badge.title = 'Literature metadatabase stats. Click for details.';
    badge.innerHTML =
      '<span class="meta-dot"></span>' +
      '<span class="meta-badge-text">' +
        '<span class="meta-badge-line1">DB: ' + (s.n_papers_indexed || 0) + ' papers</span>' +
        '<span class="meta-badge-line2">' + (s.n_reviewed_values || 0) + ' reviewed &middot; ' + (s.n_unreviewed_values || 0) + ' auto</span>' +
      '</span>';
    host.insertBefore(badge, host.firstChild);
    badge.addEventListener('click', () => openMetaBadgeModal(meta));
  }

  function openMetaBadgeModal(meta) {
    const prior = document.querySelector('.loc-sources-overlay');
    if (prior) prior.remove();
    const updated = meta.agent_state && meta.agent_state.updated ? new Date(meta.agent_state.updated).toLocaleString() : 'never';
    const coverage = Object.entries(meta.site_calibration || {})
      .map(([k, v]) => '<li><code>' + k + '</code>: ' + (v.coverage || 'seed') + '</li>').join('');
    const overlay = document.createElement('div');
    overlay.className = 'loc-sources-overlay';
    overlay.innerHTML = `
      <div class="loc-sources-modal">
        <div class="loc-sources-head">
          <h3>Metadatabase &mdash; live stats</h3>
          <button class="loc-sources-close" aria-label="Close">&times;</button>
        </div>
        <div class="loc-sources-body">
          <p><strong>Last agent run:</strong> ${updated}</p>
          <p><strong>Papers indexed:</strong> ${meta.agent_state ? meta.agent_state.n_papers_indexed : 0}</p>
          <p><strong>Reviewed parameter values:</strong> ${meta.agent_state ? meta.agent_state.n_reviewed_values : 0}</p>
          <p><strong>Auto-extracted, awaiting review:</strong> ${meta.agent_state ? meta.agent_state.n_unreviewed_values : 0}</p>
          <p>Coverage advances grey (seed) \u2192 amber (partial) \u2192 green (complete) as reviewed values accumulate for each site.</p>
          <h4>Sites with non-seed coverage</h4>
          <ul class="loc-sources-list">${coverage || '<li><em>none yet \u2014 agent seed only</em></li>'}</ul>
          <p class="loc-hint">The agent is a scheduled GitHub Action (<code>.github/workflows/literature-agent.yml</code>) that runs on GitHub\u2019s free infrastructure, independent of your local machine. See <code>agent/README.md</code> to add your Gemini API key.</p>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('.loc-sources-close').addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
  }

  // ────────────────────────────── Boot ──
  function onReady(fn) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn);
    else fn();
  }

  onReady(async function () {
    // Wire the Location tab button to trigger map render on first open.
    const tabBtn = document.querySelector('.main-tab[data-tab="tab-location"]');
    if (tabBtn) tabBtn.addEventListener('click', () => setTimeout(renderMap, 40));
    // Header badge.
    try { await renderHeaderBadge(); } catch (e) { console.warn('Metadatabase badge could not render', e); }
    // Apply default CI bands (pooled values, no site yet) on page load.
    try {
      const meta = await fetchMeta();
      const calib = buildSiteCalibration({ id: null, climate: {} }, meta);
      // Wait a frame so app.js has built the parameter panel.
      setTimeout(() => applyCIBands(calib), 80);
    } catch (e) { console.warn('Initial CI bands could not render', e); }
  });

  window.LocationPicker = { renderMap, selectSite };

})();
