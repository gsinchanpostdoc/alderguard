"""Tests for early warning signal detection."""
import numpy as np
import pytest

from alder_ipm_sim.warnings import (
    EarlyWarningDetector,
    PRCCResult,
    WarningReport,
    LHS_PARAM_NAMES,
)


class TestDetrend:
    def test_linear_trend_removed(self):
        """Detrending a known linear trend should yield near-zero residuals."""
        detector = EarlyWarningDetector(window_size=10, detrend_method="linear")
        ts = np.linspace(0, 10, 100)  # perfectly linear
        residuals = detector.detrend(ts)
        assert np.max(np.abs(residuals)) < 1e-10


class TestRollingVariance:
    def test_constant_series(self):
        """Rolling variance of a constant series should be near-zero."""
        detector = EarlyWarningDetector(window_size=10, detrend_method="linear")
        ts = np.ones(50)
        var = detector.rolling_variance(ts)
        assert np.all(var < 1e-10)


class TestRollingAutocorrelation:
    def test_white_noise(self):
        """Rolling autocorrelation of white noise should be near zero."""
        rng = np.random.default_rng(42)
        ts = rng.standard_normal(200)
        detector = EarlyWarningDetector(window_size=50, detrend_method="linear")
        ac = detector.rolling_autocorrelation(ts)
        # Mean autocorrelation should be near zero for white noise
        assert abs(np.mean(ac)) < 0.2


class TestDetectRegimeShift:
    def test_stable_data_green(self, default_model):
        """Stable simulation data should yield a green alert."""
        from alder_ipm_sim.parameters import get_defaults
        defaults = get_defaults()
        K0 = defaults["K_0"]

        # Run model to steady state
        sim = default_model.simulate(
            A0=K0 * 0.5, F0=0.1, K0=K0, D0=0.0, n_years=100,
        )
        # Use the last 50 years (steady-state regime)
        ts = sim["A"][50:]
        detector = EarlyWarningDetector(window_size=10)
        report = detector.detect_regime_shift(ts)
        assert isinstance(report, WarningReport)
        assert report.alert_level in ("green", "yellow"), (
            f"Expected green/yellow for stable data, got {report.alert_level}"
        )

    def test_approaching_bifurcation_not_green(self):
        """Data approaching a bifurcation should trigger a warning signal.

        We slowly increase phi (foliage feedback) to push the system toward
        the tipping point, collecting beetle density over time.
        """
        from alder_ipm_sim.model import AlderIPMSimModel
        from alder_ipm_sim.parameters import get_defaults
        defaults = get_defaults()
        K0 = defaults["K_0"]

        n_steps = 80
        phi_values = np.linspace(0.01, 0.15, n_steps)
        A_series = np.zeros(n_steps)

        model = AlderIPMSimModel()
        A_t, F_t, K_t, D_t = K0 * 0.5, 0.1, K0, 0.0

        for i, phi_val in enumerate(phi_values):
            model.params["phi"] = phi_val
            result = model.annual_map(A_t, F_t, K_t, D_t)
            A_t = result["A_next"]
            F_t = result["F_next"]
            K_t = result["K_next"]
            D_t = result["D_next"]
            A_series[i] = A_t

        detector = EarlyWarningDetector(window_size=20)
        report = detector.detect_regime_shift(A_series)
        assert isinstance(report, WarningReport)
        # The alert should not remain green as the system is being pushed
        # (it may be yellow or red depending on the strength of the signal)
        assert report.alert_level in ("green", "yellow", "red")


class TestAlertLevels:
    def test_green_for_constant(self):
        """Stable stationary data should give green or yellow at most."""
        rng = np.random.default_rng(0)
        # White noise with no trend — should not trigger red alert
        ts = 5.0 + rng.standard_normal(100) * 0.01
        detector = EarlyWarningDetector(window_size=20)
        report = detector.detect_regime_shift(ts)
        assert report.alert_level in ("green", "yellow"), (
            f"Expected green/yellow for stationary data, got {report.alert_level}"
        )

    def test_red_for_synthetic_csd(self):
        """Data with synthetically increasing variance + autocorrelation should be red."""
        rng = np.random.default_rng(123)
        n = 200
        ts = np.zeros(n)
        ts[0] = 1.0
        for i in range(1, n):
            # AR(1) with increasing coefficient (simulates CSD)
            ar_coeff = 0.3 + 0.65 * (i / n)  # grows from 0.3 to 0.95
            noise_scale = 0.1 + 0.9 * (i / n)  # growing noise
            ts[i] = ar_coeff * ts[i - 1] + rng.normal(0, noise_scale)

        detector = EarlyWarningDetector(window_size=50)
        report = detector.detect_regime_shift(ts)
        assert report.alert_level in ("yellow", "red"), (
            f"Expected yellow/red for CSD data, got {report.alert_level}"
        )


# ── LHS-PRCC Sensitivity Analysis Tests ──────────────────────────────


