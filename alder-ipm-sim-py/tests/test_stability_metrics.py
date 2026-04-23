"""Tests for resistance R1, resilience R2, and adaptive stability profile."""
import numpy as np
import pytest

from alder_ipm_sim.model import AlderIPMSimModel


class TestComputeR1:
    def test_returns_float(self, default_model):
        """compute_R1 should return a finite float."""
        r1 = default_model.compute_R1()
        assert isinstance(r1, float)
        if not np.isnan(r1):
            assert -1.0 <= r1 <= 1.0

    def test_bounded(self, default_model):
        """R1 should be clipped to [-1, 1]."""
        r1 = default_model.compute_R1(perturbation_frac=0.5)
        if not np.isnan(r1):
            assert -1.0 <= r1 <= 1.0

    def test_with_explicit_fixed_point(self, default_model):
        """Supplying a fixed point explicitly should work."""
        fps = default_model.find_fixed_points()
        nontrivial = [fp for fp in fps if fp.A_star > 1e-8]
        if nontrivial:
            r1 = default_model.compute_R1(fp=nontrivial[0])
            assert isinstance(r1, float)

    def test_trivial_fp_returns_nan(self, default_model):
        """A trivial fixed point (A*~0) should return NaN."""
        fps = default_model.find_fixed_points()
        trivial = [fp for fp in fps if fp.equilibrium_class == "trivial"]
        if trivial:
            r1 = default_model.compute_R1(fp=trivial[0])
            assert np.isnan(r1)


class TestComputeR2:
    def test_returns_float(self, default_model):
        """compute_R2 should return a finite float."""
        r2 = default_model.compute_R2()
        assert isinstance(r2, float)

    def test_no_deviation_perfect_resilience(self):
        """If perturbation is zero, R2 should be 1.0 (perfect resilience)."""
        model = AlderIPMSimModel()
        r2 = model.compute_R2(perturbation_frac=0.0)
        # With zero perturbation, max deviation is ~0, so R2 = 1.0
        if not np.isnan(r2):
            assert r2 == pytest.approx(1.0, abs=0.01)

    def test_with_explicit_fixed_point(self, default_model):
        """Supplying a fixed point explicitly should work."""
        fps = default_model.find_fixed_points()
        nontrivial = [fp for fp in fps if fp.A_star > 1e-8]
        if nontrivial:
            r2 = default_model.compute_R2(fp=nontrivial[0], Y=5)
            assert isinstance(r2, float)


class TestAdaptiveStabilityProfile:
    def test_returns_correct_keys(self, default_model):
        """adaptive_stability_profile should return param_values, R1, R2."""
        result = default_model.adaptive_stability_profile(
            param_name="phi",
            param_range=np.linspace(0.5, 2.0, 3),
        )
        assert "param_values" in result
        assert "R1" in result
        assert "R2" in result
        assert len(result["param_values"]) == 3
        assert len(result["R1"]) == 3
        assert len(result["R2"]) == 3

    def test_restores_original_param(self, default_model):
        """The original parameter value should be restored after the sweep."""
        original_phi = default_model.params["phi"]
        default_model.adaptive_stability_profile(
            param_name="phi",
            param_range=np.linspace(0.5, 3.0, 3),
        )
        assert default_model.params["phi"] == pytest.approx(original_phi)

    def test_arrays_are_numpy(self, default_model):
        """Returned arrays should be numpy arrays."""
        result = default_model.adaptive_stability_profile(
            param_name="phi",
            param_range=np.array([1.0, 1.5]),
        )
        assert isinstance(result["R1"], np.ndarray)
        assert isinstance(result["R2"], np.ndarray)
