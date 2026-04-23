# Early warning signal detection for regime shifts.
#
# Theoretical basis: Critical slowing down (CSD) theory predicts that as a
# dynamical system approaches a bifurcation (tipping point), the dominant
# eigenvalue of the Jacobian approaches the unit circle (for discrete maps)
# or the imaginary axis (for continuous flows).  This causes the system's
# recovery rate from small perturbations to decrease, which manifests as:
#
#   1. Increasing variance -- perturbations decay more slowly, so the state
#      variable fluctuates further from equilibrium.
#   2. Increasing lag-1 autocorrelation -- successive observations become more
#      correlated because the system "remembers" perturbations longer.
#   3. Flickering (increased skewness/kurtosis) -- the state distribution
#      becomes asymmetric and heavy-tailed as the system transiently visits
#      the alternative basin of attraction.
#
# For the Alnus-beetle-parasitoid-bird system, CSD signals in beetle larval
# density (A_t) warn of an approaching regime shift from the coexistence
# equilibrium to the parasitoid-free state, which leads to uncontrolled
# defoliation.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import stats
from scipy.ndimage import gaussian_filter1d
from scipy.stats import kendalltau, rankdata
from scipy.stats.qmc import LatinHypercube


@dataclass
class WarningReport:
    """Results of a full early-warning-signal analysis on a time series.

    Attributes
    ----------
    indicators : dict
        Rolling EWS values keyed by ``'variance'``, ``'autocorrelation'``,
        ``'skewness'``, ``'kurtosis'``.
    kendall_results : dict
        For each indicator, a dict with ``'tau'`` and ``'p_value'`` from the
        Kendall rank-correlation trend test.
    alert_level : str
        ``'green'``, ``'yellow'``, or ``'red'``.
    interpretation : str
        Plain-language explanation for forest managers.
    """

    indicators: Dict[str, np.ndarray]
    kendall_results: Dict[str, Dict[str, float]]
    alert_level: str
    interpretation: str


@dataclass
class PRCCResult:
    """Results from LHS-PRCC sensitivity analysis.

    Attributes
    ----------
    param_names : list of str
        Names of the sampled parameters.
    prcc_values : dict
        ``{param_name: prcc}`` -- partial rank correlation with rho*.
    p_values : dict
        ``{param_name: p_value}`` -- significance of each PRCC.
    regime_shift_probability : float
        Fraction of LHS samples where the equilibrium class differs from
        the reference (coexistence).
    samples : np.ndarray
        (n_samples, n_params) array of LHS parameter samples.
    rho_star : np.ndarray
        Dominant eigenvalue for each sample.
    equilibrium_classes : list of str
        Equilibrium classification for each sample.
    """

    param_names: List[str]
    prcc_values: Dict[str, float]
    p_values: Dict[str, float]
    regime_shift_probability: float
    samples: np.ndarray
    rho_star: np.ndarray
    equilibrium_classes: List[str]


# -- Default LHS parameter names and ranges (9 phenological parameters) --
LHS_PARAM_NAMES = [
    "T", "sigma_A", "sigma_F", "delta", "mu_S",
    "B_index", "phi", "beta", "R_B",
]


def _default_lhs_ranges() -> Dict[str, Tuple[float, float]]:
    """Return default (min, max) ranges for the 9 LHS parameters."""
    from .parameters import PARAM_REGISTRY
    return {
        name: (PARAM_REGISTRY[name].min_val, PARAM_REGISTRY[name].max_val)
        for name in LHS_PARAM_NAMES
    }


