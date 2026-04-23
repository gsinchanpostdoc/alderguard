# AlderIPM-Sim Web

Browser-based decision-support tool for managing *Agelastica alni* (alder leaf beetle) outbreaks in European alder (*Alnus*) forests. Implements a coupled ecoepidemiological model with interactive parameter tuning, simulation, equilibrium analysis, early warning signal detection, and management strategy comparison.

## Quick Start

1. Open `index.html` in any modern web browser (Chrome, Firefox, Edge, Safari).
2. No installation, build step, or server required — everything runs client-side.

### Local Server (Optional)

If you prefer a local HTTP server (e.g. for development or to avoid file:// restrictions):

```bash
# Linux / macOS:
bash serve.sh

# Windows:
serve.bat

# Or directly with Python:
python serve.py          # serves on port 8080
python serve.py 3000     # custom port
```

## Features

| Tab | Description |
|-----|-------------|
| **Parameters** | Adjust all 22 model parameters via sliders with ecologically meaningful bounds. |
| **Simulation** | Run multi-year simulations with configurable initial conditions and control inputs. View 4-subplot time series (beetles, parasitoids, carrying capacity, defoliation). Export results as CSV. |
| **Equilibrium** | Find fixed points of the annual map via Newton-Raphson iteration. Stability analysis via numerical Jacobian eigenvalue computation. |
| **Early Warnings** | Detect critical slowing down signals preceding regime shifts. Computes rolling variance, lag-1 autocorrelation, and spectral reddening index with Kendall tau trend tests. Supports CSV upload or simulated data. Traffic-light alert system (green/amber/red). |
| **Control Comparison** | Compare 4 management strategies (no control, chemical only, biocontrol only, IPM combined) via cost-functional evaluation. Adjustable cost weights. Results table and bar chart. |
| **About / Help** | Model description, usage guide, parameter glossary, equations, and references. |

## File Structure

```
alder-ipm-sim-web/
├── index.html          # Main application page
├── README.md           # This file
├── css/
│   └── style.css       # All styles
├── js/
│   ├── parameters.js   # Parameter registry with metadata
│   ├── model.js        # ODE model and RK4 integrator
│   ├── simulation.js   # Simulation runner and CSV export
│   ├── warnings.js     # Early warning signal detection
│   ├── control.js      # Control strategy comparison
│   ├── charts.js       # Chart.js rendering
│   └── app.js          # Main application controller
└── data/
    └── default_params.json
```

## Dependencies

- [Chart.js](https://www.chartjs.org/) (loaded from CDN) — for all chart rendering.
- No other external dependencies.

## Browser Compatibility

Works in all modern browsers supporting ES6+ (Chrome 60+, Firefox 55+, Edge 79+, Safari 12+).

## Related Packages

- `alder-ipm-sim-py/` — Python package with CLI, Streamlit app, and full test suite.
- `alder-ipm-sim-r/` — R package with Shiny app.
