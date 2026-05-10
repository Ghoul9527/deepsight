# Communication Protocol

## Message Catalog

### Commands (Host → downstream)

| Type | Direction | Payload |
|------|-----------|---------|
| `cmd.servo.set` | Host→Pi→Pico | `{servo_id, angle, speed?}` |
| `cmd.winch.set` | Host→Pi→STM32 | `{speed, direction}` |
| `cmd.winch.stop` | Host→Pi→STM32 | `{}` |
| `cmd.lighting.set` | Host→Pi→Pico | `{channel, brightness}` |
| `cmd.gopro.record` | Host→Pi | `{start: bool}` |
| `cmd.gopro.mode` | Host→Pi | `{mode: string}` |

### Telemetry (upstream → Host)

| Type | Direction | Payload |
|------|-----------|---------|
| `tel.imu` | Pico→Pi→Host | `{yaw, pitch, roll, accel_*}` |
| `tel.depth` | Pico→Pi→Host | `{depth_m, pressure_mbar, temperature_c}` |
| `tel.env` | Pico→Pi→Host | `{temperature_c, humidity_pct, pressure_hpa}` |
| `tel.leak` | Pico→Pi→Host | `{channel, wet}` |
| `tel.winch_state` | STM32→Pi→Host | `{position_mm, speed_mm_s, limit_*, e_stop_active}` |
| `tel.gopro_status` | Pi→Host | `{recording, battery_pct, storage_gb_free, mode}` |
| `tel.pi_status` | Pi→Host | `{cpu_temp_c, cpu_pct, memory_pct, uptime_s}` |
| `tel.tracking_result` | Host (internal) | `{x, y, w, h, confidence, track_id, visible}` |

### System Messages (bidirectional)

| Type | Purpose | Payload |
|------|---------|---------|
| `sys.heartbeat` | Liveness (500ms) | `{}` |
| `sys.ack` | Command acknowledgment | `{ref_msg_id}` |
| `sys.error` | Error reporting | `{code, detail}` |
| `sys.safety` | Safety state change | `{state}` |
| `sys.startup` | Node startup | `{}` |
| `sys.shutdown` | Graceful shutdown | `{}` |

## Heartbeat Protocol

- Interval: 500ms per node
- Host tracks last heartbeat timestamp per node
- 2s no heartbeat → node DEGRADED (continue with caution)
- 5s no heartbeat → node LOST (servos to safe position)
