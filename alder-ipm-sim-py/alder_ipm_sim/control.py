# Optimal control comparison for the Alnus-beetle-parasitoid-bird system.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import differential_evolution

from .model import AlderIPMSimModel


@dataclass
class OptimalControl:
    """Result of optimising a single management scenario.

    Attributes
    ----------
    scenario : str
        Scenario label ('A', 'B', or 'C').
    optimal_controls : dict
        Optimised control inputs (``u_P``, ``u_C``, ``u_B``).
    cost_J : float
        Value of the cost functional at the optimum.
    final_equilibrium : dict
        End-of-simulation state ``{'A', 'F', 'K', 'D'}``.
    final_D_star : float
        Equilibrium cumulative defoliation.
    final_K_star : float
        Equilibrium carrying capacity.
    final_rho_star : float
        Dominant eigenvalue (spectral radius) of the annual-map Jacobian at
        the terminal state — values < 1 indicate local stability.
    feasible : bool
        True when all management criteria are satisfied.
    violations : list of str
        Human-readable descriptions of any violated feasibility criteria.
    """

    scenario: str
    optimal_controls: Dict[str, float]
    cost_J: float
    final_equilibrium: Dict[str, float]
    final_D_star: float
    final_K_star: float
    final_rho_star: float
    feasible: bool
    violations: List[str] = field(default_factory=list)


# Scenario definitions keyed by label.
# Each entry lists which controls are free (True) or fixed at zero (False).
_SCENARIOS: Dict[str, Dict[str, bool]] = {
    "A": {"u_P": True, "u_C": False, "u_B": False},
    "B": {"u_P": True, "u_C": False, "u_B": True},
    "C": {"u_P": True, "u_C": True, "u_B": True},
}


