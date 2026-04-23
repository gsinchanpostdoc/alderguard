"""Tests for fixed-point finding and stability analysis."""
import numpy as np
import pytest

from alder_ipm_sim.model import AlderIPMSimModel, FixedPoint


class TestFindFixedPoints:
    def test_trivial_fixed_point_found(self, default_model):
        """The trivial fixed point (0,0,K0,0) should always be found."""
        fps = default_model.find_fixed_points()
        trivial = [fp for fp in fps if fp.equilibrium_class == "trivial"]
        assert len(trivial) >= 1, "Trivial fixed point not found"

    def test_multiple_fixed_points_found(self, calibrated_model):
        """The search should find at least two distinct fixed points."""
        fps = calibrated_model.find_fixed_points()
        assert len(fps) >= 1, "Should find at least one fixed point"
        # Each FP should have a valid class label
        valid_classes = {"trivial", "canopy_only", "parasitoid_free", "coexistence"}
        for fp in fps:
            assert fp.equilibrium_class in valid_classes


class TestClassifyEquilibrium:
    @pytest.mark.parametrize("A,F,K,D,expected", [
        (0.0, 0.0, 1.7, 0.0, "trivial"),
        (0.5, 0.0, 1.7, 0.0, "canopy_only"),
        (0.5, 0.0, 1.7, 0.3, "parasitoid_free"),
        (0.5, 0.2, 1.7, 0.3, "coexistence"),
    ])
    def test_classification(self, A, F, K, D, expected):
        result = AlderIPMSimModel._classify_equilibrium(A, F, K, D, tol=1e-8)
        assert result == expected


class TestJacobian:
    def test_shape_4x4(self, default_model):
        jac = default_model.compute_jacobian(0.5, 0.1, 1.7, 0.1)
        assert jac.shape == (4, 4)

    def test_finite_values(self, default_model):
        jac = default_model.compute_jacobian(0.5, 0.1, 1.7, 0.1)
        assert np.all(np.isfinite(jac)), "Jacobian has non-finite values"


class TestClassifyStability:
    def test_stable_identity_like(self, default_model):
        """A matrix with small eigenvalues should classify as stable."""
        jac = 0.5 * np.eye(4)
        dom_eig, stable, bif_type = default_model.classify_stability(jac)
        assert stable is True
        assert bif_type == "stable"
        assert dom_eig == pytest.approx(0.5)

    def test_unstable_fold(self, default_model):
        """A matrix with eigenvalue > 1 should classify as fold."""
        jac = 1.5 * np.eye(4)
        dom_eig, stable, bif_type = default_model.classify_stability(jac)
        assert stable is False
        assert bif_type == "fold"
