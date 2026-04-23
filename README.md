# AlderIPM-Sim

**Decision-support toolkit for the *Alnus* (alder) — bark beetle — parasitoid wasp — insectivorous bird ecoepidemic system.** AlderIPM-Sim couples a within-season ODE model with an annual discrete map to simulate canopy dieback, parasitoid biocontrol, and bird predation under different management scenarios. It predicts regime shifts, detects early warning signals, fits to field data, and evaluates integrated pest management strategies — available as a Python package, an R package, and a browser-based web app.

## Three ways to use AlderIPM-Sim

| Audience | Component | Install / Launch |
|----------|-----------|------------------|
| Practitioners, teaching, demos | **Web app** | Open <https://gsinchanpostdoc.github.io/alder-ipm-sim/> — nothing to install |
| Python users, data pipelines, CLI | **`alder-ipm-sim-py/`** | `pip install "git+https://github.com/gsinchanpostdoc/alder-ipm-sim.git#subdirectory=alder-ipm-sim-py"` |
| R users, Shiny dashboards, Rmd reports | **`alder-ipm-sim-r/`** | `remotes::install_github("gsinchanpostdoc/alder-ipm-sim", subdir = "alder-ipm-sim-r")` |

The three components share the same model, parameter names, and outputs, so a workflow started in the browser can be reproduced verbatim in Python or R. Each in-app "Use in R" / "Use in Python" button exports a snippet pre-filled with the current parameter set.

## Repository layout

```
alder-ipm-sim/
├── alder-ipm-sim-web/     # Browser-only decision-support app (HTML + Plotly; hosted on GitHub Pages)
├── alder-ipm-sim-py/      # Python 3 package with CLI and Streamlit dashboard
├── alder-ipm-sim-r/       # R package with Shiny dashboard
├── docs/               # Shared user guides (managers, researchers, conservation)
├── .github/workflows/  # GitHub Pages + CI workflows
└── README.md
```

## Install — Python

Requires Python ≥ 3.9. Install directly from the monorepo:

```bash
pip install "git+https://github.com/gsinchanpostdoc/alder-ipm-sim.git#subdirectory=alder-ipm-sim-py"
```

For the Streamlit dashboard and development extras:

```bash
git clone https://github.com/gsinchanpostdoc/alder-ipm-sim.git
cd alder-ipm-sim/alder-ipm-sim-py
pip install -e ".[app,dev]"
```

Quick start:

```python
from alder_ipm_sim.model import AlderIPMSimModel
model = AlderIPMSimModel()
traj  = model.multi_year_sim(years=50)
print(f"R_P = {model.compute_R_P():.3f}")
```

See [`alder-ipm-sim-py/README.md`](alder-ipm-sim-py/README.md) for the full API.

## Install — R

Requires R ≥ 4.1. Install directly from the monorepo:

```r
# one-time
install.packages("remotes")

remotes::install_github("gsinchanpostdoc/alder-ipm-sim", subdir = "alder-ipm-sim-r")
```

Or with `devtools`:

```r
devtools::install_github("gsinchanpostdoc/alder-ipm-sim", subdir = "alder-ipm-sim-r")
```

Quick start:

```r
library(alderIPMSim)
params <- as.list(default_params())
traj   <- simulate(params, A0 = 1.0, F0 = 0.5, K0 = 1.712, D0 = 0, n_years = 50)
cat("R_P =", round(compute_RP(params), 3), "\n")
```

Launch the Shiny dashboard:

```r
alderIPMSim::run_app()
```

See [`alder-ipm-sim-r/README.md`](alder-ipm-sim-r/README.md) for the full API.

## Use — Web app

The web app is hosted on GitHub Pages and runs entirely in the browser (no server, no account). It covers parameter tuning, multi-year simulation, equilibrium and stability analysis, 1-D and 2-D bifurcation diagrams, **parameter fitting to uploaded field-data CSV files**, early warning signals (variance, autocorrelation, spectral reddening, Kendall τ), LHS-PRCC sensitivity, basin-stability analysis, and integrated-pest-management control comparison. Each result can be exported as CSV or JSON, and the **Use in R** / **Use in Python** header buttons produce copy-paste snippets that reproduce the current configuration in either package.

To run the web app locally:

```bash
cd alder-ipm-sim-web
python serve.py            # then open http://localhost:8080
```

## Citation

If you use AlderIPM-Sim in your research, please cite:

```bibtex
@article{alderipmsim2026,
  title   = {AlderIPM-Sim: Hybrid seasonal-annual modelling and early warning
             signals for the Alnus--beetle--parasitoid--bird ecoepidemic system},
  author  = {Ghosh, Sinchan and colleagues},
  journal = {Frontiers in Ecology and Evolution},
  year    = {2026},
  note    = {Manuscript submitted}
}
```

## License

MIT License. See [`alder-ipm-sim-py/LICENSE`](alder-ipm-sim-py/LICENSE), [`alder-ipm-sim-r/LICENSE`](alder-ipm-sim-r/LICENSE), and [`alder-ipm-sim-web/LICENSE`](alder-ipm-sim-web/LICENSE).
