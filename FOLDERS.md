# AlderIPM-Sim Project Folders

This repository contains three self-contained implementations of the AlderIPM-Sim ecological model for alder-beetle-parasitoid dynamics and pest management.

## `alder-ipm-sim-py/` — Python Package

**What it contains:** A pip-installable Python package with ODE simulation, equilibrium analysis, early warning signal detection, data fitting, optimal control evaluation, a CLI, and a Streamlit web dashboard.

**Key files:**
- `alder-ipm-sim/` — core library (model.py, parameters.py, warnings.py, fitting.py, control.py)
- `alder-ipm-sim/cli.py` — command-line interface with 6 subcommands
- `alder-ipm-sim/app.py` — Streamlit interactive dashboard
- `tests/` — 44 pytest unit tests
- `examples/` — demo scripts and synthetic data generation

**How to use:**
```bash
cd alder-ipm-sim-py
pip install -e .
alder-ipm-sim simulate --years 50 --output results.csv
alder-ipm-sim dashboard                # launch Streamlit app
```

See `alder-ipm-sim-py/README.md` and `alder-ipm-sim-py/INSTALL.md` for full details.

---

## `alder-ipm-sim-r/` — R Package

**What it contains:** A standard R package with the same ODE model, equilibrium analysis, early warning signals, data fitting, and a Shiny interactive application.

**Key files:**
- `R/` — package source (model.R, parameters.R, equilibrium.R, warnings.R, fitting.R, control.R)
- `inst/shiny/app.R` — Shiny dashboard
- `man/` — 27 Rd documentation files
- `tests/testthat/` — unit tests

**How to use:**
```r
# Install from source
install.packages("alder-ipm-sim-r", repos = NULL, type = "source")
library(alderIPMSim)
result <- simulate(default_params(), years = 50)
run_app()                           # launch Shiny dashboard
```

See `alder-ipm-sim-r/README.md` and `alder-ipm-sim-r/INSTALL.md` for full details.

---

## `alder-ipm-sim-web/` — Standalone HTML/JS Web Application

**What it contains:** A zero-dependency browser application (no server required) with interactive parameter sliders, simulation plots, equilibrium analysis, early warning detection, and control strategy comparison. Uses Chart.js for plotting.

**Key files:**
- `index.html` — single-page application entry point
- `js/` — model logic (model.js, parameters.js, simulation.js, warnings.js, control.js, charts.js, app.js)
- `css/style.css` — responsive styling with print support
- `sw.js` — service worker for offline use

**How to use:**
```bash
cd alder-ipm-sim-web
# Option 1: open directly
open index.html                     # or double-click in file explorer
# Option 2: local server
python -m http.server 8080          # then visit http://localhost:8080
```

See `alder-ipm-sim-web/README.md` and `alder-ipm-sim-web/INSTALL.md` for full details.

---

## Cross-Folder Consistency

All three implementations share the same 23 calibrated default parameters and the same ODE model structure. Parameter values are synchronized across `alder-ipm-sim-py/alder-ipm-sim/parameters.py`, `alder-ipm-sim-r/R/parameters.R`, and `alder-ipm-sim-web/js/parameters.js`.

Each folder is fully self-contained and can be distributed independently.
