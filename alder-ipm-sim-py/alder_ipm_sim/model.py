# ODE model definitions for the Alnus-beetle-parasitoid-bird ecoepidemic system.
from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import fsolve
from scipy.stats import qmc

from .parameters import PARAM_REGISTRY, get_defaults


@dataclass
class FixedPoint:
    """A fixed point of the annual map with stability information."""

    A_star: float
    F_star: float
    K_star: float
    D_star: float
    equilibrium_class: str  # 'trivial', 'canopy_only', 'parasitoid_free', 'coexistence'
    stable: bool
    dominant_eigenvalue: float
    bifurcation_type: str


class AlderIPMSimModel:
    """Core ODE model for the Alnus-beetle-parasitoid-bird ecoepidemic system.

    The model couples a within-season continuous ODE (beetle larvae, parasitised
    larvae, adult parasitoid flies, cumulative defoliation) with a between-year
    discrete map (Beverton-Holt recruitment, overwinter survival, canopy
    feedback).  See manuscript Eqs. (1)-(4) for the within-season system and
    Eqs. (5)-(8) for the annual map.

    Parameters
    ----------
    params : dict, optional
        Parameter name -> value mapping.  Any parameter not supplied is filled
        from ``PARAM_REGISTRY`` defaults.
    """

    def __init__(self, params: Optional[Dict[str, float]] = None) -> None:
        self.params: Dict[str, float] = get_defaults()
        if params is not None:
            self.params.update(params)

        # Control inputs (can be set externally before integration)
        self.u_C: float = 0.0  # direct larval removal effort
        self.u_P: float = 0.0  # parasitoid augmentation effort

    # ------------------------------------------------------------------
    # Within-season ODE
    # ------------------------------------------------------------------

    def within_season_rhs(self, tau: float, y: np.ndarray) -> List[float]:
        """Right-hand side of the within-season ODE system.

        State vector ``y = [S, I, F, D]`` where:

        * S -- susceptible (unparasitised) beetle larvae density [ind/ha]
        * I -- parasitised beetle larvae density [ind/ha]
        * F -- adult parasitoid fly density [ind/ha]
        * D -- cumulative defoliation damage [0, 1]

        Equations (manuscript Eqs. 1-4)::

            dS/dt = -beta*S*F/(1+h*S) - c_B*B_t*S/(1+a_B*(S+I)) - (mu_S+u_C)*S
            dI/dt =  beta*S*F/(1+h*S) - c_B*B_t*I/(1+a_B*(S+I)) - (mu_I+delta+u_C)*I
            dF/dt =  eta*delta*I - mu_F*F + u_P
            dD/dt =  kappa*(S + I)

        Parameters
        ----------
        tau : float
            Time within the season (days).
        y : array-like
            State vector [S, I, F, D].

        Returns
        -------
        list of float
            Derivatives [dS/dt, dI/dt, dF/dt, dD/dt].
        """
        p = self.params

        # Clamp to non-negative to prevent numerical drift
        S = max(y[0], 0.0)
        I = max(y[1], 0.0)  # noqa: E741
        F = max(y[2], 0.0)
        D = y[3]

        B_t = p["B_index"]

        # Holling Type II parasitism
        parasitism = p["beta"] * S * F / (1.0 + p["h"] * S)

        # Bird predation (Holling II on total larvae, split proportionally)
        total_larvae = S + I
        bird_denom = 1.0 + p["a_B"] * total_larvae
        bird_pred_S = p["c_B"] * B_t * S / bird_denom
        bird_pred_I = p["c_B"] * B_t * I / bird_denom

        dS = -parasitism - bird_pred_S - (p["mu_S"] + self.u_C) * S
        dI = parasitism - bird_pred_I - (p["mu_I"] + p["delta"] + self.u_C) * I
        dF = p["eta"] * p["delta"] * I - p["mu_F"] * F + self.u_P
        dD = p["kappa"] * total_larvae

        return [dS, dI, dF, dD]

    # ------------------------------------------------------------------
    # Season integration
    # ------------------------------------------------------------------

    def integrate_season(
        self,
        S0: float,
        I0: float,
        F0: float,
        D0: float,
        t_span: Optional[tuple] = None,
        t_eval: Optional[np.ndarray] = None,
    ):
        """Integrate the within-season ODE from tau=0 to tau=T.

        Uses ``scipy.integrate.solve_ivp`` with RK45, tight tolerances
        (rtol=1e-8, atol=1e-10).

        Parameters
        ----------
        S0, I0, F0, D0 : float
            Initial conditions for susceptible larvae, parasitised larvae,
            adult parasitoids, and cumulative defoliation.
        t_span : tuple, optional
            Integration interval ``(t_start, t_end)``.  Defaults to
            ``(0, T)`` where *T* is the season length parameter.
        t_eval : array-like, optional
            Times at which to store the solution.

        Returns
        -------
        sol : OdeSolution
            Full ``solve_ivp`` solution object.
        end_vals : dict
            End-of-season state ``{'S_T', 'I_T', 'F_T', 'D_T'}``.
        """
        if t_span is None:
            t_span = (0.0, self.params["T"])

        y0 = [S0, I0, F0, D0]

        sol = solve_ivp(
            self.within_season_rhs,
            t_span,
            y0,
            method="RK45",
            rtol=1e-8,
            atol=1e-10,
            t_eval=t_eval,
            dense_output=True,
        )

        end_vals = {
            "S_T": max(sol.y[0, -1], 0.0),
            "I_T": max(sol.y[1, -1], 0.0),
            "F_T": max(sol.y[2, -1], 0.0),
            "D_T": sol.y[3, -1],
        }

        return sol, end_vals

    # ------------------------------------------------------------------
    # Annual (between-year) discrete map
    # ------------------------------------------------------------------

    def annual_map(
        self, A_t: float, F_t: float, K_t: float, D_t: float
    ) -> Dict:
        """Compute the between-year discrete map (manuscript Eqs. 5-8).

        1. Apply Beverton-Holt recruitment at season START::

            S(0) = R_B * A_t / (1 + A_t / K_t)

        2. Integrate within-season ODE with ``S0=S(0), I0=0, F0=F_t, D0=0``.
        3. Apply overwinter survival at season END::

            A_{t+1} = sigma_A * S(T)
            F_{t+1} = sigma_F * F_T
            K_{t+1} = K_0 * exp(-phi * D_T)
            D_{t+1} = D_T

        Parameters
        ----------
        A_t : float
            Adult beetle density entering the season.
        F_t : float
            Parasitoid fly density entering the season.
        K_t : float
            Current carrying capacity.
        D_t : float
            Defoliation from previous year (not used in within-season IC).

        Returns
        -------
        dict
            Keys: ``A_next, F_next, K_next, D_next, within_season_sol``.
        """
        p = self.params

        # Beverton-Holt recruitment at season start (Eq. 5)
        S0 = p["R_B"] * A_t / (1.0 + A_t / K_t)

        sol, end = self.integrate_season(S0=S0, I0=0.0, F0=F_t, D0=0.0)

        S_T = end["S_T"]
        F_T = end["F_T"]
        D_T = end["D_T"]

        # Simple overwinter survival (Eq. 6)
        A_next = p["sigma_A"] * S_T
        F_next = p["sigma_F"] * F_T
        K_next = p["K_0"] * np.exp(-p["phi"] * D_T)
        D_next = D_T

        return {
            "A_next": A_next,
            "F_next": F_next,
            "K_next": K_next,
            "D_next": D_next,
            "within_season_sol": sol,
        }

    # ------------------------------------------------------------------
    # Multi-year simulation
    # ------------------------------------------------------------------

    def simulate(
        self,
        A0: float,
        F0: float,
        K0: float,
        D0: float,
        n_years: int,
        store_within_season: bool = False,
    ) -> Dict:
        """Run the annual map for *n_years* successive seasons.

        Parameters
        ----------
        A0, F0, K0, D0 : float
            Initial state at year 0.
        n_years : int
            Number of annual cycles to simulate.
        store_within_season : bool
            If True, store the full within-season ``solve_ivp`` solution for
            every year.

        Returns
        -------
        dict
            ``'A', 'F', 'K', 'D'`` -- arrays of length ``n_years + 1``
            (includes initial conditions at index 0).
            ``'within_season'`` -- list of ``solve_ivp`` solutions (only if
            *store_within_season* is True).
        """
        A = np.zeros(n_years + 1)
        F = np.zeros(n_years + 1)
        K = np.zeros(n_years + 1)
        D = np.zeros(n_years + 1)

        A[0], F[0], K[0], D[0] = A0, F0, K0, D0

        within_season_sols: List = []

        for t in range(n_years):
            result = self.annual_map(A[t], F[t], K[t], D[t])
            A[t + 1] = result["A_next"]
            F[t + 1] = result["F_next"]
            K[t + 1] = result["K_next"]
            D[t + 1] = result["D_next"]

            if store_within_season:
                within_season_sols.append(result["within_season_sol"])

        out: Dict = {"A": A, "F": F, "K": K, "D": D}
        if store_within_season:
            out["within_season"] = within_season_sols

        return out

    # ------------------------------------------------------------------
    # Within-season trajectory extraction
    # ------------------------------------------------------------------

    def get_season_trajectory(
        self,
        sim_result: Dict,
        year_index: int,
    ) -> Dict:
        """Return daily-resolution within-season trajectory for a specific year.

        Requires that the simulation was run with ``store_within_season=True``.
        Returns S(tau), I(tau), F(tau), D(tau) at daily resolution together
        with derived quantities useful for understanding the mechanistic
        interactions within the larval vulnerability window.

        Parameters
        ----------
        sim_result : dict
            Output of :meth:`simulate` with ``store_within_season=True``.
        year_index : int
            Which year's within-season trajectory to extract (0-based).

        Returns
        -------
        dict
            ``'tau'`` -- time array (days within the season).
            ``'S'``, ``'I'``, ``'F'``, ``'D'`` -- state variable arrays.
            ``'parasitism_rate'`` -- instantaneous parasitism rate beta*S*F/(1+h*S).
            ``'defoliation_rate'`` -- instantaneous defoliation rate kappa*(S+I).
            ``'peak_parasitism_day'`` -- day of peak parasitism rate.
            ``'peak_parasitism_value'`` -- value at peak parasitism.
            ``'peak_defoliation_rate_day'`` -- day of peak defoliation rate.
            ``'peak_defoliation_rate_value'`` -- value at peak defoliation rate.
            ``'functional_response'`` -- dict with ``'S_range'`` and ``'fr'``
            arrays for plotting the Holling Type II functional response
            at different parasitoid levels.

        Raises
        ------
        ValueError
            If within-season data is not available or year_index is out of range.
        """
        if "within_season" not in sim_result:
            raise ValueError(
                "Simulation result has no within-season data. "
                "Run simulate() with store_within_season=True."
            )
        ws_sols = sim_result["within_season"]
        if year_index < 0 or year_index >= len(ws_sols):
            raise ValueError(
                f"year_index {year_index} out of range [0, {len(ws_sols) - 1}]."
            )

        sol = ws_sols[year_index]
        tau = np.asarray(sol.t)
        S = np.maximum(sol.y[0], 0.0)
        I = np.maximum(sol.y[1], 0.0)
        F = np.maximum(sol.y[2], 0.0)
        D = sol.y[3]

        p = self.params

        # Derived: instantaneous parasitism rate
        parasitism_rate = p["beta"] * S * F / (1.0 + p["h"] * S)

        # Derived: instantaneous defoliation rate
        defoliation_rate = p["kappa"] * (S + I)

        # Peak parasitism
        peak_par_idx = int(np.argmax(parasitism_rate))
        peak_par_day = float(tau[peak_par_idx])
        peak_par_val = float(parasitism_rate[peak_par_idx])

        # Peak defoliation rate
        peak_def_idx = int(np.argmax(defoliation_rate))
        peak_def_day = float(tau[peak_def_idx])
        peak_def_val = float(defoliation_rate[peak_def_idx])

        # Functional response curve: beta * S / (1 + h * S) at varying S
        S_range = np.linspace(0, float(np.max(S)) * 1.5 + 0.01, 200)
        fr = p["beta"] * S_range / (1.0 + p["h"] * S_range)

        return {
            "tau": tau,
            "S": S,
            "I": I,
            "F": F,
            "D": D,
            "parasitism_rate": parasitism_rate,
            "defoliation_rate": defoliation_rate,
            "peak_parasitism_day": peak_par_day,
            "peak_parasitism_value": peak_par_val,
            "peak_defoliation_rate_day": peak_def_day,
            "peak_defoliation_rate_value": peak_def_val,
            "functional_response": {
                "S_range": S_range,
                "fr": fr,
            },
        }

    # ------------------------------------------------------------------
    # Parasitoid invasion reproduction number
    # ------------------------------------------------------------------

    def compute_R_P(self, S_bar: Optional[float] = None) -> float:
        """Compute the parasitoid invasion reproduction number R_P.

        .. math::

            R_P = \\frac{\\beta \\, \\eta \\, \\delta \\, \\sigma_F}
                       {(1 + h \\, \\bar S) \\, \\mu_F \\, (\\mu_I + \\delta)}

        If *S_bar* is not provided, it is taken as the parasitoid-free
        equilibrium beetle density (manuscript Eq. 12).

        Parameters
        ----------
        S_bar : float, optional
            Equilibrium susceptible beetle density.  Defaults to
            parasitoid-free equilibrium.

        Returns
        -------
        float
            Invasion reproduction number R_P.
        """
        p = self.params

        if S_bar is None:
            # Parasitoid-free equilibrium: solve for S_bar from the annual map
            # At equilibrium A* = R_B * sigma_A * S_T / (1 + sigma_A * S_T / K_0)
            # with F=0 the within-season dynamics simplify.
            # Approximate by running the model to steady-state with F=0.
            old_u_P = self.u_P
            self.u_P = 0.0
            A_t = p["K_0"] * 0.5  # initial guess
            K_t = p["K_0"]
            for _ in range(200):
                # Beverton-Holt at season start
                S0 = p["R_B"] * A_t / (1.0 + A_t / K_t)
                sol, end = self.integrate_season(S0=S0, I0=0.0, F0=0.0, D0=0.0)
                S_T = end["S_T"]
                D_T = end["D_T"]
                A_next = p["sigma_A"] * S_T
                K_next = p["K_0"] * np.exp(-p["phi"] * D_T)
                if abs(A_next - A_t) < 1e-10 and abs(K_next - K_t) < 1e-10:
                    break
                A_t = A_next
                K_t = K_next
            S_bar = end["S_T"]
            self.u_P = old_u_P

        R_P = (
            p["beta"] * p["eta"] * p["delta"] * p["sigma_F"]
            / ((1.0 + p["h"] * S_bar) * p["mu_F"] * (p["mu_I"] + p["delta"]))
        )
        return R_P

    # ------------------------------------------------------------------
    # Equilibrium analysis
    # ------------------------------------------------------------------

    def _annual_map_vec(self, x: np.ndarray) -> np.ndarray:
        """Evaluate the annual map as a vector function (A,F,K,D) -> (A',F',K',D')."""
        A, F, K, D = float(x[0]), float(x[1]), float(x[2]), float(x[3])
        # Clamp to non-negative
        A = max(A, 0.0)
        F = max(F, 0.0)
        K = max(K, 1e-12)
        D = max(D, 0.0)
        result = self.annual_map(A, F, K, D)
        return np.array([
            result["A_next"], result["F_next"],
            result["K_next"], result["D_next"],
        ])

    @staticmethod
    def _classify_equilibrium(
        A: float, F: float, K: float, D: float, tol: float,
    ) -> str:
        """Classify an equilibrium point into one of the four classes."""
        if A < tol:
            return "trivial"
        if F < tol and D < tol:
            return "canopy_only"
        if F < tol:
            return "parasitoid_free"
        return "coexistence"

    def find_fixed_points(
        self, tol: float = 1e-8, max_iter: int = 500,
    ) -> List[FixedPoint]:
        """Find fixed points of the annual map by searching from multiple ICs.

        The annual map G maps (A, F, K, D) -> (A', F', K', D').
        A fixed point satisfies G(x*) = x*.  We search from at least 20
        initial conditions spanning the parameter ranges using
        ``scipy.optimize.fsolve``.

        Parameters
        ----------
        tol : float
            Tolerance for considering a state variable as zero and for
            deduplicating fixed points.
        max_iter : int
            Maximum iterations for each fsolve call.

        Returns
        -------
        list of FixedPoint
        """
        p = self.params
        K0 = p["K_0"]

        def residual(x: np.ndarray) -> np.ndarray:
            x_clamped = np.maximum(x, 0.0)
            x_clamped[2] = max(x_clamped[2], 1e-12)
            return self._annual_map_vec(x_clamped) - x_clamped

        # Generate initial conditions using Latin Hypercube Sampling
        sampler = qmc.LatinHypercube(d=4, seed=42)
        sample = sampler.random(n=20)
        # Scale: A in [0, 2*K0], F in [0, K0], K in [0.1*K0, K0], D in [0, 5]
        l_bounds = np.array([0.0, 0.0, 0.1 * K0, 0.0])
        u_bounds = np.array([2.0 * K0, K0, K0, 5.0])
        ics = qmc.scale(sample, l_bounds, u_bounds)

        # Also add some special initial conditions
        extra_ics = [
            [0.0, 0.0, K0, 0.0],          # trivial
            [K0 * 0.5, 0.0, K0, 0.0],     # parasitoid-free
            [K0, K0 * 0.3, K0, 1.0],       # coexistence guess
            [K0 * 0.1, K0 * 0.1, K0, 0.5], # low-density coexistence
        ]
        all_ics = np.vstack([ics, extra_ics])

        raw_fps: List[np.ndarray] = []

        for ic in all_ics:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    sol, info, ier, _ = fsolve(
                        residual, ic, full_output=True, maxfev=max_iter,
                    )
                if ier != 1:
                    continue
                # Check residual is actually small
                if np.max(np.abs(info["fvec"])) > 1e-6:
                    continue
                # Clamp and reject clearly unphysical results
                sol = np.maximum(sol, 0.0)
                sol[2] = max(sol[2], 0.0)
                if np.any(np.isnan(sol)) or np.any(np.isinf(sol)):
                    continue
                raw_fps.append(sol)
            except Exception:
                continue

        # Deduplicate fixed points
        unique_fps: List[np.ndarray] = []
        for fp in raw_fps:
            is_dup = False
            for ufp in unique_fps:
                if np.allclose(fp, ufp, atol=tol * 100):
                    is_dup = True
                    break
            if not is_dup:
                unique_fps.append(fp)

        # Classify and compute stability for each fixed point
        fixed_points: List[FixedPoint] = []
        for fp in unique_fps:
            A, F, K, D = fp[0], fp[1], fp[2], fp[3]
            eq_class = self._classify_equilibrium(A, F, K, D, tol)

            try:
                jac = self.compute_jacobian(A, F, K, D)
                dom_eig, stable, bif_type = self.classify_stability(jac)
            except Exception:
                warnings.warn(
                    f"Could not compute stability for fixed point "
                    f"A={A:.4f}, F={F:.4f}, K={K:.4f}, D={D:.4f}",
                    stacklevel=2,
                )
                dom_eig, stable, bif_type = np.nan, False, "unknown"

            fixed_points.append(FixedPoint(
                A_star=A,
                F_star=F,
                K_star=K,
                D_star=D,
                equilibrium_class=eq_class,
                stable=stable,
                dominant_eigenvalue=dom_eig,
                bifurcation_type=bif_type,
            ))

        return fixed_points

    def compute_jacobian(
        self, A: float, F: float, K: float, D: float, eps: float = 1e-6,
    ) -> np.ndarray:
        """Numerically compute the 4x4 Jacobian of the annual map.

        Uses central finite differences.

        Parameters
        ----------
        A, F, K, D : float
            State at which to evaluate the Jacobian.
        eps : float
            Perturbation size for finite differences.

        Returns
        -------
        np.ndarray
            4x4 Jacobian matrix.
        """
        x0 = np.array([A, F, K, D], dtype=float)
        jac = np.zeros((4, 4))

        for j in range(4):
            x_plus = x0.copy()
            x_minus = x0.copy()
            # Scale eps by magnitude of the variable to handle different scales
            h = eps * max(abs(x0[j]), 1.0)
            x_plus[j] += h
            x_minus[j] -= h
            # Ensure non-negative
            x_plus = np.maximum(x_plus, 0.0)
            x_minus = np.maximum(x_minus, 0.0)
            x_plus[2] = max(x_plus[2], 1e-12)
            x_minus[2] = max(x_minus[2], 1e-12)
            try:
                f_plus = self._annual_map_vec(x_plus)
                f_minus = self._annual_map_vec(x_minus)
                jac[:, j] = (f_plus - f_minus) / (x_plus[j] - x_minus[j])
            except Exception:
                warnings.warn(
                    f"Jacobian computation failed for column {j} at "
                    f"({A}, {F}, {K}, {D})",
                    stacklevel=2,
                )
                jac[:, j] = np.nan

        return jac

    def classify_stability(
        self, jacobian: np.ndarray,
    ) -> tuple:
        """Classify stability from the Jacobian eigenvalues.

        Parameters
        ----------
        jacobian : np.ndarray
            4x4 Jacobian matrix of the annual map at a fixed point.

        Returns
        -------
        dominant_eigenvalue : float
            Maximum absolute eigenvalue.
        stable : bool
            True if all eigenvalues have absolute value < 1.
        bifurcation_type : str
            'stable', 'fold', 'flip', or 'neimark_sacker'.
        """
        eigvals = np.linalg.eigvals(jacobian)
        abs_eigvals = np.abs(eigvals)
        dom_eig = float(np.max(abs_eigvals))
        stable = bool(dom_eig < 1.0)

        if stable:
            bif_type = "stable"
        else:
            # Check which eigenvalue(s) cross the unit circle
            crossing_idx = np.where(abs_eigvals >= 1.0)[0]
            crossing_eigs = eigvals[crossing_idx]

            # Check for complex pair (Neimark-Sacker)
            has_complex = any(abs(e.imag) > 1e-8 for e in crossing_eigs)
            if has_complex:
                bif_type = "neimark_sacker"
            else:
                # Real eigenvalue(s) crossing
                real_crossing = [e.real for e in crossing_eigs if abs(e.imag) <= 1e-8]
                if any(r < 0 for r in real_crossing):
                    bif_type = "flip"
                else:
                    bif_type = "fold"

        return dom_eig, stable, bif_type

    def basin_stability(self, n_samples: int = 200) -> Dict[str, float]:
        """Estimate basin stability using Latin Hypercube Sampling.

        Sample initial conditions, simulate each for 200 years, and classify
        the attractor reached.

        Parameters
        ----------
        n_samples : int
            Number of initial condition samples.

        Returns
        -------
        dict
            Mapping of equilibrium_class -> fraction of initial conditions
            that converged to it.
        """
        p = self.params
        K0 = p["K_0"]
        tol = 1e-6

        sampler = qmc.LatinHypercube(d=4, seed=123)
        sample = sampler.random(n=n_samples)
        l_bounds = np.array([0.0, 0.0, 0.1 * K0, 0.0])
        u_bounds = np.array([2.0 * K0, K0, K0, 5.0])
        ics = qmc.scale(sample, l_bounds, u_bounds)

        counts: Dict[str, int] = {
            "trivial": 0,
            "canopy_only": 0,
            "parasitoid_free": 0,
            "coexistence": 0,
            "non_convergent": 0,
        }

        for ic in ics:
            try:
                result = self.simulate(
                    A0=ic[0], F0=ic[1], K0=ic[2], D0=ic[3], n_years=200,
                )
                A_end = result["A"][-1]
                F_end = result["F"][-1]
                K_end = result["K"][-1]
                D_end = result["D"][-1]

                # Check for convergence: compare last two years
                A_prev = result["A"][-2]
                F_prev = result["F"][-2]
                K_prev = result["K"][-2]
                D_prev = result["D"][-2]

                converged = (
                    abs(A_end - A_prev) < tol * max(A_end, 1.0)
                    and abs(F_end - F_prev) < tol * max(F_end, 1.0)
                    and abs(K_end - K_prev) < tol * max(K_end, 1.0)
                    and abs(D_end - D_prev) < tol * max(D_end, 1.0)
                )

                if not converged:
                    # Could be a limit cycle — check period-2
                    if len(result["A"]) >= 3:
                        A_pp = result["A"][-3]
                        F_pp = result["F"][-3]
                        converged_p2 = (
                            abs(A_end - A_pp) < tol * max(A_end, 1.0)
                            and abs(F_end - result["F"][-3]) < tol * max(F_end, 1.0)
                        )
                        if converged_p2:
                            converged = True

                if not converged:
                    counts["non_convergent"] += 1
                    continue

                eq_class = self._classify_equilibrium(
                    A_end, F_end, K_end, D_end, tol,
                )
                counts[eq_class] += 1

            except Exception:
                counts["non_convergent"] += 1
                continue

        # Convert to fractions
        total = float(n_samples)
        fractions: Dict[str, float] = {k: v / total for k, v in counts.items()}
        # Remove classes with zero fraction
        fractions = {k: v for k, v in fractions.items() if v > 0}
        return fractions

    # ------------------------------------------------------------------
    # Resistance and Resilience metrics (manuscript Section 2.4)
    # ------------------------------------------------------------------

    def compute_R1(
        self,
        fp: Optional["FixedPoint"] = None,
        perturbation_frac: float = 0.2,
        n_years: int = 50,
    ) -> float:
        """Compute resistance R1 (manuscript Eq. R1).

        R1 = (x_ref - x_max_dev) / x_ref

        where x_ref is the equilibrium beetle density and x_max_dev is
        the maximum deviation from x_ref over *n_years* after a
        perturbation of *perturbation_frac* of x_ref.

        Parameters
        ----------
        fp : FixedPoint, optional
            Fixed point to perturb.  If None, uses the first coexistence
            fixed point found, or the first non-trivial one.
        perturbation_frac : float
            Fraction of A* to perturb (default 0.2 = 20%).
        n_years : int
            Number of years to simulate after perturbation.

        Returns
        -------
        float
            Resistance index R1, bounded in [-1, 1].
        """
        if fp is None:
            fps = self.find_fixed_points()
            coex = [f for f in fps if f.equilibrium_class == "coexistence"]
            if coex:
                fp = coex[0]
            else:
                nontrivial = [f for f in fps if f.A_star > 1e-8]
                if not nontrivial:
                    return float("nan")
                fp = nontrivial[0]

        x_ref = fp.A_star
        if x_ref < 1e-12:
            return float("nan")

        A0_perturbed = x_ref * (1.0 + perturbation_frac)
        sim = self.simulate(
            A0=A0_perturbed, F0=fp.F_star, K0=fp.K_star, D0=fp.D_star,
            n_years=n_years,
        )

        x_max_dev = float(np.max(np.abs(sim["A"] - x_ref)))
        R1 = (x_ref - x_max_dev) / x_ref
        return float(np.clip(R1, -1.0, 1.0))

    def compute_R2(
        self,
        fp: Optional["FixedPoint"] = None,
        perturbation_frac: float = 0.2,
        Y: int = 5,
        n_years: int = 50,
    ) -> float:
        """Compute resilience R2 (manuscript Eq. R2).

        R2 = (x_max_dev - x_Y) / (x_max_dev - x_ref)

        where x_Y is the beetle density after Y years following the
        maximum deviation.

        Parameters
        ----------
        fp : FixedPoint, optional
            Fixed point to perturb.
        perturbation_frac : float
            Fraction of A* to perturb (default 0.2 = 20%).
        Y : int
            Recovery window in annual cycles (default 5).
        n_years : int
            Total simulation years (must be > Y).

        Returns
        -------
        float
            Resilience index R2.
        """
        if fp is None:
            fps = self.find_fixed_points()
            coex = [f for f in fps if f.equilibrium_class == "coexistence"]
            if coex:
                fp = coex[0]
            else:
                nontrivial = [f for f in fps if f.A_star > 1e-8]
                if not nontrivial:
                    return float("nan")
                fp = nontrivial[0]

        x_ref = fp.A_star
        if x_ref < 1e-12:
            return float("nan")

        A0_perturbed = x_ref * (1.0 + perturbation_frac)
        sim = self.simulate(
            A0=A0_perturbed, F0=fp.F_star, K0=fp.K_star, D0=fp.D_star,
            n_years=n_years,
        )

        deviations = np.abs(sim["A"] - x_ref)
        max_dev_idx = int(np.argmax(deviations))
        x_max_dev = deviations[max_dev_idx]

        # x_Y: state Y years after the maximum deviation
        y_idx = min(max_dev_idx + Y, len(sim["A"]) - 1)
        x_Y = abs(sim["A"][y_idx] - x_ref)

        denom = x_max_dev - x_ref  # note: x_max_dev is deviation, x_ref used as baseline
        # Use the deviation form: R2 = (max_dev - dev_at_Y) / max_dev
        if x_max_dev < 1e-12:
            return 1.0  # no deviation = perfect resilience
        R2 = (x_max_dev - x_Y) / x_max_dev
        return float(R2)

    # ------------------------------------------------------------------
    # Latitude metric (manuscript Section 2.4)
    # ------------------------------------------------------------------

    def adaptive_stability_profile(
        self,
        param_name: str,
        param_range: np.ndarray,
        perturbation_frac: float = 0.2,
        n_recovery_years: int = 5,
        n_sim_years: int = 50,
    ) -> Dict[str, np.ndarray]:
        """Sweep a parameter and compute R1, R2 at each value.

        Parameters
        ----------
        param_name : str
            Name of the parameter to sweep.
        param_range : array-like
            Array of parameter values to evaluate.
        perturbation_frac : float
            Perturbation fraction for R1/R2 computation.
        n_recovery_years : int
            Recovery window Y for R2.
        n_sim_years : int
            Simulation length for each R1/R2 evaluation.

        Returns
        -------
        dict
            ``'param_values'``, ``'R1'``, ``'R2'`` -- arrays of equal length.
        """
        param_range = np.asarray(param_range, dtype=float)
        R1_arr = np.full(len(param_range), np.nan)
        R2_arr = np.full(len(param_range), np.nan)

        original_val = self.params[param_name]

        for i, val in enumerate(param_range):
            self.params[param_name] = val
            try:
                fps = self.find_fixed_points()
                # Pick best fixed point: prefer coexistence, then non-trivial
                coex = [f for f in fps if f.equilibrium_class == "coexistence"]
                if coex:
                    fp = coex[0]
                else:
                    nontrivial = [f for f in fps if f.A_star > 1e-8]
                    if not nontrivial:
                        continue
                    fp = nontrivial[0]

                R1_arr[i] = self.compute_R1(
                    fp=fp, perturbation_frac=perturbation_frac,
                    n_years=n_sim_years,
                )
                R2_arr[i] = self.compute_R2(
                    fp=fp, perturbation_frac=perturbation_frac,
                    Y=n_recovery_years, n_years=n_sim_years,
                )
            except Exception:
                continue

        self.params[param_name] = original_val

        return {
            "param_values": param_range,
            "R1": R1_arr,
            "R2": R2_arr,
        }

    # ------------------------------------------------------------------
    # Latitude metric (manuscript Section 2.4)
    # ------------------------------------------------------------------

    def compute_latitude(
        self,
        fp: Optional["FixedPoint"] = None,
        max_delta: float = 2.0,
        n_steps: int = 50,
        n_years: int = 50,
        tol: float = 0.1,
    ) -> float:
        """Compute latitude: maximum perturbation the system can absorb.

        Progressively increases perturbation magnitude in A_t from the
        fixed point until the annual map fails to return to the original
        equilibrium within *n_years* iterations.

        Parameters
        ----------
        fp : FixedPoint, optional
            Fixed point to test.
        max_delta : float
            Maximum perturbation magnitude to test (as fraction of A*).
        n_steps : int
            Number of perturbation levels to test.
        n_years : int
            Iterations allowed for return to equilibrium.
        tol : float
            Relative tolerance for considering the system has returned.

        Returns
        -------
        float
            Latitude (maximum perturbation fraction before regime shift).
        """
        if fp is None:
            fps = self.find_fixed_points()
            coex = [f for f in fps if f.equilibrium_class == "coexistence"]
            if coex:
                fp = coex[0]
            else:
                nontrivial = [f for f in fps if f.A_star > 1e-8]
                if not nontrivial:
                    return 0.0
                fp = nontrivial[0]

        x_ref = fp.A_star
        if x_ref < 1e-12:
            return 0.0

        latitude = 0.0
        for i in range(1, n_steps + 1):
            delta = (i / n_steps) * max_delta
            A0_perturbed = x_ref * (1.0 + delta)

            sim = self.simulate(
                A0=A0_perturbed, F0=fp.F_star, K0=fp.K_star, D0=fp.D_star,
                n_years=n_years,
            )

            # Check if system returns to the original equilibrium
            A_final = sim["A"][-1]
            returned = abs(A_final - x_ref) < tol * x_ref

            if returned:
                latitude = delta
            else:
                break

        return latitude

    # ------------------------------------------------------------------
    # Bifurcation diagrams (manuscript Figs. 2-3)
    # ------------------------------------------------------------------

    def bifurcation_diagram(
        self,
        param_name: str,
        param_range: np.ndarray,
        n_points: int = 100,
    ) -> Dict:
        """Sweep a parameter and compute equilibria at each value.

        For each parameter value, finds all fixed points, classifies
        equilibrium type, and computes stability (dominant eigenvalue
        and R_P).  This produces data for bifurcation diagrams like
        manuscript Figures 2-3.

        Parameters
        ----------
        param_name : str
            Name of the parameter to sweep.
        param_range : array-like
            Array of parameter values.  If None, *n_points* values are
            generated from the parameter's registry bounds.
        n_points : int
            Number of sweep points (used only when *param_range* is
            generated from bounds).

        Returns
        -------
        dict
            ``'param_values'`` -- 1-D array of swept values.
            ``'equilibria'`` -- list of lists of FixedPoint (one list
            per parameter value).
            ``'R_P'`` -- 1-D array of R_P at each value.
        """
        from .parameters import PARAM_REGISTRY

        param_range = np.asarray(param_range, dtype=float)
        original_val = self.params[param_name]

        all_equilibria: List[List[FixedPoint]] = []
        R_P_arr = np.full(len(param_range), np.nan)

        for i, val in enumerate(param_range):
            self.params[param_name] = val
            try:
                fps = self.find_fixed_points()
                all_equilibria.append(fps)
            except Exception:
                all_equilibria.append([])
            try:
                R_P_arr[i] = self.compute_R_P()
            except Exception:
                pass

        self.params[param_name] = original_val

        return {
            "param_values": param_range,
            "equilibria": all_equilibria,
            "R_P": R_P_arr,
        }

    def rp_boundary(
        self,
        param1_name: str,
        param1_range: np.ndarray,
        param2_name: str,
        param2_range: np.ndarray,
        n_grid: int = 50,
    ) -> Dict:
        """Compute R_P over a 2-D parameter grid.

        Returns R_P values on a meshgrid so the R_P = 1 contour
        (transcritical bifurcation boundary) can be plotted, as in
        manuscript Fig. 2 Panel J.

        Parameters
        ----------
        param1_name, param2_name : str
            Names of the two parameters to sweep.
        param1_range, param2_range : array-like
            1-D arrays of values for each parameter.
        n_grid : int
            Not used when ranges are provided explicitly.

        Returns
        -------
        dict
            ``'param1_values'``, ``'param2_values'`` -- 1-D arrays.
            ``'R_P_grid'`` -- 2-D array of shape
            ``(len(param1_range), len(param2_range))``.
        """
        p1 = np.asarray(param1_range, dtype=float)
        p2 = np.asarray(param2_range, dtype=float)

        original_v1 = self.params[param1_name]
        original_v2 = self.params[param2_name]

        R_P_grid = np.full((len(p1), len(p2)), np.nan)

        for i, v1 in enumerate(p1):
            self.params[param1_name] = v1
            for j, v2 in enumerate(p2):
                self.params[param2_name] = v2
                try:
                    R_P_grid[i, j] = self.compute_R_P()
                except Exception:
                    pass

        self.params[param1_name] = original_v1
        self.params[param2_name] = original_v2

        return {
            "param1_values": p1,
            "param2_values": p2,
            "R_P_grid": R_P_grid,
        }
