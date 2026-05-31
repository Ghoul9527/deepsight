"""Safety monitor — tracking loss handling and graceful servo fallback."""

from __future__ import annotations

import logging

from deepsight_host.control.servo_mapper import ServoAngles
from deepsight_shared.constants import SafetyState

logger = logging.getLogger("host.control.safety")


class SafetyMonitor:
    def __init__(self,
                 lost_hold_time: float = 3.0,
                 lost_neutral_time: float = 8.0,
                 neutral_pan: float = 90.0,
                 neutral_tilt: float = 90.0,
                 max_angle_step: float = 10.0):
        self.lost_hold_time = lost_hold_time
        self.lost_neutral_time = lost_neutral_time
        self.neutral_pan = neutral_pan
        self.neutral_tilt = neutral_tilt
        self.max_angle_step = max_angle_step
        self._lost_duration = 0.0
        self._state = SafetyState.NOMINAL
        self._last_angles = ServoAngles(pan=neutral_pan, tilt=neutral_tilt)

    def report_lost(self, dt: float):
        self._lost_duration += dt

    def report_found(self):
        self._lost_duration = 0.0
        self._state = SafetyState.NOMINAL

    def check(self, target: ServoAngles, current: ServoAngles,
              dt: float) -> ServoAngles | None:
        """Returns override angles if safety engaged, None if target is safe."""

        # Clamp sudden jumps
        pan_step = abs(target.pan - current.pan)
        tilt_step = abs(target.tilt - current.tilt)

        if pan_step > self.max_angle_step or tilt_step > self.max_angle_step:
            logger.warning("Safety: clamped sudden angle jump (pan:%.1f, tilt:%.1f)",
                           pan_step, tilt_step)
            pan = current.pan + (self.max_angle_step if target.pan > current.pan
                                 else -self.max_angle_step)
            tilt = current.tilt + (self.max_angle_step if target.tilt > current.tilt
                                   else -self.max_angle_step)
            return ServoAngles(pan=pan, tilt=tilt)

        # Tracking loss handling
        if self._lost_duration > self.lost_neutral_time:
            # Smoothly move to neutral
            self._state = SafetyState.CAUTION
            alpha = 0.1
            pan = current.pan * (1 - alpha) + self.neutral_pan * alpha
            tilt = current.tilt * (1 - alpha) + self.neutral_tilt * alpha
            return ServoAngles(pan=pan, tilt=tilt)

        if self._lost_duration > self.lost_hold_time:
            # Hold position
            self._state = SafetyState.DEGRADED
            return current

        return None  # No safety override

    def reset(self):
        self._lost_duration = 0.0
        self._state = SafetyState.NOMINAL

    @property
    def state(self) -> SafetyState:
        return self._state
