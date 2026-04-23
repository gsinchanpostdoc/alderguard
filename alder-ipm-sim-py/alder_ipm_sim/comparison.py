from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple
import numpy as np
from .model import AlderIPMSimModel, FixedPoint
from .parameters import get_defaults


@dataclass
class ScenarioResult:
    """Result of a single scenario simulation with equilibrium metrics."""
    name: str
    params: Dict[str, float]
    sim: Dict  # {A, F, K, D} arrays
    fixed_points: List[FixedPoint]
    R_P: float
    R1: Optional[float]
    R2: Optional[float]
    equilibrium_class: str
    D_star: float
    K_star: float
    rho_star: float


def compare_scenarios(
    param_dicts: Sequence[Dict[str, float]],
    names: Sequence[str],
    n_years: int = 50,
    A0: float = 0.8,
    F0: float = 0.1,
    K0: float = 1.712,
    D0: float = 0.0,
) -> List[ScenarioResult]:
    """Run multiple simulations with different parameter sets and return aligned results.

    Parameters
    ----------
    param_dicts : sequence of dict
        Each dict is a parameter set (partial or full).
    names : sequence of str
        Human-readable name for each scenario.
    n_years : int
        Simulation horizon.
    A0, F0, K0, D0 : float
        Common initial conditions.

    Returns
    -------
    list of ScenarioResult
    """
    results = []
    for params, name in zip(param_dicts, names):
        model = AlderIPMSimModel(params)
        sim = model.simulate(A0=A0, F0=F0, K0=K0, D0=D0, n_years=n_years)

        fps = []
        try:
            fps = model.find_fixed_points()
        except Exception:
            pass

        rp = 0.0
        try:
            rp = model.compute_R_P()
        except Exception:
            pass

        r1, r2 = None, None
        try:
            r1 = model.compute_R1()
        except Exception:
            pass
        try:
            r2 = model.compute_R2()
        except Exception:
            pass

        # Find the stable coexistence or best fixed point
        eq_class = "unknown"
        d_star = float(sim["D"][-1])
        k_star = float(sim["K"][-1])
        rho_star = 0.0
        if fps:
            stable_fps = [fp for fp in fps if fp.stable]
            best = stable_fps[0] if stable_fps else fps[0]
            eq_class = best.equilibrium_class
            d_star = best.D_star
            k_star = best.K_star
            rho_star = best.dominant_eigenvalue

        results.append(ScenarioResult(
            name=name,
            params=dict(model.params),
            sim={k: np.array(v) if not isinstance(v, np.ndarray) else v
                 for k, v in sim.items() if k in ("A", "F", "K", "D")},
            fixed_points=fps,
            R_P=rp,
            R1=r1,
            R2=r2,
            equilibrium_class=eq_class,
            D_star=d_star,
            K_star=k_star,
            rho_star=rho_star,
        ))
    return results


