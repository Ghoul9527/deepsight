# DeepSight — Distributed Underwater ROV Filming System

Freediving ROV filming and tracking platform. Multi-node distributed system: Surface Host Computer, Raspberry Pi 5, Raspberry Pi Pico, and STM32 Winch Controller.

## Quickstart (No Hardware Required)

```bash
./scripts/setup_venv.sh
deepsight-cli start --mock
```

## Architecture

```
Host (Mac/Windows)  <--UDP/WS-->  Pi 5  <--UART-->  Pico
                                              <--UART-->  STM32
```

## Nodes

| Node | Role | Language |
|------|------|----------|
| `host/` | Operator GUI, AI tracking, orchestration | Python |
| `pi/` | Video bridge, GoPro control, comms relay | Python |
| `pico/` | Servo/sensor control, deterministic loop | MicroPython |
| `stm32/` | Winch control, hardware safety | C |

## Development Phases

- **Phase 1** (current): Skeleton, mock hardware, communication
- **Phase 2**: Tracking/AI pipeline
- **Phase 3**: Real hardware integration
- **Phase 4**: Production hardening

## License

Proprietary — all rights reserved.
