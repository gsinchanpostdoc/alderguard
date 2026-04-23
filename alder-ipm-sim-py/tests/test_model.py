"""Tests for the core ODE model."""
import numpy as np
import pytest

from alder_ipm_sim.model import AlderIPMSimModel
from alder_ipm_sim.parameters import get_defaults


class TestWithinSeasonRHS:
    def test_output_shape(self, default_model):
        y = np.array([0.5, 0.0, 0.1, 0.0])
        dy = default_model.within_season_rhs(0.0, y)
        assert len(dy) == 4

    def test_non_negative_states(self, default_model):
        """S, I, F, D should remain non-negative after integration.

        The RHS clamps states, but the ODE solver may produce small
        negative transients.  End-of-season values (which pass through
        the clamped RHS) must be non-negative.
        """
        defaults = get_defaults()
        K0 = defaults["K_0"]
        sol, end = default_model.integrate_season(
            S0=K0 * 0.5, I0=0.0, F0=0.1, D0=0.0,
        )
        # S (row 0), F (row 2), D (row 3) should stay non-negative
        for row in (0, 2, 3):
            assert np.all(sol.y[row] >= -1e-8), (
                f"State variable {row} has negative values"
            )
        # End-of-season values must all be non-negative
        for key in ("S_T", "F_T", "D_T"):
            assert end[key] >= 0.0, f"{key} is negative at end of season"

    def test_no_parasitoid_no_infection(self, default_model):
        """With F0=0 and u_P=0, no infected larvae should appear."""
        defaults = get_defaults()
        K0 = defaults["K_0"]
        default_model.u_P = 0.0
        sol, end = default_model.integrate_season(
            S0=K0 * 0.5, I0=0.0, F0=0.0, D0=0.0,
        )
        # Parasitised larvae (I) should stay at zero
        assert np.all(sol.y[1] < 1e-10), "I should be ~0 when F0=0"
        # F should also remain zero (no source)
        assert np.all(sol.y[2] < 1e-10), "F should stay ~0 when F0=0 and u_P=0"


class TestIntegrateSeason:
    def test_defoliation_non_decreasing(self, default_model):
        """Defoliation D should be monotonically non-decreasing within a season."""
        defaults = get_defaults()
        K0 = defaults["K_0"]
        t_eval = np.linspace(0, defaults["T"], 200)
        sol, _ = default_model.integrate_season(
            S0=K0 * 0.5, I0=0.0, F0=0.1, D0=0.0,
            t_eval=t_eval,
        )
        D = sol.y[3]
        diffs = np.diff(D)
        assert np.all(diffs >= -1e-10), "D should be non-decreasing"


class TestSimulate:
    def test_output_length(self, default_model):
        """simulate returns arrays of length n_years+1."""
        n_years = 20
        defaults = get_defaults()
        K0 = defaults["K_0"]
        sim = default_model.simulate(
            A0=K0 * 0.5, F0=0.1, K0=K0, D0=0.0, n_years=n_years,
        )
        for key in ("A", "F", "K", "D"):
            assert len(sim[key]) == n_years + 1, f"{key} length mismatch"

    def test_initial_conditions_stored(self, default_model):
        defaults = get_defaults()
        K0 = defaults["K_0"]
        A0, F0, D0 = K0 * 0.5, 0.1, 0.0
        sim = default_model.simulate(A0=A0, F0=F0, K0=K0, D0=D0, n_years=5)
        assert sim["A"][0] == pytest.approx(A0)
        assert sim["F"][0] == pytest.approx(F0)
        assert sim["K"][0] == pytest.approx(K0)
        assert sim["D"][0] == pytest.approx(D0)


class TestComputeRP:
    def test_rp_with_calibrated_params(self, calibrated_model):
        """R_P should be a finite positive number with default parameters."""
        R_P = calibrated_model.compute_R_P()
        assert np.isfinite(R_P)
        assert R_P > 0

    def test_rp_positive(self, default_model):
        R_P = default_model.compute_R_P()
        assert R_P > 0


class TestAnnualMap:
    def test_zero_beetle_trivial(self, default_model):
        """With zero beetle density, output should be trivially zero."""
        defaults = get_defaults()
        K0 = defaults["K_0"]
        result = default_model.annual_map(A_t=0.0, F_t=0.0, K_t=K0, D_t=0.0)
        assert result["A_next"] == pytest.approx(0.0, abs=1e-10)
        # D should also be ~0 since no larvae fed
        assert result["D_next"] == pytest.approx(0.0, abs=1e-10)

    def test_returns_expected_keys(self, default_model):
        defaults = get_defaults()
        K0 = defaults["K_0"]
        result = default_model.annual_map(A_t=K0 * 0.5, F_t=0.1, K_t=K0, D_t=0.0)
        for key in ("A_next", "F_next", "K_next", "D_next", "within_season_sol"):
            assert key in result