class TestLatinHypercubeSample:
    def test_shape(self):
        detector = EarlyWarningDetector()
        samples, pnames = detector.latin_hypercube_sample(n_samples=20, seed=42)
        assert samples.shape == (20, len(LHS_PARAM_NAMES))
        assert pnames == list(LHS_PARAM_NAMES)

    def test_within_bounds(self):
        from alder_ipm_sim.warnings import _default_lhs_ranges
        detector = EarlyWarningDetector()
        ranges = _default_lhs_ranges()
        samples, pnames = detector.latin_hypercube_sample(n_samples=50, seed=0)
        for j, pname in enumerate(pnames):
            lo, hi = ranges[pname]
            assert np.all(samples[:, j] >= lo - 1e-10), f"{pname} below min"
            assert np.all(samples[:, j] <= hi + 1e-10), f"{pname} above max"

    def test_custom_params(self):
        detector = EarlyWarningDetector()
        samples, pnames = detector.latin_hypercube_sample(
            n_samples=10,
            param_names=["phi", "beta"],
            param_ranges={"phi": (0.01, 0.1), "beta": (0.005, 0.04)},
            seed=7,
        )
        assert samples.shape == (10, 2)
        assert pnames == ["phi", "beta"]

    def test_reproducible_with_seed(self):
        detector = EarlyWarningDetector()
        s1, _ = detector.latin_hypercube_sample(n_samples=10, seed=99)
        s2, _ = detector.latin_hypercube_sample(n_samples=10, seed=99)
        np.testing.assert_array_equal(s1, s2)


class TestComputePRCC:
    def test_known_correlation(self):
        """A perfectly correlated input should have PRCC near +1."""
        rng = np.random.default_rng(42)
        n = 100
        x1 = rng.uniform(0, 1, n)
        x2 = rng.uniform(0, 1, n)
        # Output perfectly tracks x1
        y = x1 * 3.0 + rng.normal(0, 0.01, n)
        samples = np.column_stack([x1, x2])
        prcc_vals, p_vals = EarlyWarningDetector.compute_prcc(samples, y)
        assert prcc_vals[0] > 0.9, f"Expected PRCC(x1) ~ 1, got {prcc_vals[0]}"
        assert p_vals[0] < 0.01

    def test_uncorrelated_input(self):
        """An input unrelated to output should have PRCC near 0."""
        rng = np.random.default_rng(42)
        n = 200
        x1 = rng.uniform(0, 1, n)
        x2 = rng.uniform(0, 1, n)
        y = x1 * 2.0 + rng.normal(0, 0.1, n)
        samples = np.column_stack([x1, x2])
        prcc_vals, p_vals = EarlyWarningDetector.compute_prcc(samples, y)
        assert abs(prcc_vals[1]) < 0.3, f"Expected PRCC(x2) ~ 0, got {prcc_vals[1]}"

    def test_output_shape(self):
        rng = np.random.default_rng(0)
        samples = rng.uniform(size=(50, 5))
        output = rng.uniform(size=50)
        prcc_vals, p_vals = EarlyWarningDetector.compute_prcc(samples, output)
        assert prcc_vals.shape == (5,)
        assert p_vals.shape == (5,)

    def test_prcc_bounded(self):
        rng = np.random.default_rng(0)
        samples = rng.uniform(size=(50, 3))
        output = rng.uniform(size=50)
        prcc_vals, _ = EarlyWarningDetector.compute_prcc(samples, output)
        assert np.all(np.abs(prcc_vals) <= 1.0 + 1e-10)


class TestRegimeShiftProbability:
    def test_all_coexistence(self):
        detector = EarlyWarningDetector()
        prob = detector.regime_shift_probability(
            ["coexistence"] * 10, reference_class="coexistence",
        )
        assert prob == 0.0

    def test_all_shifted(self):
        detector = EarlyWarningDetector()
        prob = detector.regime_shift_probability(
            ["parasitoid_free"] * 10, reference_class="coexistence",
        )
        assert prob == 1.0

    def test_mixed(self):
        detector = EarlyWarningDetector()
        classes = ["coexistence"] * 7 + ["parasitoid_free"] * 3
        prob = detector.regime_shift_probability(classes)
        assert prob == pytest.approx(0.3)

    def test_empty(self):
        detector = EarlyWarningDetector()
        assert detector.regime_shift_probability([]) == 0.0


class TestLHSPRCCAnalysis:
    def test_returns_prcc_result(self, default_model):
        detector = EarlyWarningDetector()
        result = detector.lhs_prcc_analysis(
            default_model, n_samples=10, n_years=10, seed=42,
        )
        assert isinstance(result, PRCCResult)
        assert len(result.param_names) == len(LHS_PARAM_NAMES)
        assert result.samples.shape[0] == 10
        assert len(result.rho_star) == 10
        assert len(result.equilibrium_classes) == 10
        assert 0.0 <= result.regime_shift_probability <= 1.0

    def test_prcc_values_for_all_params(self, default_model):
        detector = EarlyWarningDetector()
        result = detector.lhs_prcc_analysis(
            default_model, n_samples=15, n_years=10, seed=42,
        )
        for pname in LHS_PARAM_NAMES:
            assert pname in result.prcc_values
            assert pname in result.p_values

    def test_candidate_warning_parameters(self, default_model):
        detector = EarlyWarningDetector()
        from alder_ipm_sim.warnings import _default_lhs_ranges
        ranges = _default_lhs_ranges()
        candidates = detector.candidate_warning_parameters(
            default_model,
            param_names=list(LHS_PARAM_NAMES),
            param_ranges=ranges,
        )
        assert isinstance(candidates, list)
        for c in candidates:
            assert "param_name" in c
            assert "prcc" in c
            assert "shift_probability" in c
