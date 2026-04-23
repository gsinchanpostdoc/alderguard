/**
 * AlderIPM-Sim - wiring.js
 *
 * Glue code for the new comprehensive-edition features:
 *   - Use-in-R and Use-in-Python header buttons
 *   - Fitting tab (CSV upload, parameter checklist, run fit, render results)
 *   - Basin stability button in the Equilibrium tab
 *
 * Loaded AFTER app.js so that window.App is available. Does not modify app.js.
 */

(function () {
  'use strict';

  // Wait for DOM + App to be ready.
  function onReady(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  onReady(function () {

    // ─────────────────────────── cross-language header buttons ──
    const btnR = document.getElementById('btn-use-r');
    const btnPy = document.getElementById('btn-use-py');
    if (btnR) btnR.addEventListener('click', () => {
      const p = (window.App && App.readParams) ? App.readParams() : getDefaults();
      CrossLang.openRPanel(p);
    });
    if (btnPy) btnPy.addEventListener('click', () => {
      const p = (window.App && App.readParams) ? App.readParams() : getDefaults();
      CrossLang.openPythonPanel(p);
    });

    // ─────────────────────────── build fitting parameter checklist ──
    const fitChecklist = document.getElementById('fit-param-checklist');
    if (fitChecklist && typeof PARAM_REGISTRY !== 'undefined') {
      const suggested = new Set(['beta', 'c_B', 'phi', 'R_B', 'sigma_A', 'sigma_F']);
      Object.keys(PARAM_REGISTRY).forEach(key => {
        const meta = PARAM_REGISTRY[key];
        const id = 'fit-chk-' + key;
        const lbl = document.createElement('label');
        lbl.title = meta.description || key;
        lbl.innerHTML = `
          <input type="checkbox" id="${id}" value="${key}" ${suggested.has(key) ? 'checked' : ''} />
          <span>${meta.symbol} <span class="ew-hint">(${key})</span></span>`;
        fitChecklist.appendChild(lbl);
      });
    }

    // ─────────────────────────── fitting tab: CSV upload ──
    let fitData = null;
    const fitCSVFile = document.getElementById('fit-csv-file');
    const fitPreview = document.getElementById('fit-data-preview');
    const fitFilename = document.getElementById('fit-csv-filename');

    if (fitCSVFile) {
      fitCSVFile.addEventListener('change', function (e) {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = function (ev) {
          try {
            const parsed = FittingModule.parseFieldCSV(ev.target.result);
            const aligned = FittingModule.alignFieldData(parsed);
            fitData = aligned;
            fitFilename.textContent = `${file.name} (${parsed.rows.length} rows)`;
            const present = Object.keys(aligned.has).filter(k => aligned.has[k]).join(', ') || 'none';
            fitPreview.textContent = `Columns detected: ${parsed.columns.join(', ')} · Fit-able variables: ${present}`;
          } catch (err) {
            fitFilename.textContent = '';
            fitPreview.textContent = 'Error: ' + err.message;
            fitData = null;
          }
        };
        reader.readAsText(file);
      });
    }

    // ─────────────────────────── fitting tab: example data ──
    const btnFitExample = document.getElementById('btn-fit-example');
    if (btnFitExample) {
      btnFitExample.addEventListener('click', function () {
        // Generate synthetic field data from current params + noise
        const params = App.readParams();
        const model = new AlderIPMSimModel(params);
        const sim = model.simulate(1.0, 0.5, params.K_0, 0.0, 30, false);
        const rows = [];
        const header = 'year,A,F,K,D';
        rows.push(header);
        for (let t = 0; t <= 30; t++) {
          const noise = () => 1 + (Math.random() - 0.5) * 0.1;
          rows.push([
            t,
            (sim.A[t] * noise()).toFixed(4),
            (sim.F[t] * noise()).toFixed(4),
            (sim.K[t] * noise()).toFixed(4),
            (sim.D[t] * noise()).toFixed(4)
          ].join(','));
        }
        const csvText = rows.join('\n');
        const parsed = FittingModule.parseFieldCSV(csvText);
        fitData = FittingModule.alignFieldData(parsed);
        fitFilename.textContent = 'example_field_data.csv (31 rows, synthetic)';
        fitPreview.textContent = 'Columns: year, A, F, K, D · Synthetic data generated from current parameters with 10% noise.';
      });
    }

    // ─────────────────────────── fitting tab: run fit ──
    const btnRunFit = document.getElementById('btn-run-fit');
    if (btnRunFit) {
      btnRunFit.addEventListener('click', function () {
        if (!fitData) { alert('Please upload a CSV or click "Load Example" first.'); return; }
        const chosen = Array.from(
          document.querySelectorAll('#fit-param-checklist input:checked')
        ).map(c => c.value);
        if (chosen.length === 0) { alert('Select at least one parameter to fit.'); return; }
        if (chosen.length > 6) { alert('Maximum 6 parameters can be fit simultaneously.'); return; }

        const progress = document.getElementById('fit-progress');
        const results = document.getElementById('fit-results');
        progress.style.display = 'block';
        results.style.display = 'none';
        btnRunFit.disabled = true;

        // Extract bounds from registry
        const bounds = {};
        chosen.forEach(name => {
          const meta = PARAM_REGISTRY[name];
          if (meta && meta.min !== undefined && meta.max !== undefined) {
            bounds[name] = [meta.min, meta.max];
          }
        });

        const baseParams = App.readParams();
        const nObsYears = fitData.year.length - 1;
        const initial = {
          A0: parseFloat(document.getElementById('fit-A0').value) || 1.0,
          F0: parseFloat(document.getElementById('fit-F0').value) || 0.5,
          K0: baseParams.K_0 !== undefined ? baseParams.K_0 : 1.712,
          D0: parseFloat(document.getElementById('fit-D0').value) || 0.0
        };
        const maxIter = parseInt(document.getElementById('fit-maxiter').value) || 200;

        // Defer so UI can update
        setTimeout(function () {
          try {
            const result = FittingModule.fit({
              data: fitData,
              baseParams,
              fitParams: chosen,
              initial,
              nYears: nObsYears,
              bounds,
              maxIter
            });
            renderFitResults(result, fitData, initial, baseParams);
            window._lastFitResult = result;
            document.getElementById('btn-export-fit').style.display = 'inline-block';
            document.getElementById('btn-export-fit').onclick = function () {
              const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url; a.download = 'alder-ipm-sim_fit_result.json'; a.click();
              setTimeout(() => URL.revokeObjectURL(url), 100);
            };
          } catch (err) {
            alert('Fit failed: ' + err.message);
            console.error(err);
          } finally {
            progress.style.display = 'none';
            btnRunFit.disabled = false;
          }
        }, 30);
      });
    }

    // ─────────────────────────── render fit results ──
    function renderFitResults(result, data, initial, baseParams) {
      // Regime box
      const box = document.getElementById('fit-regime-box');
      const regime = result.regime;
      box.style.borderLeftColor = regime.color;
      box.innerHTML = `
        <span class="regime-label" style="color:${regime.color};">Forecast regime: ${regime.label}</span>
        <div>${regime.desc}</div>
        <div class="regime-rp">
          R<sub>P</sub> (with fitted params) = <strong>${Number.isFinite(regime.R_P) ? regime.R_P.toFixed(3) : 'n/a'}</strong> ·
          long-run means:
          A = ${regime.A_mean.toFixed(3)}, F = ${regime.F_mean.toFixed(3)},
          K = ${regime.K_mean.toFixed(3)}, D = ${regime.D_mean.toFixed(3)} ·
          NM iterations = ${result.iterations}, final SSE = ${result.finalSSE.toFixed(4)}
        </div>`;

      // Fitted params table
      const tbody = document.getElementById('fit-tbody');
      tbody.innerHTML = '';
      result.fitted.forEach(f => {
        const pct = f.initial !== 0 ? ((f.value - f.initial) / Math.abs(f.initial) * 100).toFixed(1) : 'n/a';
        const meta = PARAM_REGISTRY[f.name];
        const sym = meta ? meta.symbol : f.name;
        const row = document.createElement('tr');
        row.innerHTML = `<td>${sym} <span class="ew-hint">(${f.name})</span></td>
          <td>${f.initial.toPrecision(5)}</td>
          <td><strong>${f.value.toPrecision(5)}</strong></td>
          <td>${pct}%</td>`;
        tbody.appendChild(row);
      });

      // Residual diagnostics table
      const stbody = document.getElementById('fit-stats-tbody');
      stbody.innerHTML = '';
      Object.keys(result.stats).forEach(v => {
        const s = result.stats[v];
        const row = document.createElement('tr');
        row.innerHTML = `<td>${v}</td>
          <td>${s.n}</td>
          <td>${s.rmse.toFixed(4)}</td>
          <td>${s.r2.toFixed(3)}</td>
          <td>${Number.isFinite(s.acf1) ? s.acf1.toFixed(3) : '—'}</td>
          <td>${Number.isFinite(s.dw) ? s.dw.toFixed(3) : '—'}</td>`;
        stbody.appendChild(row);
      });

      // Overlay chart: observed vs fitted for each variable present
      const traces = [];
      const vars = ['A', 'F', 'K', 'D'];
      const colors = { A: '#e76f51', F: '#2a9d8f', K: '#264653', D: '#e9c46a' };
      vars.forEach(v => {
        if (!data.has[v]) return;
        const xObs = [], yObs = [];
        data.year.forEach((yr, i) => {
          if (Number.isFinite(data[v][i])) { xObs.push(yr); yObs.push(data[v][i]); }
        });
        traces.push({
          x: xObs, y: yObs, name: `${v} observed`, mode: 'markers',
          marker: { color: colors[v], size: 8, symbol: 'circle-open' }
        });
        traces.push({
          x: data.year, y: result.sim[v].slice(0, data.year.length),
          name: `${v} fitted`, mode: 'lines',
          line: { color: colors[v], width: 2 }
        });
      });
      Plotly.newPlot('chart-fit-overlay', traces, {
        title: 'Observed (markers) vs fitted (lines)',
        xaxis: { title: 'Year' }, yaxis: { title: 'Value' },
        legend: { orientation: 'h', y: -0.25 },
        margin: { l: 55, r: 20, t: 40, b: 50 },
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)'
      }, { responsive: true });

      // Residuals chart
      const residTraces = [];
      vars.forEach(v => {
        if (!data.has[v]) return;
        const xs = [], ys = [];
        result.residuals.filter(r => r.var === v).forEach(r => {
          xs.push(r.t); ys.push(r.r);
        });
        residTraces.push({ x: xs, y: ys, name: v, mode: 'markers+lines', marker: { color: colors[v] } });
      });
      residTraces.push({
        x: [Math.min(...data.year), Math.max(...data.year)], y: [0, 0],
        mode: 'lines', line: { color: '#888', dash: 'dash' },
        showlegend: false, hoverinfo: 'skip'
      });
      Plotly.newPlot('chart-fit-residuals', residTraces, {
        title: 'Residuals (fitted − observed)',
        xaxis: { title: 'Year' }, yaxis: { title: 'Residual' },
        legend: { orientation: 'h', y: -0.25 },
        margin: { l: 55, r: 20, t: 40, b: 50 },
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)'
      }, { responsive: true });

      // Forecast long-term projection
      const proj = regime.projection;
      const projX = proj.A.map((_, i) => i);
      Plotly.newPlot('chart-fit-forecast', [
        { x: projX, y: proj.A, name: 'A beetles', mode: 'lines', line: { color: colors.A } },
        { x: projX, y: proj.F, name: 'F parasitoids', mode: 'lines', line: { color: colors.F } },
        { x: projX, y: proj.K, name: 'K canopy', mode: 'lines', line: { color: colors.K } },
        { x: projX, y: proj.D, name: 'D defoliation', mode: 'lines', line: { color: colors.D } }
      ], {
        title: 'Projection under fitted parameters',
        xaxis: { title: 'Year' }, yaxis: { title: 'Value' },
        shapes: [{
          type: 'line', x0: data.year.length - 1, x1: data.year.length - 1,
          y0: 0, y1: 1, xref: 'x', yref: 'paper',
          line: { color: '#888', dash: 'dot', width: 1 }
        }],
        annotations: [{
          x: data.year.length - 1, y: 1, xref: 'x', yref: 'paper',
          text: 'data ends', showarrow: false, yanchor: 'bottom', font: { size: 11, color: '#888' }
        }],
        legend: { orientation: 'h', y: -0.2 },
        margin: { l: 55, r: 20, t: 40, b: 50 },
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)'
      }, { responsive: true });

      document.getElementById('fit-results').style.display = 'block';
    }

    // ─────────────────────────── basin stability ──
    const btnBasin = document.getElementById('btn-basin-stability');
    if (btnBasin) {
      btnBasin.addEventListener('click', function () {
        const params = App.readParams();
        btnBasin.disabled = true;
        btnBasin.textContent = 'Running...';
        setTimeout(function () {
          try {
            const result = CrossLang.basinStability(params, 120, 80);
            const box = document.getElementById('basin-results');
            const summary = document.getElementById('basin-summary');
            summary.innerHTML = `<strong>${result.nSamples}</strong> random initial conditions simulated · ${result.basins.length} distinct long-term regime${result.basins.length > 1 ? 's' : ''} identified.`;
            Plotly.newPlot('chart-basin', [{
              type: 'pie',
              labels: result.basins.map(b => b.label),
              values: result.basins.map(b => b.fraction),
              marker: { colors: result.basins.map(b => b.color) },
              textinfo: 'label+percent',
              hovertemplate: '%{label}<br>fraction: %{value:.1%}<extra></extra>'
            }], {
              title: 'Basin of attraction shares',
              margin: { l: 10, r: 10, t: 40, b: 10 },
              paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)'
            }, { responsive: true });
            box.style.display = 'block';
          } catch (err) {
            alert('Basin stability failed: ' + err.message);
          } finally {
            btnBasin.disabled = false;
            btnBasin.textContent = 'Basin Stability';
          }
        }, 30);
      });
    }

  });

})();
