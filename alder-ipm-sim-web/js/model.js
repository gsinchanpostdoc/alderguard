/**
 * AlderIPM-Sim ODE Model
 * Within-season ODE system with 4th-order Runge-Kutta solver and annual update map.
 *
 * States: S = healthy/susceptible beetle larvae, I = parasitised larvae,
 *         F = adult parasitoid flies, D = cumulative defoliation
 * (In the annual map context: A = adult beetles, F = parasitoids,
 *  K = carrying capacity, D = defoliation)
 */

class AlderIPMSimModel {
  constructor(params) {
    this.params = Object.assign(getDefaults(), params || {});
    this.u_C = 0.0; // direct larval removal effort
    this.u_P = 0.0; // parasitoid augmentation effort
  }

  /**
   * Right-hand side of the within-season ODE system.
   *
   * dS/dt = -beta*S*F/(1+h*S) - c_B*B_t*(S+I)/(1+a_B*(S+I)) - (mu_S+u_C)*S
   * dI/dt =  beta*S*F/(1+h*S) - c_B*B_t*(S+I)/(1+a_B*(S+I)) - (mu_I+delta+u_C)*I
   * dF/dt =  eta*delta*I - mu_F*F + u_P
   * dD/dt =  kappa*(S + I)
   */
  withinSeasonRHS(tau, y) {
    const p = this.params;

    const S = Math.max(y[0], 0.0);
    const I = Math.max(y[1], 0.0);
    const F = Math.max(y[2], 0.0);
    const D = y[3];

    const B_t = p.B_index;

    // Holling Type II parasitism
    const parasitism = p.beta * S * F / (1.0 + p.h * S);

    // Bird predation (Holling II on total larvae)
    const totalLarvae = S + I;
    const birdPred = p.c_B * B_t * totalLarvae / (1.0 + p.a_B * totalLarvae);

    const dS = -parasitism - birdPred - (p.mu_S + this.u_C) * S;
    const dI = parasitism - birdPred - (p.mu_I + p.delta + this.u_C) * I;
    const dF = p.eta * p.delta * I - p.mu_F * F + this.u_P;
    const dD = p.kappa * totalLarvae;

    return [dS, dI, dF, dD];
  }

  /**
   * 4th-order Runge-Kutta integrator.
   * @param {number} t0 - Start time
   * @param {number} t1 - End time
   * @param {number[]} y0 - Initial state [S, I, F, D]
   * @param {number} dt - Time step (default 0.1 days)
   * @returns {{t: number[], y: number[][]}} - Time points and state trajectories
   */
  rk4Integrate(t0, t1, y0, dt) {
    dt = dt || 0.1;
    const n = Math.ceil((t1 - t0) / dt);
    const actualDt = (t1 - t0) / n;

    const times = new Array(n + 1);
    const states = new Array(n + 1);

    times[0] = t0;
    states[0] = y0.slice();

    for (let i = 0; i < n; i++) {
      const t = times[i];
      const y = states[i];

      const k1 = this.withinSeasonRHS(t, y);
      const y2 = y.map((v, j) => v + 0.5 * actualDt * k1[j]);
      const k2 = this.withinSeasonRHS(t + 0.5 * actualDt, y2);
      const y3 = y.map((v, j) => v + 0.5 * actualDt * k2[j]);
      const k3 = this.withinSeasonRHS(t + 0.5 * actualDt, y3);
      const y4 = y.map((v, j) => v + actualDt * k3[j]);
      const k4 = this.withinSeasonRHS(t + actualDt, y4);

      const yNext = new Array(4);
      for (let j = 0; j < 4; j++) {
        yNext[j] = y[j] + (actualDt / 6.0) * (k1[j] + 2 * k2[j] + 2 * k3[j] + k4[j]);
      }

      times[i + 1] = t + actualDt;
      states[i + 1] = yNext;
    }

    return { t: times, y: states };
  }