class ControlOptimizer:
    """Optimal control comparison across three management scenarios.

    The three scenarios follow the manuscript's integrated pest-management
    framework:

    * **Scenario A — Parasitoid augmentation only.**
      Relies solely on parasitoid biocontrol augmentation (releasing
      laboratory-reared *Meigenia mutabilis* adults into the stand).
      ``u_P`` is free; ``u_C = u_B = 0``.

    * **Scenario B — Parasitoid augmentation + bird habitat enhancement.**
      Adds bird habitat enhancement (installing nest boxes, planting
      hedgerows) to increase the bird predation index ``B_idx``.
      ``u_P`` and ``u_B`` are free; ``u_C = 0``.

    * **Scenario C — Full integrated control.**
      Adds direct larval removal (mechanical collection or targeted
      biopesticide application such as *Bacillus thuringiensis*) on top of
      Scenario B.
      ``u_P``, ``u_C``, and ``u_B`` are all free.

    Parameters
    ----------
    model : AlderIPMSimModel
        The configured model instance whose parameters define the system.
    """

    # Default cost-functional weights (manuscript Table 3)
    _DEFAULT_W_D: float = 10.0
    _DEFAULT_W_S: float = 1.0
    _DEFAULT_W_T: float = 5.0
    _DEFAULT_C_P: float = 2.0
    _DEFAULT_C_C: float = 5.0
    _DEFAULT_C_B_COST: float = 3.0

    def __init__(self, model: AlderIPMSimModel) -> None:
        self.model = model
        # Allow overriding cost weights via model params
        p = model.params
        self._W_D = p.get("w_D", self._DEFAULT_W_D)
        self._W_S = p.get("w_S", self._DEFAULT_W_S)
        self._W_T = p.get("w_T", self._DEFAULT_W_T)
        self._C_P = p.get("c_P_cost", self._DEFAULT_C_P)
        self._C_C = p.get("c_C_cost", self._DEFAULT_C_C)
        self._C_B_COST = p.get("c_B_cost", self._DEFAULT_C_B_COST)

    # ------------------------------------------------------------------
    # Cost functional
    # ------------------------------------------------------------------

    def objective_functional(
        self,
        controls: Dict[str, float],
        initial_state: Dict[str, float],
        n_years: int = 50,
    ) -> float:
        """Compute the cost functional *J* for a given control strategy.

        .. math::

            J = \\sum_{t=0}^{N-1} \\Bigl[
                \\int_0^T \\bigl( w_D\\,D(\\tau) + w_S\\,S(\\tau)
                                + c_P\\,u_P + c_C\\,u_C \\bigr) d\\tau
                + w_T\\,D(T) \\Bigr]
                + c_B\\,u_B \\times N

        Parameters
        ----------
        controls : dict
            ``{'u_P': …, 'u_C': …, 'u_B': …}``.
        initial_state : dict
            ``{'A0': …, 'F0': …, 'K0': …, 'D0': …}``.
        n_years : int
            Simulation horizon.

        Returns
        -------
        float
            Total cost *J*.
        """
        u_P = controls.get("u_P", 0.0)
        u_C = controls.get("u_C", 0.0)
        u_B = controls.get("u_B", 0.0)

        # Apply controls to the model
        mdl = self.model
        mdl.u_P = u_P
        mdl.u_C = u_C
        # Bird-habitat enhancement: B_t = b_0 * (1 + rho * u_B) (Eq. 7)
        original_B = mdl.params.get("_B_index_base")
        if original_B is None:
            original_B = mdl.params["B_index"]
            mdl.params["_B_index_base"] = original_B
        rho = mdl.params["rho"]
        mdl.params["B_index"] = original_B * (1.0 + rho * u_B)

        try:
            result = mdl.simulate(
                A0=initial_state["A0"],
                F0=initial_state["F0"],
                K0=initial_state["K0"],
                D0=initial_state["D0"],
                n_years=n_years,
                store_within_season=True,
            )
        finally:
            # Restore model state
            mdl.params["B_index"] = original_B
            mdl.u_P = 0.0
            mdl.u_C = 0.0

        total_cost = 0.0

        for yr in range(n_years):
            sol = result["within_season"][yr]
            t = sol.t
            S = np.maximum(sol.y[0], 0.0)
            D = sol.y[3]

            # Trapezoidal integration of running cost over the season
            integrand = self._W_D * D + self._W_S * S + self._C_P * u_P + self._C_C * u_C
            season_cost = float(np.trapz(integrand, t))

            # Terminal cost: defoliation at end of season
            season_cost += self._W_T * D[-1]

            total_cost += season_cost

        # Annual bird-habitat enhancement cost (lump sum each year)
        total_cost += self._C_B_COST * u_B * n_years

        return total_cost

    # ------------------------------------------------------------------
    # Scenario optimisation
    # ------------------------------------------------------------------

    def optimize_scenario(
        self,
        scenario: str,
        initial_state: Dict[str, float],
        n_years: int = 50,
    ) -> OptimalControl:
        """Optimise control inputs for a given management scenario.

        Uses ``scipy.optimize.differential_evolution`` for global
        optimisation within the control bounds.

        Parameters
        ----------
        scenario : str
            ``'A'``, ``'B'``, or ``'C'``.
        initial_state : dict
            ``{'A0', 'F0', 'K0', 'D0'}``.
        n_years : int
            Simulation horizon.

        Returns
        -------
        OptimalControl
        """
        if scenario not in _SCENARIOS:
            raise ValueError(f"Unknown scenario '{scenario}'. Choose from A, B, C.")

        free = _SCENARIOS[scenario]
        p = self.model.params

        # Build bounds for the free controls
        bounds: List[Tuple[float, float]] = []
        free_keys: List[str] = []
        if free["u_P"]:
            bounds.append((0.0, p["u_P_max"]))
            free_keys.append("u_P")
        if free["u_C"]:
            bounds.append((0.0, p["u_C_max"]))
            free_keys.append("u_C")
        if free["u_B"]:
            bounds.append((0.0, p["u_B_max"]))
            free_keys.append("u_B")

        def _obj(x: np.ndarray) -> float:
            ctrl = {"u_P": 0.0, "u_C": 0.0, "u_B": 0.0}
            for k, v in zip(free_keys, x):
                ctrl[k] = float(v)
            return self.objective_functional(ctrl, initial_state, n_years)

        result = differential_evolution(
            _obj,
            bounds,
            seed=42,
            maxiter=100,
            tol=1e-6,
            polish=True,
        )

        optimal_ctrl = {"u_P": 0.0, "u_C": 0.0, "u_B": 0.0}
        for k, v in zip(free_keys, result.x):
            optimal_ctrl[k] = float(v)

        # Evaluate the terminal state under optimal controls
        traj = self.multi_year_trajectory(optimal_ctrl, initial_state, n_years)
        A_end = traj["A"][-1]
        F_end = traj["F"][-1]
        K_end = traj["K"][-1]
        D_end = traj["D"][-1]

        # Compute spectral radius at the terminal state
        mdl = self.model
        mdl.u_P = optimal_ctrl["u_P"]
        mdl.u_C = optimal_ctrl["u_C"]
        original_B = mdl.params.get("_B_index_base", mdl.params["B_index"])
        rho = mdl.params["rho"]
        mdl.params["B_index"] = original_B * (1.0 + rho * optimal_ctrl["u_B"])
        try:
            jac = mdl.compute_jacobian(A_end, F_end, K_end, D_end)
            rho = float(np.max(np.abs(np.linalg.eigvals(jac))))
        except Exception:
            rho = float("nan")
        finally:
            mdl.params["B_index"] = original_B
            mdl.u_P = 0.0
            mdl.u_C = 0.0

        feasible, violations = self.feasibility_check(
            D_end, K_end, rho, F_end, K_trajectory=traj["K"]
        )

        return OptimalControl(
            scenario=scenario,
            optimal_controls=optimal_ctrl,
            cost_J=float(result.fun),
            final_equilibrium={"A": A_end, "F": F_end, "K": K_end, "D": D_end},
            final_D_star=D_end,
            final_K_star=K_end,
            final_rho_star=rho,
            feasible=feasible,
            violations=violations,
        )

    # ------------------------------------------------------------------
    # Strategy comparison
    # ------------------------------------------------------------------

    def compare_strategies(
        self,
        initial_state: Dict[str, float],
        n_years: int = 50,
    ) -> Dict:
        """Run all three scenarios and recommend the best feasible strategy.

        Parameters
        ----------
        initial_state : dict
            ``{'A0', 'F0', 'K0', 'D0'}``.
        n_years : int
            Simulation horizon.

        Returns
        -------
        dict
            ``'results'``: list of :class:`OptimalControl` for scenarios A–C.
            ``'recommended'``: the feasible strategy with lowest cost, or
            ``None`` if no strategy is feasible.
            ``'recommendation_text'``: plain-language guidance for managers.
        """
        results: List[OptimalControl] = []
        for sc in ("A", "B", "C"):
            results.append(self.optimize_scenario(sc, initial_state, n_years))

        feasible = [r for r in results if r.feasible]
        if feasible:
            recommended = min(feasible, key=lambda r: r.cost_J)
        else:
            recommended = None

        recommendation_text = self._build_recommendation(results, recommended)

        return {
            "results": results,
            "recommended": recommended,
            "recommendation_text": recommendation_text,
        }

    @staticmethod
    def _build_recommendation(
        results: List[OptimalControl],
        recommended: Optional[OptimalControl],
    ) -> str:
        """Build a plain-language management recommendation."""
        lines: List[str] = ["=== Management Strategy Comparison ===\n"]

        scenario_desc = {
            "A": (
                "Strategy A -- Parasitoid augmentation only: "
                "relies solely on releasing laboratory-reared parasitoid flies."
            ),
            "B": (
                "Strategy B -- Parasitoid augmentation + bird habitat: "
                "combines parasitoid releases with nest boxes and hedgerow planting "
                "to boost avian predation."
            ),
            "C": (
                "Strategy C -- Full integrated control: "
                "adds targeted larval removal (mechanical or biopesticide) "
                "on top of Strategy B."
            ),
        }

        for r in results:
            lines.append(scenario_desc[r.scenario])
            lines.append(f"  Cost J = {r.cost_J:.2f}")
            lines.append(
                f"  Final defoliation D* = {r.final_D_star:.4f}, "
                f"capacity K* = {r.final_K_star:.4f}, "
                f"spectral radius rho* = {r.final_rho_star:.4f}"
            )
            status = "FEASIBLE" if r.feasible else f"INFEASIBLE ({'; '.join(r.violations)})"
            lines.append(f"  Status: {status}\n")

        if recommended is not None:
            lines.append(
                f"Recommendation: Strategy {recommended.scenario} achieves the "
                f"management objectives at lowest cost (J = {recommended.cost_J:.2f})."
            )
            if recommended.scenario == "A":
                lines.append(
                    "Parasitoid augmentation alone is sufficient. "
                    "Managers should plan periodic releases of laboratory-reared "
                    "Meigenia mutabilis at the optimal rate."
                )
            elif recommended.scenario == "B":
                lines.append(
                    "Combining parasitoid releases with bird habitat enhancement "
                    "is recommended. Install nest boxes and plant hedgerows to "
                    "sustain avian predation alongside biocontrol releases."
                )
            else:
                lines.append(
                    "Full integrated control is necessary. In addition to "
                    "parasitoid releases and bird habitat enhancement, managers "
                    "should implement targeted larval removal (mechanical "
                    "collection or Bacillus thuringiensis application)."
                )
        else:
            lines.append(
                "WARNING: No strategy met all feasibility criteria within the "
                "optimisation bounds. Consider increasing control budgets, "
                "extending the management horizon, or revising management targets."
            )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Feasibility check
    # ------------------------------------------------------------------

    def feasibility_check(
        self,
        D_star: float,
        K_star: float,
        rho_star: float,
        F_star: float,
        K_trajectory: Optional[np.ndarray] = None,
    ) -> Tuple[bool, List[str]]:
        """Check whether a management outcome satisfies all ecological criteria.

        Criteria (manuscript Section 2.4):
        1. ``D* < D_crit`` -- defoliation below the critical threshold.
        2. ``K* > K_min`` for fewer than 3 consecutive years -- carrying
           capacity does not persistently fall below the minimum viable level.
        3. ``F* > 0``      -- parasitoid population persists.
        4. ``rho* < 1``    -- equilibrium is locally stable (tolerance 1e-3
           for numerical imprecision).

        Parameters
        ----------
        D_star : float
            Equilibrium cumulative defoliation.
        K_star : float
            Equilibrium carrying capacity.
        rho_star : float
            Spectral radius (dominant eigenvalue modulus) of the Jacobian.
        F_star : float
            Equilibrium parasitoid density.
        K_trajectory : np.ndarray, optional
            Full K time series for checking 3-consecutive-years criterion.
            If None, falls back to checking only the terminal K_star value.

        Returns
        -------
        feasible : bool
        violations : list of str
        """
        p = self.model.params
        violations: List[str] = []

        if D_star >= p["D_crit"]:
            violations.append(
                f"Defoliation D* = {D_star:.4f} >= D_crit = {p['D_crit']}"
            )

        # Check K trajectory for 3+ consecutive years below K_min
        K_min = p["K_min"]
        if K_trajectory is not None:
            consec = 0
            max_consec = 0
            for K_val in K_trajectory:
                if K_val <= K_min:
                    consec += 1
                    max_consec = max(max_consec, consec)
                else:
                    consec = 0
            if max_consec >= 3:
                violations.append(
                    f"Carrying capacity below K_min for {max_consec} consecutive years"
                )
        elif K_star <= K_min:
            violations.append(
                f"Carrying capacity K* = {K_star:.4f} <= K_min = {K_min}"
            )

        if F_star <= 0.0:
            violations.append("Parasitoid population extinct (F* <= 0)")
        if not np.isnan(rho_star) and rho_star >= 1.001:
            violations.append(
                f"Equilibrium unstable (rho* = {rho_star:.4f} >= 1.001)"
            )

        return (len(violations) == 0, violations)

    # ------------------------------------------------------------------
    # Multi-year trajectory
    # ------------------------------------------------------------------

    def multi_year_trajectory(
        self,
        controls: Dict[str, float],
        initial_state: Dict[str, float],
        n_years: int,
    ) -> Dict[str, np.ndarray]:
        """Simulate the controlled system and return year-by-year trajectories.

        This is the primary output for time-series visualisation of state
        variables and control effort under a chosen strategy.

        Parameters
        ----------
        controls : dict
            ``{'u_P': …, 'u_C': …, 'u_B': …}``.
        initial_state : dict
            ``{'A0', 'F0', 'K0', 'D0'}``.
        n_years : int
            Number of annual cycles to simulate.

        Returns
        -------
        dict
            ``'A', 'F', 'K', 'D'`` -- arrays of length ``n_years + 1``.
            ``'u_P', 'u_C', 'u_B'`` -- constant control arrays of length
            ``n_years``.
        """
        u_P = controls.get("u_P", 0.0)
        u_C = controls.get("u_C", 0.0)
        u_B = controls.get("u_B", 0.0)

        mdl = self.model
        mdl.u_P = u_P
        mdl.u_C = u_C
        original_B = mdl.params.get("_B_index_base", mdl.params["B_index"])
        rho = mdl.params["rho"]
        mdl.params["B_index"] = original_B * (1.0 + rho * u_B)

        try:
            sim = mdl.simulate(
                A0=initial_state["A0"],
                F0=initial_state["F0"],
                K0=initial_state["K0"],
                D0=initial_state["D0"],
                n_years=n_years,
            )
        finally:
            mdl.params["B_index"] = original_B
            mdl.u_P = 0.0
            mdl.u_C = 0.0

        sim["u_P"] = np.full(n_years, u_P)
        sim["u_C"] = np.full(n_years, u_C)
        sim["u_B"] = np.full(n_years, u_B)

        return sim

    # ------------------------------------------------------------------
    # Custom strategy evaluation
    # ------------------------------------------------------------------

    def custom_strategy(
        self,
        u_P: float,
        u_C: float,
        u_B: float,
        initial_state: Dict[str, float],
        n_years: int = 50,
    ) -> OptimalControl:
        """Evaluate a user-defined control combination without optimisation.

        This is useful for "what-if" analysis: the caller specifies exact
        control intensities and receives the same result structure as
        :meth:`optimize_scenario`, but the controls are taken as-is rather
        than being optimised.

        Parameters
        ----------
        u_P : float
            Parasitoid augmentation intensity.
        u_C : float
            Direct larval removal intensity.
        u_B : float
            Bird habitat enhancement intensity.
        initial_state : dict
            ``{'A0', 'F0', 'K0', 'D0'}``.
        n_years : int
            Simulation horizon.

        Returns
        -------
        OptimalControl
        """
        ctrl = {"u_P": u_P, "u_C": u_C, "u_B": u_B}

        cost_J = self.objective_functional(ctrl, initial_state, n_years)
        traj = self.multi_year_trajectory(ctrl, initial_state, n_years)

        A_end = traj["A"][-1]
        F_end = traj["F"][-1]
        K_end = traj["K"][-1]
        D_end = traj["D"][-1]

        # Compute spectral radius at the terminal state
        mdl = self.model
        mdl.u_P = u_P
        mdl.u_C = u_C
        original_B = mdl.params.get("_B_index_base", mdl.params["B_index"])
        rho_param = mdl.params["rho"]
        mdl.params["B_index"] = original_B * (1.0 + rho_param * u_B)
        try:
            jac = mdl.compute_jacobian(A_end, F_end, K_end, D_end)
            rho_star = float(np.max(np.abs(np.linalg.eigvals(jac))))
        except Exception:
            rho_star = float("nan")
        finally:
            mdl.params["B_index"] = original_B
            mdl.u_P = 0.0
            mdl.u_C = 0.0

        feasible, violations = self.feasibility_check(
            D_end, K_end, rho_star, F_end, K_trajectory=traj["K"]
        )

        return OptimalControl(
            scenario="Custom",
            optimal_controls=ctrl,
            cost_J=cost_J,
            final_equilibrium={"A": A_end, "F": F_end, "K": K_end, "D": D_end},
            final_D_star=D_end,
            final_K_star=K_end,
            final_rho_star=rho_star,
            feasible=feasible,
            violations=violations,
        )

    # ------------------------------------------------------------------
    # Pareto frontier (cost-effectiveness sweep)
    # ------------------------------------------------------------------

    def pareto_frontier(
        self,
        initial_state: Dict[str, float],
        n_points: int = 50,
        n_years: int = 50,
    ) -> Dict[str, np.ndarray]:
        """Sweep cost-effectiveness trade-offs by uniformly scaling controls.

        For each budget fraction *f* in ``np.linspace(0, 1, n_points)``, all
        three controls are set to ``f * u_max`` and the resulting cost and
        terminal ecological state are recorded.  This produces an
        approximate Pareto frontier without expensive multi-objective
        optimisation.

        Parameters
        ----------
        initial_state : dict
            ``{'A0', 'F0', 'K0', 'D0'}``.
        n_points : int
            Number of budget levels to evaluate.
        n_years : int
            Simulation horizon per evaluation.

        Returns
        -------
        dict
            ``'cost'``      -- total cost *J* at each budget level (length *n_points*).
            ``'final_D'``   -- terminal defoliation (length *n_points*).
            ``'final_K'``   -- terminal carrying capacity (length *n_points*).
            ``'final_rho'`` -- spectral radius at terminal state (length *n_points*).
        """
        costs = np.zeros(n_points)
        final_D = np.zeros(n_points)
        final_K = np.zeros(n_points)
        final_rho = np.zeros(n_points)

        p = self.model.params
        for i, frac in enumerate(np.linspace(0, 1, n_points)):
            ctrl = {
                "u_P": frac * p["u_P_max"],
                "u_C": frac * p["u_C_max"],
                "u_B": frac * p["u_B_max"],
            }
            costs[i] = self.objective_functional(ctrl, initial_state, n_years)
            traj = self.multi_year_trajectory(ctrl, initial_state, n_years)
            final_D[i] = traj["D"][-1]
            final_K[i] = traj["K"][-1]

            # Compute spectral radius at the terminal state
            A_end = traj["A"][-1]
            F_end = traj["F"][-1]
            mdl = self.model
            mdl.u_P = ctrl["u_P"]
            mdl.u_C = ctrl["u_C"]
            original_B = mdl.params.get("_B_index_base", mdl.params["B_index"])
            rho_param = mdl.params["rho"]
            mdl.params["B_index"] = original_B * (1.0 + rho_param * ctrl["u_B"])
            try:
                jac = mdl.compute_jacobian(A_end, F_end, final_K[i], final_D[i])
                final_rho[i] = float(np.max(np.abs(np.linalg.eigvals(jac))))
            except Exception:
                final_rho[i] = float("nan")
            finally:
                mdl.params["B_index"] = original_B
                mdl.u_P = 0.0
                mdl.u_C = 0.0

        return {
            "cost": costs,
            "final_D": final_D,
            "final_K": final_K,
            "final_rho": final_rho,
        }

    # ------------------------------------------------------------------
    # Temporal allocation (year-by-year cost breakdown)
    # ------------------------------------------------------------------

    def temporal_allocation(
        self,
        controls: Dict[str, float],
        initial_state: Dict[str, float],
        n_years: int,
    ) -> Dict[str, np.ndarray]:
        """Return year-by-year control intensity and cost breakdown.

        Simulates the system under the given constant controls and records
        per-year running cost (integrated within-season), terminal cost
        (end-of-season defoliation penalty), and control cost.

        Parameters
        ----------
        controls : dict
            ``{'u_P': …, 'u_C': …, 'u_B': …}``.
        initial_state : dict
            ``{'A0', 'F0', 'K0', 'D0'}``.
        n_years : int
            Number of annual cycles.

        Returns
        -------
        dict
            ``'years'``        -- ``np.arange(n_years)``.
            ``'u_P'``, ``'u_C'``, ``'u_B'`` -- constant control arrays.
            ``'running_cost'`` -- within-season integrated running cost per year.
            ``'terminal_cost'``-- end-of-season defoliation penalty per year.
            ``'control_cost'`` -- per-year expenditure on controls.
        """
        u_P = controls.get("u_P", 0.0)
        u_C = controls.get("u_C", 0.0)
        u_B = controls.get("u_B", 0.0)

        # Apply controls to the model
        mdl = self.model
        mdl.u_P = u_P
        mdl.u_C = u_C
        original_B = mdl.params.get("_B_index_base", mdl.params["B_index"])
        rho_param = mdl.params["rho"]
        mdl.params["B_index"] = original_B * (1.0 + rho_param * u_B)

        try:
            result = mdl.simulate(
                A0=initial_state["A0"],
                F0=initial_state["F0"],
                K0=initial_state["K0"],
                D0=initial_state["D0"],
                n_years=n_years,
                store_within_season=True,
            )
        finally:
            mdl.params["B_index"] = original_B
            mdl.u_P = 0.0
            mdl.u_C = 0.0

        running_cost = np.zeros(n_years)
        terminal_cost = np.zeros(n_years)
        control_cost = np.zeros(n_years)

        for yr in range(n_years):
            sol = result["within_season"][yr]
            t = sol.t
            S = np.maximum(sol.y[0], 0.0)
            D = sol.y[3]

            # Within-season running cost (ecological damage + control effort)
            integrand = self._W_D * D + self._W_S * S + self._C_P * u_P + self._C_C * u_C
            running_cost[yr] = float(np.trapz(integrand, t))

            # Terminal cost: defoliation penalty at end of season
            terminal_cost[yr] = self._W_T * D[-1]

            # Per-year control expenditure
            season_length = t[-1] - t[0]
            control_cost[yr] = (
                self._C_P * u_P * season_length
                + self._C_C * u_C * season_length
                + self._C_B_COST * u_B
            )

        return {
            "years": np.arange(n_years),
            "u_P": np.full(n_years, u_P),
            "u_C": np.full(n_years, u_C),
            "u_B": np.full(n_years, u_B),
            "running_cost": running_cost,
            "terminal_cost": terminal_cost,
            "control_cost": control_cost,
        }

    # ------------------------------------------------------------------
    # Comparative trajectories
    # ------------------------------------------------------------------

    def comparative_trajectories(
        self,
        initial_state: Dict[str, float],
        n_years: int = 50,
        custom_controls: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Dict[str, np.ndarray]]:
        """Return trajectory data for all standard scenarios plus an optional custom strategy.

        Optimises scenarios A, B, and C, then simulates each under its
        optimal controls to produce full state trajectories.  If
        *custom_controls* is provided, a ``'Custom'`` entry is added using
        those controls without optimisation.

        Parameters
        ----------
        initial_state : dict
            ``{'A0', 'F0', 'K0', 'D0'}``.
        n_years : int
            Simulation horizon.
        custom_controls : dict, optional
            ``{'u_P': …, 'u_C': …, 'u_B': …}`` for an additional custom
            strategy.  If ``None``, only A/B/C are included.

        Returns
        -------
        dict
            Mapping of scenario label (``'A'``, ``'B'``, ``'C'``, and
            optionally ``'Custom'``) to trajectory dicts (as returned by
            :meth:`multi_year_trajectory`).
        """
        trajectories: Dict[str, Dict[str, np.ndarray]] = {}

        for sc in ("A", "B", "C"):
            opt = self.optimize_scenario(sc, initial_state, n_years)
            traj = self.multi_year_trajectory(
                opt.optimal_controls, initial_state, n_years
            )
            trajectories[sc] = traj

        if custom_controls is not None:
            trajectories["Custom"] = self.multi_year_trajectory(
                custom_controls, initial_state, n_years
            )

        return trajectories
