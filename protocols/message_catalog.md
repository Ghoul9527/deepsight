# DeepSight Message Catalog

Complete reference for all inter-node communication messages. Version 1.0.

## Envelope

Every message wraps in a common JSON envelope:

```json
{
  "msg_id": "string — unique message identifier (UUID short)",
  "timestamp_ns": "int — nanosecond monotonic timestamp",
  "node_id": "host | pi | pico | stm32",
  "type": "string — message type (see below)",
  "version": "1.0",
  "payload": "{ ... }"
}
```

---

## Commands (Host → downstream)

### `cmd.servo.set`
| Field | Direction | Purpose |
|-------|-----------|---------|
| `servo_id` | Host→Pi→Pico | Servo channel 0-15 |
| `angle` | Host→Pi→Pico | Target angle degrees 0-180 |
| `speed` | Host→Pi→Pico | Optional speed (0 = max) |

### `cmd.winch.set`
| Field | Direction | Purpose |
|-------|-----------|---------|
| `speed` | Host→Pi→STM32 | Speed mm/s (positive = down, negative = up) |
| `direction` | Host→Pi→STM32 | "up" / "down" / "stop" |

### `cmd.winch.stop`
| Field | Direction | Purpose |
|-------|-----------|---------|
| (none) | Host→Pi→STM32 | Emergency stop winch motor |

### `cmd.lighting.set`
| Field | Direction | Purpose |
|-------|-----------|---------|
| `channel` | Host→Pi→Pico | Lighting channel 0-N |
| `brightness` | Host→Pi→Pico | 0.0 (off) to 1.0 (full) |

### `cmd.gopro.record`
| Field | Direction | Purpose |
|-------|-----------|---------|
| `start` | Host→Pi | true = start, false = stop |

### `cmd.gopro.mode`
| Field | Direction | Purpose |
|-------|-----------|---------|
| `mode` | Host→Pi | "video" / "photo" / "timelapse" |

---

## Telemetry (upstream → Host)

### `tel.imu`
| Field | Direction | Purpose |
|-------|-----------|---------|
| `yaw` | Pico→Pi→Host | Heading degrees |
| `pitch` | Pico→Pi→Host | Pitch degrees |
| `roll` | Pico→Pi→Host | Roll degrees |
| `accel_x` | Pico→Pi→Host | Acceleration g-force X |
| `accel_y` | Pico→Pi→Host | Acceleration g-force Y |
| `accel_z` | Pico→Pi→Host | Acceleration g-force Z |

### `tel.depth`
| Field | Direction | Purpose |
|-------|-----------|---------|
| `depth_m` | Pico→Pi→Host | Depth in meters |
| `pressure_mbar` | Pico→Pi→Host | Raw pressure millibar |
| `temperature_c` | Pico→Pi→Host | Water temperature Celsius |

### `tel.env`
| Field | Direction | Purpose |
|-------|-----------|---------|
| `temperature_c` | Pico→Pi→Host | Air temperature inside housing |
| `humidity_pct` | Pico→Pi→Host | Relative humidity percentage |
| `pressure_hpa` | Pico→Pi→Host | Atmospheric pressure hPa |

### `tel.leak`
| Field | Direction | Purpose |
|-------|-----------|---------|
| `channel` | Pico→Pi→Host | Leak sensor channel number |
| `wet` | Pico→Pi→Host | true = water detected |

### `tel.winch_state`
| Field | Direction | Purpose |
|-------|-----------|---------|
| `position_mm` | STM32→Pi→Host | Current winch position mm |
| `speed_mm_s` | STM32→Pi→Host | Current speed mm/s |
| `limit_top` | STM32→Pi→Host | Top limit switch triggered |
| `limit_bottom` | STM32→Pi→Host | Bottom limit switch triggered |
| `e_stop_active` | STM32→Pi→Host | Emergency stop engaged |
| `motor_current_a` | STM32→Pi→Host | Motor current amps |

### `tel.gopro_status`
| Field | Direction | Purpose |
|-------|-----------|---------|
| `recording` | Pi→Host | Currently recording |
| `battery_pct` | Pi→Host | Battery percentage 0-100 |
| `storage_gb_free` | Pi→Host | Free storage in GB |
| `mode` | Pi→Host | Current mode string |

### `tel.pi_status`
| Field | Direction | Purpose |
|-------|-----------|---------|
| `cpu_temp_c` | Pi→Host | CPU temperature Celsius |
| `cpu_pct` | Pi→Host | CPU usage percentage |
| `memory_pct` | Pi→Host | RAM usage percentage |
| `uptime_s` | Pi→Host | Node uptime seconds |

### `tel.tracking_result`
| Field | Direction | Purpose |
|-------|-----------|---------|
| `x` | Host(internal) | Target center X (normalized 0-1) |
| `y` | Host(internal) | Target center Y (normalized 0-1) |
| `confidence` | Host(internal) | Detection confidence 0-1 |
| `track_id` | Host(internal) | ByteTrack ID |
| `visible` | Host(internal) | Target currently visible |

---

## System Messages (bidirectional)

### `sys.heartbeat`
| Field | Direction | Purpose |
|-------|-----------|---------|
| (none) | All→Host | Node liveness (every 500ms) |

### `sys.ack`
| Field | Direction | Purpose |
|-------|-----------|---------|
| `ref_msg_id` | Any→Any | Message being acknowledged |

### `sys.error`
| Field | Direction | Purpose |
|-------|-----------|---------|
| `code` | Any→Any | Error code string |
| `detail` | Any→Any | Human-readable error description |

### `sys.safety`
| Field | Direction | Purpose |
|-------|-----------|---------|
| `state` | Any→Any | Safety state: "NOMINAL" / "DEGRADED" / "CAUTION" / "SAFE" / "EMERGENCY" |

### `sys.startup`
| Field | Direction | Purpose |
|-------|-----------|---------|
| (none) | Any→Host | Node has started and is ready |

### `sys.shutdown`
| Field | Direction | Purpose |
|-------|-----------|---------|
| (none) | Any→Host | Node is shutting down gracefully |

---

## Safety Protocol

| Timeout | Action |
|---------|--------|
| Heartbeat every 500ms | Normal operation |
| No heartbeat for 2s | Node marked DEGRADED |
| No heartbeat for 5s | Node marked LOST, servos → safe position |
| Command timeout (Pico) | Servos return to neutral |
| Hardware E-Stop (STM32) | Independent of communication, immediate motor stop |
