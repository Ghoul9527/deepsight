#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== DeepSight: Setting up development environment ==="

cd "$PROJECT_ROOT"

# Create virtualenv
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "Created .venv"
fi

source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install shared library (editable)
pip install -e shared/

# Install tools (editable, includes CLI)
pip install -e tools/

# Install host (editable, with tracking deps)
pip install -e "host/[dev,tracking]"

# Install pi (editable, with dev deps)
pip install -e "pi/[dev]"

echo ""
echo "=== Setup complete ==="
echo "Activate: source .venv/bin/activate"
echo "Run: deepsight-cli start --mock"
