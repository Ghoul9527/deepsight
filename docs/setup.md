# Development Setup

## Requirements

- Python 3.11+
- macOS (primary dev) or Linux/Windows
- No hardware required for mock mode

## Quick Start

```bash
cd deepsight

# Install system deps (macOS)
brew install python@3.11

# Set up Python environment
./scripts/setup_venv.sh

# Activate
source .venv/bin/activate

# Start all nodes in mock mode
deepsight-cli start --mock
```

## Running Individual Nodes

```bash
# Host GUI (with video preview and tracking)
python -m deepsight_host.main

# Pi node (API + bridge)
python -m deepsight_pi.main

# Pico firmware (mock mode)
python pico/main.py

# STM32 firmware (mock mode, requires build first)
cd stm32 && make MOCK_MODE=1 && ./build/stm32_winch.elf
```

## Running Tests

```bash
deepsight-cli test
# or: python -m pytest tests/ -v
```
