"""Roll auto-stabilizer — P controller that keeps camera platform horizontal."""

import logging
import time

logger = logging.getLogger("pi.stabilizer")


class RollStabilizer:
    def __init__(self, servo_controller, config: dict):
        self._servo = servo_controller
        self._kp = config.get("kp", 0.5)
        self._max_correction = config.get("max_correction", 45.0)
        self._manual_timeout = config.get("manual_timeout_s", 2.0)
        self._deadband = config.get("deadband_deg", 1.5)
        self._ema_alpha = config.get("ema_alpha", 0.15)
        self._enabled = config.get("enabled", True)
        self._last_manual = 0.0
        self._current_roll = 0.0
        self._smoothed = 0.0
        self._servo_id = 2

        logger.info("RollStabilizer: kp=%.2f max=%.1f deadband=%.1f ema=%.2f",
                     self._kp, self._max_correction, self._deadband, self._ema_alpha)

    def update_imu(self, roll_deg: float):
        self._current_roll = roll_deg

    def notify_manual(self):
        self._enabled = False
        self._last_manual = time.time()
        logger.debug("Manual override: stabilizer paused")

    def is_active(self) -> bool:
        return self._enabled

    def step(self):
        if not self._enabled and time.time() - self._last_manual > self._manual_timeout:
            self._enabled = True
            logger.debug("Manual timeout expired: stabilizer resumed")
        if not self._enabled:
            return

        error = self._current_roll
        if abs(error) < self._deadband:
            error = 0.0

        correction = max(-self._max_correction, min(self._max_correction, self._kp * error))
        self._smoothed = self._ema_alpha * correction + (1 - self._ema_alpha) * self._smoothed
        self._servo.set_angle(self._servo_id, 90.0 + self._smoothed)
