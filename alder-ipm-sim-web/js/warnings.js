/**
 * Early Warning Signal Detection — pure JavaScript implementation.
 *
 * Computes rolling variance, rolling lag-1 autocorrelation, spectral
 * reddening index, and Kendall tau trend tests on sliding windows of
 * time-series data to detect critical slowing down before regime shifts.
 */

class EarlyWarningDetector {
  /**
   * @param {number} [windowSize] - Rolling window length. If null/undefined,
   *   defaults to 50% of the time series length.
   * @param {string} [detrendMethod='gaussian'] - 'gaussian' or 'linear'.
   */
  constructor(windowSize, detrendMethod) {
    this.windowSize = windowSize || null;
    this.detrendMethod = detrendMethod || "gaussian";
  }

  /**
   * Effective window size: provided value or 50% of series length.
   */
  _effectiveWindow(n) {
    if (this.windowSize !== null && this.windowSize > 0) {
      return Math.min(this.windowSize, n);
    }
    return Math.max(Math.floor(n * 0.5), 3);
  }

  // ── Detrending ──────────────────────────────────────────────────────

  /**
   * Gaussian kernel smoother (simple moving weighted average).
   */
  _gaussianSmooth(series, sigma) {
    const n = series.length;
    const out = new Array(n);
    const radius = Math.ceil(3 * sigma);
    for (let i = 0; i < n; i++) {
      let wSum = 0, vSum = 0;
      const lo = Math.max(0, i - radius);
      const hi = Math.min(n - 1, i + radius);
      for (let j = lo; j <= hi; j++) {
        const w = Math.exp(-0.5 * ((j - i) / sigma) ** 2);
        wSum += w;
        vSum += w * series[j];
      }
      out[i] = vSum / wSum;
    }
    return out;
  }

  /**
   * Remove slow trend from a time series and return residuals.
   */
  detrend(series) {
    const n = series.length;
    if (n < 3) return series.slice();

    if (this.detrendMethod === "linear") {
      // OLS linear detrend
      let sx = 0, sy = 0, sxy = 0, sx2 = 0;
      for (let i = 0; i < n; i++) {
        sx += i; sy += series[i]; sxy += i * series[i]; sx2 += i * i;
      }
      const slope = (n * sxy - sx * sy) / (n * sx2 - sx * sx);
      const intercept = (sy - slope * sx) / n;
      return series.map((v, i) => v - (intercept + slope * i));
    }

    // Default: Gaussian kernel smoother (bandwidth = window/4)
    const bw = Math.max(Math.floor(this._effectiveWindow(n) / 4), 1);
    const trend = this._gaussianSmooth(series, bw);
    return series.map((v, i) => v - trend[i]);
  }

  // ── Rolling indicators ──────────────────────────────────────────────

  /**
   * Rolling variance (sample variance, ddof=1).
   * Returns array of length (n - w + 1).
   */
  rollingVariance(series) {
    const residuals = this.detrend(series);
    const n = residuals.length;
    const w = Math.min(this._effectiveWindow(n), n);
    const out = [];
    for (let i = 0; i <= n - w; i++) {
      let sum = 0, sum2 = 0;
      for (let j = i; j < i + w; j++) {
        sum += residuals[j];
        sum2 += residuals[j] * residuals[j];
      }
      const mean = sum / w;
      const variance = (sum2 - w * mean * mean) / (w - 1);
      out.push(Math.max(variance, 0));
    }
    return out;
  }