  /**
   * Integrate the within-season ODE from tau=0 to tau=T.
   */
  integrateSeason(S0, I0, F0, D0) {
    const T = this.params.T;
    const result = this.rk4Integrate(0, T, [S0, I0, F0, D0]);
    const endState = result.y[result.y.length - 1];
    return {
      sol: result,
      endVals: {
        S_T: Math.max(endState[0], 0.0),
        I_T: Math.max(endState[1], 0.0),
        F_T: Math.max(endState[2], 0.0),
        D_T: endState[3]
      }
    };
  }

  /**
   * Compute the between-year discrete map (Eqs. 5-8).
   *
   * Season start (Eq. 5): S(0) = R_B * A_t / (1 + A_t / K_t)
   * Season end (Eq. 6):   A_{t+1} = sigma_A * S(T)
   * F_{t+1} = sigma_F * F_T
   * K_{t+1} = K_0 * exp(-phi * D_T)
   * D_{t+1} = D_T
   */
  annualMap(A_t, F_t, K_t, D_t) {
    const p = this.params;

    // Beverton-Holt recruitment at season start (Eq. 5)
    const S0 = p.R_B * A_t / (1.0 + A_t / K_t);

    const { sol, endVals } = this.integrateSeason(S0, 0.0, F_t, 0.0);

    const S_T = endVals.S_T;
    const F_T = endVals.F_T;
    const D_T = endVals.D_T;

    // Simple overwinter survival (Eq. 6)
    const A_next = p.sigma_A * S_T;
    const F_next = p.sigma_F * F_T;
    const K_next = p.K_0 * Math.exp(-p.phi * D_T);
    const D_next = D_T;

    return {
      A_next, F_next, K_next, D_next,
      withinSeasonSol: sol
    };
  }

  /**
   * Run the annual map for n_years successive seasons.
   */
  simulate(A0, F0, K0, D0, nYears, storeWithinSeason) {
    const A = new Array(nYears + 1);
    const F = new Array(nYears + 1);
    const K = new Array(nYears + 1);
    const D = new Array(nYears + 1);
    const withinSeason = [];

    A[0] = A0;
    F[0] = F0;
    K[0] = K0;
    D[0] = D0;

    for (let t = 0; t < nYears; t++) {
      const result = this.annualMap(A[t], F[t], K[t], D[t]);
      A[t + 1] = result.A_next;
      F[t + 1] = result.F_next;
      K[t + 1] = result.K_next;
      D[t + 1] = result.D_next;
      if (storeWithinSeason) {
        withinSeason.push(result.withinSeasonSol);
      }
    }

    const out = { A, F, K, D };
    if (storeWithinSeason) {
      out.withinSeason = withinSeason;
    }
    return out;
  }

  /**
   * Compute the parasitoid invasion reproduction number R_P.
   */
  computeRP(S_bar) {
    const p = this.params;

    if (S_bar === undefined || S_bar === null) {
      // Approximate parasitoid-free equilibrium
      const oldUP = this.u_P;
      this.u_P = 0.0;
      let A_t = p.K_0 * 0.5;
      let K_t = p.K_0;
      let endVals;
      for (let i = 0; i < 200; i++) {
        // Beverton-Holt at season start
        const S0 = p.R_B * A_t / (1.0 + A_t / K_t);
        const result = this.integrateSeason(S0, 0.0, 0.0, 0.0);
        endVals = result.endVals;
        const S_T = endVals.S_T;
        const D_T = endVals.D_T;
        const A_next = p.sigma_A * S_T;
        const K_next = p.K_0 * Math.exp(-p.phi * D_T);
        if (Math.abs(A_next - A_t) < 1e-10 && Math.abs(K_next - K_t) < 1e-10) break;
        A_t = A_next;
        K_t = K_next;
      }
      S_bar = endVals.S_T;
      this.u_P = oldUP;
    }

    return (p.beta * p.eta * p.delta * p.sigma_F) /
           ((1.0 + p.h * S_bar) * p.mu_F * (p.mu_I + p.delta));
  }

