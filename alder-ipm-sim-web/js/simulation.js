/**
 * Simulation runner — manages model execution, result formatting, and CSV export.
 */

class SimulationRunner {
  constructor() {
    this.model = null;
    this.lastResult = null;
  }

  /**
   * Create or update the model with given parameters.
   */
  initModel(params) {
    this.model = new AlderIPMSimModel(params);
  }

  /**
   * Run a multi-year simulation.
   * Iterates the annual map for nYears, storing A, F, K, D at each year step.
   */
  runSimulation(config) {
    const {
      A0 = 1.0,
      F0 = 0.5,
      K0 = null,
      D0 = 0.0,
      nYears = 50,
      u_C = 0.0,
      u_P = 0.0,
      storeWithinSeason = false
    } = config;

    if (!this.model) {
      this.initModel({});
    }

    this.model.u_C = u_C;
    this.model.u_P = u_P;

    const effectiveK0 = K0 !== null ? K0 : this.model.params.K_0;

    this.lastResult = this.model.simulate(A0, F0, effectiveK0, D0, nYears, storeWithinSeason);
    return this.lastResult;
  }

  /**
   * Run a single within-season integration and return the trajectory.
   */
  runWithinSeason(config) {
    const {
      S0 = 1.0,
      I0 = 0.0,
      F0 = 0.5,
      D0 = 0.0,
      u_C = 0.0,
      u_P = 0.0
    } = config;

    if (!this.model) {
      this.initModel({});
    }

    this.model.u_C = u_C;
    this.model.u_P = u_P;

    return this.model.integrateSeason(S0, I0, F0, D0);
  }

  /**
   * Compute summary statistics from the last simulation result.
   */
  computeSummary(result) {
    if (!result) return null;

    const n = result.A.length;
    const lastA = result.A[n - 1];
    const lastF = result.F[n - 1];
    const lastK = result.K[n - 1];
    const lastD = result.D[n - 1];

    const maxA = Math.max(...result.A);
    const maxD = Math.max(...result.D);

    const p = this.model.params;
    const dCritExceeded = maxD > p.D_crit;
    const kBelowMin = lastK < p.K_min;

    let status = "healthy";
    if (dCritExceeded && kBelowMin) {
      status = "collapse_risk";
    } else if (dCritExceeded) {
      status = "defoliation_warning";
    } else if (lastA < 0.01) {
      status = "beetle_extinct";
    }

    return {
      finalA: lastA,
      finalF: lastF,
      finalK: lastK,
      finalD: lastD,
      peakBeetles: maxA,
      peakDefoliation: maxD,
      dCritExceeded,
      kBelowMin,
      status
    };
  }

  /**
   * Export the last simulation result as a CSV string.
   */
  exportCSV(result) {
    if (!result) return "";
    const rows = ["year,A_beetles,F_parasitoids,K_capacity,D_defoliation"];
    for (let i = 0; i < result.A.length; i++) {
      rows.push(`${i},${result.A[i]},${result.F[i]},${result.K[i]},${result.D[i]}`);
    }
    return rows.join("\n");
  }

  /**
   * Trigger a CSV download in the browser.
   */
  downloadCSV(result, filename) {
    const csv = this.exportCSV(result);
    if (!csv) return;
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename || "alder-ipm-sim_simulation.csv";
    link.click();
    URL.revokeObjectURL(link.href);
  }
}
