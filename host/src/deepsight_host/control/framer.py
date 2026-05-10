"""Framing logic — keeps the tracked target centered in frame.

Pipeline: Detection → Tracking → Kalman → EMA → PID → ServoAngles
"""

from __future__ import annotations

import logging
import time

from deepsight_host.control.pid import PIDController
from deepsight_host.control.servo_mapper import ServoMapper, ServoAngles
from deepsight_host.control.safety import SafetyMonitor
from deepsight_host.tracking.base import TrackingResult
from deepsight_host.tracking.kalman import KalmanPredictor
from deepsight_host.tracking.smoother import EMASmoother

logger = logging.getLogger("host.control.framer")


class Framer:
    def __init__(self, servo_mapper: ServoMapper,
                 pid_pan: PIDController,
                 pid_tilt: PIDController,
                 kalman: KalmanPredictor | None = None,
                 smoother: EMASmoother | None = None,
                 safety: SafetyMonitor | None = None):
        self._mapper = servo_mapper
        self._pid_pan = pid_pan
        self._pid_tilt = pid_tilt
        self._kalman = kalman or KalmanPredictor()
        self._smoother = smoother or EMASmoother(alpha=0.3)
        self._safety = safety or SafetyMonitor()
        self._last_time = time.monotonic()
        self._current_angles = ServoAngles(pan=90.0, tilt=90.0)

    def process(self, tracking: TrackingResult) -> ServoAngles:
        now = time.monotonic()
        dt = now - self._last_time
        self._last_time = now
        if dt <= 0 or dt > 0.5:
            dt = 1.0 / 30.0

        # Step 1: Kalman update or predict
        if tracking.visible and not tracking.lost:
            self._kalman.update((tracking.center_x, tracking.center_y))
            self._safety.report_found()
        else:
            self._kalman.predict()
            self._safety.report_lost(dt)

        # Step 2: EMA smooth the Kalman prediction
        kalman_pos = self._kalman.predicted_position
        smooth_pos = self._smoother.update(kalman_pos)

        # Step 3: Target servo angles from smoothed position
        # Build a synthetic TrackingResult with smoothed center for the mapper
        smoothed_result = TrackingResult(
            bbox=tracking.bbox,
            center_x=smooth_pos[0],
            center_y=smooth_pos[1],
            confidence=tracking.confidence,
            track_id=tracking.track_id,
            visible=tracking.visible,
            lost=tracking.lost,
        )
        target = self._mapper.tracking_to_servo(smoothed_result)

        # Step 4: PID control — approach target smoothly
        pan_error = target.pan - self._current_angles.pan
        tilt_error = target.tilt - self._current_angles.tilt

        pid_pan = self._pid_pan.update(pan_error, dt)
        pid_tilt = self._pid_tilt.update(tilt_error, dt)

        # Step 5: Compute new angles with rate limiting
        max_step = self._mapper.pan_range * 0.15  # max 15% of range per frame
        pan_step = pid_pan * max_step
        tilt_step = pid_tilt * max_step

        pan = self._current_angles.pan + pan_step
        tilt = self._current_angles.tilt + tilt_step

        # Clamp to servo limits
        pan = max(self._mapper.pan_center - self._mapper.pan_range,
                  min(self._mapper.pan_center + self._mapper.pan_range, pan))
        tilt = max(self._mapper.tilt_center - self._mapper.tilt_range,
                   min(self._mapper.tilt_center + self._mapper.tilt_range, tilt))

        # Step 6: Safety check
        safe_override = self._safety.check(
            ServoAngles(pan=pan, tilt=tilt),
            self._current_angles, dt)
        if safe_override is not None:
            self._current_angles = safe_override
        else:
            self._current_angles = ServoAngles(pan=pan, tilt=tilt)

        return self._current_angles

    @property
    def current_angles(self) -> ServoAngles:
        return self._current_angles

    def reset(self):
        self._kalman.reset()
        self._smoother.reset()
        self._pid_pan.reset()
        self._pid_tilt.reset()
        self._safety.reset()
        self._current_angles = ServoAngles(pan=90.0, tilt=90.0)
