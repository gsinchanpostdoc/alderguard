#!/usr/bin/env python3
"""Demo: Fit model parameters to synthetic data.

Loads example_stable_coexistence.csv, fits four key parameters
(beta, R_B, phi, sigma_A) using ModelFitter, prints fitted vs true values,
and plots observed vs predicted trajectories.

Run:
    python examples/generate_synthetic_data.py   # generate data first
    python examples/demo_fitting.py
"""

import sys
import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from alder_ipm_sim.model import AlderIPMSimModel
from alder_ipm_sim.parameters import get_defaults
from alder_ipm_sim.fitting import ModelFitter

# ── Load data ────────────────────────────────────────────────────────────────
examples_dir = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(examples_dir, "example_stable_coexistence.csv")

if not os.path.exists(data_path):
    print("Data file not found. Run generate_synthetic_data.py first.")
    sys.exit(1)

df = pd.read_csv(data_path)
print(f"Loaded {len(df)} rows from {data_path}")
print(f"Columns: {list(df.columns)}\n")

# ── True parameter values (used to generate the data) ────────────────────────
true_params = {
    "beta": 0.0301,
    "R_B": 9.5,
    "phi": 0.045,
    "sigma_A": 0.78,
}

# ── Set up fitter ────────────────────────────────────────────────────────────
# Start from default parameters (slightly different from truth)
model = AlderIPMSimModel()
fitter = ModelFitter(model)

# Prepare data with column name mapping
prepared = fitter.prepare_data(
    df,
    time_col="year",
    state_cols={
        "A": "beetle_density",
        "F": "parasitoid_density",
        "D": "defoliation",
    },
    timestep="annual",
)

# ── Fit parameters ───────────────────────────────────────────────────────────
fit_params = ["beta", "R_B", "phi", "sigma_A"]
print(f"Fitting parameters: {fit_params}")
print("Method: Trust Region Reflective (least_squares)\n")

result = fitter.fit(prepared, fit_params=fit_params, method="least_squares")

# ── Print comparison ─────────────────────────────────────────────────────────
print("Parameter    | True     | Fitted   | 95% CI")
print("-" * 55)
for p in fit_params:
    true_val = true_params[p]
    fit_val = result.fitted_params[p]
    ci = result.confidence_intervals[p]
    print(f"{p:12s} | {true_val:8.5f} | {fit_val:8.5f} | [{ci[0]:.5f}, {ci[1]:.5f}]")

print(f"\nR-squared:  {result.r_squared:.4f}")
print(f"AIC:        {result.AIC:.2f}")
print(f"BIC:        {result.BIC:.2f}")
print(f"Converged:  {result.convergence_info.get('success', 'N/A')}")

# ── Plot observed vs predicted ───────────────────────────────────────────────
# Run model with fitted parameters to get predicted trajectories
fitted_model = AlderIPMSimModel({**get_defaults(), **result.fitted_params})
n_years = len(df) - 1
sim = fitted_model.simulate(
    A0=df["beetle_density"].iloc[0],
    F0=df["parasitoid_density"].iloc[0],
    K0=get_defaults()["K_0"],
    D0=df["defoliation"].iloc[0],
    n_years=n_years,
)

years = df["year"].values

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
fig.suptitle("Model Fitting: Observed vs Predicted", fontsize=13)

# Beetle density
ax = axes[0]
ax.scatter(years, df["beetle_density"], s=15, color="brown", alpha=0.7, label="Observed")
ax.plot(years, sim["A"][:len(years)], color="brown", linewidth=1.5, label="Predicted")
ax.set_xlabel("Year")
ax.set_ylabel("Beetle density")
ax.set_title("Beetle larval density A(t)")
ax.legend()
ax.grid(alpha=0.3)

# Parasitoid density
ax = axes[1]
ax.scatter(years, df["parasitoid_density"], s=15, color="teal", alpha=0.7, label="Observed")
ax.plot(years, sim["F"][:len(years)], color="teal", linewidth=1.5, label="Predicted")
ax.set_xlabel("Year")
ax.set_ylabel("Parasitoid density")
ax.set_title("Parasitoid fly density F(t)")
ax.legend()
ax.grid(alpha=0.3)

# Defoliation
ax = axes[2]
ax.scatter(years, df["defoliation"], s=15, color="orange", alpha=0.7, label="Observed")
ax.plot(years, sim["D"][:len(years)], color="orange", linewidth=1.5, label="Predicted")
ax.set_xlabel("Year")
ax.set_ylabel("Defoliation")
ax.set_title("Cumulative defoliation D(t)")
ax.legend()
ax.grid(alpha=0.3)

plt.tight_layout()

out_path = os.path.join(examples_dir, "fitting_result.png")
fig.savefig(out_path, dpi=150)
print(f"\nFigure saved to {out_path}")
plt.close(fig)