def parameter_sweep_1d(
    param_name: str,
    values: np.ndarray,
    n_years: int = 50,
    A0: float = 0.8,
    F0: float = 0.1,
    K0: float = 1.712,
    D0: float = 0.0,
    base_params: Optional[Dict[str, float]] = None,
) -> Dict:
    """Sweep one parameter and record final-state metrics at each value.

    Parameters
    ----------
    param_name : str
        Name of the parameter to sweep.
    values : array-like
        Values to try.
    n_years : int
        Simulation horizon.
    base_params : dict, optional
        Base parameter set (defaults used if None).

    Returns
    -------
    dict
        'param_values': array, 'D_star': array, 'K_star': array,
        'rho_star': array, 'R_P': array, 'A_star': array, 'F_star': array,
        'equilibrium_class': list of str
    """
    values = np.asarray(values, dtype=float)
    base = dict(get_defaults())
    if base_params:
        base.update(base_params)

    n = len(values)
    D_star = np.full(n, np.nan)
    K_star = np.full(n, np.nan)
    A_star = np.full(n, np.nan)
    F_star = np.full(n, np.nan)
    rho_star = np.full(n, np.nan)
    R_P = np.full(n, np.nan)
    eq_class = ["unknown"] * n

    for i, val in enumerate(values):
        p = dict(base)
        p[param_name] = val
        model = AlderIPMSimModel(p)
        try:
            sim = model.simulate(A0=A0, F0=F0, K0=K0, D0=D0, n_years=n_years)
            D_star[i] = sim["D"][-1]
            K_star[i] = sim["K"][-1]
            A_star[i] = sim["A"][-1]
            F_star[i] = sim["F"][-1]
        except Exception:
            continue
        try:
            R_P[i] = model.compute_R_P()
        except Exception:
            pass
        try:
            fps = model.find_fixed_points()
            stable_fps = [fp for fp in fps if fp.stable]
            if stable_fps:
                best = stable_fps[0]
                rho_star[i] = best.dominant_eigenvalue
                eq_class[i] = best.equilibrium_class
        except Exception:
            pass

    return {
        "param_values": values,
        "D_star": D_star,
        "K_star": K_star,
        "A_star": A_star,
        "F_star": F_star,
        "rho_star": rho_star,
        "R_P": R_P,
        "equilibrium_class": eq_class,
    }


def parameter_sweep_2d(
    param1: str,
    values1: np.ndarray,
    param2: str,
    values2: np.ndarray,
    n_years: int = 50,
    A0: float = 0.8,
    F0: float = 0.1,
    K0: float = 1.712,
    D0: float = 0.0,
    base_params: Optional[Dict[str, float]] = None,
) -> Dict:
    """Sweep two parameters on a grid and record final-state regime metrics.

    Parameters
    ----------
    param1, param2 : str
        Parameter names.
    values1, values2 : array-like
        Values for each parameter.
    n_years : int
        Simulation horizon.
    base_params : dict, optional
        Base parameter set.

    Returns
    -------
    dict
        'param1_values', 'param2_values': 1-D arrays,
        'D_star': 2-D array (len(v1) x len(v2)),
        'K_star': 2-D array,
        'rho_star': 2-D array,
        'R_P': 2-D array,
        'equilibrium_class': 2-D list of str
    """
    v1 = np.asarray(values1, dtype=float)
    v2 = np.asarray(values2, dtype=float)
    base = dict(get_defaults())
    if base_params:
        base.update(base_params)

    n1, n2 = len(v1), len(v2)
    D_grid = np.full((n1, n2), np.nan)
    K_grid = np.full((n1, n2), np.nan)
    rho_grid = np.full((n1, n2), np.nan)
    RP_grid = np.full((n1, n2), np.nan)
    eq_grid = [["unknown"] * n2 for _ in range(n1)]

    for i, val1 in enumerate(v1):
        for j, val2 in enumerate(v2):
            p = dict(base)
            p[param1] = val1
            p[param2] = val2
            model = AlderIPMSimModel(p)
            try:
                sim = model.simulate(A0=A0, F0=F0, K0=K0, D0=D0, n_years=n_years)
                D_grid[i, j] = sim["D"][-1]
                K_grid[i, j] = sim["K"][-1]
            except Exception:
                continue
            try:
                RP_grid[i, j] = model.compute_R_P()
            except Exception:
                pass
            try:
                fps = model.find_fixed_points()
                stable_fps = [fp for fp in fps if fp.stable]
                if stable_fps:
                    rho_grid[i, j] = stable_fps[0].dominant_eigenvalue
                    eq_grid[i][j] = stable_fps[0].equilibrium_class
            except Exception:
                pass

    return {
        "param1_values": v1,
        "param2_values": v2,
        "D_star": D_grid,
        "K_star": K_grid,
        "rho_star": rho_grid,
        "R_P": RP_grid,
        "equilibrium_class": eq_grid,
    }
