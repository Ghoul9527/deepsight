"""Format and output telemetry data."""

import json
import time


def make_telemetry(msg_type: str, payload: dict) -> str:
    msg = {
        "msg_id": "",
        "timestamp_ns": int(time.time() * 1e9),
        "node_id": "pico",
        "type": msg_type,
        "version": "1.0",
        "payload": payload,
    }
    return json.dumps(msg)


def tel_imu(yaw: float, pitch: float, roll: float,
            ax: float = 0.0, ay: float = 0.0, az: float = 0.0) -> str:
    return make_telemetry("tel.imu", {
        "yaw": yaw, "pitch": pitch, "roll": roll,
        "accel_x": ax, "accel_y": ay, "accel_z": az,
    })


def tel_depth(depth_m: float, pressure_mbar: float = 0.0,
              temp_c: float = 0.0) -> str:
    return make_telemetry("tel.depth", {
        "depth_m": depth_m, "pressure_mbar": pressure_mbar,
        "temperature_c": temp_c,
    })


def tel_env(temp_c: float, humidity: float, pressure_hpa: float) -> str:
    return make_telemetry("tel.env", {
        "temperature_c": temp_c, "humidity_pct": humidity,
        "pressure_hpa": pressure_hpa,
    })


def tel_leak(channel: int, wet: bool) -> str:
    return make_telemetry("tel.leak", {"channel": channel, "wet": wet})


def tel_heartbeat() -> str:
    return make_telemetry("sys.heartbeat", {})
