#!/usr/bin/env python3
"""Demo: Run a 100-year forward simulation with default parameters.

Imports AlderIPMSimModel, simulates 100 annual cycles, prints a summary,
and saves a 4-panel matplotlib figure of beetle density, parasitoid density,
carrying capacity, and defoliation over time.

Run:
    python examples/demo_simulation.py
"""

import sys
import os

import numpy as np
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from alder_ipm_sim.model import AlderIPMSimModel
from alder_ipm_sim.parameters import get_defaults

# ── Set up model with default (calibrated) parameters ────────────────────────
params = get_defaults()
model = AlderIPMSimModel(params)

# Initial conditions: moderate beetle density, small parasitoid population
A0 = params["K_0"] * 0.5   # beetles at half carrying capacity
F0 = 0.1                    # small parasitoid inoculum
K0 = params["K_0"]          # full canopy carrying capacity
D0 = 0.0                    # no prior defoliation

n_years = 100

# ── Simulate ─────────────────────────────────────────────────────────────────
print(f"Running {n_years}-year simulation...")
result = model.simulate(A0=A0, F0=F0, K0=K0, D0=D0, n_years=n_years)

years = np.arange(n_years + 1)

# ── Print summary ────────────────────────────────────────────────────────────
R_P = model.compute_R_P()
print(f"\nParasitoid invasion number R_P = {R_P:.3f}")
print(f"  (R_P > 1 means parasitoid can invade => coexistence possible)\n")

print("Year  | Beetle A  | Parasitoid F | Capacity K | Defoliation D")
print("-" * 65)
for yr in [0, 10, 25, 50, 75, 100]:
    print(f"{yr:5d} | {result['A'][yr]:9.4f} | {result['F'][yr]:12.4f} | "
          f"{result['K'][yr]:10.4f} | {result['D'][yr]:13.4f}")

print(f"\nEquilibrium (year {n_years}):")
print(f"  A* = {result['A'][-1]:.4f}  (beetle density)")
print(f"  F* = {result['F'][-1]:.4f}  (parasitoid density)")
print(f"  K* = {result['K'][-1]:.4f}  (carrying capacity)")
print(f"  D* = {result['D'][-1]:.4f}  (cumulative defoliation)")

# ── Create 4-panel figure ────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
fig.suptitle("AlderIPM-Sim: 100-Year Forward Simulation", fontsize=14)

# Panel 1: Beetle density
ax = axes[0, 0]
ax.plot(years, result["A"], color="brown", linewidth=1.5)
ax.set_ylabel("Beetle density A(t)")
ax.set_title("Agelastica alni larval density")
ax.grid(alpha=0.3)

# Panel 2: Parasitoid density
ax = axes[0, 1]
ax.plot(years, result["F"], color="teal", linewidth=1.5)
ax.set_ylabel("Parasitoid density F(t)")
ax.set_title("Meigenia mutabilis fly density")
ax.grid(alpha=0.3)

# Panel 3: Carrying capacity
ax = axes[1, 0]
ax.plot(years, result["K"], color="green", linewidth=1.5)
ax.axhline(params["K_min"], color="red", linestyle="--", alpha=0.6, label="K_min")
ax.set_xlabel("Year")
ax.set_ylabel("Carrying capacity K(t)")
ax.set_title("Canopy carrying capacity")
ax.legend()
ax.grid(alpha=0.3)

# Panel 4: Cumulative defoliation
ax = axes[1, 1]
ax.plot(years, result["D"], color="orange", linewidth=1.5)
ax.axhline(params["D_crit"], color="red", linestyle="--", alpha=0.6, label="D_crit")
ax.set_xlabel("Year")
ax.set_ylabel("Defoliation D(t)")
ax.set_title("Cumulative defoliation")
ax.legend()
ax.grid(alpha=0.3)

plt.tight_layout()

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "simulation_100yr.png")
fig.savefig(out_path, dpi=150)
print(f"\nFigure saved to {out_path}")
plt.close(fig)