  /**
   * Rolling lag-1 autocorrelation (Pearson correlation between x[t] and x[t+1]).
   * Returns array of length (n - w + 1).
   */
  rollingAutocorrelation(series, lag) {
    lag = lag || 1;
    const residuals = this.detrend(series);
    const n = residuals.length;
    const w = Math.min(this._effectiveWindow(n), n);
    const out = [];
    for (let i = 0; i <= n - w; i++) {
      const seg = residuals.slice(i, i + w);
      // Check for near-zero variance
      let std = 0;
      let mean = 0;
      for (let j = 0; j < w; j++) mean += seg[j];
      mean /= w;
      for (let j = 0; j < w; j++) std += (seg[j] - mean) ** 2;
      std = Math.sqrt(std / w);
      if (std < 1e-15) { out.push(0); continue; }

      const x = seg.slice(0, -lag);
      const y = seg.slice(lag);
      const m = x.length;
      if (m < 3) { out.push(0); continue; }

      let mx = 0, my = 0;
      for (let j = 0; j < m; j++) { mx += x[j]; my += y[j]; }
      mx /= m; my /= m;

      let num = 0, dx2 = 0, dy2 = 0;
      for (let j = 0; j < m; j++) {
        const dxj = x[j] - mx;
        const dyj = y[j] - my;
        num += dxj * dyj;
        dx2 += dxj * dxj;
        dy2 += dyj * dyj;
      }
      const den = Math.sqrt(dx2 * dy2);
      out.push(den > 1e-15 ? num / den : 0);
    }
    return out;
  }

  /**
   * Spectral reddening index: ratio of low-frequency to high-frequency
   * power in each rolling window, estimated via a simple periodogram.
   * Rising values indicate the spectrum shifting toward lower frequencies
   * (another signature of critical slowing down).
   * Returns array of length (n - w + 1).
   */
  rollingSpectralIndex(series) {
    const residuals = this.detrend(series);
    const n = residuals.length;
    const w = Math.min(this._effectiveWindow(n), n);
    const out = [];

    for (let i = 0; i <= n - w; i++) {
      const seg = residuals.slice(i, i + w);
      // Compute periodogram via DFT
      const halfW = Math.floor(w / 2);
      let lowPower = 0, highPower = 0;
      const cutoff = Math.max(Math.floor(halfW / 2), 1);

      for (let k = 1; k <= halfW; k++) {
        let re = 0, im = 0;
        for (let t = 0; t < w; t++) {
          const angle = 2 * Math.PI * k * t / w;
          re += seg[t] * Math.cos(angle);
          im -= seg[t] * Math.sin(angle);
        }
        const power = (re * re + im * im) / w;
        if (k <= cutoff) {
          lowPower += power;
        } else {
          highPower += power;
        }
      }

      out.push(highPower > 1e-15 ? lowPower / highPower : 0);
    }
    return out;
  }

  // ── Kendall tau trend test ──────────────────────────────────────────

  /**
   * Kendall's tau rank correlation between a series and its time index.
   * Returns { tau, pValue, significant }.
   */
  kendallTau(series) {
    const n = series.length;
    if (n < 3) return { tau: 0, pValue: 1, significant: false };

    let concordant = 0, discordant = 0;
    for (let i = 0; i < n - 1; i++) {
      for (let j = i + 1; j < n; j++) {
        const diff = series[j] - series[i];
        if (diff > 0) concordant++;
        else if (diff < 0) discordant++;
      }
    }
    const totalPairs = n * (n - 1) / 2;
    const tau = (concordant - discordant) / totalPairs;

    // Two-sided Z-test approximation for significance
    const variance = (2 * (2 * n + 5)) / (9 * n * (n - 1));
    const z = Math.abs(tau) / Math.sqrt(variance);
    // Approximate two-sided p-value from standard normal
    const pValue = 2 * (1 - this._normalCDF(z));

    return { tau, pValue, significant: pValue < 0.05 };
  }

  /**
   * Standard normal CDF approximation (Abramowitz & Stegun 26.2.17).
   */
  _normalCDF(x) {
    if (x < 0) return 1 - this._normalCDF(-x);
    const b1 = 0.319381530, b2 = -0.356563782, b3 = 1.781477937;
    const b4 = -1.821255978, b5 = 1.330274429, p = 0.2316419;
    const t = 1 / (1 + p * x);
    const poly = t * (b1 + t * (b2 + t * (b3 + t * (b4 + t * b5))));
    return 1 - (1 / Math.sqrt(2 * Math.PI)) * Math.exp(-0.5 * x * x) * poly;
  }

