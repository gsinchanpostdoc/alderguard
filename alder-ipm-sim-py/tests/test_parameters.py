"""Tests for the parameter registry and validation."""
import pytest

from alder_ipm_sim.parameters import (
    PARAM_REGISTRY,
    ParamMeta,
    get_defaults,
    get_param,
    validate_params,
)

# Complete list of expected parameter names.
EXPECTED_PARAMS = {
    "beta", "h", "c_B", "a_B", "mu_S", "mu_I", "delta", "eta",
    "mu_F", "kappa", "T", "B_index",
    "R_B", "sigma_A", "sigma_F", "K_0", "phi", "rho",
    "u_P_max", "u_C_max", "u_B_max",
    "D_crit", "K_min",
}


class TestParamRegistry:
    def test_registry_count(self):
        assert len(PARAM_REGISTRY) == len(EXPECTED_PARAMS)

    def test_all_expected_params_present(self):
        assert set(PARAM_REGISTRY.keys()) == EXPECTED_PARAMS

    def test_defaults_within_bounds(self):
        for name, meta in PARAM_REGISTRY.items():
            assert meta.min_val <= meta.default <= meta.max_val, (
                f"{name}: default {meta.default} not in "
                f"[{meta.min_val}, {meta.max_val}]"
            )

    def test_param_meta_fields(self):
        for meta in PARAM_REGISTRY.values():
            assert isinstance(meta, ParamMeta)
            assert meta.name
            assert meta.symbol
            assert meta.unit
            assert meta.description
            assert meta.module in ("within_season", "annual")


class TestGetDefaults:
    def test_returns_dict(self):
        d = get_defaults()
        assert isinstance(d, dict)

    def test_all_values_are_float(self):
        for name, val in get_defaults().items():
            assert isinstance(val, (int, float)), f"{name} is {type(val)}"

    def test_matches_registry(self):
        d = get_defaults()
        for name, val in d.items():
            assert val == PARAM_REGISTRY[name].default


class TestGetParam:
    def test_known_param(self):
        meta = get_param("beta")
        assert meta.name == "beta"

    def test_unknown_param_raises(self):
        with pytest.raises(KeyError, match="Unknown parameter"):
            get_param("nonexistent_param")


class TestValidateParams:
    def test_valid_defaults_pass(self):
        validate_params(get_defaults())

    def test_out_of_range_raises(self):
        with pytest.raises(ValueError, match="outside"):
            validate_params({"beta": 999.0})

    def test_below_min_raises(self):
        with pytest.raises(ValueError, match="outside"):
            validate_params({"beta": -1.0})

    def test_unknown_params_ignored(self):
        # Should not raise for unknown keys
        validate_params({"unknown_xyz": 42.0})

    def test_boundary_values_pass(self):
        # min and max should both be valid
        for name, meta in PARAM_REGISTRY.items():
            validate_params({name: meta.min_val})
            validate_params({name: meta.max_val})
