"""Shared pytest fixtures for the AlderIPM-Sim test suite."""
import numpy as np
import pytest

from alder_ipm_sim.model import AlderIPMSimModel
from alder_ipm_sim.parameters import get_defaults


@pytest.fixture
def default_model():
    """AlderIPMSimModel with all default parameters."""
    return AlderIPMSimModel()


@pytest.fixture
def calibrated_model():
    """AlderIPMSimModel with calibrated baseline parameters."""
    return AlderIPMSimModel()


@pytest.fixture
def synthetic_annual_data(default_model):
    """50-year annual trajectory from default parameters.

    Returns a dict with keys 'year', 'A', 'F', 'K', 'D'.
    """
    defaults = get_defaults()
    K0 = defaults["K_0"]
    sim = default_model.simulate(
        A0=K0 * 0.5, F0=0.1, K0=K0, D0=0.0, n_years=50,
    )
    return {
        "year": np.arange(51, dtype=float),
        "A": sim["A"],
        "F": sim["F"],
        "K": sim["K"],
        "D": sim["D"],
    }


@pytest.fixture
def synthetic_seasonal_data(default_model):
    """Within-season trajectory (100 time points) from default parameters.

    Returns a dict with keys 'time', 'A', 'F', 'D'.
    """
    defaults = get_defaults()
    K0 = defaults["K_0"]
    t_eval = np.linspace(0, defaults["T"], 100)
    sol, _ = default_model.integrate_season(
        S0=K0 * 0.5, I0=0.0, F0=0.1, D0=0.0, t_eval=t_eval,
    )
    return {
        "time": t_eval,
        "A": sol.y[0],
        "F": sol.y[2],
        "D": sol.y[3],
    }
