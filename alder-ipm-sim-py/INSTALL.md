# AlderIPM-Sim Installation Guide

## One-Command Setup

The fastest way to get started is with the setup script, which creates a virtual environment, installs the package with all dependencies, and runs the test suite:

```bash
# Linux / macOS:
bash setup_and_run.sh

# Windows:
setup_and_run.bat
```

## Manual Installation

### Prerequisites

- Python 3.9 or later
- pip (included with Python)

### Step 1 — Create a virtual environment

```bash
python -m venv .venv

# Activate on Linux / macOS:
source .venv/bin/activate

# Activate on Windows:
.venv\Scripts\activate
```

## Step 2 — Install the package

```bash
# Core install (simulation, analysis, CLI):
pip install .

# With the Streamlit dashboard:
pip install ".[app]"

# Development install (editable + tests):
pip install -e ".[app,dev]"
```

## Step 3 — Verify the installation

```bash
alder-ipm-sim --help
```

Or via the module entry point:

```bash
python -m alder-ipm-sim --help
```

## Step 4 — Run a simulation

```bash
alder-ipm-sim simulate --years 50 --output trajectory.csv
```

## Step 5 — Launch the interactive dashboard

```bash
alder-ipm-sim dashboard
# or equivalently:
streamlit run alder-ipm-sim/app.py
```

## Running tests

```bash
pip install -e ".[dev]"
pytest tests/
```