  // ── Full detection pipeline ─────────────────────────────────────────

  /**
   * Run the full early warning analysis on a time series.
   *
   * @param {number[]} series - Raw time series (e.g. annual beetle density A_t).
   * @param {number} [thresholdVarTau=0.3] - Minimum Kendall tau for variance.
   * @param {number} [thresholdAcTau=0.3] - Minimum Kendall tau for autocorrelation.
   * @returns {{ indicators, kendallResults, alertLevel, interpretation }}
   */
  analyze(series, thresholdVarTau, thresholdAcTau) {
    thresholdVarTau = thresholdVarTau !== undefined ? thresholdVarTau : 0.3;
    thresholdAcTau = thresholdAcTau !== undefined ? thresholdAcTau : 0.3;

    const variance = this.rollingVariance(series);
    const autocorrelation = this.rollingAutocorrelation(series);
    const spectralIndex = this.rollingSpectralIndex(series);

    const varTrend = this.kendallTau(variance);
    const acTrend = this.kendallTau(autocorrelation);
    const specTrend = this.kendallTau(spectralIndex);

    // Determine alert level (matches Python logic)
    const varSig = varTrend.pValue < 0.05 && varTrend.tau > thresholdVarTau;
    const acSig = acTrend.pValue < 0.05 && acTrend.tau > thresholdAcTau;

    let alertLevel, interpretation;
    if (varSig && acSig) {
      alertLevel = "red";
      interpretation =
        "RED ALERT: Both variance and autocorrelation of the selected " +
        "state variable are increasing, indicating critical slowing down. " +
        "The system may be approaching a regime shift. " +
        "Recommended: evaluate integrated control (parasitoid augmentation " +
        "+ direct larval removal + bird habitat enhancement).";
    } else if (varSig || acSig) {
      alertLevel = "amber";
      const which = varSig ? "Variance" : "Autocorrelation";
      const trend = varSig ? varTrend : acTrend;
      interpretation =
        "AMBER WARNING: " + which + " shows a significant increasing trend " +
        "(tau=" + trend.tau.toFixed(3) + ", p=" + trend.pValue.toFixed(4) + "). " +
        "This is a potential early indicator of critical slowing down. " +
        "Recommended: increase monitoring frequency and prepare contingency plans.";
    } else {
      alertLevel = "green";
      interpretation =
        "GREEN: No significant increasing trends detected in variance or " +
        "autocorrelation. The system appears to be in a stable regime. " +
        "Continue routine monitoring.";
    }

    return {
      indicators: { variance, autocorrelation, spectralIndex },
      kendallResults: {
        variance: varTrend,
        autocorrelation: acTrend,
        spectralIndex: specTrend
      },
      alertLevel,
      interpretation
    };
  }

  // ── LHS-PRCC Sensitivity Analysis ────────────────────────────────

  /**
   * Default 9 phenological parameter names for LHS-PRCC analysis.
   */
  static get LHS_PARAM_NAMES() {
    return ["T", "sigma_A", "sigma_F", "delta", "mu_S",
            "B_index", "phi", "beta", "R_B"];
  }

  /**
   * Default parameter ranges from the registry.
   */
  static lhsParamRanges() {
    const reg = typeof PARAM_REGISTRY !== "undefined" ? PARAM_REGISTRY : {};
    const ranges = {};
    for (const name of EarlyWarningDetector.LHS_PARAM_NAMES) {
      if (reg[name]) {
        ranges[name] = [reg[name].min, reg[name].max];
      }
    }
    // Fallback defaults if PARAM_REGISTRY is not available
    const defaults = {
      T: [45, 70], sigma_A: [0.5, 0.9], sigma_F: [0.3, 0.7],
      delta: [0.05, 0.25], mu_S: [0.003, 0.03], B_index: [0.5, 2.0],
      phi: [0.01, 0.1], beta: [0.005, 0.04], R_B: [6, 16]
    };
    for (const name of EarlyWarningDetector.LHS_PARAM_NAMES) {
      if (!ranges[name]) ranges[name] = defaults[name];
    }
    return ranges;
  }

