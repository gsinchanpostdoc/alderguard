#!/usr/bin/env python3
"""Demo: Complete end-to-end forest management workflow.

This script demonstrates the full pipeline a forest manager would follow:
  1. Load monitoring data
  2. Fit the model to observed data
  3. Check early warning signals
  4. Evaluate control strategies
  5. Print a management recommendation

Run:
    python examples/generate_synthetic_data.py   # generate data first
    python examples/demo_full_workflow.py
"""

import sys
import os

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from alder_ipm_sim.model import AlderIPMSimModel
from alder_ipm_sim.parameters import get_defaults
from alder_ipm_sim.fitting import ModelFitter
from alder_ipm_sim.warnings import EarlyWarningDetector
from alder_ipm_sim.control import ControlOptimizer

examples_dir = os.path.dirname(os.path.abspath(__file__))

# =====================================================================
# STEP 1: Load monitoring data
# =====================================================================
print("=" * 60)
print("STEP 1: Load monitoring data")
print("=" * 60)

data_path = os.path.join(examples_dir, "example_approaching_tipping.csv")
if not os.path.exists(data_path):
    print("Data file not found. Run generate_synthetic_data.py first.")
    sys.exit(1)

df = pd.read_csv(data_path)
print(f"Loaded {len(df)} years of monitoring data")
print(f"  Beetle density range: [{df['beetle_density'].min():.3f}, {df['beetle_density'].max():.3f}]")
print(f"  Parasitoid range:     [{df['parasitoid_density'].min():.3f}, {df['parasitoid_density'].max():.3f}]")
print(f"  Defoliation range:    [{df['defoliation'].min():.3f}, {df['defoliation'].max():.3f}]")

# =====================================================================
# STEP 2: Fit the model to data
# =====================================================================
print(f"\n{'=' * 60}")
print("STEP 2: Fit model parameters to observed data")
print("=" * 60)

model = AlderIPMSimModel()
fitter = ModelFitter(model)

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

# Fit the four most identifiable parameters
fit_params = ["beta", "R_B", "phi", "sigma_A"]
print(f"Fitting: {fit_params}")
fit_result = fitter.fit(prepared, fit_params=fit_params, method="least_squares")

print(f"\nFitted parameters:")
for p in fit_params:
    v = fit_result.fitted_params[p]
    ci = fit_result.confidence_intervals[p]
    print(f"  {p:12s} = {v:.5f}  (95% CI: [{ci[0]:.5f}, {ci[1]:.5f}])")
print(f"  R-squared = {fit_result.r_squared:.4f}")

# Compute R_P with fitted parameters
fitted_model = AlderIPMSimModel({**get_defaults(), **fit_result.fitted_params})
R_P = fitted_model.compute_R_P()
print(f"\n  Parasitoid invasion number R_P = {R_P:.3f}")
if R_P > 1:
    print("  -> Parasitoid CAN persist (R_P > 1)")
else:
    print("  -> Parasitoid CANNOT persist (R_P < 1) -- biocontrol at risk!")

# =====================================================================
# STEP 3: Check early warning signals
# =====================================================================
print(f"\n{'=' * 60}")
print("STEP 3: Early warning signal analysis")
print("=" * 60)

detector = EarlyWarningDetector(detrend_method="gaussian")
beetle_ts = df["beetle_density"].values
report = detector.detect_regime_shift(beetle_ts)

print(f"\n  Alert Level: {report.alert_level.upper()}")
print(f"\n  Interpretation:\n    {report.interpretation}")

print(f"\n  Kendall trend tests:")
for name, vals in report.kendall_results.items():
    sig_marker = " *" if (vals["p_value"] < 0.05 and vals["tau"] > 0.3) else ""
    print(f"    {name:<20s}  tau = {vals['tau']:+.3f}  (p = {vals['p_value']:.4f}){sig_marker}")

# =====================================================================
# STEP 4: Evaluate control strategies
# =====================================================================
print(f"\n{'=' * 60}")
print("STEP 4: Evaluate management strategies")
print("=" * 60)

# Use the last observed state as the starting point for control optimisation
last_A = df["beetle_density"].iloc[-1]
last_F = df["parasitoid_density"].iloc[-1]
last_D = df["defoliation"].iloc[-1]

initial_state = {
    "A0": last_A,
    "F0": last_F,
    "K0": fitted_model.params["K_0"],
    "D0": last_D,
}

# Use the fitted model for control optimisation
control_model = AlderIPMSimModel({**get_defaults(), **fit_result.fitted_params})
optimizer = ControlOptimizer(control_model)

print("\nOptimising 3 management scenarios (this may take a minute)...")
comparison = optimizer.compare_strategies(initial_state, n_years=30)

for r in comparison["results"]:
    ctrl = r.optimal_controls
    status = "FEASIBLE" if r.feasible else "INFEASIBLE"
    print(f"\n  Strategy {r.scenario}: {status}")
    print(f"    u_P={ctrl['u_P']:.4f}, u_C={ctrl['u_C']:.4f}, u_B={ctrl['u_B']:.4f}")
    print(f"    Cost J={r.cost_J:.1f}, D*={r.final_D_star:.4f}, K*={r.final_K_star:.4f}")

# =====================================================================
# STEP 5: Management recommendation
# =====================================================================
print(f"\n{'=' * 60}")
print("STEP 5: Management Recommendation")
print("=" * 60)

rec = comparison["recommended"]
if rec is not None:
    print(f"\n  RECOMMENDED: Strategy {rec.scenario}")
    print(f"  Total cost J = {rec.cost_J:.1f}")
    print(f"  Controls: u_P = {rec.optimal_controls['u_P']:.4f} "
          f"(parasitoid augmentation rate)")
    if rec.optimal_controls["u_C"] > 0:
        print(f"             u_C = {rec.optimal_controls['u_C']:.4f} "
              f"(direct larval removal effort)")
    if rec.optimal_controls["u_B"] > 0:
        print(f"             u_B = {rec.optimal_controls['u_B']:.4f} "
              f"(bird habitat enhancement)")
    print(f"\n  Expected outcomes:")
    print(f"    Final defoliation D* = {rec.final_D_star:.4f} (threshold: {control_model.params['D_crit']})")
    print(f"    Carrying capacity K* = {rec.final_K_star:.4f} (minimum: {control_model.params['K_min']})")
    print(f"    Stability rho*       = {rec.final_rho_star:.4f} (stable if < 1)")
else:
    print("\n  WARNING: No feasible strategy found within current budget constraints.")
    print("  Consider increasing control budgets or extending the management horizon.")

# Final summary based on alert level
print(f"\n{'=' * 60}")
print("SUMMARY")
print("=" * 60)
if report.alert_level == "red":
    print("\n  URGENT: Early warning signals indicate the ecosystem is approaching")
    print("  a tipping point. Immediate management intervention is recommended.")
elif report.alert_level == "yellow":
    print("\n  CAUTION: Some early warning indicators are elevated. Increase")
    print("  monitoring frequency and prepare management contingency plans.")
else:
    print("\n  System appears stable. Continue routine monitoring.")

print(f"\n  R_P = {R_P:.3f} | Alert: {report.alert_level.upper()}", end="")
if rec:
    print(f" | Recommended: Strategy {rec.scenario}")
else:
    print(" | No feasible strategy found")

print("\nWorkflow complete.")
