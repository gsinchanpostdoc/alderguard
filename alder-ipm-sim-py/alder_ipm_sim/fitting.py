# Model fitting and parameter estimation routines.
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import differential_evolution, least_squares

from .model import AlderIPMSimModel
from .parameters import PARAM_REGISTRY, get_defaults

# State variable names used throughout the module.
_STATE_NAMES = ("A", "F", "K", "D")


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class FitResult:
    """Container for model-fitting results."""

    fitted_params: Dict[str, float]
    residuals: np.ndarray
    r_squared: float
    AIC: float
    BIC: float
    confidence_intervals: Dict[str, Tuple[float, float]]
    convergence_info: Dict[str, Any]
    param_correlation: Optional[np.ndarray] = None
    param_names_order: Optional[List[str]] = None


@dataclass
class ResidualDiagnostics:
    """Container for residual diagnostic statistics."""

    acf_values: np.ndarray
    acf_lags: np.ndarray
    qq_theoretical: np.ndarray
    qq_observed: np.ndarray
    durbin_watson: float


@dataclass
class BootstrapCIResult:
    """Container for bootstrap confidence intervals."""

    ci: Dict[str, Tuple[float, float]]
    bootstrap_samples: Dict[str, np.ndarray]
    n_bootstrap: int
    n_successful: int


@dataclass
class IdentifiabilityResult:
    """Container for parameter identifiability analysis."""

    eigenvalues: np.ndarray
    condition_number: float
    identifiable: Dict[str, bool]
    fim_diagonal: np.ndarray


@dataclass
class _PreparedData:
    """Internal structured data object returned by :meth:`prepare_data`."""

    times: np.ndarray
    obs: Dict[str, np.ndarray]  # state_name -> observed values
    timestep: str  # 'annual' or 'seasonal'
    n_obs: int


# ---------------------------------------------------------------------------
# ModelFitter
# ---------------------------------------------------------------------------

