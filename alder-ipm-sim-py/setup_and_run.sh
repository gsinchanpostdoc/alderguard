#!/usr/bin/env bash
# setup_and_run.sh — One-command setup for alder-ipm-sim-py on Linux / macOS
# Usage:  bash setup_and_run.sh

set -euo pipefail

VENV_DIR=".venv"

echo "=== AlderIPM-Sim Python — Setup & Run ==="
echo ""

# 1. Create virtual environment
if [ -d "$VENV_DIR" ]; then
    echo "[skip] Virtual environment already exists at $VENV_DIR"
else
    echo "[1/4] Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# 2. Activate
echo "[2/4] Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# 3. Install package with dev dependencies
echo "[3/4] Installing alder-ipm-sim with dev dependencies..."
pip install --upgrade pip -q
pip install -e ".[app,dev]" -q

# 4. Run tests
echo "[4/4] Running test suite..."
echo ""
pytest tests/ -v
echo ""

echo "============================================"
echo "  Setup complete — all tests passed!"
echo "============================================"
echo ""
echo "Next steps:"
echo "  source $VENV_DIR/bin/activate"
echo "  alder-ipm-sim --help              # CLI overview"
echo "  alder-ipm-sim simulate --years 50 # run a simulation"
echo "  alder-ipm-sim dashboard           # launch Streamlit app"
echo "  pytest tests/ -v               # re-run tests"
echo ""
