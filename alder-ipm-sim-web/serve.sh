#!/usr/bin/env bash
# serve.sh — Start a local server for alder-ipm-sim-web (Linux / macOS)
# Usage:  bash serve.sh [port]

set -euo pipefail
cd "$(dirname "$0")"
PORT="${1:-8080}"
echo "Starting alder-ipm-sim-web on http://localhost:$PORT"
python3 serve.py "$PORT"
