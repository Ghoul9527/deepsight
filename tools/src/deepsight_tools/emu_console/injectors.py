"""Fake telemetry injectors — generate Message objects matching real Pi signals.

Each injector class exposes set_*() methods for UI control and a generate()
method called periodically to produce telemetry messages.
"""

from __future__ import annotations

import math

from deepsight_shared.protocol import (
    Message, new_message,
    tel_imu, tel_depth, tel_env, tel_leak,
    tel_winch_state, tel_gopro_status, tel_pi_status,
)


# ── IMU injector ──────────────────────────────────────

class IMUInjector:
    def __init__(self):
        self.yaw = 0.0
        self.pitch = 0.0
        self.roll = 0.0
        self.accel_x = 0.0
        self.accel_y = 0.0
        self.accel_z = 1.0
        self._wave = True
        self._t = 0.0
        self._amp_yaw = 5.0
        self._amp_pitch = 3.0
        self._amp_roll = 2.0
        self._period = 4.0

    def set_wave(self, enabled: bool):
        self._wave = enabled

    def set_yaw(self, v: float): self.yaw = v
    def set_pitch(self, v: float): self.pitch = v
    def set_roll(self, v: float): self.roll = v

    def step(self, dt: float):
        if self._wave:
            self._t += dt
            self.yaw = self._amp_yaw * math.sin(2 * math.pi * self._t / self._period)
            self.pitch = self._amp_pitch * math.sin(2 * math.pi * self._t / (self._period * 1.3))
            self.roll = self._amp_roll * math.sin(2 * math.pi * self._t / (self._period * 1.7))
            self.accel_x = 0.1 * math.sin(2 * math.pi * self._t / self._period)
            self.accel_y = 0.1 * math.cos(2 * math.pi * self._t / self._period)
            self.accel_z = 1.0 + 0.05 * math.sin(2 * math.pi * self._t / 3.0)

    def generate(self) -> Message:
        return tel_imu("pico", self.yaw, self.pitch, self.roll,
                       self.accel_x, self.accel_y, self.accel_z)


# ── Depth injector ────────────────────────────────────

class DepthInjector:
    def __init__(self):
        self.depth_m = 5.0
        self.temp_c = 22.0

    def set_depth(self, v: float):
        self.depth_m = v

    def set_temp(self, v: float):
        self.temp_c = v

    def generate(self) -> Message:
        pressure_mbar = 1013.0 + self.depth_m * 100.0
        return tel_depth("pico", self.depth_m, pressure_mbar, self.temp_c)


# ── Environment injector ──────────────────────────────

class EnvInjector:
    def __init__(self):
        self.temp_c = 22.0
        self.humidity_pct = 65.0
        self.pressure_hpa = 1013.0

    def set_temp(self, v: float): self.temp_c = v
    def set_humidity(self, v: float): self.humidity_pct = v
    def set_pressure(self, v: float): self.pressure_hpa = v

    def generate(self) -> Message:
        return tel_env("pico", self.temp_c, self.humidity_pct, self.pressure_hpa)


# ── Leak sensor injector ──────────────────────────────

class LeakInjector:
    CHANNELS = {0: "Port", 1: "Starboard", 2: "Bottom", 3: "Dome"}

    def __init__(self):
        self.channels: dict[int, bool] = {c: False for c in self.CHANNELS}

    def set_channel(self, channel: int, wet: bool):
        self.channels[channel] = wet

    def generate(self) -> list[Message]:
        return [tel_leak("pico", ch, wet) for ch, wet in self.channels.items()]


# ── Winch state injector ──────────────────────────────

class WinchInjector:
    def __init__(self):
        self.position_mm = 2500.0
        self.speed_mm_s = 0.0
        self.limit_top = False
        self.limit_bottom = False
        self.e_stop = False
        self.current_a = 0.0
        self._max_pos = 5000.0

    def set_position(self, v: float): self.position_mm = v
    def set_speed(self, v: float): self.speed_mm_s = v

    def step(self, dt: float):
        if self.e_stop or self.speed_mm_s == 0:
            return
        self.position_mm += self.speed_mm_s * dt
        self.limit_bottom = False
        self.limit_top = False
        if self.position_mm <= 0:
            self.position_mm = 0
            self.limit_bottom = True
            self.speed_mm_s = 0
        elif self.position_mm >= self._max_pos:
            self.position_mm = self._max_pos
            self.limit_top = True
            self.speed_mm_s = 0
        self.current_a = 0.5 + abs(self.speed_mm_s) * 0.02

    def generate(self) -> Message:
        return tel_winch_state("stm32", self.position_mm, self.speed_mm_s,
                               self.limit_top, self.limit_bottom,
                               self.e_stop, self.current_a)


# ── GoPro status injector ─────────────────────────────

class GoProInjector:
    MODES = ["video", "photo", "timelapse"]

    def __init__(self):
        self.recording = False
        self.battery_pct = 85.0
        self.storage_gb = 120.0
        self.mode = "video"

    def set_recording(self, v: bool): self.recording = v
    def set_battery(self, v: float): self.battery_pct = v
    def set_storage(self, v: float): self.storage_gb = v
    def set_mode(self, v: str):
        if v in self.MODES:
            self.mode = v

    def generate(self) -> Message:
        return tel_gopro_status("pi", self.recording, self.battery_pct,
                                self.storage_gb, self.mode)


# ── Pi status injector ────────────────────────────────

class PiStatusInjector:
    def __init__(self):
        self.cpu_temp_c = 45.0
        self.cpu_pct = 15.0
        self.mem_pct = 30.0
        self._start_time = __import__('time').monotonic()

    def set_cpu_temp(self, v: float): self.cpu_temp_c = v
    def set_cpu(self, v: float): self.cpu_pct = v
    def set_mem(self, v: float): self.mem_pct = v

    def generate(self) -> Message:
        import time
        uptime = time.monotonic() - self._start_time
        return tel_pi_status("pi", self.cpu_temp_c, self.cpu_pct,
                            self.mem_pct, uptime)


# ── Servo position injector (fake feedback) ───────────

class ServoPositionInjector:
    def __init__(self):
        self.positions: dict[int, float] = {0: 90.0, 1: 90.0}

    def set_angle(self, servo_id: int, angle: float):
        self.positions[servo_id] = angle

    def generate(self, servo_id: int) -> Message:
        angle = self.positions.get(servo_id, 90.0)
        return new_message("pico", "tel.servo_position", {
            "servo_id": servo_id, "angle": angle,
        })


# ── Lighting state injector (fake feedback) ───────────

class LightingInjector:
    def __init__(self):
        self.brightness = 0.0

    def set_brightness(self, v: float):
        self.brightness = max(0.0, min(1.0, v))

    def generate(self) -> Message:
        return new_message("pico", "tel.lighting_state", {
            "brightness": self.brightness,
        })
