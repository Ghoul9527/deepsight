# DeepSight Architecture

## Overview

Distributed freediving ROV filming system with 4 nodes:

```
Host (macOS/Windows) ──UDP──┐
                             ├── Pi 5 ──UART── Pico (servos/sensors)
                             └── Pi 5 ──UART── STM32 (winch)
```

## Nodes

### Surface Host Computer
- PySide6 GUI: operator dashboard, video preview, manual controls
- AI Tracking: YOLO detection, ByteTrack, Kalman prediction, EMA smoothing
- Control: PID-based servo positioning, framing logic
- Orchestration: node registry, heartbeat monitoring, safety state machine

### Raspberry Pi 5
- Communication bridge: Host ↔ MCUs
- GoPro controller (USB)
- HDMI capture / video encoding
- Watchdog / auto-reconnect

### Raspberry Pi Pico
- Servo control (PCA9685 PWM)
- Sensor polling (IMU, depth, environment, leak)
- Deterministic 50 Hz control loop
- Local safety fallback

### STM32 Winch Controller
- Winch state machine (IDLE, MOVING_UP, MOVING_DOWN, ESTOP)
- Motor control with current monitoring
- Limit switch handling
- Independent hardware emergency stop

## Communication Layers

| Layer | Transport | Direction | Purpose |
|-------|-----------|-----------|---------|
| Host ↔ Pi | UDP | Bidirectional | Realtime commands, telemetry, heartbeats |
| Host → Pi | WebSocket | Bidirectional | Future: streaming, API queries |
| Pi ↔ Pico | UART (115200) | Bidirectional | Servo commands, sensor telemetry |
| Pi ↔ STM32 | UART (115200) | Bidirectional | Winch commands, state telemetry |

## Protocol

All messages are versioned JSON with a common envelope:

```json
{
  "msg_id": "uuid",
  "timestamp_ns": 1715299200000000000,
  "node_id": "host|pi|pico|stm32",
  "type": "category.message",
  "version": "1.0",
  "payload": {}
}
```

## Safety Layers

1. **Application (Host)**: Tracking loss → smooth servo return to neutral
2. **Bridge (Pi)**: Watchdog heartbeat monitoring, reconnect logic
3. **Local (Pico)**: No-command timeout → safe servo position
4. **Hardware (STM32)**: Independent emergency stop, limit switch override

## Tracking Pipeline

```
Frame → Detection (YOLO) → Tracking (ByteTrack) → Kalman Predict
     → EMA Smooth → PID Control → Servo Mapper → Servo Command
```