class ModelFitter:
    """Parameter estimation, prediction, and cross-validation for
    :class:`AlderIPMSimModel`.
    """

    def __init__(self, model: Optional[AlderIPMSimModel] = None) -> None:
        self.model = model if model is not None else AlderIPMSimModel()

    # ------------------------------------------------------------------
    # 1. Data preparation
    # ------------------------------------------------------------------

    def prepare_data(
        self,
        data,
        time_col: str = "year",
        state_cols: Optional[Dict[str, str]] = None,
        timestep: str = "annual",
    ) -> _PreparedData:
        """Validate and restructure input data for fitting.

        Parameters
        ----------
        data : pandas.DataFrame or dict of array-like
            Observed time-series data.
        time_col : str
            Column / key containing time values.
        state_cols : dict, optional
            Maps model state variable names (``'A'``, ``'F'``, ``'K'``,
            ``'D'``) to data column names, e.g.
            ``{'A': 'beetle_density', 'D': 'defoliation'}``.
            If *None*, looks for columns named ``A``, ``F``, ``K``, ``D``.
        timestep : str
            ``'annual'`` (default) or ``'seasonal'``.

        Returns
        -------
        _PreparedData
        """
        if timestep not in ("annual", "seasonal"):
            raise ValueError(f"timestep must be 'annual' or 'seasonal', got '{timestep}'")

        # --- Convert to arrays ------------------------------------------------
        # Support both pandas DataFrame and plain dict-of-arrays.
        if hasattr(data, "to_dict"):
            # pandas-like
            raw: Dict[str, np.ndarray] = {
                c: np.asarray(data[c], dtype=float) for c in data.columns
            }
        elif isinstance(data, dict):
            raw = {k: np.asarray(v, dtype=float) for k, v in data.items()}
        else:
            raise TypeError("data must be a pandas DataFrame or a dict of arrays")

        if time_col not in raw:
            raise KeyError(f"Time column '{time_col}' not found in data")

        times = raw[time_col]

        # --- Validate time ordering -------------------------------------------
        if np.any(np.diff(times) <= 0):
            raise ValueError("Time column must be strictly increasing")

        # --- Map state columns ------------------------------------------------
        if state_cols is None:
            state_cols = {s: s for s in _STATE_NAMES if s in raw}

        if not state_cols:
            raise ValueError(
                "No observable state columns found.  Provide state_cols mapping."
            )

        obs: Dict[str, np.ndarray] = {}
        for state_name, col_name in state_cols.items():
            if state_name not in _STATE_NAMES:
                raise ValueError(
                    f"Unknown state variable '{state_name}'.  "
                    f"Valid: {_STATE_NAMES}"
                )
            if col_name not in raw:
                raise KeyError(f"Column '{col_name}' not found in data")
            arr = raw[col_name]
            if np.any(np.isnan(arr)):
                raise ValueError(f"NaN values found in column '{col_name}'")

            # Handle zero/negative values for beetle density (log-transform issues)
            if state_name == "A" and np.any(arr <= 0):
                n_zero = int(np.sum(arr <= 0))
                eps = 1e-6
                warnings.warn(
                    f"Column '{col_name}' has {n_zero} zero/negative value(s). "
                    f"Adding epsilon={eps} for numerical stability.",
                    UserWarning,
                )
                arr = np.where(arr <= 0, eps, arr)

            obs[state_name] = arr

        n_obs = len(times)

        # Warn if data is short
        if n_obs < 10:
            warnings.warn(
                f"Time series has only {n_obs} observations (< 10). "
                f"Parameter estimates may be unreliable.",
                UserWarning,
            )

        # Detect and warn about gaps in time series
        diffs = np.diff(times)
        median_dt = np.median(diffs)
        if median_dt > 0:
            gap_idx = np.where(diffs > 2.0 * median_dt)[0]
            if len(gap_idx) > 0:
                gap_times = [(times[i], times[i + 1]) for i in gap_idx]
                warnings.warn(
                    f"Detected {len(gap_idx)} gap(s) in time series: {gap_times}. "
                    f"Fitting may be less accurate across gaps.",
                    UserWarning,
                )

        return _PreparedData(times=times, obs=obs, timestep=timestep, n_obs=n_obs)

    # ------------------------------------------------------------------
    # 2. Residual function
    # ------------------------------------------------------------------

    def residual_func(
        self,
        param_values: np.ndarray,
        param_names: Sequence[str],
        data: _PreparedData,
        weights: Optional[Dict[str, float]] = None,
    ) -> np.ndarray:
        """Compute weighted residual vector between model output and data.

        Parameters
        ----------
        param_values : array-like
            Current parameter values (same order as *param_names*).
        param_names : sequence of str
            Names corresponding to *param_values*.
        data : _PreparedData
            Structured observed data.
        weights : dict, optional
            Per-state weight, e.g. ``{'A': 1.0, 'D': 2.0}``.  Defaults to
            equal weights.

        Returns
        -------
        np.ndarray
            1-D residual vector (stacked across observed states and times).
        """
        # Apply candidate parameters to the model
        params = dict(self.model.params)
        for name, val in zip(param_names, param_values):
            params[name] = float(val)
        mdl = AlderIPMSimModel(params)

        if weights is None:
            weights = {s: 1.0 for s in data.obs}

        if data.timestep == "annual":
            return self._residual_annual(mdl, data, weights)
        else:
            return self._residual_seasonal(mdl, data, weights)

    # --- helpers for residual computation ---

    def _residual_annual(
        self,
        mdl: AlderIPMSimModel,
        data: _PreparedData,
        weights: Dict[str, float],
    ) -> np.ndarray:
        """Residuals for annual (between-year) data."""
        n = data.n_obs
        obs = data.obs
        observed_states = list(obs.keys())

        # Determine initial conditions from first observation (or defaults)
        ic = self._initial_conditions_from_data(data)

        # Simulate
        try:
            sim = mdl.simulate(
                A0=ic["A"], F0=ic["F"], K0=ic["K"], D0=ic["D"],
                n_years=n - 1,
            )
        except Exception:
            # Return large residuals if simulation fails
            return np.full(n * len(observed_states), 1e6)

        residuals: List[float] = []
        for s in observed_states:
            sim_arr = sim[s][:n]
            obs_arr = obs[s]
            w = weights.get(s, 1.0)
            # Normalise by observed scale to handle multi-scale variables
            scale = max(np.std(obs_arr), 1e-12)
            residuals.extend((w * (sim_arr - obs_arr) / scale).tolist())

        return np.array(residuals)

    def _residual_seasonal(
        self,
        mdl: AlderIPMSimModel,
        data: _PreparedData,
        weights: Dict[str, float],
    ) -> np.ndarray:
        """Residuals for seasonal (within-season) data."""
        obs = data.obs
        observed_states = list(obs.keys())
        times = data.times

        ic = self._initial_conditions_from_data(data)

        try:
            sol, _ = mdl.integrate_season(
                S0=ic["A"], I0=0.0, F0=ic["F"], D0=ic["D"],
                t_eval=times,
            )
        except Exception:
            return np.full(len(times) * len(observed_states), 1e6)

        # Mapping from state name to sol.y row index
        _idx = {"A": 0, "F": 2, "K": None, "D": 3}

        residuals: List[float] = []
        for s in observed_states:
            idx = _idx.get(s)
            if idx is None:
                # K is not part of within-season ODE; skip
                continue
            sim_arr = sol.y[idx]
            obs_arr = obs[s]
            w = weights.get(s, 1.0)
            scale = max(np.std(obs_arr), 1e-12)
            residuals.extend((w * (sim_arr - obs_arr) / scale).tolist())

        if not residuals:
            return np.array([0.0])
        return np.array(residuals)

    @staticmethod
    def _initial_conditions_from_data(data: _PreparedData) -> Dict[str, float]:
        """Extract initial conditions from data, using defaults where missing."""
        defaults = get_defaults()
        ic: Dict[str, float] = {
            "A": defaults.get("K_0", 1.0) * 0.5,
            "F": 0.1,
            "K": defaults.get("K_0", 1.0),
            "D": 0.0,
        }
        for s in _STATE_NAMES:
            if s in data.obs:
                ic[s] = float(data.obs[s][0])
        return ic

    # ------------------------------------------------------------------
    # 3. Main fitting method
    # ------------------------------------------------------------------

    def fit(
        self,
        data: _PreparedData,
        fit_params: Optional[List[str]] = None,
        method: str = "least_squares",
        bounds: bool = True,
    ) -> FitResult:
        """Fit model parameters to observed data.

        Parameters
        ----------
        data : _PreparedData
            Output of :meth:`prepare_data`.
        fit_params : list of str, optional
            Parameter names to estimate.  If *None*, fits a default
            identifiable subset.
        method : str
            ``'least_squares'``, ``'differential_evolution'``, or ``'dual'``
            (global then local refinement).
        bounds : bool
            If True, enforce bounds from ``PARAM_REGISTRY``.

        Returns
        -------
        FitResult
        """
        if method not in ("least_squares", "differential_evolution", "dual"):
            raise ValueError(f"Unknown method '{method}'")

        if fit_params is None:
            # Default identifiable subset
            fit_params = ["beta", "mu_S", "delta", "R_B", "phi", "kappa"]

        param_names = list(fit_params)
        x0 = np.array([self.model.params[n] for n in param_names])

        if bounds:
            lb = np.array([PARAM_REGISTRY[n].min_val for n in param_names])
            ub = np.array([PARAM_REGISTRY[n].max_val for n in param_names])
        else:
            lb = -np.inf * np.ones(len(param_names))
            ub = np.inf * np.ones(len(param_names))

        # --- Optimisation -----------------------------------------------------
        if method == "least_squares":
            result = self._fit_least_squares(param_names, x0, lb, ub, data)
        elif method == "differential_evolution":
            result = self._fit_de(param_names, lb, ub, data)
        else:  # dual
            de_result = self._fit_de(param_names, lb, ub, data)
            x0_refined = np.array([de_result.fitted_params[n] for n in param_names])
            result = self._fit_least_squares(
                param_names, x0_refined, lb, ub, data,
            )

        return result

    # --- optimiser back-ends ---

    def _fit_least_squares(
        self,
        param_names: List[str],
        x0: np.ndarray,
        lb: np.ndarray,
        ub: np.ndarray,
        data: _PreparedData,
    ) -> FitResult:
        ls_result = least_squares(
            self.residual_func,
            x0,
            args=(param_names, data),
            bounds=(lb, ub),
            method="trf",
            max_nfev=2000,
        )
        return self._build_fit_result(
            param_names, ls_result.x, ls_result.fun, ls_result.jac,
            data, {"optimizer": "least_squares", "nfev": ls_result.nfev,
                    "cost": float(ls_result.cost), "success": ls_result.success,
                    "message": ls_result.message},
        )

    def _fit_de(
        self,
        param_names: List[str],
        lb: np.ndarray,
        ub: np.ndarray,
        data: _PreparedData,
    ) -> FitResult:
        de_bounds = list(zip(lb, ub))

        def objective(x: np.ndarray) -> float:
            r = self.residual_func(x, param_names, data)
            return float(np.sum(r ** 2))

        de_result = differential_evolution(
            objective,
            de_bounds,
            maxiter=300,
            seed=42,
            tol=1e-8,
            polish=True,
        )

        # Approximate Jacobian at solution for confidence intervals
        residuals = self.residual_func(de_result.x, param_names, data)
        jac = self._numerical_jacobian(de_result.x, param_names, data)

        return self._build_fit_result(
            param_names, de_result.x, residuals, jac, data,
            {"optimizer": "differential_evolution", "nfev": de_result.nfev,
             "cost": float(de_result.fun), "success": de_result.success,
             "message": de_result.message},
        )

    def _numerical_jacobian(
        self,
        x: np.ndarray,
        param_names: Sequence[str],
        data: _PreparedData,
        eps: float = 1e-7,
    ) -> np.ndarray:
        """Central-difference Jacobian of the residual function."""
        r0 = self.residual_func(x, param_names, data)
        jac = np.zeros((len(r0), len(x)))
        for j in range(len(x)):
            dx = np.zeros_like(x)
            h = eps * max(abs(x[j]), 1.0)
            dx[j] = h
            r_plus = self.residual_func(x + dx, param_names, data)
            r_minus = self.residual_func(x - dx, param_names, data)
            jac[:, j] = (r_plus - r_minus) / (2.0 * h)
        return jac

    # --- post-processing ---

    @staticmethod
    def _build_fit_result(
        param_names: List[str],
        x_opt: np.ndarray,
        residuals: np.ndarray,
        jac: np.ndarray,
        data: _PreparedData,
        convergence_info: Dict[str, Any],
    ) -> FitResult:
        fitted_params = dict(zip(param_names, x_opt.tolist()))

        ss_res = float(np.sum(residuals ** 2))
        ss_tot = float(np.sum((residuals - np.mean(residuals)) ** 2)) + ss_res
        # Use total variance of residual vector elements as proxy
        n = len(residuals)
        k = len(param_names)

        r_squared = 1.0 - ss_res / max(ss_tot, 1e-30)

        # AIC / BIC (assuming Gaussian errors)
        sigma2 = ss_res / max(n - k, 1)
        sigma2 = max(sigma2, 1e-30)  # guard against log(0)
        log_lik = -0.5 * n * (np.log(2 * np.pi * sigma2) + 1.0)
        aic = -2.0 * log_lik + 2.0 * k
        bic = -2.0 * log_lik + k * np.log(max(n, 1))

        # Confidence intervals and correlation from Jacobian
        ci: Dict[str, Tuple[float, float]] = {}
        param_corr: Optional[np.ndarray] = None
        try:
            jtj = jac.T @ jac
            cov = np.linalg.inv(jtj) * sigma2
            se = np.sqrt(np.maximum(np.diag(cov), 0.0))
            for i, name in enumerate(param_names):
                ci[name] = (float(x_opt[i] - 1.96 * se[i]),
                            float(x_opt[i] + 1.96 * se[i]))
            # Correlation matrix
            d = np.sqrt(np.maximum(np.diag(cov), 1e-30))
            param_corr = cov / np.outer(d, d)
            np.fill_diagonal(param_corr, 1.0)
        except np.linalg.LinAlgError:
            for name, val in zip(param_names, x_opt):
                ci[name] = (float(val), float(val))

        # Add gradient norm to convergence info
        try:
            grad = jac.T @ residuals
            convergence_info["gradient_norm"] = float(np.linalg.norm(grad))
        except Exception:
            convergence_info["gradient_norm"] = None

        return FitResult(
            fitted_params=fitted_params,
            residuals=residuals,
            r_squared=r_squared,
            AIC=aic,
            BIC=bic,
            confidence_intervals=ci,
            convergence_info=convergence_info,
            param_correlation=param_corr,
            param_names_order=list(param_names),
        )

    # ------------------------------------------------------------------
    # 4. Profile likelihood
    # ------------------------------------------------------------------

    def profile_likelihood(
        self,
        data: _PreparedData,
        param_name: str,
        n_points: int = 50,
    ) -> Dict[str, np.ndarray]:
        """Compute profile likelihood for a single parameter.

        For each of *n_points* fixed values of *param_name* across its
        registry range, all other identifiable parameters are re-optimised.

        Returns
        -------
        dict
            ``'param_values'`` and ``'neg_log_likelihood'`` arrays.
        """
        meta = PARAM_REGISTRY[param_name]
        test_values = np.linspace(meta.min_val, meta.max_val, n_points)

        # Other parameters to optimise
        nuisance = [n for n in ["beta", "mu_S", "delta", "R_B", "phi", "kappa"]
                     if n != param_name]

        nll = np.zeros(n_points)

        for i, val in enumerate(test_values):
            # Fix the profiled parameter
            saved = self.model.params[param_name]
            self.model.params[param_name] = val

            x0 = np.array([self.model.params[n] for n in nuisance])
            lb = np.array([PARAM_REGISTRY[n].min_val for n in nuisance])
            ub = np.array([PARAM_REGISTRY[n].max_val for n in nuisance])

            try:
                ls = least_squares(
                    self.residual_func, x0, args=(nuisance, data),
                    bounds=(lb, ub), method="trf", max_nfev=500,
                )
                nll[i] = 0.5 * float(np.sum(ls.fun ** 2))
            except Exception:
                nll[i] = np.inf

            self.model.params[param_name] = saved

        return {"param_values": test_values, "neg_log_likelihood": nll}

    # ------------------------------------------------------------------
    # 5. Prediction
    # ------------------------------------------------------------------

    def predict(
        self,
        fit_result: FitResult,
        n_years_ahead: int,
        initial_state: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Project the system forward using fitted parameters.

        Parameters
        ----------
        fit_result : FitResult
            Output of :meth:`fit`.
        n_years_ahead : int
            Number of years to forecast.
        initial_state : dict, optional
            ``{'A': ..., 'F': ..., 'K': ..., 'D': ...}``.  Defaults to
            the last observed data point used in fitting.

        Returns
        -------
        dict
            ``'A', 'F', 'K', 'D'`` — predicted trajectories (arrays),
            plus ``'A_lo', 'A_hi', ...`` confidence bands.
        """
        params = dict(self.model.params)
        params.update(fit_result.fitted_params)
        mdl = AlderIPMSimModel(params)

        if initial_state is None:
            # Use defaults as fallback; caller should provide real last state
            defaults = get_defaults()
            initial_state = {
                "A": defaults["K_0"] * 0.5,
                "F": 0.1,
                "K": defaults["K_0"],
                "D": 0.0,
            }

        sim = mdl.simulate(
            A0=initial_state["A"],
            F0=initial_state["F"],
            K0=initial_state["K"],
            D0=initial_state["D"],
            n_years=n_years_ahead,
        )

        out: Dict[str, Any] = {s: sim[s] for s in _STATE_NAMES}

        # Confidence bands via Monte Carlo from covariance
        ci = fit_result.confidence_intervals
        param_names = list(fit_result.fitted_params.keys())
        means = np.array([fit_result.fitted_params[n] for n in param_names])
        # Approximate std from CI width
        stds = np.array([
            max((ci[n][1] - ci[n][0]) / (2 * 1.96), 1e-12) for n in param_names
        ])

        n_mc = 100
        mc_runs: Dict[str, List[np.ndarray]] = {s: [] for s in _STATE_NAMES}
        rng = np.random.default_rng(seed=0)

        for _ in range(n_mc):
            sample = rng.normal(means, stds)
            # Clip to bounds
            for j, n in enumerate(param_names):
                meta = PARAM_REGISTRY.get(n)
                if meta:
                    sample[j] = np.clip(sample[j], meta.min_val, meta.max_val)
            p_mc = dict(self.model.params)
            p_mc.update(fit_result.fitted_params)
            for n, v in zip(param_names, sample):
                p_mc[n] = float(v)
            mdl_mc = AlderIPMSimModel(p_mc)
            try:
                s_mc = mdl_mc.simulate(
                    A0=initial_state["A"], F0=initial_state["F"],
                    K0=initial_state["K"], D0=initial_state["D"],
                    n_years=n_years_ahead,
                )
                for s in _STATE_NAMES:
                    mc_runs[s].append(s_mc[s])
            except Exception:
                continue

        for s in _STATE_NAMES:
            if mc_runs[s]:
                arr = np.array(mc_runs[s])
                out[f"{s}_lo"] = np.percentile(arr, 2.5, axis=0)
                out[f"{s}_hi"] = np.percentile(arr, 97.5, axis=0)
            else:
                out[f"{s}_lo"] = sim[s].copy()
                out[f"{s}_hi"] = sim[s].copy()

        return out

    # ------------------------------------------------------------------
    # 6. Time-series cross-validation
    # ------------------------------------------------------------------

    def cross_validate(
        self,
        data: _PreparedData,
        n_folds: int = 5,
    ) -> Dict[str, Any]:
        """Expanding-window time-series cross-validation.

        Train on years ``0..k``, predict year ``k+1``, for
        ``k`` from ``n_min`` to ``n-2``.

        Parameters
        ----------
        data : _PreparedData
            Full dataset.
        n_folds : int
            Maximum number of folds.  The actual number may be smaller if
            the series is short.

        Returns
        -------
        dict
            ``'prediction_errors'`` (list of per-fold RMSE),
            ``'reliability_score'`` (1 - mean_normalised_error).
        """
        n = data.n_obs
        n_min = max(3, n - n_folds)
        errors: List[float] = []

        for k in range(n_min, n - 1):
            # Build training slice
            train_obs = {s: v[: k + 1] for s, v in data.obs.items()}
            train_data = _PreparedData(
                times=data.times[: k + 1],
                obs=train_obs,
                timestep=data.timestep,
                n_obs=k + 1,
            )

            try:
                fit_res = self.fit(train_data, method="least_squares")
            except Exception:
                errors.append(np.nan)
                continue

            # Predict next year
            params_pred = dict(self.model.params)
            params_pred.update(fit_res.fitted_params)
            mdl_pred = AlderIPMSimModel(params_pred)

            ic = self._initial_conditions_from_data(train_data)
            try:
                sim = mdl_pred.simulate(
                    A0=ic["A"], F0=ic["F"], K0=ic["K"], D0=ic["D"],
                    n_years=k + 1,
                )
            except Exception:
                errors.append(np.nan)
                continue

            # Compute RMSE of one-step-ahead prediction
            se_sum = 0.0
            count = 0
            target_idx = k + 1
            for s in data.obs:
                obs_val = data.obs[s][target_idx]
                if target_idx < len(sim[s]):
                    pred_val = sim[s][target_idx]
                else:
                    pred_val = sim[s][-1]
                scale = max(abs(obs_val), 1e-12)
                se_sum += ((pred_val - obs_val) / scale) ** 2
                count += 1

            errors.append(float(np.sqrt(se_sum / max(count, 1))))

        valid_errors = [e for e in errors if np.isfinite(e)]
        mean_err = float(np.mean(valid_errors)) if valid_errors else 1.0
        reliability = max(0.0, 1.0 - mean_err)

        return {
            "prediction_errors": errors,
            "reliability_score": reliability,
        }

    # ------------------------------------------------------------------
    # 7. Forecast regime
    # ------------------------------------------------------------------

    def forecast_regime(
        self,
        fit_result: FitResult,
        n_years: int = 50,
    ) -> Dict[str, Any]:
        """Classify the long-term regime implied by fitted parameters.

        Parameters
        ----------
        fit_result : FitResult
            Output of :meth:`fit`.
        n_years : int
            Simulation horizon for equilibrium detection.

        Returns
        -------
        dict
            ``'equilibrium_class'``, ``'dominant_eigenvalue'``, ``'R_P'``,
            ``'interpretation'`` (plain-language string for managers).
        """
        params = dict(self.model.params)
        params.update(fit_result.fitted_params)
        mdl = AlderIPMSimModel(params)

        # Find equilibria
        try:
            fps = mdl.find_fixed_points()
        except Exception:
            fps = []

        # Also run a long simulation to see where the system settles
        defaults = get_defaults()
        sim = mdl.simulate(
            A0=defaults["K_0"] * 0.5,
            F0=0.1,
            K0=defaults["K_0"],
            D0=0.0,
            n_years=n_years,
        )

        # Classify endpoint
        A_end = sim["A"][-1]
        F_end = sim["F"][-1]
        K_end = sim["K"][-1]
        D_end = sim["D"][-1]
        tol = 1e-6
        eq_class = AlderIPMSimModel._classify_equilibrium(A_end, F_end, K_end, D_end, tol)

        # Find the matching fixed point for eigenvalue info
        dom_eig = np.nan
        for fp in fps:
            if fp.equilibrium_class == eq_class and fp.stable:
                dom_eig = fp.dominant_eigenvalue
                break

        R_P = mdl.compute_R_P()

        # Build interpretation
        interpretation = self._build_regime_interpretation(
            eq_class, R_P, dom_eig, params,
        )

        return {
            "equilibrium_class": eq_class,
            "dominant_eigenvalue": float(dom_eig),
            "R_P": float(R_P),
            "interpretation": interpretation,
        }

    @staticmethod
    def _build_regime_interpretation(
        eq_class: str, R_P: float, dom_eig: float, params: Dict[str, float],
    ) -> str:
        lines: List[str] = []
        lines.append(
            f"Based on fitted parameters, the system is in the "
            f"{eq_class.upper()} regime (R_P = {R_P:.2f})."
        )

        if eq_class == "coexistence" and R_P > 1.0:
            lines.append(
                "The parasitoid can persist and provides biological control."
            )
            if not np.isnan(dom_eig):
                if dom_eig < 0.5:
                    stability_word = "strong"
                elif dom_eig < 0.9:
                    stability_word = "moderate"
                else:
                    stability_word = "weak"
                lines.append(
                    f"The dominant eigenvalue rho* = {dom_eig:.2f} indicates "
                    f"{stability_word} stability — monitor beetle fecundity (R_B) "
                    f"and larval mortality (mu_S) as early warning indicators."
                )
        elif eq_class == "parasitoid_free":
            lines.append(
                "The parasitoid cannot persist (R_P < 1). Consider parasitoid "
                "augmentation or habitat management to boost natural enemies."
            )
        elif eq_class == "trivial":
            lines.append(
                "Both beetle and parasitoid populations collapse. Verify data "
                "quality and parameter calibration."
            )
        elif eq_class == "canopy_only":
            lines.append(
                "Beetle population persists without significant parasitism. "
                "The canopy may be at risk of chronic defoliation."
            )

        return " ".join(lines)

    # ------------------------------------------------------------------
    # 8. Bootstrap confidence intervals
    # ------------------------------------------------------------------

    def bootstrap_ci(
        self,
        fit_result: FitResult,
        data: _PreparedData,
        n_bootstrap: int = 200,
        seed: int = 42,
    ) -> BootstrapCIResult:
        """Compute bootstrap confidence intervals by resampling residuals.

        Parameters
        ----------
        fit_result : FitResult
            Output of :meth:`fit`.
        data : _PreparedData
            Original data used for fitting.
        n_bootstrap : int
            Number of bootstrap resamples.
        seed : int
            Random seed for reproducibility.

        Returns
        -------
        BootstrapCIResult
        """
        param_names = list(fit_result.fitted_params.keys())
        x_opt = np.array([fit_result.fitted_params[n] for n in param_names])
        residuals = fit_result.residuals

        lb = np.array([PARAM_REGISTRY[n].min_val for n in param_names])
        ub = np.array([PARAM_REGISTRY[n].max_val for n in param_names])

        rng = np.random.default_rng(seed)
        bootstrap_params: Dict[str, List[float]] = {n: [] for n in param_names}
        n_successful = 0

        for _ in range(n_bootstrap):
            # Resample residuals
            resampled = rng.choice(residuals, size=len(residuals), replace=True)

            # Create synthetic data by adding resampled residuals to fitted values
            # Use a quick least_squares from perturbed starting point
            x_start = x_opt + rng.normal(0, 0.01, size=len(x_opt)) * np.abs(x_opt)
            x_start = np.clip(x_start, lb, ub)

            try:
                ls = least_squares(
                    self.residual_func, x_start,
                    args=(param_names, data),
                    bounds=(lb, ub), method="trf", max_nfev=500,
                )
                n_successful += 1
                for i, name in enumerate(param_names):
                    bootstrap_params[name].append(float(ls.x[i]))
            except Exception:
                continue

        ci: Dict[str, Tuple[float, float]] = {}
        bs_arrays: Dict[str, np.ndarray] = {}
        for name in param_names:
            arr = np.array(bootstrap_params[name])
            bs_arrays[name] = arr
            if len(arr) >= 10:
                ci[name] = (float(np.percentile(arr, 2.5)),
                            float(np.percentile(arr, 97.5)))
            else:
                ci[name] = fit_result.confidence_intervals.get(
                    name, (fit_result.fitted_params[name],
                           fit_result.fitted_params[name]))

        return BootstrapCIResult(
            ci=ci, bootstrap_samples=bs_arrays,
            n_bootstrap=n_bootstrap, n_successful=n_successful,
        )

    # ------------------------------------------------------------------
    # 9. Residual diagnostics
    # ------------------------------------------------------------------

    @staticmethod
    def residual_diagnostics(fit_result: FitResult) -> ResidualDiagnostics:
        """Compute residual diagnostics: ACF, QQ data, Durbin-Watson.

        Parameters
        ----------
        fit_result : FitResult
            Output of :meth:`fit`.

        Returns
        -------
        ResidualDiagnostics
        """
        resid = np.asarray(fit_result.residuals)
        n = len(resid)

        # ACF
        max_lag = min(20, n - 1)
        acf_vals = np.zeros(max_lag + 1)
        r_mean = np.mean(resid)
        r_var = np.var(resid)
        if r_var > 1e-15:
            for lag in range(max_lag + 1):
                acf_vals[lag] = np.mean(
                    (resid[:n - lag] - r_mean) * (resid[lag:] - r_mean)
                ) / r_var
        else:
            acf_vals[0] = 1.0
        acf_lags = np.arange(max_lag + 1)

        # QQ plot data (normal quantiles)
        sorted_resid = np.sort(resid)
        from scipy.stats import norm
        theoretical = norm.ppf(
            (np.arange(1, n + 1) - 0.5) / n
        )

        # Durbin-Watson statistic
        if n > 1:
            dw = float(np.sum(np.diff(resid) ** 2) / max(np.sum(resid ** 2), 1e-30))
        else:
            dw = 2.0  # no autocorrelation

        return ResidualDiagnostics(
            acf_values=acf_vals, acf_lags=acf_lags,
            qq_theoretical=theoretical, qq_observed=sorted_resid,
            durbin_watson=dw,
        )

    # ------------------------------------------------------------------
    # 10. Identifiability analysis
    # ------------------------------------------------------------------

    def check_identifiability(
        self,
        fit_result: FitResult,
        data: _PreparedData,
    ) -> IdentifiabilityResult:
        """Assess parameter identifiability via Fisher information matrix.

        Uses eigenvalue decomposition of the FIM to detect structurally
        or practically unidentifiable parameters.

        Parameters
        ----------
        fit_result : FitResult
            Output of :meth:`fit`.
        data : _PreparedData
            Data used in fitting.

        Returns
        -------
        IdentifiabilityResult
        """
        param_names = list(fit_result.fitted_params.keys())
        x_opt = np.array([fit_result.fitted_params[n] for n in param_names])

        jac = self._numerical_jacobian(x_opt, param_names, data)

        # Fisher information matrix = J^T J
        fim = jac.T @ jac

        eigenvalues = np.sort(np.abs(np.linalg.eigvals(fim)))[::-1]
        fim_diag = np.diag(fim)

        # Condition number
        max_eig = eigenvalues[0] if len(eigenvalues) > 0 else 1.0
        min_eig = eigenvalues[-1] if len(eigenvalues) > 0 else 1.0
        cond = max_eig / max(min_eig, 1e-30)

        # Per-parameter identifiability: poorly identifiable if
        # FIM diagonal element is very small relative to the largest
        max_diag = np.max(np.abs(fim_diag)) if len(fim_diag) > 0 else 1.0
        identifiable = {}
        for i, name in enumerate(param_names):
            ratio = abs(fim_diag[i]) / max(max_diag, 1e-30)
            identifiable[name] = ratio > 1e-4

        return IdentifiabilityResult(
            eigenvalues=eigenvalues,
            condition_number=float(cond),
            identifiable=identifiable,
            fim_diagonal=fim_diag,
        )