  /**
   * Generate Latin Hypercube Samples.
   * Simple LHS: for each dimension, create a random permutation of
   * intervals and sample uniformly within each interval.
   *
   * @param {number} nSamples - Number of samples.
   * @param {string[]} paramNames - Parameter names.
   * @param {Object} paramRanges - {name: [min, max]}.
   * @returns {number[][]} Array of nSamples parameter vectors.
   */
  static latinHypercubeSample(nSamples, paramNames, paramRanges) {
    const d = paramNames.length;
    const samples = [];

    // Generate permutations for each dimension
    const perms = [];
    for (let j = 0; j < d; j++) {
      const perm = [];
      for (let i = 0; i < nSamples; i++) perm.push(i);
      // Fisher-Yates shuffle
      for (let i = nSamples - 1; i > 0; i--) {
        const k = Math.floor(Math.random() * (i + 1));
        [perm[i], perm[k]] = [perm[k], perm[i]];
      }
      perms.push(perm);
    }

    for (let i = 0; i < nSamples; i++) {
      const row = new Array(d);
      for (let j = 0; j < d; j++) {
        const u = (perms[j][i] + Math.random()) / nSamples; // uniform in interval
        const [lo, hi] = paramRanges[paramNames[j]];
        row[j] = lo + (hi - lo) * u;
      }
      samples.push(row);
    }
    return samples;
  }

  /**
   * Rank-transform an array (ties get average rank).
   */
  static _rankArray(arr) {
    const n = arr.length;
    const indexed = arr.map((v, i) => ({ v, i }));
    indexed.sort((a, b) => a.v - b.v);
    const ranks = new Array(n);
    let i = 0;
    while (i < n) {
      let j = i;
      while (j < n && indexed[j].v === indexed[i].v) j++;
      const avgRank = (i + j + 1) / 2; // 1-based
      for (let k = i; k < j; k++) ranks[indexed[k].i] = avgRank;
      i = j;
    }
    return ranks;
  }

  /**
   * Compute PRCC for each parameter vs the output.
   *
   * @param {number[][]} samples - (n x d) parameter matrix.
   * @param {number[]} output - (n,) response values.
   * @param {string[]} paramNames - Parameter names.
   * @returns {{ paramName: string, prcc: number, pValue: number }[]}
   */
  static computePRCC(samples, output, paramNames) {
    const n = samples.length;
    const d = paramNames.length;

    // Rank-transform
    const rankedX = [];
    for (let j = 0; j < d; j++) {
      const col = samples.map(row => row[j]);
      rankedX.push(EarlyWarningDetector._rankArray(col));
    }
    const rankedY = EarlyWarningDetector._rankArray(output);

    const results = [];

    for (let j = 0; j < d; j++) {
      const others = [];
      for (let k = 0; k < d; k++) if (k !== j) others.push(k);

      if (others.length === 0) {
        // Degenerate case
        const corr = EarlyWarningDetector._pearsonCorr(rankedX[j], rankedY);
        results.push({ paramName: paramNames[j], prcc: corr, pValue: 1 });
        continue;
      }

      // Build Z matrix (n x others.length) and regress
      const eX = EarlyWarningDetector._regressResiduals(rankedX[j], others.map(k => rankedX[k]), n);
      const eY = EarlyWarningDetector._regressResiduals(rankedY, others.map(k => rankedX[k]), n);

      const prcc = EarlyWarningDetector._pearsonCorr(eX, eY);

      // t-test for significance
      const dof = n - 2 - others.length;
      let pValue = 1;
      if (dof > 0 && Math.abs(prcc) < 1) {
        const tStat = prcc * Math.sqrt(dof / (1 - prcc * prcc));
        // Approximate p-value from t-distribution using normal approx for large dof
        const z = Math.abs(tStat);
        pValue = 2 * (1 - EarlyWarningDetector.prototype._normalCDF.call({}, z));
      }

      results.push({ paramName: paramNames[j], prcc, pValue });
    }
    return results;
  }

