"""Tests for model fitting and prediction."""
import numpy as np
import pytest

from alder_ipm_sim.fitting import ModelFitter, FitResult
from alder_ipm_sim.model import AlderIPMSimModel
from alder_ipm_sim.parameters import get_defaults


class TestFitOnSyntheticData:
    def test_recovers_known_parameters(self, synthetic_annual_data):
        """Fitting on synthetic model output should recover known parameters
        within 20% tolerance.
        """
        defaults = get_defaults()
        fitter = ModelFitter()
        data = fitter.prepare_data(
            synthetic_annual_data, time_col="year",
            state_cols={"A": "A", "D": "D"},
        )

        # Fit only a small subset for speed
        fit_params = ["beta", "kappa"]
        result = fitter.fit(data, fit_params=fit_params, method="least_squares")

        assert isinstance(result, FitResult)
        for name in fit_params:
            true_val = defaults[name]
            fitted_val = result.fitted_params[name]
            rel_error = abs(fitted_val - true_val) / max(abs(true_val), 1e-12)
            assert rel_error < 0.20, (
                f"{name}: fitted={fitted_val:.6f}, true={true_val:.6f}, "
                f"rel_error={rel_error:.2%}"
            )


class TestPredict:
    def test_output_length(self, synthetic_annual_data):
        """predict returns arrays of the correct length."""
        fitter = ModelFitter()
        data = fitter.prepare_data(
            synthetic_annual_data, time_col="year",
            state_cols={"A": "A", "D": "D"},
        )
        result = fitter.fit(data, fit_params=["beta"], method="least_squares")

        n_ahead = 10
        pred = fitter.predict(result, n_years_ahead=n_ahead)
        for key in ("A", "F", "K", "D"):
            assert len(pred[key]) == n_ahead + 1, f"{key} length mismatch"
            assert len(pred[f"{key}_lo"]) == n_ahead + 1
            assert len(pred[f"{key}_hi"]) == n_ahead + 1


class TestForecastRegime:
    def test_returns_valid_class(self, synthetic_annual_data):
        """forecast_regime should return a valid equilibrium class."""
        fitter = ModelFitter()
        data = fitter.prepare_data(
            synthetic_annual_data, time_col="year",
            state_cols={"A": "A", "D": "D"},
        )
        result = fitter.fit(data, fit_params=["beta"], method="least_squares")
        regime = fitter.forecast_regime(result)

        assert regime["equilibrium_class"] in (
            "trivial", "canopy_only", "parasitoid_free", "coexistence",
        )
        assert "R_P" in regime
        assert "interpretation" in regime
        assert isinstance(regime["interpretation"], str)
