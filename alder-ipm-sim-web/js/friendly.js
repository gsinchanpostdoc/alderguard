/**
 * AlderIPM-Sim - friendly.js
 *
 * Non-specialist UX layer:
 *   1. Audience-mode toggle (Simple / Full). Simple mode hides the technical
 *      tabs (Equilibrium, Bifurcation, Fitting, Early Warnings) so newcomers
 *      see only Parameters, Simulation, Control Comparison, About. Persisted
 *      in localStorage under "alderipmsim-audience".
 *
 *   2. Scenario cards on the Parameters tab: four big clickable tiles that
 *      preload an ecologically meaningful parameter preset, jump to the
 *      Simulation tab, run the simulation, and render a plain-language
 *      interpretation banner.
 *
 *   3. Interpretation banners after Simulation and Control runs: translate
 *      R_P, peak defoliation, canopy status, and control-strategy winners
 *      into plain English with traffic-light colour codes.
 *
 * Loaded AFTER app.js. Touches nothing in app.js directly - hooks entirely
 * through DOM observation and button delegation.
 */

(function () {
  'use strict';

  // ─────────────────────────── audience mode ──
  const SIMPLE_HIDDEN_TABS = ['tab-equilibrium', 'tab-bifurcation', 'tab-fitting', 'tab-warnings'];

  function applyAudienceMode(mode) {
    document.body.setAttribute('data-audience', mode);
    SIMPLE_HIDDEN_TABS.forEach(tabId => {
      const btn = document.querySelector('.main-tab[data-tab="' + tabId + '"]');
      if (btn) btn.style.display = (mode === 'simple') ? 'none' : '';
    });
    // If the currently active tab is now hidden, jump back to Parameters.
    if (mode === 'simple') {
      const active = document.querySelector('.main-tab.active');
      if (active && SIMPLE_HIDDEN_TABS.includes(active.dataset.tab)) {
        const paramTab = document.querySelector('.main-tab[data-tab="tab-parameters"]');
        if (paramTab) paramTab.click();
      }
    }
    localStorage.setItem('alderipmsim-audience', mode);
    const btn = document.getElementById('btn-audience-mode');
    if (btn) {
      btn.innerHTML = '<span class="mode-dot mode-dot-' + mode + '"></span>' +
                      'Mode: ' + (mode === 'simple' ? 'Simple' : 'Full');
      btn.title = mode === 'simple'
        ? 'Switch to full technical view (shows Equilibrium, Bifurcation, Fitting, Early Warnings tabs)'
        : 'Switch to simplified view (hides advanced tabs for non-specialists)';
    }
  }

  // ─────────────────────────── scenario cards ──
  // Photo credits registry. Every image used in the UI is listed here so the
  // About/Help "Photo credits" section can be auto-generated. All sources are
  // Creative Commons with attribution; licensing terms respected per each
  // source's requirements (CC-BY-SA preserves share-alike on derivatives).
  const PHOTO_CREDITS = [
    {
      file: 'Alnus_glutinosa_002.jpg',
      title: 'Alnus glutinosa (black alder) at a pond, Hunsr\u00fcck, Germany',
      author: 'Nikanos',
      license: 'CC BY-SA 2.5',
      license_url: 'https://creativecommons.org/licenses/by-sa/2.5/',
      source_url: 'https://commons.wikimedia.org/wiki/File:Alnus_glutinosa_002.jpg',
      usage: 'Scenario cards (healthy forest, warmer winters); Tree/Foliage parameter group'
    },
    {
      file: 'Agelastica_alni_(aka).jpg',
      title: 'Agelastica alni (alder leaf beetle) adult, 7.1 mm',
      author: 'Andr\u00e9 Karwath (Aka)',
      license: 'CC BY-SA 2.5',
      license_url: 'https://creativecommons.org/licenses/by-sa/2.5/',
      source_url: 'https://commons.wikimedia.org/wiki/File:Agelastica_alni_(aka).jpg',
      usage: 'Scenario card (outbreak risk); Beetle parameter group'
    },
    {
      file: 'Focus_stacking_Tachinid_fly.jpg',
      title: 'Tachinid fly (Tachinidae) \u2014 focus-stacked macro',
      author: 'Muhammad Mahdi Karim',
      license: 'CC BY-SA 3.0 / GFDL 1.2',
      license_url: 'https://creativecommons.org/licenses/by-sa/3.0/',
      source_url: 'https://commons.wikimedia.org/wiki/File:Focus_stacking_Tachinid_fly.jpg',
      usage: 'Parasitoid parameter group (Meigenia mutabilis is a tachinid)'
    },
    {
      file: 'A_tit_on_my_fatballs_(26251618102).jpg',
      title: 'Great tit (Parus major)',
      author: 'Airwolfhound (Hertfordshire, UK)',
      license: 'CC BY-SA 2.0',
      license_url: 'https://creativecommons.org/licenses/by-sa/2.0/',
      source_url: 'https://commons.wikimedia.org/wiki/File:A_tit_on_my_fatballs_(26251618102).jpg',
      usage: 'Scenario card (managed forest); Bird parameter group'
    }
  ];

  // Wikimedia Special:FilePath redirects to the full-resolution image; appending
  // ?width=480 returns a scaled thumbnail hosted on the Commons CDN.
  const WM = 'https://commons.wikimedia.org/wiki/Special:FilePath/';
  const PHOTO_URLS = {
    alder:      WM + 'Alnus_glutinosa_002.jpg?width=480',
    beetle:     WM + 'Agelastica_alni_(aka).jpg?width=480',
    tachinid:   WM + 'Focus_stacking_Tachinid_fly.jpg?width=480',
    great_tit:  WM + 'A_tit_on_my_fatballs_(26251618102).jpg?width=480'
  };

  // Each card names a preset key from PRESETS (see parameters.js) plus a
  // plain-language label, one-sentence tagline, a colour, and a photo URL.
  const SCENARIO_CARDS = [
    {
      preset: 'baseline_calibrated',
      title: 'Healthy forest baseline',
      tagline: 'Current observed conditions. See how the system behaves without intervention.',
      accent: '#40916c',
      icon: 'tree',
      photo: PHOTO_URLS.alder,
      photo_alt: 'Alnus glutinosa at a pond (photo: Nikanos, CC BY-SA 2.5)'
    },
    {
      preset: 'outbreak_risk',
      title: 'Outbreak risk',
      tagline: 'High beetle fecundity, warm winters, weak canopy recovery. When does the forest collapse?',
      accent: '#e76f51',
      icon: 'warning',
      photo: PHOTO_URLS.beetle,
      photo_alt: 'Agelastica alni close-up (photo: Andr\u00e9 Karwath, CC BY-SA 2.5)'
    },
    {
      preset: 'warm_winter',
      title: 'Warmer winters',
      tagline: 'Climate change boosts overwinter survival and lengthens the larval season.',
      accent: '#f4a261',
      icon: 'sun',
      photo: PHOTO_URLS.alder,
      photo_alt: 'Alnus glutinosa (photo: Nikanos, CC BY-SA 2.5)'
    },
    {
      preset: 'managed_forest',
      title: 'Managed forest',
      tagline: 'Integrated pest management with biocontrol, larval removal, and bird habitat.',
      accent: '#2d6a4f',
      icon: 'shield',
      photo: PHOTO_URLS.great_tit,
      photo_alt: 'Great tit (photo: Airwolfhound, CC BY-SA 2.0)'
    }
  ];

  // Tiny inline SVG icon set (no external dependency, renders in every browser).
  function iconSVG(name, color) {
    const icons = {
      tree:    '<path d="M32 6L20 24h6L16 38h8L12 52h40L40 38h8L38 24h6z" fill="' + color + '"/><rect x="29" y="50" width="6" height="8" fill="#8d6e63"/>',
      warning: '<path d="M32 8l28 48H4z" fill="' + color + '"/><rect x="30" y="24" width="4" height="16" fill="#fff"/><circle cx="32" cy="46" r="2.5" fill="#fff"/>',
      sun:     '<circle cx="32" cy="32" r="12" fill="' + color + '"/><g stroke="' + color + '" stroke-width="4" stroke-linecap="round"><line x1="32" y1="6" x2="32" y2="14"/><line x1="32" y1="50" x2="32" y2="58"/><line x1="6" y1="32" x2="14" y2="32"/><line x1="50" y1="32" x2="58" y2="32"/><line x1="14" y1="14" x2="20" y2="20"/><line x1="44" y1="44" x2="50" y2="50"/><line x1="14" y1="50" x2="20" y2="44"/><line x1="44" y1="20" x2="50" y2="14"/></g>',
      shield:  '<path d="M32 6l22 8v16c0 14-10 24-22 28-12-4-22-14-22-28V14z" fill="' + color + '"/><path d="M22 32l7 7 13-14" stroke="#fff" stroke-width="4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
    };
    return '<svg viewBox="0 0 64 64" width="44" height="44" aria-hidden="true">' + (icons[name] || '') + '</svg>';
  }

  function renderScenarioCards() {
    // Inject a banner container at the top of the Parameters tab.
    const paramTab = document.getElementById('tab-parameters');
    if (!paramTab || document.getElementById('scenario-cards')) return;
    const section = document.createElement('section');
    section.id = 'scenario-cards';
    section.className = 'scenario-cards-wrap';
    section.innerHTML = `
      <div class="scenario-cards-header">
        <h2>Try a scenario</h2>
        <p>New here? Click a card below. It loads the matching conditions and runs a 50-year simulation so you can see the outcome before touching any slider.</p>
      </div>
      <div class="scenario-cards-grid">
        ${SCENARIO_CARDS.map(card => `
          <button class="scenario-card" data-preset="${card.preset}" aria-label="Load ${card.title} scenario">
            <span class="scenario-card-photo" style="background:${card.accent}1a;">
              <img src="${card.photo}"
                   alt="${card.photo_alt}"
                   loading="lazy"
                   referrerpolicy="no-referrer"
                   onerror="this.style.display='none'; this.nextElementSibling.style.display='inline-flex';" />
              <span class="scenario-card-fallback" style="display:none;">${iconSVG(card.icon, card.accent)}</span>
            </span>
            <span class="scenario-card-body">
              <span class="scenario-card-title">${card.title}</span>
              <span class="scenario-card-tagline">${card.tagline}</span>
            </span>
            <span class="scenario-card-go" style="color:${card.accent};">Load &amp; simulate &rarr;</span>
          </button>
        `).join('')}
      </div>
    `;
    paramTab.insertBefore(section, paramTab.firstChild);

    section.querySelectorAll('.scenario-card').forEach(btn => {
      btn.addEventListener('click', () => loadAndRunScenario(btn.dataset.preset));
    });
  }

  function loadAndRunScenario(presetKey) {
    if (typeof PRESETS === 'undefined' || !PRESETS[presetKey]) return;
    const preset = PRESETS[presetKey];
    // Reset to defaults first, then apply preset deltas. Mirrors the preset-select dropdown logic.
    const defaults = getDefaults();
    Object.keys(defaults).forEach(key => {
      const slider = document.getElementById('slider-' + key);
      if (!slider) return;
      const v = (preset.params && preset.params[key] !== undefined) ? preset.params[key] : defaults[key];
      slider.value = v;
      slider.dispatchEvent(new Event('input'));
    });
    // Update the preset dropdown so the user sees which scenario is active.
    const presetSelect = document.getElementById('preset-select');
    if (presetSelect) {
      presetSelect.value = presetKey;
      presetSelect.dispatchEvent(new Event('change'));
    }

    // Jump to Simulation tab and click Run.
    const simTab = document.querySelector('.main-tab[data-tab="tab-simulation"]');
    if (simTab) simTab.click();
    setTimeout(function () {
      const runBtn = document.getElementById('btn-run-sim');
      if (runBtn) runBtn.click();
      // Scroll the interpretation banner into view once it renders.
      setTimeout(() => {
        const banner = document.getElementById('sim-interpret-banner');
        if (banner) banner.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 150);
    }, 60);
  }

  // ─────────────────────────── simulation banner ──
  function ensureSimBanner() {
    if (document.getElementById('sim-interpret-banner')) return;
    const summary = document.getElementById('sim-summary');
    if (!summary) return;
    const banner = document.createElement('div');
    banner.id = 'sim-interpret-banner';
    banner.className = 'interpret-banner';
    summary.parentNode.insertBefore(banner, summary);
  }

  function renderSimBanner() {
    ensureSimBanner();
    const banner = document.getElementById('sim-interpret-banner');
    if (!banner) return;

    const statusEl = document.getElementById('sum-status');
    const rpEl     = document.getElementById('sum-rp');
    const peakAEl  = document.getElementById('sum-peak-a');
    const peakDEl  = document.getElementById('sum-peak-d');
    const finalKEl = document.getElementById('sum-final-k');
    if (!statusEl || !rpEl) return;

    const status = statusEl.textContent.trim().toLowerCase();
    const rp = parseFloat(rpEl.textContent);
    const peakA = parseFloat(peakAEl ? peakAEl.textContent : NaN);
    const peakD = parseFloat(peakDEl ? peakDEl.textContent : NaN);
    const finalK = parseFloat(finalKEl ? finalKEl.textContent : NaN);

    // Translate numbers into plain language.
    let headline, verdict, color, advice;
    if (/collaps|dieback|outbreak/.test(status) || peakD > 0.7) {
      headline = 'High risk of canopy damage';
      verdict = 'The simulation shows ' + fmtPct(peakD) + ' peak defoliation and final canopy capacity around ' + safe(finalK) + '. Defoliation above 50% is associated with long-term canopy loss.';
      color = '#b7094c';
      advice = 'Try the Control Comparison tab to see how biocontrol, larval removal, and bird-habitat enhancement each reduce the damage.';
    } else if (/stress|warning|amber/.test(status) || peakD > 0.4) {
      headline = 'Moderate pressure';
      verdict = 'The beetle persists with ' + fmtPct(peakD) + ' peak defoliation. Canopy recovers between outbreak years but remains below full capacity.';
      color = '#f4a261';
      advice = 'Try increasing bird habitat (u_B^max) or strengthening the canopy-feedback term (phi) in Parameters to see if pressure eases.';
    } else {
      headline = 'Healthy forest';
      verdict = 'Peak defoliation stays around ' + fmtPct(peakD) + ' and canopy capacity ends near ' + safe(finalK) + '. The beetle does not escape natural regulation.';
      color = '#2d6a4f';
      advice = 'Try the Outbreak Risk scenario card to see what breaks this balance.';
    }

    // R_P interpretation
    let rpText;
    if (!Number.isFinite(rp)) {
      rpText = '';
    } else if (rp > 1.2) {
      rpText = 'R<sub>P</sub> = ' + rp.toFixed(2) + ' (&gt; 1 &mdash; <em>parasitoids establish and regulate the beetle</em>)';
    } else if (rp > 0.8) {
      rpText = 'R<sub>P</sub> = ' + rp.toFixed(2) + ' (near 1 &mdash; <em>parasitoid persistence is marginal</em>)';
    } else {
      rpText = 'R<sub>P</sub> = ' + rp.toFixed(2) + ' (&lt; 1 &mdash; <em>parasitoids cannot establish without augmentation</em>)';
    }

    banner.style.borderLeftColor = color;
    banner.style.display = 'block';
    banner.innerHTML = `
      <div class="interpret-row">
        <div class="interpret-dot" style="background:${color};"></div>
        <div>
          <div class="interpret-headline" style="color:${color};">${headline}</div>
          <div class="interpret-body">${verdict}</div>
          <div class="interpret-rp">${rpText}</div>
          <div class="interpret-advice"><strong>Next step:</strong> ${advice}</div>
        </div>
      </div>`;
  }

  function fmtPct(v) {
    if (!Number.isFinite(v)) return '--';
    return (v * 100).toFixed(0) + '%';
  }
  function safe(v) {
    return Number.isFinite(v) ? v.toFixed(2) : '--';
  }

  // ─────────────────────────── control banner ──
  function ensureControlBanner() {
    if (document.getElementById('ctrl-interpret-banner')) return;
    const tab = document.getElementById('tab-control');
    if (!tab) return;
    const banner = document.createElement('div');
    banner.id = 'ctrl-interpret-banner';
    banner.className = 'interpret-banner';
    banner.style.display = 'none';
    // Insert after the toolbar, before the results.
    const toolbar = tab.querySelector('.ctrl-toolbar');
    if (toolbar && toolbar.nextSibling) {
      toolbar.parentNode.insertBefore(banner, toolbar.nextSibling);
    } else {
      tab.appendChild(banner);
    }
  }

  function renderControlBanner() {
    ensureControlBanner();
    const banner = document.getElementById('ctrl-interpret-banner');
    if (!banner) return;
    // Look for a results table with strategy rows and a "best" status.
    const table = document.getElementById('ctrl-table') || document.querySelector('#tab-control table');
    if (!table) return;
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    if (rows.length === 0) return;

    // Heuristic: parse each row's first cell (strategy name), cost, finalK, finalD.
    const parsed = rows.map(r => {
      const cells = r.querySelectorAll('td');
      return {
        name: cells[0] ? cells[0].textContent.trim() : '',
        row: Array.from(cells).map(c => c.textContent.trim())
      };
    }).filter(x => x.name);
    if (parsed.length === 0) return;

    // Best strategy = smallest numeric in the second column (cost J) per Control Comparison table layout.
    const withCost = parsed.map(p => {
      const cost = parseFloat((p.row[1] || '').replace(/[^0-9.eE+\-]/g, ''));
      return Object.assign({}, p, { cost });
    });
    const finite = withCost.filter(x => Number.isFinite(x.cost));
    if (finite.length === 0) return;
    finite.sort((a, b) => a.cost - b.cost);
    const best = finite[0];
    const worst = finite[finite.length - 1];

    banner.style.display = 'block';
    banner.style.borderLeftColor = '#2d6a4f';
    banner.innerHTML = `
      <div class="interpret-row">
        <div class="interpret-dot" style="background:#2d6a4f;"></div>
        <div>
          <div class="interpret-headline" style="color:#2d6a4f;">Most cost-effective strategy: ${best.name}</div>
          <div class="interpret-body">
            Across ${finite.length} strategies, <strong>${best.name}</strong> delivers the lowest cost functional
            (${best.cost.toFixed(2)}) while <strong>${worst.name}</strong> is the most expensive
            (${worst.cost.toFixed(2)}). Lower cost means less defoliation and/or less input spending.
          </div>
          <div class="interpret-advice"><strong>Next step:</strong> Adjust the cost weights on the left to reflect your own priorities &mdash; e.g., raise <em>w<sub>1</sub></em> if canopy protection matters more than budget.</div>
        </div>
      </div>`;
  }

  // ─────────────────────────── wire up ──
  function onReady(fn) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn);
    else fn();
  }

  onReady(function () {
    // Audience mode
    const savedMode = localStorage.getItem('alderipmsim-audience') || 'simple';
    const btn = document.getElementById('btn-audience-mode');
    if (btn) {
      btn.addEventListener('click', function () {
        const current = document.body.getAttribute('data-audience') || 'simple';
        applyAudienceMode(current === 'simple' ? 'full' : 'simple');
      });
    }
    applyAudienceMode(savedMode);

    // Scenario cards
    renderScenarioCards();

    // Parameter-group header photo chips (run after app.js builds the panel).
    setTimeout(renderGroupPhotos, 120);

    // Photo credits in About tab.
    renderPhotoCredits();

    // Hook simulation Run button for banner render
    const runSimBtn = document.getElementById('btn-run-sim');
    if (runSimBtn) {
      runSimBtn.addEventListener('click', function () {
        setTimeout(renderSimBanner, 80);
      });
    }

    // Hook control Run button - try several candidate IDs
    ['btn-run-ctrl', 'btn-run-control', 'btn-compare-ctrl', 'btn-run-compare'].forEach(id => {
      const b = document.getElementById(id);
      if (b) b.addEventListener('click', function () { setTimeout(renderControlBanner, 80); });
    });

    // Fallback: MutationObserver on control table body so we catch any button wiring variation.
    const ctrlTbody = document.getElementById('ctrl-tbody') || document.querySelector('#tab-control tbody');
    if (ctrlTbody) {
      const obs = new MutationObserver(function () { renderControlBanner(); });
      obs.observe(ctrlTbody, { childList: true });
    }
  });

  // ─────────────────────────── photo chips on parameter group headers ──
  function renderGroupPhotos() {
    const groups = [
      { id: 'group-tree',       photo: PHOTO_URLS.alder,     alt: 'Alnus glutinosa (Nikanos, CC BY-SA 2.5)' },
      { id: 'group-beetle',     photo: PHOTO_URLS.beetle,    alt: 'Agelastica alni (Andr\u00e9 Karwath, CC BY-SA 2.5)' },
      { id: 'group-parasitoid', photo: PHOTO_URLS.tachinid,  alt: 'Tachinid fly (Muhammad Mahdi Karim, CC BY-SA 3.0)' },
      { id: 'group-bird',       photo: PHOTO_URLS.great_tit, alt: 'Great tit (Airwolfhound, CC BY-SA 2.0)' }
    ];
    groups.forEach(g => {
      const box = document.getElementById(g.id);
      if (!box) return;
      const header = box.querySelector('.param-group-header');
      if (!header || header.querySelector('.group-photo-chip')) return;
      const chip = document.createElement('span');
      chip.className = 'group-photo-chip';
      chip.innerHTML = '<img src="' + g.photo + '" alt="' + g.alt + '" loading="lazy" referrerpolicy="no-referrer" onerror="this.style.opacity=0.2" />';
      header.insertBefore(chip, header.firstChild);
    });
  }

  // ─────────────────────────── photo credits panel in About ──
  function renderPhotoCredits() {
    const about = document.querySelector('#tab-about .about-container');
    if (!about || document.getElementById('about-photo-credits')) return;
    const section = document.createElement('div');
    section.className = 'about-section';
    section.id = 'about-photo-credits';
    section.innerHTML = `
      <h2>Photo credits</h2>
      <p>All photographs are used under their respective Creative Commons licences. Click any entry to open the source page on Wikimedia Commons.</p>
      <ul class="photo-credits-list">
        ${PHOTO_CREDITS.map(p => `
          <li>
            <a href="${p.source_url}" target="_blank" rel="noopener"><strong>${p.title}</strong></a><br>
            Author: ${p.author} &middot; Licence: <a href="${p.license_url}" target="_blank" rel="noopener">${p.license}</a><br>
            <span class="photo-credits-usage">Used for: ${p.usage}</span>
          </li>
        `).join('')}
      </ul>`;
    about.appendChild(section);
  }

  // Public for testing
  window.Friendly = { applyAudienceMode, renderSimBanner, renderControlBanner, loadAndRunScenario, renderGroupPhotos, renderPhotoCredits };

})();
