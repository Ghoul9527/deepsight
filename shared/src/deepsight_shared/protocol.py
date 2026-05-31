from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from deepsight_shared.constants import NodeId
from deepsight_shared.timestamps import now_ns

PROTOCOL_VERSION = "1.0"


@dataclass
class Message:
    msg_id: str
    timestamp_ns: int
    node_id: str
    type: str
    version: str = PROTOCOL_VERSION
    payload: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({
            "msg_id": self.msg_id,
            "timestamp_ns": self.timestamp_ns,
            "node_id": self.node_id,
            "type": self.type,
            "version": self.version,
            "payload": self.payload,
        })

    def to_bytes(self) -> bytes:
        return (self.to_json() + "\n").encode("utf-8")

    @classmethod
    def from_json(cls, data: str) -> Message:
        raw = json.loads(data)
        return cls(
            msg_id=raw["msg_id"],
            timestamp_ns=raw["timestamp_ns"],
            node_id=raw["node_id"],
            type=raw["type"],
            version=raw.get("version", PROTOCOL_VERSION),
            payload=raw.get("payload", {}),
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> Message:
        return cls.from_json(data.decode("utf-8").strip())


# ---- Message factory helpers ----


def new_message(node_id: str, msg_type: str, payload: dict | None = None) -> Message:
    return Message(
        msg_id=str(uuid.uuid4())[:8],
        timestamp_ns=now_ns(),
        node_id=node_id,
        type=msg_type,
        payload=payload or {},
    )


# ---- Heartbeat ----


def make_heartbeat(node_id: str) -> Message:
    return new_message(node_id, "sys.heartbeat")


# ---- Commands ----


def cmd_servo_set(node_id: str, servo_id: int, angle: float,
                  speed: float = 0.0, seq: int = 0) -> Message:
    return new_message(node_id, "cmd.servo.set", {
        "servo_id": servo_id, "angle": angle, "speed": speed, "seq": seq,
    })


def cmd_winch_set(node_id: str, speed: float, direction: str = "stop") -> Message:
    return new_message(node_id, "cmd.winch.set", {
        "speed": speed, "direction": direction,
    })


def cmd_winch_stop(node_id: str) -> Message:
    return new_message(node_id, "cmd.winch.stop", {})


def cmd_lighting_set(node_id: str, channel: int, brightness: float) -> Message:
    return new_message(node_id, "cmd.lighting.set", {
        "channel": channel, "brightness": brightness,
    })


def cmd_gopro_record(node_id: str, start: bool) -> Message:
    return new_message(node_id, "cmd.gopro.record", {"start": start})


def cmd_gopro_mode(node_id: str, mode: str) -> Message:
    return new_message(node_id, "cmd.gopro.mode", {"mode": mode})


def cmd_gopro_setting(node_id: str, setting: str, value) -> Message:
    return new_message(node_id, "cmd.gopro.setting", {"setting": setting, "value": value})


def cmd_gopro_preset(node_id: str, group: int, preset: int = -1) -> Message:
    return new_message(node_id, "cmd.gopro.preset", {"group": group, "preset": preset})


def cmd_gopro_get_settings(node_id: str) -> Message:
    return new_message(node_id, "cmd.gopro.get_settings", {})


def cmd_gopro_get_presets(node_id: str, group: int = 1000) -> Message:
    """Request preset list for a group. 1000=video, 1001=photo, 1002=timelapse."""
    return new_message(node_id, "cmd.gopro.get_presets", {"group": group})


def cmd_gopro_load_preset(node_id: str, preset_id: int) -> Message:
    """Load a specific preset by its numeric ID."""
    return new_message(node_id, "cmd.gopro.load_preset", {"preset_id": preset_id})


def cmd_gopro_probe(node_id: str, setting: str, probe_option: str) -> Message:
    """Probe available options for a setting without changing the current value.

    Pi sends GET /setting?setting=X&option=PROBE to trigger error-3,
    then restores the original value if the probe option was accepted.
    """
    return new_message(node_id, "cmd.gopro.probe", {
        "setting": setting, "probe_option": probe_option,
    })


def tel_gopro_probe_result(node_id: str, setting: str, current_option: str,
                           available_options: list | None = None,
                           probe_changed: bool = False) -> Message:
    """Result of a context-sensitive setting probe.

    *available_options* is a list of ``{id, name}`` dicts when error-3 fires,
    or None when the probe option itself was valid (probe_changed=True).
    """
    payload = {
        "setting": setting,
        "current_option": current_option,
        "probe_changed": probe_changed,
    }
    if available_options is not None:
        payload["available"] = available_options
    return new_message(node_id, "tel.gopro.probe_result", payload)


# ---- Telemetry ----


def tel_imu(node_id: str, yaw: float, pitch: float, roll: float,
            ax: float = 0.0, ay: float = 0.0, az: float = 0.0) -> Message:
    return new_message(node_id, "tel.imu", {
        "yaw": yaw, "pitch": pitch, "roll": roll,
        "accel_x": ax, "accel_y": ay, "accel_z": az,
    })


def tel_depth(node_id: str, depth_m: float, pressure_mbar: float = 0.0,
              temperature_c: float = 0.0) -> Message:
    return new_message(node_id, "tel.depth", {
        "depth_m": depth_m, "pressure_mbar": pressure_mbar,
        "temperature_c": temperature_c,
    })


def tel_env(node_id: str, temp_c: float, humidity: float, pressure_hpa: float) -> Message:
    return new_message(node_id, "tel.env", {
        "temperature_c": temp_c, "humidity_pct": humidity,
        "pressure_hpa": pressure_hpa,
    })


def tel_leak(node_id: str, channel: int, wet: bool) -> Message:
    return new_message(node_id, "tel.leak", {"channel": channel, "wet": wet})


def tel_winch_state(node_id: str, position_mm: float, speed_mm_s: float,
                    limit_top: bool, limit_bottom: bool, e_stop: bool,
                    current_a: float = 0.0) -> Message:
    return new_message(node_id, "tel.winch_state", {
        "position_mm": position_mm, "speed_mm_s": speed_mm_s,
        "limit_top": limit_top, "limit_bottom": limit_bottom,
        "e_stop_active": e_stop, "motor_current_a": current_a,
    })


def tel_gopro_status(node_id: str, recording: bool, battery_pct: float,
                     storage_gb: float, mode: str = "video") -> Message:
    return new_message(node_id, "tel.gopro_status", {
        "recording": recording, "battery_pct": battery_pct,
        "storage_gb_free": storage_gb, "mode": mode,
    })


def tel_gopro_settings(node_id: str, settings: dict) -> Message:
    return new_message(node_id, "tel.gopro_settings", settings)


def tel_gopro_presets(node_id: str, presets: list[dict],
                      active_preset_id: int = -1, group_id: int = 1000) -> Message:
    """Preset list with current active preset marker."""
    return new_message(node_id, "tel.gopro.presets", {
        "group_id": group_id,
        "active_preset_id": active_preset_id,
        "presets": presets,
    })


def tel_gopro_setting_ack(node_id: str, setting: str, value: str,
                          success: bool, available_options: list | None = None) -> Message:
    payload = {"setting": setting, "value": value, "success": success}
    if available_options is not None:
        payload["available"] = available_options
    return new_message(node_id, "tel.gopro_setting_ack", payload)


def tel_pi_status(node_id: str, cpu_temp: float, cpu_pct: float,
                  mem_pct: float, uptime_s: float) -> Message:
    return new_message(node_id, "tel.pi_status", {
        "cpu_temp_c": cpu_temp, "cpu_pct": cpu_pct,
        "memory_pct": mem_pct, "uptime_s": uptime_s,
    })


def tel_tracking_result(node_id: str, result: dict) -> Message:
    return new_message(node_id, "tel.tracking_result", result)


# ---- System messages ----


def sys_ack(node_id: str, ref_msg_id: str) -> Message:
    return new_message(node_id, "sys.ack", {"ref_msg_id": ref_msg_id})


def sys_error(node_id: str, code: str, detail: str) -> Message:
    return new_message(node_id, "sys.error", {"code": code, "detail": detail})


def sys_safety(node_id: str, state: str) -> Message:
    return new_message(node_id, "sys.safety", {"state": state})


def sys_startup(node_id: str) -> Message:
    return new_message(node_id, "sys.startup", {})


def sys_shutdown(node_id: str) -> Message:
    return new_message(node_id, "sys.shutdown", {})


def sys_ping(node_id: str, seq: int = 0) -> Message:
    """UDP connectivity check."""
    return new_message(node_id, "sys.ping", {"seq": seq})


def sys_pong(node_id: str, seq: int = 0) -> Message:
    return new_message(node_id, "sys.pong", {"seq": seq})


def sys_startup_status(node_id: str, checks: dict) -> Message:
    """Pi startup self-check results. *checks* is a dict of check_name → {ok, detail}."""
    return new_message(node_id, "sys.startup_status", {"checks": checks})


def cmd_startup_check(node_id: str) -> Message:
    """Request Pi to run its startup self-check and report back."""
    return new_message(node_id, "cmd.sys.startup_check", {})


# ---- Protocol validation ----


KNOWN_TYPES = frozenset({
    "cmd.servo.set", "cmd.winch.set", "cmd.winch.stop",
    "cmd.lighting.set", "cmd.gopro.record", "cmd.gopro.mode",
    "cmd.gopro.setting", "cmd.gopro.preset", "cmd.gopro.get_settings",
    "cmd.gopro.get_presets", "cmd.gopro.load_preset", "cmd.gopro.probe",
    "tel.imu", "tel.depth", "tel.pressure", "tel.env", "tel.leak",
    "tel.winch_state", "tel.gopro_status", "tel.gopro_settings",
    "tel.gopro_setting_ack", "tel.gopro.presets", "tel.gopro.probe_result", "tel.pi_status",
    "tel.tracking_result",
    "sys.heartbeat", "sys.ack", "sys.error", "sys.safety",
    "sys.startup", "sys.shutdown", "sys.ping", "sys.pong",
    "sys.startup_status", "cmd.sys.startup_check",
})


def validate_message(msg: Message) -> list[str]:
    errors: list[str] = []
    if not msg.msg_id:
        errors.append("missing msg_id")
    if not msg.timestamp_ns:
        errors.append("missing timestamp_ns")
    if msg.node_id not in {n.value for n in NodeId}:
        errors.append(f"unknown node_id: {msg.node_id}")
    if msg.type not in KNOWN_TYPES:
        errors.append(f"unknown message type: {msg.type}")
    return errors