  /**
   * Compute OLS residuals: regress y on Z columns.
   */
  static _regressResiduals(y, zCols, n) {
    // Simple approach: use normal equations
    // Z_aug = [1, z1, z2, ...] (n x (p+1))
    const p = zCols.length;
    // For numerical stability, just use iterative subtraction approach
    // Regress y on each z column sequentially (Gram-Schmidt-like)
    let residuals = y.slice();
    for (let k = 0; k < p; k++) {
      const z = zCols[k];
      // Project residuals onto z and subtract
      let zMean = 0, rMean = 0;
      for (let i = 0; i < n; i++) { zMean += z[i]; rMean += residuals[i]; }
      zMean /= n; rMean /= n;
      let num = 0, den = 0;
      for (let i = 0; i < n; i++) {
        const dz = z[i] - zMean;
        num += dz * (residuals[i] - rMean);
        den += dz * dz;
      }
      if (den > 1e-15) {
        const beta = num / den;
        const alpha = rMean - beta * zMean;
        for (let i = 0; i < n; i++) {
          residuals[i] -= (alpha + beta * z[i]);
        }
      }
    }
    return residuals;
  }

  /**
   * Pearson correlation between two arrays.
   */
  static _pearsonCorr(a, b) {
    const n = a.length;
    let ma = 0, mb = 0;
    for (let i = 0; i < n; i++) { ma += a[i]; mb += b[i]; }
    ma /= n; mb /= n;
    let num = 0, da2 = 0, db2 = 0;
    for (let i = 0; i < n; i++) {
      const da = a[i] - ma;
      const db = b[i] - mb;
      num += da * db;
      da2 += da * da;
      db2 += db * db;
    }
    const den = Math.sqrt(da2 * db2);
    return den > 1e-15 ? num / den : 0;
  }

  /**
   * Run full LHS-PRCC analysis.
   *
   * @param {Object} baseParams - Base parameter set (from getDefaults()).
   * @param {number} [nSamples=200] - Number of LHS samples (smaller default for browser).
   * @param {number} [nYears=50] - Simulation years per sample (shorter for browser).
   * @param {Function} [onProgress] - Callback(i, nSamples) for progress updates.
   * @returns {{ prccResults, regimeShiftProb, samples, rhoStar, eqClasses }}
   */
  static lhsPRCC(baseParams, nSamples, nYears, onProgress) {
    nSamples = nSamples || 200;
    nYears = nYears || 50;
    const paramNames = EarlyWarningDetector.LHS_PARAM_NAMES;
    const paramRanges = EarlyWarningDetector.lhsParamRanges();

    const samples = EarlyWarningDetector.latinHypercubeSample(nSamples, paramNames, paramRanges);
    const rhoStar = new Array(nSamples).fill(NaN);
    const eqClasses = new Array(nSamples).fill("unknown");

    for (let i = 0; i < nSamples; i++) {
      try {
        const p = Object.assign({}, baseParams);
        for (let j = 0; j < paramNames.length; j++) {
          p[paramNames[j]] = samples[i][j];
        }

        const model = new AlderIPMSimModel(p);
        const K0 = p.K_0;
        const sim = model.simulate(K0 * 0.5, K0 * 0.1, K0, 0.0, nYears, false);
        const nT = sim.A.length;
        const A_end = sim.A[nT - 1];
        const F_end = sim.F[nT - 1];
        const K_end = sim.K[nT - 1];
        const D_end = sim.D[nT - 1];

        const jac = model.computeJacobian(A_end, F_end, K_end, D_end);
        // Compute eigenvalues of 4x4 matrix using characteristic polynomial
        // or use the model's built-in method if available
        const eigMods = EarlyWarningDetector._eigenvalueModuli4x4(jac);
        rhoStar[i] = Math.max(...eigMods);

        // Classify
        const tol = 1e-6;
        if (A_end < tol) eqClasses[i] = "trivial";
        else if (F_end < tol && D_end < tol) eqClasses[i] = "canopy_only";
        else if (F_end < tol) eqClasses[i] = "parasitoid_free";
        else eqClasses[i] = "coexistence";
      } catch (e) {
        rhoStar[i] = NaN;
        eqClasses[i] = "unknown";
      }
      if (onProgress) onProgress(i + 1, nSamples);
    }

    // Filter valid samples
    const validIdx = [];
    for (let i = 0; i < nSamples; i++) {
      if (isFinite(rhoStar[i])) validIdx.push(i);
    }

    let prccResults;
    if (validIdx.length < 10) {
      prccResults = paramNames.map(pn => ({ paramName: pn, prcc: 0, pValue: 1 }));
    } else {
      const validSamples = validIdx.map(i => samples[i]);
      const validRho = validIdx.map(i => rhoStar[i]);
      prccResults = EarlyWarningDetector.computePRCC(validSamples, validRho, paramNames);
    }

    // Regime shift probability
    const shifted = eqClasses.filter(c => c !== "coexistence").length;
    const regimeShiftProb = eqClasses.length > 0 ? shifted / eqClasses.length : 0;

    return { prccResults, regimeShiftProb, samples, rhoStar, eqClasses };
  }

