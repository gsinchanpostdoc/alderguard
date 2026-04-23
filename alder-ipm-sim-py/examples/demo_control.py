#!/usr/bin/env python3
"""Demo: Compare optimal control strategies.

Uses calibrated parameters to run ControlOptimizer.compare_strategies
across three management scenarios (A, B, C), prints the comparison table,
and creates trajectory plots for each strategy.

Run:
    python examples/demo_control.py
"""

import sys
import os

import numpy as np
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from alder_ipm_sim.model import AlderIPMSimModel
from alder_ipm_sim.parameters import get_defaults
from alder_ipm_sim.control import ControlOptimizer

# ── Set up model ─────────────────────────────────────────────────────────────
params = get_defaults()
model = AlderIPMSimModel(params)

optimizer = ControlOptimizer(model)

# Initial state: beetles near carrying capacity, parasitoids present
initial_state = {
    "A0": params["K_0"] * 0.6,
    "F0": 0.1,
    "K0": params["K_0"],
    "D0": 0.0,
}

n_years = 50

# ── Compare strategies ───────────────────────────────────────────────────────
print(f"Optimising control strategies over {n_years} years...")
print("(This may take a minute due to differential evolution optimisation)\n")

comparison = optimizer.compare_strategies(initial_state, n_years=n_years)

# ── Print recommendation text ────────────────────────────────────────────────
print(comparison["recommendation_text"])
print()

# ── Print detailed table ─────────────────────────────────────────────────────
print("\nDetailed control inputs:")
print(f"{'Scenario':<12s} {'u_P':>8s} {'u_C':>8s} {'u_B':>8s} {'Cost J':>10s} {'D*':>8s} {'K*':>8s} {'rho*':>8s}")
print("-" * 72)
for r in comparison["results"]:
    ctrl = r.optimal_controls
    print(f"{r.scenario:<12s} {ctrl['u_P']:8.4f} {ctrl['u_C']:8.4f} {ctrl['u_B']:8.4f} "
          f"{r.cost_J:10.2f} {r.final_D_star:8.4f} {r.final_K_star:8.4f} {r.final_rho_star:8.4f}")

# ── Create trajectory plots for each strategy ───────────────────────────────
fig, axes = plt.subplots(3, 2, figsize=(14, 12))
fig.suptitle("Control Strategy Comparison — State Trajectories", fontsize=14)

scenario_labels = {
    "A": "Strategy A: Parasitoid augmentation only",
    "B": "Strategy B: Parasitoid + bird habitat",
    "C": "Strategy C: Full integrated control",
}
colors_A = {"A": "brown", "F": "teal", "K": "green", "D": "orange"}

for row, r in enumerate(comparison["results"]):
    # Simulate trajectory under optimal controls
    traj = optimizer.multi_year_trajectory(r.optimal_controls, initial_state, n_years)
    years = np.arange(n_years + 1)

    # Left panel: beetle and parasitoid densities
    ax = axes[row, 0]
    ax.plot(years, traj["A"], color="brown", linewidth=1.5, label="Beetle A")
    ax.plot(years, traj["F"], color="teal", linewidth=1.5, label="Parasitoid F")
    ax.set_ylabel("Density")
    ax.set_title(scenario_labels[r.scenario])
    ax.legend(loc="upper right")
    ax.grid(alpha=0.3)
    if row == 2:
        ax.set_xlabel("Year")

    # Right panel: defoliation and carrying capacity
    ax = axes[row, 1]
    ax.plot(years, traj["D"], color="orange", linewidth=1.5, label="Defoliation D")
    ax.plot(years, traj["K"], color="green", linewidth=1.5, label="Capacity K")
    ax.axhline(params["D_crit"], color="red", linestyle="--", alpha=0.5, label="D_crit")
    ax.axhline(params["K_min"], color="darkred", linestyle=":", alpha=0.5, label="K_min")
    ax.set_ylabel("Value")
    ax.set_title(f"Cost J = {r.cost_J:.1f}, rho* = {r.final_rho_star:.3f}")
    ax.legend(loc="upper right")
    ax.grid(alpha=0.3)
    if row == 2:
        ax.set_xlabel("Year")

plt.tight_layout()

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "control_comparison.png")
fig.savefig(out_path, dpi=150)
print(f"\nFigure saved to {out_path}")
plt.close(fig)
