#!/bin/bash
set -euo pipefail

echo "=== DeepSight: Installing system dependencies ==="

# macOS
if [[ "$(uname)" == "Darwin" ]]; then
    echo "Detected macOS"
    echo "Install with: brew install python@3.11 cmake pkg-config"

# Linux (Raspberry Pi)
elif [[ "$(uname)" == "Linux" ]]; then
    echo "Detected Linux"
    sudo apt-get update
    sudo apt-get install -y \
        python3.11 python3.11-venv python3.11-dev \
        libopencv-dev cmake pkg-config \
        libxcb-cursor0 libxcb-util1 \
        ffmpeg gstreamer1.0-tools \
        git curl
fi

echo "Dependencies installed. Run ./scripts/setup_venv.sh next."