  /**
   * Approximate eigenvalue moduli of a 4x4 matrix using the QR algorithm.
   * Simple iterative approach sufficient for our purposes.
   */
  static _eigenvalueModuli4x4(mat) {
    const n = 4;
    // Copy matrix
    let A = mat.map(row => row.slice());

    // QR iteration (30 iterations typically sufficient for 4x4)
    for (let iter = 0; iter < 50; iter++) {
      // QR decomposition via Gram-Schmidt
      const Q = Array.from({ length: n }, () => new Array(n).fill(0));
      const R = Array.from({ length: n }, () => new Array(n).fill(0));

      for (let j = 0; j < n; j++) {
        // Copy column j of A
        const v = new Array(n);
        for (let i = 0; i < n; i++) v[i] = A[i][j];

        // Subtract projections
        for (let k = 0; k < j; k++) {
          let dot = 0;
          for (let i = 0; i < n; i++) dot += Q[i][k] * v[i];
          R[k][j] = dot;
          for (let i = 0; i < n; i++) v[i] -= dot * Q[i][k];
        }

        let norm = 0;
        for (let i = 0; i < n; i++) norm += v[i] * v[i];
        norm = Math.sqrt(norm);
        R[j][j] = norm;

        if (norm > 1e-15) {
          for (let i = 0; i < n; i++) Q[i][j] = v[i] / norm;
        } else {
          for (let i = 0; i < n; i++) Q[i][j] = 0;
        }
      }

      // A = R * Q
      const newA = Array.from({ length: n }, () => new Array(n).fill(0));
      for (let i = 0; i < n; i++) {
        for (let j = 0; j < n; j++) {
          let s = 0;
          for (let k = 0; k < n; k++) s += R[i][k] * Q[k][j];
          newA[i][j] = s;
        }
      }
      A = newA;
    }

    // Extract eigenvalue moduli from the quasi-upper-triangular result
    const moduli = [];
    let i = 0;
    while (i < n) {
      if (i + 1 < n && Math.abs(A[i + 1][i]) > 1e-10) {
        // 2x2 block: eigenvalues are complex conjugates
        const a = A[i][i], b = A[i][i + 1], c = A[i + 1][i], d = A[i + 1][i + 1];
        const trace = a + d;
        const det = a * d - b * c;
        const disc = trace * trace - 4 * det;
        if (disc < 0) {
          moduli.push(Math.sqrt(det));
          moduli.push(Math.sqrt(det));
        } else {
          const sqrtDisc = Math.sqrt(disc);
          moduli.push(Math.abs((trace + sqrtDisc) / 2));
          moduli.push(Math.abs((trace - sqrtDisc) / 2));
        }
        i += 2;
      } else {
        moduli.push(Math.abs(A[i][i]));
        i++;
      }
    }
    return moduli;
  }

