#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== DeepSight: Starting all nodes (mock mode) ==="

cd "$PROJECT_ROOT"

# Activate venv
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "Error: .venv not found. Run ./scripts/setup_venv.sh first"
    exit 1
fi

# Start using the CLI orchestrator
deepsight-cli start --mock