  /**
   * Compute resistance R1 (Section 2.4, Eq. R1).
   * R1 = (x_ref - x_max_dev) / x_ref
   */
  computeR1(A_star, F_star, K_star, D_star, perturbationFrac, nYears) {
    perturbationFrac = perturbationFrac || 0.2;
    nYears = nYears || 50;
    if (A_star < 1e-12) return NaN;

    const A0 = A_star * (1.0 + perturbationFrac);
    const sim = this.simulate(A0, F_star, K_star, D_star, nYears, false);

    let maxDev = 0;
    for (let i = 0; i <= nYears; i++) {
      maxDev = Math.max(maxDev, Math.abs(sim.A[i] - A_star));
    }
    const R1 = (A_star - maxDev) / A_star;
    return Math.max(-1, Math.min(1, R1));
  }

  /**
   * Compute resilience R2 (Section 2.4, Eq. R2).
   * R2 = (x_max_dev - x_Y) / x_max_dev
   */
  computeR2(A_star, F_star, K_star, D_star, perturbationFrac, Y, nYears) {
    perturbationFrac = perturbationFrac || 0.2;
    Y = Y || 5;
    nYears = nYears || 50;
    if (A_star < 1e-12) return NaN;

    const A0 = A_star * (1.0 + perturbationFrac);
    const sim = this.simulate(A0, F_star, K_star, D_star, nYears, false);

    let maxDev = 0, maxDevIdx = 0;
    for (let i = 0; i <= nYears; i++) {
      const dev = Math.abs(sim.A[i] - A_star);
      if (dev > maxDev) { maxDev = dev; maxDevIdx = i; }
    }

    if (maxDev < 1e-12) return 1.0;

    const yIdx = Math.min(maxDevIdx + Y, nYears);
    const xY = Math.abs(sim.A[yIdx] - A_star);
    return (maxDev - xY) / maxDev;
  }

  /**
   * Numerically compute the 4x4 Jacobian of the annual map using central
   * finite differences.
   * @param {number} A - Adult beetle density.
   * @param {number} F - Parasitoid density.
   * @param {number} K - Carrying capacity.
   * @param {number} D - Defoliation.
   * @param {number} [eps=1e-6] - Perturbation size.
   * @returns {number[][]} 4x4 Jacobian matrix.
   */
  computeJacobian(A, F, K, D, eps) {
    eps = eps || 1e-6;
    const x0 = [A, F, K, D];
    const jac = [
      [0, 0, 0, 0],
      [0, 0, 0, 0],
      [0, 0, 0, 0],
      [0, 0, 0, 0]
    ];

    const mapVec = (x) => {
      x = x.map(v => Math.max(v, 0));
      x[2] = Math.max(x[2], 1e-12);
      const res = this.annualMap(x[0], x[1], x[2], x[3]);
      return [res.A_next, res.F_next, res.K_next, res.D_next];
    };

    for (let j = 0; j < 4; j++) {
      const h = eps * Math.max(Math.abs(x0[j]), 1.0);
      const xPlus = x0.slice();
      const xMinus = x0.slice();
      xPlus[j] += h;
      xMinus[j] -= h;
      try {
        const fPlus = mapVec(xPlus);
        const fMinus = mapVec(xMinus);
        for (let i = 0; i < 4; i++) {
          jac[i][j] = (fPlus[i] - fMinus[i]) / (xPlus[j] - xMinus[j]);
        }
      } catch (e) {
        for (let i = 0; i < 4; i++) jac[i][j] = NaN;
      }
    }
    return jac;
  }

  /**
   * Compute latitude: maximum perturbation before regime shift (Section 2.4).
   */
  computeLatitude(A_star, F_star, K_star, D_star, maxDelta, nSteps, nYears, tol) {
    maxDelta = maxDelta || 2.0;
    nSteps = nSteps || 50;
    nYears = nYears || 50;
    tol = tol || 0.1;
    if (A_star < 1e-12) return 0;

    let latitude = 0;
    for (let i = 1; i <= nSteps; i++) {
      const delta = (i / nSteps) * maxDelta;
      const A0 = A_star * (1.0 + delta);
      const sim = this.simulate(A0, F_star, K_star, D_star, nYears, false);
      const Afinal = sim.A[nYears];
      if (Math.abs(Afinal - A_star) < tol * A_star) {
        latitude = delta;
      } else {
        break;
      }
    }
    return latitude;
  }
}
