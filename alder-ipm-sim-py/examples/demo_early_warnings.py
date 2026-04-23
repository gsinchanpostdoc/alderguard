#!/usr/bin/env python3
"""Demo: Early warning signal detection on a tipping-point time series.

Loads example_approaching_tipping.csv (beetle density with rising R_B),
runs the EarlyWarningDetector, prints the WarningReport, and creates
a 4-panel EWS diagnostic plot.

Run:
    python examples/generate_synthetic_data.py   # generate data first
    python examples/demo_early_warnings.py
"""

import sys
import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from alder_ipm_sim.warnings import EarlyWarningDetector

# ── Load data ────────────────────────────────────────────────────────────────
examples_dir = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(examples_dir, "example_approaching_tipping.csv")

if not os.path.exists(data_path):
    print("Data file not found. Run generate_synthetic_data.py first.")
    sys.exit(1)

df = pd.read_csv(data_path)
print(f"Loaded {len(df)} rows from {data_path}\n")

# Extract the beetle density time series for EWS analysis
beetle_ts = df["beetle_density"].values

# ── Run EWS detection ────────────────────────────────────────────────────────
# Use Gaussian kernel detrending (default) and auto window size (50% of series)
detector = EarlyWarningDetector(detrend_method="gaussian")
report = detector.detect_regime_shift(beetle_ts)

# ── Print WarningReport ──────────────────────────────────────────────────────
print("=" * 60)
print("EARLY WARNING SIGNAL REPORT")
print("=" * 60)
print(f"\nAlert Level: {report.alert_level.upper()}")
print(f"\nInterpretation:\n  {report.interpretation}\n")

print("Kendall trend tests:")
print(f"  {'Indicator':<20s} {'tau':>8s} {'p-value':>10s} {'Trend?':>8s}")
print("  " + "-" * 50)
for name, vals in report.kendall_results.items():
    tau = vals["tau"]
    pval = vals["p_value"]
    sig = "YES" if (pval < 0.05 and tau > 0.3) else "no"
    print(f"  {name:<20s} {tau:8.3f} {pval:10.4f} {sig:>8s}")

# ── 4-panel EWS diagnostic plot ──────────────────────────────────────────────
indicators = report.indicators
# The rolling window trims the series; create matching x-axis
n_full = len(beetle_ts)
window = detector._effective_window(beetle_ts)
n_rolling = len(indicators["variance"])
x_rolling = np.arange(window - 1, window - 1 + n_rolling)

fig, axes = plt.subplots(2, 2, figsize=(12, 8))
fig.suptitle("Early Warning Signals — Approaching Tipping Point", fontsize=14)

titles = ["Rolling Variance", "Rolling Autocorrelation (lag-1)",
          "Rolling Skewness", "Rolling Kurtosis"]
keys = ["variance", "autocorrelation", "skewness", "kurtosis"]
colors = ["#d62728", "#1f77b4", "#2ca02c", "#9467bd"]

for ax, key, title, color in zip(axes.flat, keys, titles, colors):
    vals = indicators[key]
    ax.plot(x_rolling, vals, color=color, linewidth=1.5)
    ax.set_title(title)
    ax.set_xlabel("Year")
    ax.grid(alpha=0.3)

    # Annotate with Kendall tau
    tau = report.kendall_results[key]["tau"]
    pval = report.kendall_results[key]["p_value"]
    ax.text(0.02, 0.95, f"tau={tau:.3f}, p={pval:.4f}",
            transform=ax.transAxes, fontsize=9, verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))

plt.tight_layout()

out_path = os.path.join(examples_dir, "early_warnings.png")
fig.savefig(out_path, dpi=150)
print(f"\nFigure saved to {out_path}")
plt.close(fig)
