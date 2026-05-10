#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== DeepSight: Cleaning build artifacts ==="

cd "$PROJECT_ROOT"

# Python cache
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

# Build artifacts
rm -rf builds/ deployments/

# STM32 build
rm -rf stm32/build/

# Logs
rm -rf logs/

# Virtualenv
if [ -d ".venv" ]; then
    rm -rf .venv
    echo "Removed .venv"
fi

echo "Clean complete."
