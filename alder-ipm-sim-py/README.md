# AlderIPM-Sim — Python Decision-Support Toolkit

Python implementation of the AlderIPM-Sim toolkit for the *Alnus*--beetle--parasitoid--bird ecoepidemic system. This package provides ODE simulation, equilibrium and stability analysis, early warning signal detection, data fitting, optimal control evaluation, a CLI, and an interactive Streamlit dashboard.

## Quick Setup (Recommended)

Run the one-command setup script to create a virtual environment, install everything, and verify with tests:

```bash
# Linux / macOS:
bash setup_and_run.sh

# Windows:
setup_and_run.bat
```

## Manual Installation

See [INSTALL.md](INSTALL.md) for detailed step-by-step instructions.

```bash
# Quick start:
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install .                # core (simulation, analysis, CLI)
pip install ".[app]"         # with Streamlit dashboard
pip install -e ".[app,dev]"  # development install
```

You can also install from `requirements.txt`:

```bash
pip install -r requirements.txt
```

## Quick Start

```python
from alder_ipm_sim.model import AlderIPMSimModel

model = AlderIPMSimModel()
traj = model.multi_year_sim(years=50)
print(f"Year 50 canopy: K={traj[-1]['K']:.3f}")
```

## Modules

| Module | Description |
|--------|-------------|
| `parameters` | Parameter registry with ecological metadata and units |
| `model` | Within-season ODE, annual map, equilibrium & stability analysis |
| `warnings` | Early warning signal detection (variance, autocorrelation, spectral) |
| `fitting` | Time series fitting and parameter estimation |
| `control` | Optimal control strategy evaluation and comparison |
| `cli` | Command-line interface (6 subcommands) |
| `app` | Streamlit interactive web dashboard |

## CLI Usage

```bash
alder-ipm-sim simulate --years 50 --output trajectory.csv
alder-ipm-sim equilibrium --verbose
alder-ipm-sim fit --data field_data.csv --fit-params beta c_B phi
alder-ipm-sim warn --data canopy_series.csv --column K --window 15
alder-ipm-sim control --years 30
alder-ipm-sim dashboard
```

Or via module entry point:

```bash
python -m alder-ipm-sim simulate --years 50
```

## Examples

The `examples/` directory contains:

- `generate_synthetic_data.py` — create synthetic CSV datasets
- `demo_simulation.py` — run and plot a 100-year simulation
- `demo_fitting.py` — fit model parameters to field data
- `demo_early_warnings.py` — detect tipping-point early warnings
- `demo_control.py` — compare pest management strategies
- `demo_full_workflow.py` — end-to-end workflow

## Documentation

The `docs/` directory includes user guides for different audiences:

- [Forest Managers Guide](docs/user_guide_managers.md)
- [Researchers Guide](docs/user_guide_researchers.md)
- [Conservation Practitioners Guide](docs/user_guide_conservation.md)
- [Data Format Specification](docs/data_format.md)

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/
```

## License

MIT License. See [LICENSE](LICENSE) for details.
