#!/usr/bin/env python3
"""Generate synthetic datasets for AlderIPM-Sim examples.

Creates three CSV files that mimic field-collected monitoring data:
  1. example_stable_coexistence.csv  -- 30 years of stable annual data
  2. example_approaching_tipping.csv -- 40 years with rising R_B toward tipping
  3. example_seasonal_data.csv       -- daily within-season data for one year

Run:
    python examples/generate_synthetic_data.py
"""

import sys
import os

import numpy as np
import pandas as pd

# Allow running from the repo root or examples/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from alder_ipm_sim.model import AlderIPMSimModel
from alder_ipm_sim.parameters import get_defaults

# Reproducibility
rng = np.random.default_rng(seed=2024)


# ── Dataset 1: Stable coexistence (30 years) ────────────────────────────────
# Use calibrated parameters where parasitoid and beetle coexist stably.
# Add 5 % Gaussian noise to simulate measurement error.

def generate_stable_coexistence(out_path: str) -> None:
    params = get_defaults()
    # Ensure coexistence: moderate beetle fecundity, baseline calibrated values
    params["R_B"] = 9.5
    params["phi"] = 0.045
    params["sigma_A"] = 0.78
    params["sigma_F"] = 0.36

    model = AlderIPMSimModel(params)
    n_years = 30

    # Initial conditions near the coexistence equilibrium
    result = model.simulate(A0=0.8, F0=0.15, K0=params["K_0"], D0=0.0,
                            n_years=n_years)

    # Add 5 % relative Gaussian noise (floored at zero)
    noise_level = 0.05
    A_obs = np.maximum(result["A"] + rng.normal(0, noise_level * np.mean(result["A"]), n_years + 1), 0)
    F_obs = np.maximum(result["F"] + rng.normal(0, noise_level * np.mean(result["F"]), n_years + 1), 0)
    D_obs = np.maximum(result["D"] + rng.normal(0, noise_level * np.mean(result["D"] + 0.01), n_years + 1), 0)
    # Bird index is an exogenous covariate with minor noise
    B_obs = params["B_index"] + rng.normal(0, 0.05, n_years + 1)

    df = pd.DataFrame({
        "year": np.arange(n_years + 1),
        "beetle_density": np.round(A_obs, 6),
        "parasitoid_density": np.round(F_obs, 6),
        "defoliation": np.round(D_obs, 6),
        "bird_index": np.round(B_obs, 4),
    })
    df.to_csv(out_path, index=False)
    print(f"  Saved {out_path}  ({len(df)} rows)")


# ── Dataset 2: Approaching tipping point (40 years) ─────────────────────────
# R_B slowly increases from 8 to 14, mimicking climate-driven fecundity rise.
# The system starts in coexistence and drifts toward the parasitoid-free regime.

def generate_approaching_tipping(out_path: str) -> None:
    params = get_defaults()
    params["phi"] = 0.045
    params["sigma_A"] = 0.78
    params["sigma_F"] = 0.36

    n_years = 40
    R_B_series = np.linspace(8.0, 14.0, n_years)

    # Run year-by-year with changing R_B
    A = np.zeros(n_years + 1)
    F = np.zeros(n_years + 1)
    K = np.zeros(n_years + 1)
    D = np.zeros(n_years + 1)

    A[0], F[0], K[0], D[0] = 0.8, 0.15, params["K_0"], 0.0

    for t in range(n_years):
        params["R_B"] = R_B_series[t]
        model = AlderIPMSimModel(params)
        res = model.annual_map(A[t], F[t], K[t], D[t])
        A[t + 1] = res["A_next"]
        F[t + 1] = res["F_next"]
        K[t + 1] = res["K_next"]
        D[t + 1] = res["D_next"]

    # Add 5 % noise
    noise_level = 0.05
    A_obs = np.maximum(A + rng.normal(0, noise_level * np.mean(A), n_years + 1), 0)
    F_obs = np.maximum(F + rng.normal(0, noise_level * np.mean(F), n_years + 1), 0)
    D_obs = np.maximum(D + rng.normal(0, noise_level * np.mean(D + 0.01), n_years + 1), 0)
    B_obs = params["B_index"] + rng.normal(0, 0.05, n_years + 1)

    df = pd.DataFrame({
        "year": np.arange(n_years + 1),
        "beetle_density": np.round(A_obs, 6),
        "parasitoid_density": np.round(F_obs, 6),
        "defoliation": np.round(D_obs, 6),
        "bird_index": np.round(B_obs, 4),
    })
    df.to_csv(out_path, index=False)
    print(f"  Saved {out_path}  ({len(df)} rows)")


# ── Dataset 3: Within-season daily data (one year) ──────────────────────────
# High-resolution data at daily time steps during the larval vulnerability window.

def generate_seasonal_data(out_path: str) -> None:
    params = get_defaults()
    params["R_B"] = 9.5
    model = AlderIPMSimModel(params)

    # Season length T ~ 50 days; sample every day
    T = params["T"]
    t_eval = np.arange(0, int(T) + 1, dtype=float)

    # Initial conditions: start of season with moderate beetle density
    S0, I0, F0, D0 = 0.8, 0.0, 0.15, 0.0
    sol, end_vals = model.integrate_season(S0, I0, F0, D0, t_eval=t_eval)

    # Add small measurement noise (2 % for within-season data)
    noise_level = 0.02
    S_obs = np.maximum(sol.y[0] + rng.normal(0, noise_level * np.mean(sol.y[0]), len(t_eval)), 0)
    I_obs = np.maximum(sol.y[1] + rng.normal(0, noise_level * max(np.mean(sol.y[1]), 0.001), len(t_eval)), 0)
    F_obs = np.maximum(sol.y[2] + rng.normal(0, noise_level * np.mean(sol.y[2]), len(t_eval)), 0)
    D_obs = np.maximum(sol.y[3] + rng.normal(0, noise_level * max(np.mean(sol.y[3]), 0.001), len(t_eval)), 0)

    df = pd.DataFrame({
        "day": t_eval.astype(int),
        "S": np.round(S_obs, 6),
        "I": np.round(I_obs, 6),
        "F": np.round(F_obs, 6),
        "D": np.round(D_obs, 6),
    })
    df.to_csv(out_path, index=False)
    print(f"  Saved {out_path}  ({len(df)} rows)")


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    examples_dir = os.path.dirname(os.path.abspath(__file__))

    print("Generating synthetic datasets...")
    generate_stable_coexistence(os.path.join(examples_dir, "example_stable_coexistence.csv"))
    generate_approaching_tipping(os.path.join(examples_dir, "example_approaching_tipping.csv"))
    generate_seasonal_data(os.path.join(examples_dir, "example_seasonal_data.csv"))
    print("Done.")