  /**
   * Parse a single CSV line respecting quoted fields.
   * Handles double-quote enclosed fields and escaped quotes ("").
   * @param {string} line - A single CSV row.
   * @param {string} delimiter - The field delimiter character.
   * @returns {string[]} Array of field values.
   */
  static _parseCSVLine(line, delimiter) {
    const fields = [];
    let current = "";
    let inQuotes = false;
    let i = 0;
    while (i < line.length) {
      const ch = line[i];
      if (inQuotes) {
        if (ch === '"') {
          if (i + 1 < line.length && line[i + 1] === '"') {
            current += '"';
            i += 2;
          } else {
            inQuotes = false;
            i++;
          }
        } else {
          current += ch;
          i++;
        }
      } else {
        if (ch === '"') {
          inQuotes = true;
          i++;
        } else if (ch === delimiter) {
          fields.push(current.trim());
          current = "";
          i++;
        } else {
          current += ch;
          i++;
        }
      }
    }
    fields.push(current.trim());
    return fields;
  }

  /**
   * Parse a CSV string into an object of named columns.
   * Detects delimiter (comma, semicolon, tab), handles quoted fields,
   * strips BOM, and skips empty lines.
   *
   * @param {string} csvText - Raw CSV text content.
   * @returns {{ headers: string[], columns: Object<string, number[]>, delimiter: string, rowCount: number } | null}
   */
  static parseCSV(csvText) {
    // Strip BOM
    if (csvText.charCodeAt(0) === 0xFEFF) {
      csvText = csvText.slice(1);
    }

    // Split into lines and remove empty ones
    const lines = csvText.split(/\r?\n/).filter(line => line.trim().length > 0);
    if (lines.length < 2) return null;

    // Detect delimiter: try comma, semicolon, tab
    // Pick whichever produces the most consistent column count across the first few lines
    const candidates = [",", ";", "\t"];
    let bestDelimiter = ",";
    let bestScore = -1;

    for (const delim of candidates) {
      const counts = [];
      const sampleSize = Math.min(lines.length, 10);
      for (let i = 0; i < sampleSize; i++) {
        counts.push(EarlyWarningDetector._parseCSVLine(lines[i], delim).length);
      }
      const headerCount = counts[0];
      if (headerCount < 2) continue;
      // Score: number of rows matching header column count, weighted by column count
      let matching = 0;
      for (let i = 1; i < counts.length; i++) {
        if (counts[i] === headerCount) matching++;
      }
      const score = matching * headerCount;
      if (score > bestScore) {
        bestScore = score;
        bestDelimiter = delim;
      }
    }

    const headers = EarlyWarningDetector._parseCSVLine(lines[0], bestDelimiter);
    const columns = {};
    headers.forEach(h => { columns[h] = []; });

    let rowCount = 0;
    for (let i = 1; i < lines.length; i++) {
      const vals = EarlyWarningDetector._parseCSVLine(lines[i], bestDelimiter);
      for (let j = 0; j < headers.length; j++) {
        const v = parseFloat(vals[j]);
        columns[headers[j]].push(isNaN(v) ? 0 : v);
      }
      rowCount++;
    }
    return { headers, columns, delimiter: bestDelimiter, rowCount };
  }

