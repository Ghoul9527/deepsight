# DeepSight Project Overview

Distributed underwater ROV filming/tracking system for freediving. 4-node architecture:

| Node | HW | Language | Purpose |
|------|----|---------|---------|
| Host | Laptop (macOS/Windows) | Python 3.11+ | GUI (PySide6), YOLO tracking, control |
| Pi 5 | Raspberry Pi 5 | Python 3.11+ | GoPro control, HDMI capture, bridge routing |
| Pico | RP2040 | MicroPython | Sensors (IMU, depth, env), servos, lights |
| STM32 | STM32F4 | C (HAL) | Winch motor control, emergency stop |

## Topology (wired only)

```
GoPro USB-C ──▶ Pi USB 3.0 (control)
GoPro MicroHDMI ──▶ Capture Dongle ──▶ Pi USB 3.0 (video)
Pi ──▶ RJ45 ──▶ Host (Ethernet)
Pi ──▶ UART0 ──▶ Pico
Pi ──▶ UART1 ──▶ STM32
```

No BLE, no WiFi, no GoPro wireless preview. Video comes from HDMI capture card, not GoPro SDK.

## Communication

- Host ↔ Pi: UDP (commands) + WebSocket (telemetry) over Ethernet
- Pi ↔ Pico: UART serial with JSONL framing
- Pi ↔ STM32: UART serial with JSONL framing
- All messages: versioned JSON envelope

## Quickstart

```bash
# Install all dependencies
./scripts/install_deps.sh
./scripts/setup_venv.sh

# Start entire mock system
./scripts/run_all_mock.sh

# Or via CLI
python -m deepsight_tools.cli start --mock

# Run tests
python -m pytest tests/
```

## Key Conventions

- Every hardware interface behind an ABC with mock + real implementations
- Mock is the default; config selects mock vs real per device
- `configs/` directory holds YAML configs per node
- Shared types in `shared/`, installed as editable package
- Async where possible (asyncio on host + pi, async GPIO mock on pico)
- All methods return bool for success/failure
- Loggers use `"node.component"` naming: `"host.tracking.fast"`, `"pi.gopro.real"`

## Build/Test Commands

```bash
# Host + Pi tests
python3 -m pytest host/tests/ pi/tests/ tests/ -v

# STM32 (mock mode, builds on macOS)
cd stm32 && make MOCK=1 && ./build/stm32_winch.elf

# Lint
python3 -m ruff check .
python3 -m mypy host/src pi/src shared/src
```
