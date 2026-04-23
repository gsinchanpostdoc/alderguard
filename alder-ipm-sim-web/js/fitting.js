/**
 * AlderIPM-Sim - Parameter Fitting Module
 *
 * Client-side parameter estimation against uploaded field data.
 * Implements:
 *   - CSV field-data parser (columns: year, A, F, K, D - any subset)
 *   - Nelder-Mead simplex optimizer (no external dependency)
 *   - Residual diagnostics (RMSE, R2, ACF(1), Durbin-Watson)
 *   - Regime forecast classification (extinction / parasitoid-free /
 *     coexistence / high-defoliation) based on fitted params
 *
 * Mirrors the fit_model() / forecast_regime() calls in alder-ipm-sim-py
 * (alder-ipm-sim/fitting.py) and alder-ipm-sim-r (R/fitting.R) so that the web
 * app is feature-comparable with the library packages.
 */

const FittingModule = (function () {

  // ─────────────────────────────────────────── CSV parsing ──
  /**
   * Parse a CSV string into {columns, rows}. Expects a header row.
   * Rows with non-numeric / missing values in a column are flagged
   * but not dropped - NaN is preserved so the loss function can skip them.
   */
  function parseFieldCSV(text) {
    const lines = text.replace(/\r/g, '').split('\n').filter(l => l.trim().length > 0);
    if (lines.length < 2) {
      throw new Error('CSV must contain a header row and at least one data row.');
    }
    const header = lines[0].split(',').map(s => s.trim());
    const rows = [];
    for (let i = 1; i < lines.length; i++) {
      const parts = lines[i].split(',').map(s => s.trim());
      const obj = {};
      header.forEach((h, j) => {
        const v = parts[j];
        obj[h] = (v === '' || v === undefined || v === 'NA' || v === 'NaN')
          ? NaN
          : Number(v);
      });
      rows.push(obj);
    }
    return { columns: header, rows };
  }

  /**
   * Given parsed CSV, identify which of {year,A,F,K,D} columns are present
   * and return clean parallel arrays.
   */
  function alignFieldData(parsed) {
    const cols = parsed.columns.map(c => c.toLowerCase());
    const idx = {};
    ['year', 'a', 'f', 'k', 'd'].forEach(name => {
      const i = cols.indexOf(name);
      if (i >= 0) idx[name] = parsed.columns[i];
    });
    if (idx.year === undefined) {
      // fall back to sequential years 0..n-1
      idx.year = null;
    }
    const aligned = { year: [], A: [], F: [], K: [], D: [] };
    parsed.rows.forEach((row, i) => {
      aligned.year.push(idx.year ? row[idx.year] : i);
      aligned.A.push(idx.a ? row[idx.a] : NaN);
      aligned.F.push(idx.f ? row[idx.f] : NaN);
      aligned.K.push(idx.k ? row[idx.k] : NaN);
      aligned.D.push(idx.d ? row[idx.d] : NaN);
    });
    aligned.has = {
      A: idx.a !== undefined,
      F: idx.f !== undefined,
      K: idx.k !== undefined,
      D: idx.d !== undefined
    };
    return aligned;
  }

  // ─────────────────────────────────────────── loss function ──
  /**
   * Sum of squared residuals between observed field data and
   * simulated annual-map trajectory, normalised per-variable so
   * that states with very different magnitudes contribute comparably.
   */
  function residualSSE(model, data, nYears, initialState) {
    const sim = model.simulate(
      initialState.A0, initialState.F0,
      initialState.K0, initialState.D0,
      nYears, false
    );
    let sse = 0;
    let n = 0;
    const residuals = [];
    ['A', 'F', 'K', 'D'].forEach(v => {
      if (!data.has[v]) return;
      // normalise by variance of observations to balance scales
      const obs = data[v];
      const finiteObs = obs.filter(x => Number.isFinite(x));
      if (finiteObs.length === 0) return;
      const mean = finiteObs.reduce((a, b) => a + b, 0) / finiteObs.length;
      const variance = finiteObs.reduce((a, b) => a + (b - mean) ** 2, 0) / finiteObs.length;
      const scale = Math.max(variance, 1e-6);
      for (let t = 0; t <= nYears && t < obs.length; t++) {
        const y_obs = obs[t];
        const y_sim = sim[v][t];
        if (Number.isFinite(y_obs)) {
          const r = (y_sim - y_obs);
          sse += (r * r) / scale;
          residuals.push({ var: v, t, sim: y_sim, obs: y_obs, r });
          n++;
        }
      }
    });
    return { sse, n, residuals, sim };
  }

  // ─────────────────────────────────────────── Nelder-Mead ──
  /**
   * Generic Nelder-Mead simplex optimisation on an objective f(x: number[]).
   * Returns { x: best point, f: best value, iterations, history }.
   * Convergence: relative change in f < tol OR maxIter reached.
   */
  function nelderMead(f, x0, opts) {
    opts = opts || {};
    const alpha = opts.alpha || 1.0;   // reflection
    const gamma = opts.gamma || 2.0;   // expansion
    const rho = opts.rho || 0.5;       // contraction
    const sigma = opts.sigma || 0.5;   // shrink
    const tol = opts.tol || 1e-5;
    const maxIter = opts.maxIter || 300;
    const step = opts.step || 0.1;     // initial simplex spread (relative)

    const n = x0.length;
    // build initial simplex
    const simplex = [x0.slice()];
    for (let i = 0; i < n; i++) {
      const v = x0.slice();
      const delta = v[i] !== 0 ? v[i] * step : step;
      v[i] = v[i] + delta;
      simplex.push(v);
    }
    let values = simplex.map(f);
    const history = [];

    for (let it = 0; it < maxIter; it++) {
      // sort simplex by value ascending
      const order = values.map((v, i) => [v, i]).sort((a, b) => a[0] - b[0]);
      const ordered = order.map(([_, i]) => simplex[i]);
      const orderedVals = order.map(([v, _]) => v);
      for (let i = 0; i < simplex.length; i++) {
        simplex[i] = ordered[i];
        values[i] = orderedVals[i];
      }
      history.push(values[0]);

      // termination
      const fbest = values[0], fworst = values[n];
      if (Math.abs(fworst - fbest) < tol * (1 + Math.abs(fbest))) {
        return { x: simplex[0], f: fbest, iterations: it, history };
      }

      // centroid of all but worst
      const centroid = new Array(n).fill(0);
      for (let i = 0; i < n; i++) {
        for (let j = 0; j < n; j++) centroid[j] += simplex[i][j];
      }
      for (let j = 0; j < n; j++) centroid[j] /= n;

      const worst = simplex[n];
      // reflect
      const reflected = centroid.map((c, j) => c + alpha * (c - worst[j]));
      const fR = f(reflected);
      if (fR < values[n - 1] && fR >= values[0]) {
        simplex[n] = reflected;
        values[n] = fR;
        continue;
      }
      if (fR < values[0]) {
        // expand
        const expanded = centroid.map((c, j) => c + gamma * (reflected[j] - c));
        const fE = f(expanded);
        if (fE < fR) { simplex[n] = expanded; values[n] = fE; }
        else { simplex[n] = reflected; values[n] = fR; }
        continue;
      }
      // contract
      const contracted = centroid.map((c, j) => c + rho * (worst[j] - c));
      const fC = f(contracted);
      if (fC < values[n]) { simplex[n] = contracted; values[n] = fC; continue; }
      // shrink
      const best = simplex[0];
      for (let i = 1; i <= n; i++) {
        for (let j = 0; j < n; j++) simplex[i][j] = best[j] + sigma * (simplex[i][j] - best[j]);
        values[i] = f(simplex[i]);
      }
    }
    // exhausted
    const order = values.map((v, i) => [v, i]).sort((a, b) => a[0] - b[0]);
    return { x: simplex[order[0][1]], f: order[0][0], iterations: maxIter, history };
  }

  // ─────────────────────────────────────────── fit driver ──
  /**
   * Main fit() API.
   * @param {Object} opts
   *   data:     object with {year,A,F,K,D,has} (from alignFieldData)
   *   baseParams: current parameter values (copy of app state)
   *   fitParams:  array of parameter names to estimate
   *   initial:  {A0,F0,K0,D0} initial conditions for simulation
   *   nYears:   number of annual steps to simulate
   *   bounds:   {paramName: [lo, hi]} optional per-param bounds
   *   maxIter:  NM iterations
   * @returns  { fitted, rmse, r2, dw, acf1, residuals, sim, regime }
   */
  function fit(opts) {
    const data = opts.data;
    const baseParams = Object.assign({}, opts.baseParams);
    const fitParams = opts.fitParams;
    const initial = opts.initial;
    const bounds = opts.bounds || {};
    const nYears = opts.nYears;

    if (!fitParams || fitParams.length === 0) {
      throw new Error('At least one parameter must be selected for fitting.');
    }
    if (fitParams.length > 6) {
      throw new Error('Maximum 6 parameters can be fit simultaneously.');
    }

    const x0 = fitParams.map(p => baseParams[p]);

    function unpack(x) {
      const params = Object.assign({}, baseParams);
      fitParams.forEach((name, i) => {
        let v = x[i];
        // apply soft bound clamp if provided
        if (bounds[name]) {
          const [lo, hi] = bounds[name];
          if (v < lo) v = lo;
          if (v > hi) v = hi;
        } else if (v < 0) {
          v = 1e-9;
        }
        params[name] = v;
      });
      return params;
    }

    function objective(x) {
      const params = unpack(x);
      const model = new AlderIPMSimModel(params);
      model.u_C = 0; model.u_P = 0;
      try {
        const { sse, n } = residualSSE(model, data, nYears, initial);
        if (!Number.isFinite(sse)) return 1e20;
        // penalty for hitting bounds (soft)
        let penalty = 0;
        fitParams.forEach((name, i) => {
          if (bounds[name]) {
            const [lo, hi] = bounds[name];
            if (x[i] < lo) penalty += (lo - x[i]) ** 2 * 1000;
            if (x[i] > hi) penalty += (x[i] - hi) ** 2 * 1000;
          }
        });
        return sse + penalty;
      } catch (e) {
        return 1e20;
      }
    }

    const result = nelderMead(objective, x0, {
      maxIter: opts.maxIter || 200,
      tol: 1e-6,
      step: 0.15
    });

    const fittedParams = unpack(result.x);
    const model = new AlderIPMSimModel(fittedParams);
    model.u_C = 0; model.u_P = 0;
    const { residuals, sim, n } = residualSSE(model, data, nYears, initial);

    // residual stats per variable
    const stats = {};
    ['A', 'F', 'K', 'D'].forEach(v => {
      if (!data.has[v]) return;
      const rs = residuals.filter(r => r.var === v);
      if (rs.length === 0) return;
      const obs = rs.map(r => r.obs);
      const sim_v = rs.map(r => r.sim);
      const resid = rs.map(r => r.r);
      const mean_obs = obs.reduce((a, b) => a + b, 0) / obs.length;
      const ss_tot = obs.reduce((a, b) => a + (b - mean_obs) ** 2, 0);
      const ss_res = resid.reduce((a, b) => a + b * b, 0);
      const rmse = Math.sqrt(ss_res / obs.length);
      const r2 = ss_tot > 0 ? 1 - ss_res / ss_tot : 0;
      // lag-1 autocorrelation of residuals
      let acf1 = NaN;
      if (resid.length >= 3) {
        const rmean = resid.reduce((a, b) => a + b, 0) / resid.length;
        let num = 0, den = 0;
        for (let i = 0; i < resid.length - 1; i++) num += (resid[i] - rmean) * (resid[i + 1] - rmean);
        for (let i = 0; i < resid.length; i++) den += (resid[i] - rmean) ** 2;
        acf1 = den > 0 ? num / den : NaN;
      }
      // Durbin-Watson
      let dwNum = 0, dwDen = 0;
      for (let i = 1; i < resid.length; i++) dwNum += (resid[i] - resid[i - 1]) ** 2;
      for (let i = 0; i < resid.length; i++) dwDen += resid[i] ** 2;
      const dw = dwDen > 0 ? dwNum / dwDen : NaN;
      stats[v] = { rmse, r2, acf1, dw, n: obs.length };
    });

    // Regime forecast
    const regime = forecastRegime(fittedParams, initial, nYears);

    return {
      fittedParams,
      fitted: fitParams.map((name, i) => ({
        name,
        value: fittedParams[name],
        initial: baseParams[name]
      })),
      stats,
      residuals,
      sim,
      iterations: result.iterations,
      finalSSE: result.f,
      regime
    };
  }

  // ─────────────────────────────────────────── regime forecast ──
  /**
   * Classify the long-term regime that the fitted parameter set predicts.
   * Runs a long simulation, looks at the terminal state, and tags it:
   *   "trivial"             - beetle and parasitoid both ~ 0
   *   "parasitoid_free"     - beetles persist, parasitoid goes extinct
   *   "coexistence_stable"  - both persist, low defoliation
   *   "outbreak_cycle"      - defoliation high, oscillatory
   *   "collapse"            - defoliation saturates, canopy loss
   */
  function forecastRegime(params, initial, nYears) {
    const model = new AlderIPMSimModel(params);
    model.u_C = 0; model.u_P = 0;
    const projYears = Math.max(100, nYears * 2);
    const sim = model.simulate(
      initial.A0, initial.F0, initial.K0, initial.D0,
      projYears, false
    );

    const last50 = projYears - 50;
    const tailA = sim.A.slice(last50);
    const tailF = sim.F.slice(last50);
    const tailK = sim.K.slice(last50);
    const tailD = sim.D.slice(last50);
    const mean = arr => arr.reduce((a, b) => a + b, 0) / arr.length;
    const std = arr => {
      const m = mean(arr);
      return Math.sqrt(arr.reduce((a, b) => a + (b - m) ** 2, 0) / arr.length);
    };

    const A_mean = mean(tailA), F_mean = mean(tailF);
    const K_mean = mean(tailK), D_mean = mean(tailD);
    const A_std = std(tailA);

    let R_P = NaN;
    try { R_P = model.computeRP(); } catch (e) { }

    let label, desc, color;
    if (A_mean < 1e-3 && F_mean < 1e-3) {
      label = 'Trivial extinction';
      desc = 'Both beetle and parasitoid decay to zero. Forest recovers.';
      color = '#2d6a4f';
    } else if (F_mean < 1e-3 && A_mean > 1e-2) {
      label = 'Parasitoid-free';
      desc = 'Beetle persists without parasitoid regulation. Defoliation driven only by bird predation.';
      color = '#e76f51';
    } else if (K_mean < 0.1 && D_mean > 0.8) {
      label = 'Canopy collapse';
      desc = 'Defoliation saturates, carrying capacity decays. Regime shift to degraded state.';
      color = '#b7094c';
    } else if (A_std / Math.max(A_mean, 1e-6) > 0.4) {
      label = 'Outbreak cycles';
      desc = 'Persistent high-amplitude oscillations. Parasitoid regulation insufficient.';
      color = '#f4a261';
    } else {
      label = 'Stable coexistence';
      desc = 'Beetle and parasitoid both persist at endemic levels. Low, steady defoliation.';
      color = '#40916c';
    }

    return { label, desc, color, R_P, A_mean, F_mean, K_mean, D_mean, projection: sim };
  }

  // ─────────────────────────────────────────── public API ──
  return {
    parseFieldCSV,
    alignFieldData,
    residualSSE,
    nelderMead,
    fit,
    forecastRegime
  };

})();

// Expose globally for app.js
if (typeof window !== 'undefined') window.FittingModule = FittingModule;