  /**
   * Assess data quality for early warning analysis.
   *
   * @param {Object<string, number[]>} columns - Column data from parseCSV.
   * @param {string} timeCol - Name of the time column (used to detect gaps).
   * @returns {{ length: number, completeness: number, gaps: {from: number, to: number}[], hasZeros: boolean, qualityLevel: string }}
   */
  static dataQualityReport(columns, timeCol) {
    const colNames = Object.keys(columns);
    if (colNames.length === 0) {
      return { length: 0, completeness: 0, gaps: [], hasZeros: false, qualityLevel: "poor" };
    }

    const length = columns[colNames[0]].length;

    // Completeness: fraction of non-NaN values across all columns
    let totalCells = 0;
    let nonNanCells = 0;
    let hasZeros = false;
    for (const name of colNames) {
      const col = columns[name];
      for (let i = 0; i < col.length; i++) {
        totalCells++;
        if (!isNaN(col[i]) && col[i] !== null && col[i] !== undefined) {
          nonNanCells++;
        }
        if (col[i] === 0) hasZeros = true;
      }
    }
    const completeness = totalCells > 0 ? nonNanCells / totalCells : 0;

    // Gaps: detect where time differences exceed 2x median
    const gaps = [];
    if (timeCol && columns[timeCol] && columns[timeCol].length > 2) {
      const times = columns[timeCol];
      const diffs = [];
      for (let i = 1; i < times.length; i++) {
        diffs.push(times[i] - times[i - 1]);
      }
      // Compute median of diffs
      const sortedDiffs = diffs.slice().sort((a, b) => a - b);
      const mid = Math.floor(sortedDiffs.length / 2);
      const median = sortedDiffs.length % 2 === 0
        ? (sortedDiffs[mid - 1] + sortedDiffs[mid]) / 2
        : sortedDiffs[mid];

      const threshold = 2 * median;
      for (let i = 0; i < diffs.length; i++) {
        if (diffs[i] > threshold) {
          gaps.push({ from: times[i], to: times[i + 1] });
        }
      }
    }

    // Quality level
    let qualityLevel;
    if (length >= 20 && completeness > 0.95 && gaps.length === 0) {
      qualityLevel = "good";
    } else if (length >= 10 && completeness > 0.80) {
      qualityLevel = "fair";
    } else {
      qualityLevel = "poor";
    }

    return { length, completeness, gaps, hasZeros, qualityLevel };
  }

  /**
   * Generate an HTML preview table from parsed CSV data.
   *
   * @param {{ headers: string[], columns: Object<string, number[]>, rowCount: number }} parsed - Output of parseCSV.
   * @param {number} [maxRows=5] - Maximum number of data rows to show.
   * @returns {string} HTML string for a <table> element.
   */
  static generatePreviewHTML(parsed, maxRows) {
    if (!parsed) return "<p>No data available.</p>";
    maxRows = maxRows !== undefined ? maxRows : 5;

    const headers = parsed.headers;
    const rowCount = parsed.rowCount || 0;
    const displayRows = Math.min(maxRows, rowCount);

    let html = '<table class="data-preview-table">';
    // Header row
    html += "<thead><tr>";
    for (const h of headers) {
      html += "<th>" + EarlyWarningDetector._escapeHTML(h) + "</th>";
    }
    html += "</tr></thead>";

    // Data rows
    html += "<tbody>";
    for (let i = 0; i < displayRows; i++) {
      html += "<tr>";
      for (const h of headers) {
        const val = parsed.columns[h][i];
        html += "<td>" + (val !== undefined ? val : "") + "</td>";
      }
      html += "</tr>";
    }
    html += "</tbody>";

    html += "</table>";
    if (rowCount > maxRows) {
      html += '<p style="font-size:12px;color:var(--text-muted,#888);">Showing ' + displayRows + ' of ' + rowCount + ' rows.</p>';
    }
    return html;
  }

  /**
   * Escape HTML special characters to prevent XSS in preview tables.
   * @param {string} str
   * @returns {string}
   */
  static _escapeHTML(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
}
