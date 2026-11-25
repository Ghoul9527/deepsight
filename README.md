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

## Camera target

The active camera integration targets the fixed-lens **GoPro MISSION 1 PRO**
with GoPro Labs firmware `v2.02.70`. Setup, firmware and API compatibility
details are in [docs/gopro_mission1_pro.md](docs/gopro_mission1_pro.md).

## Development Phases

- **Phase 1** (current): Skeleton, mock hardware, communication
- **Phase 2**: Tracking/AI pipeline
- **Phase 3**: Real hardware integration
- **Phase 4**: Production hardening

## License

Proprietary — all rights reserved.
## Windows HUD export

Install Pillow in the Host Python environment and make FFmpeg available on
`PATH` or pass its executable with `--ffmpeg`. The input MP4 and depth JSONL
are read without changes. The exporter looks for a same-name JSONL unless
`--data` is specified.

```powershell
.\scripts\Burn-HUD.cmd "D:\Media\GX010011.MP4" --lang zh --name "陈林" --discipline FIM --target-depth 45
```

Use `--lang en` for English. `--offset 1.25` puts JSONL time zero at video
time 1.25 seconds. The default output is `GX010011_HUD_zh.mp4` for Chinese
and `GX010011_HUD_en.mp4` for English.