class EarlyWarningDetector:
    """Compute early warning signals (EWS) for critical transitions.

    This class implements the statistical toolbox for detecting critical
    slowing down in ecological time series, following the methodology of
    Scheffer et al. (2009) and Dakos et al. (2012).  It is tailored to the
    Alnus-beetle-parasitoid-bird ecoepidemic system described in the
    accompanying manuscript.

    The core idea: as the dominant eigenvalue rho* of the annual map's
    Jacobian approaches 1, recovery from perturbations slows.  This
    "critical slowing down" is detectable in rolling-window statistics
    computed on state-variable time series *before* the actual tipping
    event occurs, providing an actionable early warning to forest managers.

    Parameters
    ----------
    window_size : int or None
        Rolling window length for computing EWS statistics.  If None,
        defaults to 50 % of the time series length (a standard choice
        that balances sensitivity and smoothness).
    detrend_method : str
        Method used to remove slow trends before computing EWS:
        ``'gaussian'`` (Gaussian kernel smoother, default),
        ``'linear'`` (ordinary least-squares linear trend).
    """

    def __init__(
        self,
        window_size: Optional[int] = None,
        detrend_method: str = "gaussian",
    ) -> None:
        if detrend_method not in ("gaussian", "linear", "loess"):
            raise ValueError(
                f"detrend_method must be 'gaussian', 'linear', or 'loess', "
                f"got '{detrend_method}'"
            )
        self.window_size = window_size
        self.detrend_method = detrend_method

    def _effective_window(self, ts: np.ndarray) -> int:
        """Return the window size, defaulting to 50 % of the series length."""
        if self.window_size is not None:
            return self.window_size
        return max(int(len(ts) * 0.5), 3)

    # ------------------------------------------------------------------
    # Detrending
    # ------------------------------------------------------------------

    def detrend(self, ts: np.ndarray, method: Optional[str] = None) -> np.ndarray:
        """Remove a slow trend from *ts* and return the residuals.

        Detrending is essential before computing rolling EWS because a
        deterministic trend (e.g. gradual decline toward a tipping point)
        would inflate variance and autocorrelation estimates even in the
        absence of critical slowing down.

        Parameters
        ----------
        ts : array-like
            1-D time series.
        method : str or None
            Override the instance-level ``detrend_method``.  Accepts
            ``'gaussian'``, ``'linear'``, or ``'loess'``.

        Returns
        -------
        np.ndarray
            Residual time series (same length as *ts*).
        """
        ts = np.asarray(ts, dtype=float)
        method = method or self.detrend_method

        if method == "gaussian":
            # Bandwidth = window_size / 4 is a common default for EWS;
            # it smooths slow dynamics while preserving fluctuations.
            bw = max(self._effective_window(ts) // 4, 1)
            trend = gaussian_filter1d(ts, sigma=bw)
            return ts - trend

        if method == "linear":
            t = np.arange(len(ts), dtype=float)
            slope, intercept, _, _, _ = stats.linregress(t, ts)
            trend = intercept + slope * t
            return ts - trend

        if method == "loess":
            # Simple local regression approximation using a Gaussian kernel
            # (true LOESS requires statsmodels; this is a lightweight proxy).
            bw = max(self._effective_window(ts) // 4, 1)
            trend = gaussian_filter1d(ts, sigma=bw)
            return ts - trend

        raise ValueError(f"Unknown detrend method: {method}")

    # ------------------------------------------------------------------
    # Rolling indicators
    # ------------------------------------------------------------------

    def rolling_variance(self, ts: np.ndarray) -> np.ndarray:
        """Compute rolling variance of the detrended time series.

        Rising variance is a hallmark of critical slowing down: as the
        dominant eigenvalue rho* -> 1 the system amplifies noise,
        increasing the spread of the state-variable distribution.

        Parameters
        ----------
        ts : array-like
            Raw (or pre-detrended) 1-D time series.

        Returns
        -------
        np.ndarray
            Rolling variance values (length = ``len(ts) - window + 1``).
        """
        residuals = self.detrend(ts)
        w = self._effective_window(ts)
        n = len(residuals)
        if w > n:
            w = n
        out = np.array([
            np.var(residuals[i : i + w], ddof=1) for i in range(n - w + 1)
        ])
        return out

    def rolling_autocorrelation(
        self, ts: np.ndarray, lag: int = 1,
    ) -> np.ndarray:
        """Compute rolling lag-1 autocorrelation (AR(1) coefficient).

        Increasing AR(1) reflects the system's growing "memory" as recovery
        from perturbations slows near a bifurcation.

        Parameters
        ----------
        ts : array-like
            Raw 1-D time series.
        lag : int
            Autocorrelation lag (default 1).

        Returns
        -------
        np.ndarray
            Rolling autocorrelation values.
        """
        residuals = self.detrend(ts)
        w = self._effective_window(ts)
        n = len(residuals)
        if w > n:
            w = n
        results = []
        for i in range(n - w + 1):
            segment = residuals[i : i + w]
            if np.std(segment) < 1e-15:
                results.append(0.0)
                continue
            x = segment[: -lag] if lag > 0 else segment
            y = segment[lag:]
            if len(x) < 3:
                results.append(0.0)
                continue
            corr = np.corrcoef(x, y)[0, 1]
            results.append(corr if np.isfinite(corr) else 0.0)
        return np.array(results)

    def rolling_skewness(self, ts: np.ndarray) -> np.ndarray:
        """Compute rolling skewness (flickering indicator).

        Increased skewness can indicate that the state-variable distribution
        is becoming asymmetric, a sign that the system transiently "flickers"
        into the alternative basin of attraction before permanently shifting.

        Parameters
        ----------
        ts : array-like
            Raw 1-D time series.

        Returns
        -------
        np.ndarray
            Rolling skewness values.
        """
        residuals = self.detrend(ts)
        w = self._effective_window(ts)
        n = len(residuals)
        if w > n:
            w = n
        out = np.array([
            float(stats.skew(residuals[i : i + w], bias=False))
            for i in range(n - w + 1)
        ])
        return out

    def rolling_kurtosis(self, ts: np.ndarray) -> np.ndarray:
        """Compute rolling kurtosis (excess kurtosis, flickering indicator).

        Elevated kurtosis (heavy tails) suggests the occurrence of extreme
        fluctuations consistent with transient excursions toward an
        alternative attractor.

        Parameters
        ----------
        ts : array-like
            Raw 1-D time series.

        Returns
        -------
        np.ndarray
            Rolling excess kurtosis values.
        """
        residuals = self.detrend(ts)
        w = self._effective_window(ts)
        n = len(residuals)
        if w > n:
            w = n
        out = np.array([
            float(stats.kurtosis(residuals[i : i + w], bias=False))
            for i in range(n - w + 1)
        ])
        return out

    # ------------------------------------------------------------------
    # Composite EWS
    # ------------------------------------------------------------------

    def compute_all_ews(self, ts: np.ndarray) -> Dict[str, np.ndarray]:
        """Compute all four early-warning indicators.

        Parameters
        ----------
        ts : array-like
            Raw 1-D time series (e.g. annual beetle density A_t).

        Returns
        -------
        dict
            Keys ``'variance'``, ``'autocorrelation'``, ``'skewness'``,
            ``'kurtosis'``, each mapping to a 1-D numpy array of rolling
            window values.
        """
        return {
            "variance": self.rolling_variance(ts),
            "autocorrelation": self.rolling_autocorrelation(ts),
            "skewness": self.rolling_skewness(ts),
            "kurtosis": self.rolling_kurtosis(ts),
        }

    # ------------------------------------------------------------------
    # Trend testing
    # ------------------------------------------------------------------

    def kendall_tau_trend(
        self, indicator_ts: np.ndarray,
    ) -> Tuple[float, float]:
        """Kendall tau rank-correlation trend test for an EWS indicator.

        A significantly positive Kendall tau for variance or autocorrelation
        is the canonical statistical test for critical slowing down
        (Dakos et al. 2008).  The non-parametric nature of Kendall's tau
        makes it robust to the non-normality typical of ecological data.

        Parameters
        ----------
        indicator_ts : array-like
            1-D array of a rolling EWS indicator (e.g. rolling variance).

        Returns
        -------
        tau : float
            Kendall tau statistic in [-1, 1].
        p_value : float
            Two-sided p-value for the null hypothesis of no trend.
        """
        indicator_ts = np.asarray(indicator_ts, dtype=float)
        # Remove NaN/inf values
        mask = np.isfinite(indicator_ts)
        indicator_ts = indicator_ts[mask]
        if len(indicator_ts) < 3:
            return 0.0, 1.0
        time_index = np.arange(len(indicator_ts))
        tau, p_value = kendalltau(time_index, indicator_ts)
        return float(tau), float(p_value)

    # ------------------------------------------------------------------
    # Sensitivity analysis
    # ------------------------------------------------------------------

    def sensitivity_analysis(
        self,
        model,
        param_name: str,
        param_range: Tuple[float, float],
        n_points: int = 50,
        n_years: int = 100,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Sweep a parameter and compute the dominant eigenvalue rho* at each.

        This implements the tipping-point proximity analysis from the
        manuscript: for each value of the focal parameter, the model is
        simulated to quasi-steady state and the dominant eigenvalue of the
        annual-map Jacobian is computed.  When rho* crosses 1 a bifurcation
        (regime shift) occurs.

        Parameters
        ----------
        model : AlderIPMSimModel
            An instance of the core model (will be modified in-place for
            each parameter value; the original value is restored on exit).
        param_name : str
            Name of the parameter to sweep (must exist in the model's
            ``params`` dict).
        param_range : tuple of float
            ``(low, high)`` bounds for the sweep.
        n_points : int
            Number of evenly spaced parameter values to evaluate.
        n_years : int
            Number of years to simulate for each parameter value (should
            be long enough for transients to decay).

        Returns
        -------
        param_values : np.ndarray
            The swept parameter values (length *n_points*).
        rho_star : np.ndarray
            Dominant eigenvalue of the annual-map Jacobian at each
            parameter value.
        """
        original_value = model.params[param_name]
        param_values = np.linspace(param_range[0], param_range[1], n_points)
        rho_star = np.full(n_points, np.nan)

        p = model.params
        K0 = p["K_0"]

        for i, val in enumerate(param_values):
            model.params[param_name] = val
            try:
                result = model.simulate(
                    A0=K0 * 0.5, F0=K0 * 0.1, K0=K0, D0=0.0,
                    n_years=n_years,
                )
                A_end = result["A"][-1]
                F_end = result["F"][-1]
                K_end = result["K"][-1]
                D_end = result["D"][-1]

                jac = model.compute_jacobian(A_end, F_end, K_end, D_end)
                eigvals = np.linalg.eigvals(jac)
                rho_star[i] = float(np.max(np.abs(eigvals)))
            except Exception:
                rho_star[i] = np.nan

        model.params[param_name] = original_value
        return param_values, rho_star

    # ------------------------------------------------------------------
    # Full detection pipeline
    # ------------------------------------------------------------------

    def detect_regime_shift(
        self,
        ts: np.ndarray,
        threshold_variance_tau: float = 0.3,
        threshold_ac_tau: float = 0.3,
    ) -> WarningReport:
        """Run the full EWS detection pipeline on a time series.

        Computes all four rolling-window indicators, tests each for an
        increasing trend via Kendall's tau, and assigns an alert level
        based on the joint significance of variance and autocorrelation
        trends.

        Alert levels
        ------------
        - **green**: neither variance nor autocorrelation shows a significant
          increasing trend (p > 0.05 or tau below threshold).
        - **yellow**: *one* of variance or autocorrelation has a significant
          increasing trend (p < 0.05 and tau > threshold).
        - **red**: *both* variance and autocorrelation have significant
          increasing trends -- the hallmark of critical slowing down.

        Parameters
        ----------
        ts : array-like
            1-D time series of a state variable (typically beetle density
            ``A_t`` from the annual map).
        threshold_variance_tau : float
            Minimum Kendall tau to flag variance as increasing.
        threshold_ac_tau : float
            Minimum Kendall tau to flag autocorrelation as increasing.

        Returns
        -------
        WarningReport
            Dataclass with indicators, Kendall results, alert level, and
            plain-language interpretation.
        """
        ts = np.asarray(ts, dtype=float)
        indicators = self.compute_all_ews(ts)

        kendall_results: Dict[str, Dict[str, float]] = {}
        for name, values in indicators.items():
            tau, pval = self.kendall_tau_trend(values)
            kendall_results[name] = {"tau": tau, "p_value": pval}

        var_tau = kendall_results["variance"]["tau"]
        var_p = kendall_results["variance"]["p_value"]
        ac_tau = kendall_results["autocorrelation"]["tau"]
        ac_p = kendall_results["autocorrelation"]["p_value"]

        var_sig = var_p < 0.05 and var_tau > threshold_variance_tau
        ac_sig = ac_p < 0.05 and ac_tau > threshold_ac_tau

        if var_sig and ac_sig:
            alert_level = "red"
            interpretation = (
                "RED ALERT: Both variance and autocorrelation of beetle "
                "larval density are increasing, indicating critical slowing "
                "down. The system may be approaching a regime shift from "
                "coexistence to parasitoid-free state. "
                "Recommended action: evaluate integrated control Strategy C "
                "(parasitoid augmentation + direct larval removal + bird "
                "habitat enhancement)."
            )
        elif var_sig or ac_sig:
            alert_level = "yellow"
            which = "variance" if var_sig else "autocorrelation"
            interpretation = (
                f"YELLOW ALERT: {which.capitalize()} of beetle larval "
                f"density shows a significant increasing trend "
                f"(tau={kendall_results[which]['tau']:.3f}, "
                f"p={kendall_results[which]['p_value']:.4f}). "
                f"This is a potential early indicator of critical slowing "
                f"down. Recommended action: increase monitoring frequency "
                f"and prepare contingency plans for parasitoid augmentation."
            )
        else:
            alert_level = "green"
            interpretation = (
                "GREEN: No significant increasing trends detected in "
                "variance or autocorrelation of beetle larval density. "
                "The system appears to be in a stable regime. Continue "
                "routine monitoring."
            )

        return WarningReport(
            indicators=indicators,
            kendall_results=kendall_results,
            alert_level=alert_level,
            interpretation=interpretation,
        )

    # ------------------------------------------------------------------
    # LHS-PRCC Sensitivity Analysis (manuscript Table 1 / Figure 4)
    # ------------------------------------------------------------------

    def latin_hypercube_sample(
        self,
        n_samples: int = 500,
        param_names: Optional[List[str]] = None,
        param_ranges: Optional[Dict[str, Tuple[float, float]]] = None,
        seed: Optional[int] = None,
    ) -> Tuple[np.ndarray, List[str]]:
        """Generate parameter sets via Latin Hypercube Sampling.

        Uses ``scipy.stats.qmc.LatinHypercube`` to generate a space-filling
        design across the 9 phenological parameters.

        Parameters
        ----------
        n_samples : int
            Number of LHS samples (default 500).
        param_names : list of str or None
            Parameter names to sample. Defaults to the 9 phenological
            parameters from the manuscript.
        param_ranges : dict or None
            ``{param_name: (low, high)}``. Defaults to registry bounds.
        seed : int or None
            Random seed for reproducibility.

        Returns
        -------
        samples : np.ndarray
            (n_samples, n_params) array of parameter values.
        param_names : list of str
            Ordered parameter names corresponding to columns.
        """
        if param_names is None:
            param_names = list(LHS_PARAM_NAMES)
        if param_ranges is None:
            param_ranges = _default_lhs_ranges()

        d = len(param_names)
        sampler = LatinHypercube(d=d, seed=seed)
        unit_samples = sampler.random(n=n_samples)  # (n_samples, d) in [0,1]

        # Scale to parameter ranges
        samples = np.empty_like(unit_samples)
        for j, pname in enumerate(param_names):
            lo, hi = param_ranges[pname]
            samples[:, j] = lo + (hi - lo) * unit_samples[:, j]

        return samples, param_names

    def _simulate_to_rho_star(
        self,
        model,
        param_dict: Dict[str, float],
        n_years: int = 100,
    ) -> Tuple[float, str]:
        """Simulate with given params to quasi-steady state, return (rho*, eq_class).

        Parameters
        ----------
        model : AlderIPMSimModel
            Model instance (params will be temporarily overridden).
        param_dict : dict
            Parameter overrides for this sample.
        n_years : int
            Simulation length.

        Returns
        -------
        rho_star : float
            Dominant eigenvalue magnitude.
        eq_class : str
            Equilibrium classification.
        """
        from .model import AlderIPMSimModel

        original = dict(model.params)
        try:
            model.params.update(param_dict)
            K0 = model.params["K_0"]
            result = model.simulate(
                A0=K0 * 0.5, F0=K0 * 0.1, K0=K0, D0=0.0,
                n_years=n_years,
            )
            A_end = result["A"][-1]
            F_end = result["F"][-1]
            K_end = result["K"][-1]
            D_end = result["D"][-1]

            jac = model.compute_jacobian(A_end, F_end, K_end, D_end)
            eigvals = np.linalg.eigvals(jac)
            rho_star = float(np.max(np.abs(eigvals)))

            eq_class = AlderIPMSimModel._classify_equilibrium(
                A_end, F_end, K_end, D_end, tol=1e-6,
            )
            return rho_star, eq_class
        except Exception:
            return np.nan, "unknown"
        finally:
            model.params.update(original)

    @staticmethod
    def compute_prcc(
        samples: np.ndarray,
        output_values: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Compute Partial Rank Correlation Coefficients (PRCC).

        Rank-transforms all variables, then for each input parameter
        computes the partial correlation with the output (rho*) by
        regressing out the effects of all other parameters.

        Parameters
        ----------
        samples : np.ndarray
            (n_samples, n_params) input parameter matrix.
        output_values : np.ndarray
            (n_samples,) response variable (e.g. rho*).

        Returns
        -------
        prcc_values : np.ndarray
            (n_params,) PRCC for each parameter.
        p_values : np.ndarray
            (n_params,) two-sided p-values.
        """
        n, d = samples.shape

        # Rank-transform everything
        ranked_X = np.empty_like(samples)
        for j in range(d):
            ranked_X[:, j] = rankdata(samples[:, j])
        ranked_Y = rankdata(output_values)

        prcc_vals = np.zeros(d)
        p_vals = np.ones(d)

        for j in range(d):
            # Indices of all other parameters
            others = [k for k in range(d) if k != j]
            if len(others) == 0:
                # Degenerate: only one parameter
                corr, pval = stats.spearmanr(samples[:, j], output_values)
                prcc_vals[j] = corr if np.isfinite(corr) else 0.0
                p_vals[j] = pval if np.isfinite(pval) else 1.0
                continue

            Z = ranked_X[:, others]

            # Add intercept for regression
            Z_aug = np.column_stack([np.ones(n), Z])

            # Regress ranked X_j on Z -> residuals e_X
            try:
                coef_x, _, _, _ = np.linalg.lstsq(Z_aug, ranked_X[:, j], rcond=None)
                e_x = ranked_X[:, j] - Z_aug @ coef_x

                # Regress ranked Y on Z -> residuals e_Y
                coef_y, _, _, _ = np.linalg.lstsq(Z_aug, ranked_Y, rcond=None)
                e_y = ranked_Y - Z_aug @ coef_y

                # PRCC = Pearson correlation of residuals
                if np.std(e_x) < 1e-15 or np.std(e_y) < 1e-15:
                    prcc_vals[j] = 0.0
                    p_vals[j] = 1.0
                else:
                    corr = np.corrcoef(e_x, e_y)[0, 1]
                    prcc_vals[j] = corr if np.isfinite(corr) else 0.0

                    # t-test for significance: t = prcc * sqrt((n-2-d)/(1-prcc^2))
                    dof = n - 2 - len(others)
                    if dof > 0 and abs(prcc_vals[j]) < 1.0:
                        t_stat = prcc_vals[j] * np.sqrt(dof / (1.0 - prcc_vals[j] ** 2))
                        p_vals[j] = 2.0 * stats.t.sf(abs(t_stat), dof)
                    else:
                        p_vals[j] = 0.0 if abs(prcc_vals[j]) > 0.99 else 1.0
            except Exception:
                prcc_vals[j] = 0.0
                p_vals[j] = 1.0

        return prcc_vals, p_vals

    def regime_shift_probability(
        self,
        equilibrium_classes: List[str],
        reference_class: str = "coexistence",
    ) -> float:
        """Fraction of samples where equilibrium class differs from reference.

        Parameters
        ----------
        equilibrium_classes : list of str
            Classification for each LHS sample.
        reference_class : str
            The reference regime (default ``'coexistence'``).

        Returns
        -------
        float
            Regime shift probability in [0, 1].
        """
        if not equilibrium_classes:
            return 0.0
        shifted = sum(1 for c in equilibrium_classes if c != reference_class)
        return shifted / len(equilibrium_classes)

    def lhs_prcc_analysis(
        self,
        model,
        n_samples: int = 500,
        param_names: Optional[List[str]] = None,
        param_ranges: Optional[Dict[str, Tuple[float, float]]] = None,
        n_years: int = 100,
        seed: Optional[int] = None,
    ) -> PRCCResult:
        """Full LHS-PRCC sensitivity analysis pipeline.

        For each Latin Hypercube sample: simulate to quasi-steady state,
        compute rho*, classify the equilibrium. Then compute PRCC of each
        parameter with rho* and the regime shift probability.

        Parameters
        ----------
        model : AlderIPMSimModel
            Model instance.
        n_samples : int
            Number of LHS samples (default 500).
        param_names : list of str or None
            Parameters to sample (default: 9 phenological parameters).
        param_ranges : dict or None
            Sampling bounds per parameter (default: registry bounds).
        n_years : int
            Simulation years per sample.
        seed : int or None
            Random seed.

        Returns
        -------
        PRCCResult
            Full results including PRCC values, p-values, regime shift
            probability, samples, and rho* values.
        """
        samples, pnames = self.latin_hypercube_sample(
            n_samples=n_samples,
            param_names=param_names,
            param_ranges=param_ranges,
            seed=seed,
        )

        rho_star = np.full(n_samples, np.nan)
        eq_classes: List[str] = []

        for i in range(n_samples):
            param_dict = {pnames[j]: samples[i, j] for j in range(len(pnames))}
            rho_i, eq_i = self._simulate_to_rho_star(model, param_dict, n_years)
            rho_star[i] = rho_i
            eq_classes.append(eq_i)

        # Filter valid (non-NaN) samples for PRCC
        mask = np.isfinite(rho_star)
        valid_samples = samples[mask]
        valid_rho = rho_star[mask]

        if len(valid_rho) < 10:
            # Not enough valid samples for meaningful PRCC
            prcc_dict = {p: 0.0 for p in pnames}
            pval_dict = {p: 1.0 for p in pnames}
        else:
            prcc_vals, p_vals = self.compute_prcc(valid_samples, valid_rho)
            prcc_dict = {pnames[j]: float(prcc_vals[j]) for j in range(len(pnames))}
            pval_dict = {pnames[j]: float(p_vals[j]) for j in range(len(pnames))}

        shift_prob = self.regime_shift_probability(eq_classes)

        return PRCCResult(
            param_names=pnames,
            prcc_values=prcc_dict,
            p_values=pval_dict,
            regime_shift_probability=shift_prob,
            samples=samples,
            rho_star=rho_star,
            equilibrium_classes=eq_classes,
        )

    # Backward-compatible wrapper
    def candidate_warning_parameters(
        self,
        model,
        param_names: List[str],
        param_ranges: Dict[str, Tuple[float, float]],
        prcc_threshold: float = 0.25,
        shift_prob_threshold: float = 0.2,
    ) -> List[Dict]:
        """Identify candidate early warning parameters using LHS-PRCC.

        This is a convenience wrapper around ``lhs_prcc_analysis`` that
        filters to parameters exceeding the given thresholds.

        Parameters
        ----------
        model : AlderIPMSimModel
            Model instance.
        param_names : list of str
            Parameter names to screen.
        param_ranges : dict
            ``{param_name: (low, high)}`` sweep ranges.
        prcc_threshold : float
            Minimum |PRCC| with rho* to qualify.
        shift_prob_threshold : float
            Minimum regime shift probability.

        Returns
        -------
        list of dict
            Each dict has keys ``'param_name'``, ``'prcc'``,
            ``'shift_probability'``, ``'p_value'``.
        """
        result = self.lhs_prcc_analysis(
            model,
            n_samples=200,
            param_names=param_names,
            param_ranges=param_ranges,
            seed=42,
        )

        candidates: List[Dict] = []
        for pname in param_names:
            prcc = result.prcc_values.get(pname, 0.0)
            pval = result.p_values.get(pname, 1.0)
            if abs(prcc) > prcc_threshold and result.regime_shift_probability > shift_prob_threshold:
                candidates.append({
                    "param_name": pname,
                    "prcc": prcc,
                    "shift_probability": result.regime_shift_probability,
                    "p_value": pval,
                })

        return candidates
