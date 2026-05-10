from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class TrackingResult:
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2 (normalized 0-1)
    center_x: float
    center_y: float
    confidence: float
    track_id: int
    visible: bool
    lost: bool
    mask: Any | None = None
    pose_landmarks: list | None = None


@dataclass
class ServoCommand:
    servo_id: int
    angle: float  # degrees
    speed: float = 0.0  # deg/s, 0 = max


@dataclass
class WinchCommand:
    speed: float  # -1.0 to 1.0
    direction: str = "stop"  # "up" | "down" | "stop"


@dataclass
class IMUData:
    yaw: float
    pitch: float
    roll: float
    accel_x: float = 0.0
    accel_y: float = 0.0
    accel_z: float = 0.0


@dataclass
class DepthData:
    depth_m: float
    pressure_mbar: float = 0.0
    temperature_c: float = 0.0


@dataclass
class EnvData:
    temperature_c: float
    humidity_pct: float
    pressure_hpa: float


@dataclass
class LeakData:
    channel: int
    wet: bool


@dataclass
class WinchState:
    position_mm: float
    speed_mm_s: float
    limit_top: bool
    limit_bottom: bool
    e_stop_active: bool
    motor_current_a: float = 0.0


@dataclass
class GoProStatus:
    recording: bool
    battery_pct: float
    storage_gb_free: float
    mode: str = "video"


@dataclass
class PiStatus:
    cpu_temp_c: float
    cpu_pct: float
    memory_pct: float
    uptime_s: float
